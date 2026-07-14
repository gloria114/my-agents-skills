#!/usr/bin/env python3
"""Fail-closed validation, sealing, and live verification for WH6 features.

Validation writes only below an already-created external run root.  It never
modifies qdh or ClickHouse.  ``finalize`` is the sole operation that can create
``control/READY`` and does so only after a full-scope, full recomputation PASS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

import wh6_common as common
from wh6_candidate import PurePythonWH6Engine
from wh6_formulas_v2 import COLUMN_ORDER


SCHEMA_VERSION = 1
FEATURE_COLUMNS = tuple(COLUMN_ORDER)
OUTPUT_COLUMNS = ("trade_time",) + FEATURE_COLUMNS
SHA256_RE = re.compile(r"[0-9a-f]{64}")
CONTROL_HASH_FILES = (
    "run_manifest.json",
    "files.jsonl",
    "build_summary.json",
    "market_after.json",
    "warmup_after.json",
)


class ValidationFailure(RuntimeError):
    """A validation gate failed closed."""


def _validation_tool_hashes() -> dict[str, str]:
    root = Path(__file__).resolve().parent
    names = ("wh6_validate.py", "wh6_publish.py")
    return {name: common.sha256_file(root / name) for name in names}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationFailure(message)


def _strict_json(path: Path) -> Any:
    def reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValidationFailure(f"duplicate JSON key {key!r}: {path}")
            result[key] = value
        return result

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=reject_pairs)


def _manifest_sequences(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    selected_scope = manifest.get("selected_scope")
    _require(isinstance(selected_scope, dict), "run manifest selected_scope is missing")
    value = selected_scope.get("sequences")
    _require(isinstance(value, list) and value, "run manifest has no selected sequences")
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in value:
        _require(isinstance(row, dict), "run manifest sequence must be an object")
        symbol = row.get("symbol")
        timeframe = row.get("timeframe")
        contract_code = row.get("contract_code")
        _require(isinstance(symbol, str) and symbol, "invalid sequence symbol")
        _require(timeframe in common.TIMEFRAMES, f"invalid sequence timeframe: {timeframe}")
        _require(contract_code == symbol + "JQ", f"invalid contract mapping: {symbol}")
        key = (symbol, timeframe)
        _require(key not in seen, f"duplicate selected sequence: {symbol}/{timeframe}")
        seen.add(key)
        result.append(row)
    result.sort(key=lambda row: (row["symbol"], common.TIMEFRAMES.index(row["timeframe"])))
    return result


def _validate_run_identity(
    qdh_root: Path | str, run_root: Path | str
) -> tuple[Path, Path, Path, dict[str, Any]]:
    qdh, run = common.ensure_qdh_run_roots(qdh_root, run_root, require_run=True)
    control = run / "control"
    manifest_path = control / "run_manifest.json"
    _require(control.is_dir(), f"control directory missing: {control}")
    _require(manifest_path.is_file(), f"run manifest missing: {manifest_path}")
    manifest = _strict_json(manifest_path)
    _require(isinstance(manifest, dict), "run manifest must be an object")
    _require(
        set(manifest)
        == {
            "schema_version",
            "run_id",
            "created_at",
            "qdh_root",
            "run_root",
            "stage_features",
            "start_date",
            "ch",
            "bundle",
            "runtime",
            "engine",
            "selected_scope",
            "output",
            "sources",
            "initial_workers",
        },
        "run manifest contains missing or unexpected fields",
    )
    _require(manifest.get("schema_version") == SCHEMA_VERSION, "unsupported run schema")
    _require(
        manifest.get("runtime") == common.require_exact_runtime(),
        "run runtime identity mismatch",
    )
    _require(manifest.get("run_id") == run.name, "run_id must equal run directory name")
    _require(Path(str(manifest.get("qdh_root"))).resolve() == qdh, "qdh_root identity mismatch")
    _require(Path(str(manifest.get("run_root"))).resolve(strict=False) == run, "run_root identity mismatch")
    _require(manifest.get("start_date") == common.START_DATE, "run start_date mismatch")
    stage = run / "stage" / "features"
    _require(
        Path(str(manifest.get("stage_features"))).resolve(strict=False) == stage.resolve(strict=False),
        "stage_features must be exactly <run_root>/stage/features",
    )
    _require(stage.is_dir(), f"staged features missing: {stage}")
    output = manifest.get("output")
    _require(
        isinstance(output, dict)
        and set(output)
        == {"layout", "columns", "feature_dtype", "pre_2020_output_rows"}
        and output.get("layout")
        == "features/<symbol>/<timeframe>/<year>/data.parquet"
        and output.get("feature_dtype") == "float64"
        and output.get("pre_2020_output_rows") == 0
        and tuple(output.get("columns", ())) == OUTPUT_COLUMNS,
        "199-column order mismatch",
    )
    _manifest_sequences(manifest)
    return qdh, run, control, manifest


def _verify_bundle_hashes(manifest: dict[str, Any]) -> None:
    current = common.bundle_hashes(Path(__file__).resolve().parent)
    bundle = manifest.get("bundle")
    _require(isinstance(bundle, dict), "bundle hashes missing from run manifest")
    core = bundle.get("core")
    runtime = bundle.get("runtime")
    _require(core == current["core"], "Python formula core changed since build")
    # Runtime may include wh6_validate/wh6_publish in a future schema.  For v1,
    # require every build-recorded runtime file to match, without accepting an
    # unrecorded changed core.
    _require(isinstance(runtime, dict) and runtime, "runtime hashes missing")
    for name, expected in runtime.items():
        path = Path(__file__).resolve().parent / name
        _require(path.is_file(), f"recorded runtime file missing: {name}")
        _require(common.sha256_file(path) == expected, f"runtime changed since build: {name}")
    _require(
        bundle.get("core_semantic_sha256") == current["core_semantic_sha256"],
        "core semantic hash mismatch",
    )
    _require(
        bundle.get("runtime_semantic_sha256") == current["runtime_semantic_sha256"],
        "runtime semantic hash mismatch",
    )


def _verify_build_complete(control: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    marker_path = control / "BUILD_COMPLETE"
    _require(marker_path.is_file(), "BUILD_COMPLETE is missing")
    marker = _strict_json(marker_path)
    _require(isinstance(marker, dict), "BUILD_COMPLETE must be JSON")
    _require(marker.get("run_id") == manifest["run_id"], "BUILD_COMPLETE run_id mismatch")
    _require(
        marker.get("status") == "BUILD_COMPLETE_NOT_VALIDATED",
        "BUILD_COMPLETE has an invalid status",
    )
    _require(
        marker.get("runtime") == common.require_exact_runtime(),
        "BUILD_COMPLETE runtime identity mismatch",
    )
    aliases = {
        "run_manifest.json": "run_manifest_sha256",
        "files.jsonl": "files_sha256",
        "build_summary.json": "build_summary_sha256",
        "market_before.json": "market_before_sha256",
        "market_after.json": "market_after_sha256",
        "warmup_before.json": "warmup_before_sha256",
        "warmup_after.json": "warmup_after_sha256",
    }
    for name, field in aliases.items():
        path = control / name
        _require(path.is_file(), f"build control file missing: {name}")
        expected = marker.get(field)
        _require(isinstance(expected, str) and SHA256_RE.fullmatch(expected), f"missing hash for {name}")
        _require(common.sha256_file(path) == expected, f"build control hash mismatch: {name}")
    summary = _strict_json(control / "build_summary.json")
    _require(
        summary.get("status") == "BUILT_NOT_VALIDATED",
        f"build is not complete: {summary.get('status')}",
    )
    _require(
        summary.get("runtime") == common.require_exact_runtime(),
        "build summary runtime identity mismatch",
    )
    return marker


def _source_files(control: Path, manifest: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    market_before = _strict_json(control / "market_before.json")
    market_after = _strict_json(control / "market_after.json")
    warmup_before = _strict_json(control / "warmup_before.json")
    warmup_after = _strict_json(control / "warmup_after.json")
    _require(
        market_before.get("semantic_sha256") == market_after.get("semantic_sha256"),
        "market changed during build",
    )
    _require(
        warmup_before.get("semantic_sha256") == warmup_after.get("semantic_sha256"),
        "ClickHouse warmup changed during build",
    )
    sources = manifest.get("sources")
    _require(isinstance(sources, dict), "run manifest sources are missing")
    expected_market = sources.get("market_before_sha256")
    expected_warmup = sources.get("warmup_before_sha256")
    _require(
        expected_market == market_before.get("semantic_sha256"),
        "manifest/market source identity mismatch",
    )
    _require(
        expected_warmup == warmup_before.get("semantic_sha256"),
        "manifest/warmup source identity mismatch",
    )
    return market_before, market_after, warmup_before, warmup_after


def _expected_paths(
    market_snapshot: dict[str, Any], sequences: Iterable[dict[str, Any]]
) -> tuple[set[str], bool]:
    selected = {(row["symbol"], row["timeframe"]) for row in sequences}
    all_sequences = {
        (row["symbol"], row["timeframe"]) for row in market_snapshot["sequences"]
    }
    paths = {
        row["relative_path"]
        for row in market_snapshot["partitions"]
        if (row["symbol"], row["timeframe"]) in selected
    }
    _require(paths, "selected scope has no market partitions")
    return paths, selected == all_sequences


def _tree_paths(root: Path) -> set[str]:
    _require(root.is_dir(), f"partition root missing: {root}")
    result: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        _require(path.name == "data.parquet", f"unexpected staged file: {relative}")
        parts = relative.split("/")
        _require(
            len(parts) == 4
            and parts[1] in common.TIMEFRAMES
            and parts[2].isdigit()
            and int(parts[2]) >= 2020,
            f"invalid staged path: {relative}",
        )
        _require(relative not in result, f"duplicate staged path: {relative}")
        result.add(relative)
    return result


def _trade_time_ns(column: pa.ChunkedArray | pa.Array) -> np.ndarray:
    kind = column.type
    _require(pa.types.is_timestamp(kind), f"trade_time is not timestamp: {kind}")
    raw = np.asarray(pc.cast(column, pa.int64()), dtype=np.int64)
    multiplier = {"s": 1_000_000_000, "ms": 1_000_000, "us": 1_000, "ns": 1}[kind.unit]
    return raw * multiplier


def _scan_stage_partition(
    stage: Path,
    qdh: Path,
    relative: str,
    build_row: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    feature_path = stage / Path(relative)
    market_path = qdh / "market" / Path(relative)
    try:
        feature_file = pq.ParquetFile(feature_path)
        market_file = pq.ParquetFile(market_path)
        feature_schema = feature_file.schema_arrow
        market_schema = market_file.schema_arrow
        if tuple(feature_schema.names) != OUTPUT_COLUMNS:
            errors.append("column order/schema is not trade_time + locked 198")
        elif any(feature_schema.field(name).type != pa.float64() for name in FEATURE_COLUMNS):
            errors.append("one or more feature columns are not float64")
        if feature_schema.field("trade_time").type != market_schema.field("trade_time").type:
            errors.append("trade_time Arrow type differs from paired market")
        feature_rows = feature_file.metadata.num_rows
        market_rows = market_file.metadata.num_rows
        if feature_rows != market_rows or feature_rows <= 0:
            errors.append(f"row mismatch feature={feature_rows} market={market_rows}")
        feature_key = feature_file.read(columns=["trade_time"]).column(0).combine_chunks()
        market_key = market_file.read(columns=["trade_time"]).column(0).combine_chunks()
        if not feature_key.equals(market_key):
            errors.append("trade_time differs from paired market")
        times = _trade_time_ns(feature_key)
        boundary = int(pd.Timestamp(common.START_DATE, tz=common.TZ).value)
        if len(times) and int(times.min()) < boundary:
            errors.append("pre-2020 row found in staged output")
        if len(times) > 1 and np.any(times[1:] <= times[:-1]):
            errors.append("trade_time is not strictly increasing")
        feature_sha = common.sha256_file(feature_path)
        market_sha = common.sha256_file(market_path)
        if build_row is not None:
            recorded_feature = build_row.get("file_sha256", build_row.get("feature_sha256"))
            recorded_market = build_row.get("market_file_sha256", build_row.get("market_sha256"))
            if recorded_feature != feature_sha:
                errors.append("staged file changed since build")
            if recorded_market != market_sha:
                errors.append("paired market changed since build")
            if build_row.get("rows") != feature_rows:
                errors.append("build row count differs")
        result = {
            "relative_path": relative,
            "bytes": feature_path.stat().st_size,
            "rows": feature_rows,
            "file_sha256": feature_sha,
            "market_file_sha256": market_sha,
            "schema_sha256": common.schema_signature(feature_schema),
        }
    except Exception as exc:
        result = {"relative_path": relative, "bytes": 0, "rows": 0}
        errors.append(str(exc))
    return result, errors


def _load_build_file_map(control: Path) -> dict[str, dict[str, Any]]:
    rows = common.read_jsonl(control / "files.jsonl")
    result: dict[str, dict[str, Any]] = {}
    previous: str | None = None
    for row in rows:
        relative = row.get("relative_path")
        _require(isinstance(relative, str), "files.jsonl row has no relative_path")
        _require(relative not in result, f"duplicate path in files.jsonl: {relative}")
        if previous is not None:
            _require(relative > previous, "files.jsonl must be strictly path-sorted")
        previous = relative
        result[relative] = row
    return result


def _structure_validation(
    qdh: Path,
    run: Path,
    control: Path,
    manifest: dict[str, Any],
    workers: int,
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    marker = _verify_build_complete(control, manifest)
    _verify_bundle_hashes(manifest)
    market_before, _, warmup_before, _ = _source_files(control, manifest)
    sequences = _manifest_sequences(manifest)
    expected_paths, full_scope = _expected_paths(market_before, sequences)
    actual_paths = _tree_paths(run / "stage" / "features")
    build_files = _load_build_file_map(control)
    if actual_paths != expected_paths:
        failures.append(
            {
                "gate": "stage_path_set",
                "missing": sorted(expected_paths - actual_paths)[:100],
                "extra": sorted(actual_paths - expected_paths)[:100],
            }
        )
    if set(build_files) != expected_paths:
        failures.append(
            {
                "gate": "build_manifest_path_set",
                "missing": sorted(expected_paths - set(build_files))[:100],
                "extra": sorted(set(build_files) - expected_paths)[:100],
            }
        )
    scan_paths = sorted(expected_paths & actual_paths & set(build_files))
    records: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(int(workers), 8))) as pool:
        futures = {
            pool.submit(
                _scan_stage_partition,
                run / "stage" / "features",
                qdh,
                relative,
                build_files[relative],
            ): relative
            for relative in scan_paths
        }
        for future in as_completed(futures):
            relative = futures[future]
            record, errors = future.result()
            records.append(record)
            if errors:
                failures.append({"gate": "partition_structure", "relative_path": relative, "errors": errors})
    records.sort(key=lambda row: row["relative_path"])
    counts = manifest.get("selected_scope", {}).get("counts", {})
    expected_partitions = counts.get("partitions")
    expected_rows = counts.get("rows")
    if expected_partitions is not None and expected_partitions != len(expected_paths):
        failures.append({"gate": "expected_partitions", "manifest": expected_partitions, "actual": len(expected_paths)})
    total_rows = sum(row.get("rows", 0) for row in records)
    if expected_rows is not None and expected_rows != total_rows:
        failures.append({"gate": "expected_rows", "manifest": expected_rows, "actual": total_rows})
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "structure",
        "status": "PASS" if not failures else "FAIL",
        "run_id": manifest["run_id"],
        "validated_at_utc": common.now_utc(),
        "full_scope": full_scope,
        "run_manifest_sha256": common.sha256_file(control / "run_manifest.json"),
        "build_complete_sha256": common.sha256_file(control / "BUILD_COMPLETE"),
        "market_semantic_sha256": market_before["semantic_sha256"],
        "warmup_semantic_sha256": warmup_before["semantic_sha256"],
        "validation_tool_sha256s": _validation_tool_hashes(),
        "scope": {
            "sequences": len(sequences),
            "partitions": len(expected_paths),
            "rows": total_rows,
        },
        "marker": marker,
        "records": records,
        "failures": failures[:500],
    }


def _frame_from_arrow(warmup: pa.Table, market: pa.Table) -> pd.DataFrame:
    columns: dict[str, np.ndarray] = {}
    for name in common.ENGINE_INPUT_COLUMNS:
        left = np.asarray(warmup[name], dtype=np.float64)
        right = np.asarray(market[name], dtype=np.float64)
        columns[name] = np.concatenate((left, right))
    return pd.DataFrame(columns, index=pd.RangeIndex(len(next(iter(columns.values())))))


def _compare_feature_array(
    actual: pa.ChunkedArray | pa.Array, expected: np.ndarray
) -> tuple[int, int, int]:
    actual = actual.combine_chunks() if isinstance(actual, pa.ChunkedArray) else actual
    actual_null = np.asarray(pc.is_null(actual), dtype=bool)
    expected_values = np.asarray(expected, dtype=np.float64)
    expected_null = ~np.isfinite(expected_values)
    null_mismatch = int(np.count_nonzero(actual_null != expected_null))
    actual_values = np.asarray(pc.fill_null(actual, np.nan), dtype=np.float64)
    infinite = int(np.count_nonzero(np.isinf(actual_values[~actual_null])))
    comparable = ~(actual_null | expected_null)
    bit_mismatch = int(
        np.count_nonzero(
            actual_values[comparable].view(np.uint64)
            != expected_values[comparable].view(np.uint64)
        )
    )
    return null_mismatch, bit_mismatch, infinite


def _validate_sequence_full(
    qdh: Path,
    stage: Path,
    ch_url: str,
    sequence: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    symbol = sequence["symbol"]
    timeframe = sequence["timeframe"]
    code = sequence["contract_code"]
    market = common.load_market_sequence(qdh, symbol, timeframe)
    warmup = common.load_warmup_sequence(ch_url, code, timeframe)
    frame = _frame_from_arrow(warmup, market["table"])
    computed = PurePythonWH6Engine().compute(frame)
    live = computed.iloc[warmup.num_rows :].reset_index(drop=True)
    _require(len(live) == market["table"].num_rows, f"{symbol}/{timeframe}: computed row mismatch")
    records: list[dict[str, Any]] = []
    null_mismatch_total = 0
    bit_mismatch_total = 0
    infinite_total = 0
    for partition, market_table in zip(market["partitions"], market["tables"], strict=True):
        relative = partition["relative_path"]
        feature_path = stage / Path(relative)
        table = pq.read_table(feature_path).combine_chunks()
        rows = partition["rows"]
        offset = partition["offset"]
        expected = live.iloc[offset : offset + rows]
        if table.num_rows != rows:
            raise ValidationFailure(f"{relative}: row mismatch during full recomputation")
        if not table["trade_time"].equals(market_table["trade_time"]):
            raise ValidationFailure(f"{relative}: trade_time changed during full recomputation")
        partition_null = 0
        partition_bits = 0
        partition_inf = 0
        for column in FEATURE_COLUMNS:
            nulls, bits, infs = _compare_feature_array(table[column], expected[column].to_numpy())
            partition_null += nulls
            partition_bits += bits
            partition_inf += infs
        null_mismatch_total += partition_null
        bit_mismatch_total += partition_bits
        infinite_total += partition_inf
        records.append(
            {
                "relative_path": relative,
                "bytes": feature_path.stat().st_size,
                "rows": rows,
                "file_sha256": common.sha256_file(feature_path),
                "market_file_sha256": partition["market_file_sha256"],
                "schema_sha256": common.schema_signature(table.schema),
                "null_mask_mismatches": partition_null,
                "float64_bit_mismatches": partition_bits,
                "infinite_values": partition_inf,
            }
        )
    summary = {
        "symbol": symbol,
        "contract_code": code,
        "timeframe": timeframe,
        "warmup_rows": warmup.num_rows,
        "live_rows": len(live),
        "partitions": len(records),
        "null_mask_mismatches": null_mismatch_total,
        "float64_bit_mismatches": bit_mismatch_total,
        "infinite_values": infinite_total,
        "status": "PASS"
        if null_mismatch_total == bit_mismatch_total == infinite_total == 0
        else "FAIL",
    }
    return records, summary


def _resolve_ch_url(manifest: dict[str, Any], supplied: str | None) -> str:
    identity = manifest.get("ch")
    _require(
        isinstance(identity, dict)
        and set(identity) == {"endpoint", "url", "url_sha256", "readonly", "read_mode"}
        and identity.get("readonly") == 2
        and identity.get("read_mode") == "SELECT FINAL",
        "invalid ClickHouse identity in run manifest",
    )
    recorded = identity.get("url")
    if supplied is None:
        _require(isinstance(recorded, str) and recorded, "--ch-url is required for this run")
        supplied = recorded
    normalized = common.normalize_ch_url(supplied)
    redacted = common.redact_ch_url(normalized)
    expected_hash = identity.get("url_sha256")
    _require(
        hashlib.sha256(normalized.encode("utf-8")).hexdigest() == expected_hash,
        "ClickHouse URL identity mismatch",
    )
    _require(identity.get("endpoint") == redacted, "ClickHouse endpoint mismatch")
    if recorded is not None:
        _require(recorded == normalized, "stored ClickHouse URL mismatch")
    return normalized


def _full_validation(
    qdh: Path,
    run: Path,
    control: Path,
    manifest: dict[str, Any],
    ch_url: str,
    workers: int,
    structure: dict[str, Any],
) -> dict[str, Any]:
    _require(structure["status"] == "PASS", "structure validation did not pass")
    sequences = _manifest_sequences(manifest)
    market_before = _strict_json(control / "market_before.json")
    warmup_before = _strict_json(control / "warmup_before.json")
    current_market_before = common.market_snapshot(qdh, workers=workers)
    _require(current_market_before["semantic_sha256"] == market_before["semantic_sha256"], "market changed before full validation")
    # The build pins the complete 62 x 9 warmup source even for a selected
    # development scope, so source stability is always checked globally.
    source_sequences = market_before["sequences"]
    current_warmup_before = common.warmup_snapshot(ch_url, source_sequences)
    _require(current_warmup_before["semantic_sha256"] == warmup_before["semantic_sha256"], "ClickHouse warmup changed before full validation")

    records: list[dict[str, Any]] = []
    sequence_results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    # Limit parallel sequence materialization: each task holds a full sequence,
    # 198 output arrays, and its Arrow inputs simultaneously.
    sequence_workers = max(1, min(int(workers), 4))
    with ThreadPoolExecutor(max_workers=sequence_workers) as pool:
        futures = {
            pool.submit(
                _validate_sequence_full,
                qdh,
                run / "stage" / "features",
                ch_url,
                sequence,
            ): sequence
            for sequence in sequences
        }
        for future in as_completed(futures):
            sequence = futures[future]
            try:
                part_records, result = future.result()
                records.extend(part_records)
                sequence_results.append(result)
                if result["status"] != "PASS":
                    failures.append({"gate": "bitwise_recompute", **result})
            except Exception as exc:
                failure = {
                    "gate": "sequence_recompute",
                    "symbol": sequence["symbol"],
                    "timeframe": sequence["timeframe"],
                    "error": str(exc),
                }
                failures.append(failure)
                sequence_results.append({**failure, "status": "FAIL"})

    records.sort(key=lambda row: row["relative_path"])
    sequence_results.sort(key=lambda row: (row["symbol"], common.TIMEFRAMES.index(row["timeframe"])))
    current_market_after = common.market_snapshot(qdh, workers=workers)
    current_warmup_after = common.warmup_snapshot(ch_url, source_sequences)
    if current_market_after["semantic_sha256"] != current_market_before["semantic_sha256"]:
        failures.append({"gate": "market_stability", "error": "market changed during full validation"})
    if current_warmup_after["semantic_sha256"] != current_warmup_before["semantic_sha256"]:
        failures.append({"gate": "warmup_stability", "error": "ClickHouse warmup changed during full validation"})
    expected_paths, full_scope = _expected_paths(current_market_after, sequences)
    if {row["relative_path"] for row in records} != expected_paths:
        failures.append({"gate": "recomputed_path_set", "error": "not every expected partition was recomputed"})

    report = {
        "schema_version": SCHEMA_VERSION,
        "mode": "full",
        "status": "PASS" if not failures else "FAIL",
        "run_id": manifest["run_id"],
        "validated_at_utc": common.now_utc(),
        "full_scope": full_scope,
        "run_manifest_sha256": common.sha256_file(control / "run_manifest.json"),
        "build_complete_sha256": common.sha256_file(control / "BUILD_COMPLETE"),
        "structure_report_sha256": common.sha256_file(control / "validation_structure.json"),
        "market_semantic_sha256": current_market_after["semantic_sha256"],
        "warmup_semantic_sha256": current_warmup_after["semantic_sha256"],
        "validation_tool_sha256s": _validation_tool_hashes(),
        "scope": {
            "symbols": len({row["symbol"] for row in sequences}),
            "timeframes": [tf for tf in common.TIMEFRAMES if any(row["timeframe"] == tf for row in sequences)],
            "sequences": len(sequences),
            "partitions": len(records),
            "rows": sum(row["rows"] for row in records),
            "warmup_rows": sum(row.get("warmup_rows", 0) for row in sequence_results),
        },
        "totals": {
            "null_mask_mismatches": sum(row.get("null_mask_mismatches", 0) for row in records),
            "float64_bit_mismatches": sum(row.get("float64_bit_mismatches", 0) for row in records),
            "infinite_values": sum(row.get("infinite_values", 0) for row in records),
            "pre_2020_rows": 0,
        },
        "sequence_results": sequence_results,
        "failures": failures[:500],
    }
    common.write_jsonl(control / "files_manifest.jsonl", records)
    report["files_manifest_sha256"] = common.sha256_file(control / "files_manifest.jsonl")
    return report


def command_validate(args: argparse.Namespace) -> int:
    qdh, run, control, manifest = _validate_run_identity(args.qdh_root, args.run_root)
    _require(not (control / "READY").exists(), "run is already sealed; validation refused")
    report_path = control / f"validation_{args.mode}.json"
    try:
        if args.mode == "structure":
            report = _structure_validation(qdh, run, control, manifest, args.workers)
        else:
            structure = _structure_validation(qdh, run, control, manifest, args.workers)
            common.atomic_write_json(control / "validation_structure.json", structure)
            _require(structure["status"] == "PASS", "structure validation failed")
            ch_url = _resolve_ch_url(manifest, args.ch_url)
            report = _full_validation(
                qdh, run, control, manifest, ch_url, args.workers, structure
            )
    except Exception as exc:
        report = {
            "schema_version": SCHEMA_VERSION,
            "mode": args.mode,
            "status": "FAIL",
            "run_id": manifest.get("run_id"),
            "validated_at_utc": common.now_utc(),
            "full_scope": False,
            "error": str(exc),
        }
    common.atomic_write_json(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


def _verify_files_manifest(stage: Path, path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows = common.read_jsonl(path)
    expected = _tree_paths(stage)
    records: list[dict[str, Any]] = []
    previous: str | None = None
    for row in rows:
        relative = row.get("relative_path")
        _require(isinstance(relative, str) and relative in expected, f"invalid finalized path: {relative}")
        _require(previous is None or relative > previous, "files manifest is not sorted/unique")
        previous = relative
        feature = stage / Path(relative)
        _require(common.sha256_file(feature) == row.get("file_sha256"), f"stage changed after full validation: {relative}")
        _require(feature.stat().st_size == row.get("bytes"), f"stage size changed: {relative}")
        records.append(row)
    _require({row["relative_path"] for row in records} == expected, "finalized manifest/path set mismatch")
    return records, {
        "partitions": len(records),
        "rows": sum(int(row["rows"]) for row in records),
        "bytes": sum(int(row["bytes"]) for row in records),
    }


def command_finalize(args: argparse.Namespace) -> int:
    qdh, run, control, manifest = _validate_run_identity(args.qdh_root, args.run_root)
    ready_path = control / "READY"
    _require(not ready_path.exists(), "READY already exists; sealed runs are immutable")
    report_path = control / "validation_full.json"
    _require(report_path.is_file(), "full validation report is missing")
    report = _strict_json(report_path)
    _require(report.get("status") == "PASS" and report.get("mode") == "full", "full validation did not pass")
    _require(report.get("full_scope") is True, "partial-scope runs cannot be finalized")
    _require(report.get("run_id") == manifest["run_id"], "validation run_id mismatch")
    _require(report.get("run_manifest_sha256") == common.sha256_file(control / "run_manifest.json"), "run manifest changed after validation")
    _require(report.get("build_complete_sha256") == common.sha256_file(control / "BUILD_COMPLETE"), "BUILD_COMPLETE changed after validation")
    _require(
        report.get("validation_tool_sha256s") == _validation_tool_hashes(),
        "validation/publish tools changed after full validation",
    )
    files_path = control / "files_manifest.jsonl"
    _require(report.get("files_manifest_sha256") == common.sha256_file(files_path), "files manifest changed after validation")
    _verify_build_complete(control, manifest)
    _verify_bundle_hashes(manifest)
    records, totals = _verify_files_manifest(run / "stage" / "features", files_path)
    _require(totals["partitions"] == report["scope"]["partitions"], "partition total changed")
    _require(totals["rows"] == report["scope"]["rows"], "row total changed")
    # A PASS report is not a lease on mutable inputs.  Re-snapshot both qdh
    # market and pre-2020 ClickHouse immediately before sealing.
    ch_url = _resolve_ch_url(manifest, args.ch_url)
    sequences = _strict_json(control / "market_before.json")["sequences"]
    market_current = common.market_snapshot(qdh, workers=args.workers)
    _require(
        market_current["semantic_sha256"] == report["market_semantic_sha256"],
        "market changed after full validation",
    )
    warmup_current = common.warmup_snapshot(ch_url, sequences)
    _require(
        warmup_current["semantic_sha256"] == report["warmup_semantic_sha256"],
        "ClickHouse warmup changed after full validation",
    )
    ready = {
        "schema_version": SCHEMA_VERSION,
        "status": "READY",
        "run_id": manifest["run_id"],
        "created_at_utc": common.now_utc(),
        "full_scope": True,
        "scope": report["scope"],
        "columns": list(OUTPUT_COLUMNS),
        "run_manifest_sha256": common.sha256_file(control / "run_manifest.json"),
        "build_complete_sha256": common.sha256_file(control / "BUILD_COMPLETE"),
        "validation_full_sha256": common.sha256_file(report_path),
        "files_manifest_sha256": common.sha256_file(files_path),
        "market_semantic_sha256": report["market_semantic_sha256"],
        "warmup_semantic_sha256": report["warmup_semantic_sha256"],
        "validation_tool_sha256s": _validation_tool_hashes(),
        "stage": totals,
    }
    # READY is intentionally the final write in finalize.
    common.atomic_write_json(ready_path, ready)
    result = {**ready, "ready_sha256": common.sha256_file(ready_path)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _read_live_manifest(path: Path, expected_sha: str) -> list[dict[str, Any]]:
    _require(path.is_file() and common.sha256_file(path) == expected_sha, "live manifest hash mismatch")
    rows = common.read_jsonl(path)
    required = {"relative_path", "bytes", "rows", "feature_sha256", "market_sha256"}
    previous: str | None = None
    for row in rows:
        _require(set(row) == required, "live manifest has missing/unexpected fields")
        relative = row["relative_path"]
        _require(previous is None or relative > previous, "live manifest not sorted/unique")
        previous = relative
    _require(rows, "live manifest is empty")
    return rows


def _verify_live_partition(qdh: Path, row: dict[str, Any], columns: tuple[str, ...]) -> list[str]:
    relative = row["relative_path"]
    errors: list[str] = []
    try:
        feature = qdh / "features" / Path(relative)
        market = qdh / "market" / Path(relative)
        if feature.stat().st_size != row["bytes"]:
            errors.append("byte size mismatch")
        if common.sha256_file(feature) != row["feature_sha256"]:
            errors.append("feature SHA256 mismatch")
        if common.sha256_file(market) != row["market_sha256"]:
            errors.append("market SHA256 mismatch")
        ff = pq.ParquetFile(feature)
        mf = pq.ParquetFile(market)
        if tuple(ff.schema_arrow.names) != columns:
            errors.append("schema/order mismatch")
        if any(ff.schema_arrow.field(name).type != pa.float64() for name in columns[1:]):
            errors.append("feature dtype mismatch")
        if ff.schema_arrow.field("trade_time").type != mf.schema_arrow.field("trade_time").type:
            errors.append("trade_time type mismatch")
        if ff.metadata.num_rows != mf.metadata.num_rows or ff.metadata.num_rows != row["rows"]:
            errors.append("row count mismatch")
        fk = ff.read(columns=["trade_time"]).column(0).combine_chunks()
        mk = mf.read(columns=["trade_time"]).column(0).combine_chunks()
        if not fk.equals(mk):
            errors.append("trade_time mismatch")
        times = _trade_time_ns(fk)
        if len(times) > 1 and np.any(times[1:] <= times[:-1]):
            errors.append("trade_time not strict")
        boundary = int(pd.Timestamp(common.START_DATE, tz=common.TZ).value)
        if len(times) and times.min() < boundary:
            errors.append("pre-2020 output")
        table = ff.read(columns=list(columns[1:])).combine_chunks()
        infs = 0
        for name in columns[1:]:
            values = np.asarray(pc.fill_null(table[name], np.nan), dtype=np.float64)
            infs += int(np.count_nonzero(np.isinf(values)))
        if infs:
            errors.append(f"infinite feature values={infs}")
    except Exception as exc:
        errors.append(str(exc))
    return errors


def verify_live(qdh_root: Path | str, workers: int = 4) -> dict[str, Any]:
    qdh = Path(qdh_root).resolve(strict=True)
    snapshot_path = qdh / "meta" / "features_snapshot.json"
    manifest_path = qdh / "meta" / "features_manifest.jsonl"
    snapshot_before = common.sha256_file(snapshot_path)
    snapshot = _strict_json(snapshot_path)
    _require(snapshot.get("schema_version") == 2, "unsupported live snapshot schema")
    _require(snapshot.get("dataset") == "features" and snapshot.get("status") == "COMMITTED", "live snapshot is not COMMITTED")
    manifest_meta = snapshot.get("manifest", {})
    expected_sha = manifest_meta.get("sha256")
    _require(isinstance(expected_sha, str) and SHA256_RE.fullmatch(expected_sha), "invalid live manifest SHA")
    _require(snapshot.get("release_id") == f"sha256:{expected_sha}", "live release identity mismatch")
    rows = _read_live_manifest(manifest_path, expected_sha)
    columns = tuple(snapshot.get("schema", {}).get("columns", ()))
    _require(columns == OUTPUT_COLUMNS, "live 199-column contract mismatch")
    paths = {row["relative_path"] for row in rows}
    _require(_tree_paths(qdh / "features") == paths, "live feature path set differs from manifest")
    _require(_tree_paths(qdh / "market") == paths, "live market path set differs from manifest")
    failures: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(int(workers), 8))) as pool:
        futures = {pool.submit(_verify_live_partition, qdh, row, columns): row for row in rows}
        for future in as_completed(futures):
            row = futures[future]
            errors = future.result()
            if errors:
                failures.append({"relative_path": row["relative_path"], "errors": errors})
    _require(common.sha256_file(snapshot_path) == snapshot_before, "live snapshot changed during verification")
    scope = snapshot.get("scope", {})
    calculated = {
        "symbols": len({row["relative_path"].split("/")[0] for row in rows}),
        "sequences": len({tuple(row["relative_path"].split("/")[:2]) for row in rows}),
        "partitions": len(rows),
        "rows": sum(row["rows"] for row in rows),
    }
    for key, value in calculated.items():
        if scope.get(key) != value:
            failures.append({"gate": "snapshot_scope", "field": key, "snapshot": scope.get(key), "actual": value})
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "verify-live",
        "status": "PASS" if not failures else "FAIL",
        "verified_at_utc": common.now_utc(),
        "release_id": snapshot.get("release_id"),
        "snapshot_sha256": snapshot_before,
        "manifest_sha256": expected_sha,
        "scope": calculated,
        "failures": failures[:500],
    }


def command_verify_live(args: argparse.Namespace) -> int:
    try:
        report = verify_live(args.qdh_root, args.workers)
    except Exception as exc:
        report = {
            "schema_version": SCHEMA_VERSION,
            "mode": "verify-live",
            "status": "FAIL",
            "verified_at_utc": common.now_utc(),
            "error": str(exc),
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    validate_parser = sub.add_parser("validate", help="validate an external staged run")
    validate_parser.add_argument("--mode", choices=("structure", "full"), required=True)
    validate_parser.add_argument("--qdh-root", required=True)
    validate_parser.add_argument("--run-root", required=True)
    validate_parser.add_argument("--ch-url")
    validate_parser.add_argument("--workers", type=int, default=2, choices=range(1, 9))
    validate_parser.set_defaults(func=command_validate)

    finalize_parser = sub.add_parser("finalize", help="seal a full-scope full PASS as READY")
    finalize_parser.add_argument("--qdh-root", required=True)
    finalize_parser.add_argument("--run-root", required=True)
    finalize_parser.add_argument("--ch-url")
    finalize_parser.add_argument("--workers", type=int, default=4, choices=range(1, 9))
    finalize_parser.set_defaults(func=command_finalize)

    live_parser = sub.add_parser("verify-live", help="read-only verification of qdh live features")
    live_parser.add_argument("--qdh-root", required=True)
    live_parser.add_argument("--workers", type=int, default=4, choices=range(1, 9))
    live_parser.set_defaults(func=command_verify_live)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        common.require_exact_runtime()
        return int(args.func(args))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
