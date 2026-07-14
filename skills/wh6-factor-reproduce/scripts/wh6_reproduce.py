#!/usr/bin/env python3
"""Preflight and stage the locked 198-column WH6 feature set.

``preflight`` is strictly read-only.  ``build`` writes only below an explicit,
absolute, same-volume run root outside qdh.  It never writes to qdh or
ClickHouse and never publishes a staging generation into the live feature
directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlsplit

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from wh6_candidate import load_engine
from wh6_common import (
    ENGINE_INPUT_COLUMNS,
    EXPECTED_SEQUENCES,
    EXPECTED_SYMBOLS,
    START_DATE,
    TIMEFRAMES,
    arrow_table_sha256,
    atomic_write_json,
    bundle_hashes,
    canonical_json_sha256,
    ensure_qdh_run_roots,
    load_market_sequence,
    load_warmup_sequence,
    market_snapshot,
    normalize_ch_url,
    now_utc,
    read_json,
    redact_ch_url,
    require_exact_runtime,
    schema_signature,
    select_sequences,
    sha256_file,
    warmup_snapshot,
    write_jsonl,
)


SCRIPT_DIR = Path(__file__).resolve().parent


def _csv_filter(value: str | None) -> list[str] | None:
    if value is None:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise RuntimeError("a supplied filter cannot be empty")
    if len(items) != len(set(items)):
        raise RuntimeError(f"duplicate filter values: {items}")
    return items


def _engine_contract() -> dict[str, Any]:
    engine = load_engine()
    capability = engine.capability_report()
    columns = list(engine.columns)
    if capability.get("status") != "READY":
        raise RuntimeError(f"WH6 core is not READY: {capability}")
    if len(columns) != 198 or len(set(columns)) != 198:
        raise RuntimeError("WH6 core must expose exactly 198 unique columns")
    if not all(isinstance(column, str) and column.startswith("wh6_") for column in columns):
        raise RuntimeError("WH6 output column contract is invalid")
    if capability.get("runtime_formula_file_reads") is not False:
        raise RuntimeError("WH6 core must not read formula files at runtime")
    return {
        "capability": capability,
        "columns": columns,
        "column_order_sha256": canonical_json_sha256(columns),
    }


def _selected_scope(
    snapshot: dict[str, Any],
    symbols: list[str] | None,
    timeframes: list[str] | None,
) -> dict[str, Any]:
    sequences = select_sequences(snapshot, symbols, timeframes)
    chosen_symbols = sorted({row["symbol"] for row in sequences})
    chosen_timeframes = [
        timeframe
        for timeframe in TIMEFRAMES
        if any(row["timeframe"] == timeframe for row in sequences)
    ]
    return {
        "symbols": chosen_symbols,
        "timeframes": chosen_timeframes,
        "sequences": sequences,
        "counts": {
            "symbols": len(chosen_symbols),
            "timeframes": len(chosen_timeframes),
            "sequences": len(sequences),
            "partitions": sum(row["partitions"] for row in sequences),
            "rows": sum(row["rows"] for row in sequences),
        },
    }


def _ch_identity(ch_url: str) -> dict[str, Any]:
    normalized = normalize_ch_url(ch_url)
    parsed = urlsplit(normalized)
    safe_to_store = parsed.username is None and parsed.password is None and not parsed.query
    return {
        "endpoint": redact_ch_url(normalized),
        "url": normalized if safe_to_store else None,
        "url_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "readonly": 2,
        "read_mode": "SELECT FINAL",
    }


def _summary(
    market: dict[str, Any],
    warmup: dict[str, Any],
    scope: dict[str, Any],
    engine: dict[str, Any],
    bundles: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": "PREFLIGHT_PASS",
        "writes_performed": False,
        "runtime": require_exact_runtime(),
        "qdh_market": {
            **market["counts"],
            "start_trade_date": market["start_trade_date"],
            "cutoff_trade_date": market["cutoff_trade_date"],
            "semantic_sha256": market["semantic_sha256"],
        },
        "clickhouse_warmup": {
            **warmup["counts"],
            "boundary": warmup["boundary"],
            "readonly": warmup["readonly"],
            "read_mode": warmup["read_mode"],
            "semantic_sha256": warmup["semantic_sha256"],
        },
        "selected_scope": scope["counts"],
        "output": {
            "columns": 1 + len(engine["columns"]),
            "feature_columns": len(engine["columns"]),
            "column_order_sha256": engine["column_order_sha256"],
            "pre_2020_output_rows": 0,
        },
        "core_semantic_sha256": bundles["core_semantic_sha256"],
        "runtime_semantic_sha256": bundles["runtime_semantic_sha256"],
    }


def command_preflight(args: argparse.Namespace) -> int:
    qdh = Path(args.qdh_root)
    if not qdh.is_absolute():
        raise RuntimeError("qdh root must be absolute")
    qdh = qdh.resolve(strict=True)
    engine = _engine_contract()
    bundles = bundle_hashes(SCRIPT_DIR)
    before = market_snapshot(qdh, workers=args.workers)
    if before["counts"]["symbols"] != EXPECTED_SYMBOLS:
        raise RuntimeError("market symbol count changed")
    if before["counts"]["sequences"] != EXPECTED_SEQUENCES:
        raise RuntimeError("market sequence count changed")
    warmup = warmup_snapshot(args.ch_url, before["sequences"])
    scope = _selected_scope(
        before, _csv_filter(args.symbols), _csv_filter(args.timeframes)
    )
    print(
        json.dumps(
            _summary(before, warmup, scope, engine, bundles),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _safe_reset_incomplete_sequence(
    stage_features: Path, symbol: str, timeframe: str
) -> None:
    target = (stage_features / symbol / timeframe).resolve(strict=False)
    root = stage_features.resolve(strict=True)
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"unsafe staging cleanup target: {target}") from exc
    if relative.parts != (symbol, timeframe):
        raise RuntimeError(f"unsafe staging cleanup target: {target}")
    if target.exists():
        shutil.rmtree(target)


def _atomic_write_parquet(table: pa.Table, final: Path) -> None:
    final.parent.mkdir(parents=True, exist_ok=True)
    partial = final.with_name(final.name + ".partial")
    if final.exists() or partial.exists():
        raise RuntimeError(f"refusing to overwrite staged output: {final}")
    pq.write_table(
        table,
        partial,
        compression="snappy",
        version="2.6",
        use_dictionary=True,
        write_statistics=True,
        row_group_size=max(1, table.num_rows),
    )
    with partial.open("r+b") as handle:
        os.fsync(handle.fileno())
    os.replace(partial, final)


def _record_path(control: Path, symbol: str, timeframe: str) -> Path:
    return control / "sequence_records" / f"{symbol}__{timeframe}.json"


def _validate_completed_record(
    record: dict[str, Any],
    *,
    stage_features: Path,
    sequence: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    if record.get("status") != "COMPLETE":
        raise RuntimeError("sequence record is not COMPLETE")
    for key in ("symbol", "contract_code", "timeframe"):
        if record.get(key) != sequence[key]:
            raise RuntimeError(f"sequence record identity mismatch for {key}")
    if record.get("market_before_sha256") != manifest["sources"]["market_before_sha256"]:
        raise RuntimeError("sequence record market source mismatch")
    if record.get("warmup_before_sha256") != manifest["sources"]["warmup_before_sha256"]:
        raise RuntimeError("sequence record warmup source mismatch")
    if record.get("core_semantic_sha256") != manifest["bundle"]["core_semantic_sha256"]:
        raise RuntimeError("sequence record core mismatch")
    expected_paths = set(sequence["partition_paths"])
    files = record.get("files")
    if not isinstance(files, list) or {row.get("relative_path") for row in files} != expected_paths:
        raise RuntimeError("sequence record partition set mismatch")
    for row in files:
        path = stage_features / row["relative_path"]
        if not path.is_file() or sha256_file(path) != row.get("file_sha256"):
            raise RuntimeError(f"completed staged file is missing or changed: {path}")


def _warmup_row(
    warmup_before: dict[str, Any], symbol: str, timeframe: str
) -> dict[str, Any]:
    matches = [
        row
        for row in warmup_before["sequences"]
        if row["symbol"] == symbol and row["timeframe"] == timeframe
    ]
    if len(matches) != 1:
        raise RuntimeError(f"warmup snapshot identity mismatch: {symbol}/{timeframe}")
    return matches[0]


def _build_sequence(
    sequence: dict[str, Any],
    *,
    qdh: Path,
    stage_features: Path,
    control: Path,
    ch_url: str,
    manifest: dict[str, Any],
    market_before: dict[str, Any],
    warmup_before: dict[str, Any],
    resume: bool,
) -> dict[str, Any]:
    symbol = sequence["symbol"]
    timeframe = sequence["timeframe"]
    record_path = _record_path(control, symbol, timeframe)
    if record_path.is_file():
        if not resume:
            raise RuntimeError(f"unexpected existing sequence record: {record_path}")
        record = read_json(record_path)
        _validate_completed_record(
            record,
            stage_features=stage_features,
            sequence=sequence,
            manifest=manifest,
        )
        return record
    if (stage_features / symbol / timeframe).exists():
        if not resume:
            raise RuntimeError(f"unexpected staged sequence directory: {symbol}/{timeframe}")
        _safe_reset_incomplete_sequence(stage_features, symbol, timeframe)

    partition_index = {
        row["relative_path"]: row
        for row in market_before["partitions"]
        if row["symbol"] == symbol and row["timeframe"] == timeframe
    }
    if set(partition_index) != set(sequence["partition_paths"]):
        raise RuntimeError(f"market snapshot partition mismatch: {symbol}/{timeframe}")
    loaded = load_market_sequence(qdh, symbol, timeframe)
    actual_paths = {row["relative_path"] for row in loaded["partitions"]}
    if actual_paths != set(partition_index):
        raise RuntimeError(f"live market path drift: {symbol}/{timeframe}")
    for row in loaded["partitions"]:
        expected = partition_index[row["relative_path"]]
        if row["market_file_sha256"] != expected["file_sha256"] or row["rows"] != expected["rows"]:
            raise RuntimeError(f"live market file drift: {row['relative_path']}")

    warmup = load_warmup_sequence(ch_url, sequence["contract_code"], timeframe)
    expected_warmup = _warmup_row(warmup_before, symbol, timeframe)
    if warmup.num_rows != expected_warmup["rows"]:
        raise RuntimeError(
            f"warmup row drift {symbol}/{timeframe}: "
            f"{warmup.num_rows} != {expected_warmup['rows']}"
        )
    warmup_data_sha256 = arrow_table_sha256(warmup)

    live_table: pa.Table = loaded["table"]
    warmup_frame = warmup.select(list(ENGINE_INPUT_COLUMNS)).to_pandas()
    live_frame = live_table.select(list(ENGINE_INPUT_COLUMNS)).to_pandas()
    input_frame = pd.concat([warmup_frame, live_frame], ignore_index=True)
    engine = load_engine()
    calculated = engine.compute(input_frame)
    if len(calculated) != len(input_frame):
        raise RuntimeError(f"engine row mismatch: {symbol}/{timeframe}")
    live_features = calculated.iloc[warmup.num_rows :].reset_index(drop=True)
    if len(live_features) != live_table.num_rows:
        raise RuntimeError(f"live output row mismatch: {symbol}/{timeframe}")
    for column in engine.columns:
        values = live_features[column].to_numpy(dtype=np.float64, copy=False)
        if np.isinf(values).any():
            raise RuntimeError(f"{symbol}/{timeframe}: output Inf in {column}")

    file_rows: list[dict[str, Any]] = []
    offset = 0
    for market_part, loaded_part in zip(
        loaded["tables"], loaded["partitions"], strict=True
    ):
        rows = market_part.num_rows
        feature_part = live_features.iloc[offset : offset + rows].reset_index(drop=True).copy()
        trade_time = market_part["trade_time"].to_pandas()
        feature_part.insert(0, "trade_time", trade_time)
        expected_columns = ["trade_time", *engine.columns]
        if list(feature_part.columns) != expected_columns:
            raise RuntimeError("output column order changed")
        output_table = pa.Table.from_pandas(feature_part, preserve_index=False)
        if output_table.schema.field("trade_time").type != market_part.schema.field("trade_time").type:
            raise RuntimeError(
                f"trade_time type changed for {loaded_part['relative_path']}: "
                f"{output_table.schema.field('trade_time').type} != "
                f"{market_part.schema.field('trade_time').type}"
            )
        if any(output_table.schema.field(column).type != pa.float64() for column in engine.columns):
            raise RuntimeError("one or more WH6 output columns are not float64")
        destination = stage_features / loaded_part["relative_path"]
        _atomic_write_parquet(output_table, destination)
        expected_market = partition_index[loaded_part["relative_path"]]
        file_rows.append(
            {
                "relative_path": loaded_part["relative_path"],
                "symbol": symbol,
                "contract_code": sequence["contract_code"],
                "timeframe": timeframe,
                "period": sequence["period"],
                "year": loaded_part["year"],
                "rows": rows,
                "bytes": destination.stat().st_size,
                "file_sha256": sha256_file(destination),
                "market_file_sha256": expected_market["file_sha256"],
                "schema_sha256": schema_signature(output_table.schema),
                "min_trade_date": expected_market["min_trade_date"],
                "max_trade_date": expected_market["max_trade_date"],
                "min_trade_time_epoch_ns": expected_market["min_trade_time_epoch_ns"],
                "max_trade_time_epoch_ns": expected_market["max_trade_time_epoch_ns"],
            }
        )
        offset += rows
    if offset != live_table.num_rows:
        raise RuntimeError(f"partition slicing mismatch: {symbol}/{timeframe}")

    record = {
        "schema_version": 1,
        "status": "COMPLETE",
        "completed_at": now_utc(),
        "symbol": symbol,
        "contract_code": sequence["contract_code"],
        "timeframe": timeframe,
        "period": sequence["period"],
        "warmup_rows": warmup.num_rows,
        "warmup_data_sha256": warmup_data_sha256,
        "live_rows": live_table.num_rows,
        "market_before_sha256": manifest["sources"]["market_before_sha256"],
        "warmup_before_sha256": manifest["sources"]["warmup_before_sha256"],
        "core_semantic_sha256": manifest["bundle"]["core_semantic_sha256"],
        "runtime_semantic_sha256": manifest["bundle"]["runtime_semantic_sha256"],
        "files": file_rows,
    }
    atomic_write_json(record_path, record)
    return record


def _new_run(
    args: argparse.Namespace,
    qdh: Path,
    run: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if run.exists():
        raise RuntimeError(f"run root already exists; use --resume only for a pinned run: {run}")
    engine = _engine_contract()
    bundles = bundle_hashes(SCRIPT_DIR)
    market_before = market_snapshot(qdh, workers=args.workers)
    warmup_before = warmup_snapshot(args.ch_url, market_before["sequences"])
    scope = _selected_scope(
        market_before, _csv_filter(args.symbols), _csv_filter(args.timeframes)
    )
    control = run / "control"
    stage_features = run / "stage" / "features"
    control.mkdir(parents=True, exist_ok=False)
    stage_features.mkdir(parents=True, exist_ok=False)
    (control / "sequence_records").mkdir(parents=False, exist_ok=False)
    manifest = {
        "schema_version": 1,
        "run_id": run.name,
        "created_at": now_utc(),
        "qdh_root": str(qdh),
        "run_root": str(run),
        "stage_features": str(stage_features),
        "start_date": START_DATE,
        "ch": _ch_identity(args.ch_url),
        "bundle": bundles,
        "runtime": require_exact_runtime(),
        "engine": engine,
        "selected_scope": scope,
        "output": {
            "layout": "features/<symbol>/<timeframe>/<year>/data.parquet",
            "columns": ["trade_time", *engine["columns"]],
            "feature_dtype": "float64",
            "pre_2020_output_rows": 0,
        },
        "sources": {
            "market_before_sha256": market_before["semantic_sha256"],
            "warmup_before_sha256": warmup_before["semantic_sha256"],
        },
        "initial_workers": args.workers,
    }
    atomic_write_json(control / "market_before.json", market_before)
    atomic_write_json(control / "warmup_before.json", warmup_before)
    atomic_write_json(control / "run_manifest.json", manifest)
    return manifest, market_before, warmup_before


def _resume_run(
    args: argparse.Namespace,
    qdh: Path,
    run: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    control = run / "control"
    manifest = read_json(control / "run_manifest.json")
    if manifest.get("schema_version") != 1:
        raise RuntimeError("unsupported run manifest schema")
    if manifest.get("runtime") != require_exact_runtime():
        raise RuntimeError("resume runtime identity mismatch")
    if manifest.get("qdh_root") != str(qdh) or manifest.get("run_root") != str(run):
        raise RuntimeError("resume root identity mismatch")
    expected_stage = str(run / "stage" / "features")
    if manifest.get("stage_features") != expected_stage:
        raise RuntimeError("resume staging path mismatch")
    normalized_url = normalize_ch_url(args.ch_url)
    actual_url_hash = hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()
    if manifest.get("ch", {}).get("url_sha256") != actual_url_hash:
        raise RuntimeError("ClickHouse URL identity differs from the pinned run")
    bundles = bundle_hashes(SCRIPT_DIR)
    if bundles != manifest.get("bundle"):
        raise RuntimeError("skill core/runtime changed since the run was created")
    requested_symbols = _csv_filter(args.symbols)
    requested_timeframes = _csv_filter(args.timeframes)
    if requested_symbols is not None and sorted(requested_symbols) != manifest["selected_scope"]["symbols"]:
        raise RuntimeError("--symbols differs from the pinned run")
    if requested_timeframes is not None:
        ordered = [value for value in TIMEFRAMES if value in set(requested_timeframes)]
        if ordered != manifest["selected_scope"]["timeframes"]:
            raise RuntimeError("--timeframes differs from the pinned run")
    market_before = read_json(control / "market_before.json")
    warmup_before = read_json(control / "warmup_before.json")
    current_market = market_snapshot(qdh, workers=args.workers)
    if current_market["semantic_sha256"] != market_before["semantic_sha256"]:
        raise RuntimeError("qdh market changed since the run was created")
    current_warmup = warmup_snapshot(args.ch_url, current_market["sequences"])
    if current_warmup["semantic_sha256"] != warmup_before["semantic_sha256"]:
        raise RuntimeError("ClickHouse warmup changed since the run was created")
    if (control / "BUILD_COMPLETE").is_file():
        complete = read_json(control / "BUILD_COMPLETE")
        if complete.get("run_manifest_sha256") != sha256_file(control / "run_manifest.json"):
            raise RuntimeError("existing BUILD_COMPLETE does not match run manifest")
    return manifest, market_before, warmup_before


def command_build(args: argparse.Namespace) -> int:
    qdh, run = ensure_qdh_run_roots(
        args.qdh_root, args.run_root, require_run=args.resume
    )
    if args.resume:
        manifest, market_before, warmup_before = _resume_run(args, qdh, run)
    else:
        manifest, market_before, warmup_before = _new_run(args, qdh, run)
    control = run / "control"
    stage_features = run / "stage" / "features"
    if (control / "BUILD_COMPLETE").is_file():
        print(json.dumps(read_json(control / "BUILD_COMPLETE"), ensure_ascii=False, indent=2))
        return 0

    sequences = manifest["selected_scope"]["sequences"]
    records: list[dict[str, Any]] = []
    failures: list[str] = []
    print(
        f"building {len(sequences)} sequences / "
        f"{manifest['selected_scope']['counts']['partitions']} partitions / "
        f"{manifest['selected_scope']['counts']['rows']} live rows",
        flush=True,
    )
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                _build_sequence,
                sequence,
                qdh=qdh,
                stage_features=stage_features,
                control=control,
                ch_url=args.ch_url,
                manifest=manifest,
                market_before=market_before,
                warmup_before=warmup_before,
                resume=args.resume,
            ): sequence
            for sequence in sequences
        }
        for index, future in enumerate(as_completed(futures), 1):
            sequence = futures[future]
            try:
                records.append(future.result())
            except Exception as exc:
                failures.append(
                    f"{sequence['symbol']}/{sequence['timeframe']}: {type(exc).__name__}: {exc}"
                )
            print(
                f"progress {index}/{len(sequences)} complete={len(records)} failed={len(failures)}",
                flush=True,
            )
    if failures:
        summary = {
            "schema_version": 1,
            "status": "FAILED",
            "finished_at": now_utc(),
            "completed_sequences": len(records),
            "expected_sequences": len(sequences),
            "failures": failures,
        }
        atomic_write_json(control / "build_summary.json", summary)
        raise RuntimeError(f"build failed for {len(failures)} sequences")

    records.sort(key=lambda row: (row["symbol"], TIMEFRAMES.index(row["timeframe"])))
    file_rows = sorted(
        [file_row for record in records for file_row in record["files"]],
        key=lambda row: row["relative_path"],
    )
    expected_paths = {
        path
        for sequence in sequences
        for path in sequence["partition_paths"]
    }
    if {row["relative_path"] for row in file_rows} != expected_paths:
        raise RuntimeError("completed file inventory differs from selected market partitions")
    write_jsonl(control / "files.jsonl", file_rows)

    market_after = market_snapshot(qdh, workers=args.workers)
    warmup_after = warmup_snapshot(args.ch_url, market_after["sequences"])
    atomic_write_json(control / "market_after.json", market_after)
    atomic_write_json(control / "warmup_after.json", warmup_after)
    current_bundles = bundle_hashes(SCRIPT_DIR)
    drift: list[str] = []
    if market_after["semantic_sha256"] != market_before["semantic_sha256"]:
        drift.append("qdh market")
    if warmup_after["semantic_sha256"] != warmup_before["semantic_sha256"]:
        drift.append("ClickHouse warmup")
    if current_bundles != manifest["bundle"]:
        drift.append("skill core/runtime")
    if drift:
        summary = {
            "schema_version": 1,
            "status": "SOURCE_DRIFT",
            "finished_at": now_utc(),
            "drift": drift,
        }
        atomic_write_json(control / "build_summary.json", summary)
        raise RuntimeError(f"source drift detected: {', '.join(drift)}")

    summary = {
        "schema_version": 1,
        "status": "BUILT_NOT_VALIDATED",
        "finished_at": now_utc(),
        "runtime": require_exact_runtime(),
        "sequences": len(records),
        "partitions": len(file_rows),
        "rows": sum(row["rows"] for row in file_rows),
        "bytes": sum(row["bytes"] for row in file_rows),
        "warmup_rows": sum(record["warmup_rows"] for record in records),
        "market_semantic_sha256": market_after["semantic_sha256"],
        "warmup_semantic_sha256": warmup_after["semantic_sha256"],
        "core_semantic_sha256": current_bundles["core_semantic_sha256"],
        "runtime_semantic_sha256": current_bundles["runtime_semantic_sha256"],
        "pre_2020_output_rows": 0,
    }
    atomic_write_json(control / "build_summary.json", summary)
    complete = {
        "schema_version": 1,
        "run_id": manifest["run_id"],
        "status": "BUILD_COMPLETE_NOT_VALIDATED",
        "created_at": now_utc(),
        "runtime": require_exact_runtime(),
        "run_manifest_sha256": sha256_file(control / "run_manifest.json"),
        "files_sha256": sha256_file(control / "files.jsonl"),
        "build_summary_sha256": sha256_file(control / "build_summary.json"),
        "market_before_sha256": sha256_file(control / "market_before.json"),
        "market_after_sha256": sha256_file(control / "market_after.json"),
        "warmup_before_sha256": sha256_file(control / "warmup_before.json"),
        "warmup_after_sha256": sha256_file(control / "warmup_after.json"),
        "market_semantic_sha256": market_after["semantic_sha256"],
        "warmup_semantic_sha256": warmup_after["semantic_sha256"],
        "core_semantic_sha256": current_bundles["core_semantic_sha256"],
        "runtime_semantic_sha256": current_bundles["runtime_semantic_sha256"],
        "partitions": len(file_rows),
        "rows": sum(row["rows"] for row in file_rows),
    }
    atomic_write_json(control / "BUILD_COMPLETE", complete)
    print(json.dumps(complete, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight", help="read-only full source preflight")
    preflight.add_argument("--qdh-root", required=True)
    preflight.add_argument("--ch-url", required=True)
    preflight.add_argument("--workers", type=int, choices=range(1, 9), default=4)
    preflight.add_argument("--symbols", help="case-sensitive comma-separated filter")
    preflight.add_argument("--timeframes", help="comma-separated filter")
    preflight.set_defaults(func=command_preflight)

    build = subparsers.add_parser("build", help="build isolated staging features")
    build.add_argument("--qdh-root", required=True)
    build.add_argument("--run-root", required=True)
    build.add_argument("--ch-url", required=True)
    build.add_argument("--workers", type=int, choices=range(1, 5), default=1)
    build.add_argument("--symbols", help="case-sensitive comma-separated filter")
    build.add_argument("--timeframes", help="comma-separated filter")
    build.add_argument("--resume", action="store_true")
    build.set_defaults(func=command_build)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        require_exact_runtime()
        return int(args.func(args))
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
