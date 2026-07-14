"""Fail-closed validation and READY sealing for a 466-column candidate."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from skill_paths import activate_import_paths, source_hashes

activate_import_paths()
import wh6_common as common  # noqa: E402
from feature_build import exclusive_run_lock, require, require_market_profile, scope_counts, warmup_row  # noqa: E402
from feature_runtime import (  # noqa: E402
    BASE_COLUMNS,
    COLUMN_ORDER_SHA256,
    FEATURE_COLUMNS,
    OUTPUT_COLUMNS,
    compute_all,
    selftest as runtime_selftest,
)


def load_run(qdh_root: str, run_root: str) -> tuple[Path, Path, dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    qdh, run = common.ensure_qdh_run_roots(qdh_root, run_root, require_run=True)
    control = run / "control"
    for name in ("manifest.json", "market_before.json", "market_after.json", "warmup_before.json", "warmup_after.json", "files.jsonl", "build_complete.json"):
        require((control / name).is_file(), f"run evidence missing: {name}")
    manifest = common.read_json(control / "manifest.json")
    build = common.read_json(control / "build_complete.json")
    files = common.read_jsonl(control / "files.jsonl")
    selected = manifest["selected_scope"]["sequences"]
    require_market_profile(common.read_json(control / "market_before.json"))
    expected = scope_counts(selected)
    require(build["status"] in ("BUILD_COMPLETE_NOT_VALIDATED", "VALIDATED"), "build is incomplete")
    require(manifest["run_id"] == run.name, "run id mismatch")
    require(manifest["qdh_root"] == str(qdh) and manifest["run_root"] == str(run), "run root identity mismatch")
    require(manifest["columns"]["names"] == list(OUTPUT_COLUMNS), "manifest column order mismatch")
    require(manifest["columns"]["order_sha256"] == COLUMN_ORDER_SHA256, "manifest column hash mismatch")
    require(build["files_sha256"] == common.sha256_file(control / "files.jsonl"), "files manifest changed")
    require(len(files) == build["partitions"] == expected["partitions"], "partition count mismatch")
    require(sum(row["rows"] for row in files) == build["rows"] == expected["rows"], "row count mismatch")
    current_sources = source_hashes()
    require(current_sources == manifest["sources"]["files"], "orchestration or formula source changed")
    require(common.canonical_json_sha256(current_sources) == build["source_semantic_sha256"], "source semantic hash changed")
    runtime_selftest()
    return qdh, run, manifest, build, files


def partition_scan(payload: dict[str, Any]) -> dict[str, Any]:
    qdh = Path(payload["qdh"])
    stage = Path(payload["stage"])
    row = payload["row"]
    feature_path = stage / row["relative_path"]
    market_path = qdh / "market" / row["relative_path"]
    require(feature_path.is_file() and market_path.is_file(), f"paired file missing: {row['relative_path']}")
    require(feature_path.stat().st_size == row["bytes"], f"stage size mismatch: {row['relative_path']}")
    require(common.sha256_file(feature_path) == row["feature_sha256"], f"stage hash mismatch: {row['relative_path']}")
    require(common.sha256_file(market_path) == row["market_sha256"], f"market hash mismatch: {row['relative_path']}")
    feature = pq.ParquetFile(feature_path)
    market = pq.ParquetFile(market_path)
    require(feature.schema_arrow.names == list(OUTPUT_COLUMNS), f"schema order mismatch: {row['relative_path']}")
    require(feature.schema_arrow.metadata is not None and b"pandas" in feature.schema_arrow.metadata, f"pandas metadata missing: {row['relative_path']}")
    require(feature.metadata.num_rows == market.metadata.num_rows == row["rows"], f"row mismatch: {row['relative_path']}")
    require(feature.schema_arrow.field("trade_time").type == market.schema_arrow.field("trade_time").type, f"trade_time type mismatch: {row['relative_path']}")
    for name in FEATURE_COLUMNS:
        require(feature.schema_arrow.field(name).type == pa.float64(), f"dtype mismatch: {row['relative_path']}/{name}")
    feature_time = feature.read(columns=["trade_time"])["trade_time"].combine_chunks()
    market_time = market.read(columns=["trade_time"])["trade_time"].combine_chunks()
    require(feature_time.equals(market_time), f"trade_time values mismatch: {row['relative_path']}")
    if len(feature_time):
        units = {"s": 1_000_000_000, "ms": 1_000_000, "us": 1_000, "ns": 1}
        raw = np.asarray(pc.cast(feature_time, pa.int64()), dtype=np.int64)
        ns = raw * units[feature_time.type.unit]
        require(np.all(ns[1:] > ns[:-1]), f"trade_time not strict: {row['relative_path']}")
        require(int(ns[0]) >= pd.Timestamp(common.START_DATE, tz=common.TZ).value, f"pre-2020 output: {row['relative_path']}")
    nulls = 0
    values = feature.read(columns=list(FEATURE_COLUMNS)).combine_chunks()
    for name in FEATURE_COLUMNS:
        column = values[name].combine_chunks()
        nulls += column.null_count
        valid = pc.fill_null(column, 0.0).to_numpy(zero_copy_only=False)
        require(np.isfinite(valid).all(), f"Inf/non-finite valid value: {row['relative_path']}/{name}")
    return {"relative_path": row["relative_path"], "rows": row["rows"], "nulls": nulls}


def structure_validation(qdh: Path, run: Path, files: list[dict[str, Any]], workers: int) -> dict[str, Any]:
    stage = run / "stage" / "features"
    expected = {row["relative_path"] for row in files}
    actual = {path.relative_to(stage).as_posix() for path in stage.rglob("*") if path.is_file()}
    require(actual == expected, "stage path set differs from files manifest")
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 8))) as pool:
        futures = [pool.submit(partition_scan, {"qdh": str(qdh), "stage": str(stage), "row": row}) for row in files]
        for future in as_completed(futures):
            results.append(future.result())
    return {
        "status": "PASS", "mode": "structure", "validated_at_utc": common.now_utc(),
        "partitions": len(results), "rows": sum(row["rows"] for row in results),
        "columns": len(OUTPUT_COLUMNS), "null_values": sum(row["nulls"] for row in results),
        "infinite_values": 0, "pre_2020_rows": 0, "strict_trade_time": True,
        "column_order_sha256": COLUMN_ORDER_SHA256,
    }


def compare_values(actual: pa.Array | pa.ChunkedArray, expected: np.ndarray, label: str) -> tuple[int, int]:
    if isinstance(actual, pa.ChunkedArray):
        actual = actual.combine_chunks()
    expected = np.asarray(expected, dtype=np.float64)
    actual_null = pc.is_null(actual).to_numpy(zero_copy_only=False)
    expected_null = np.isnan(expected)
    require(np.array_equal(actual_null, expected_null), f"null-mask mismatch: {label}")
    mask = ~actual_null
    actual_values = pc.fill_null(actual, 0.0).to_numpy(zero_copy_only=False)
    require(np.isfinite(actual_values[mask]).all(), f"non-finite valid value: {label}")
    require(np.array_equal(actual_values[mask].view(np.uint64), expected[mask].view(np.uint64)), f"float64 bit mismatch: {label}")
    return int(mask.sum()), int(actual_null.sum())


def validate_sequence(payload: dict[str, Any]) -> dict[str, Any]:
    qdh = Path(payload["qdh"])
    stage = Path(payload["stage"])
    sequence = payload["sequence"]
    symbol, timeframe = sequence["symbol"], sequence["timeframe"]
    loaded = common.load_market_sequence(qdh, symbol, timeframe)
    warmup = common.load_warmup_sequence(payload["ch_url"], sequence["contract_code"], timeframe)
    expected_warm = warmup_row(payload["warmup_snapshot"], symbol, timeframe)
    require(warmup.num_rows == expected_warm["rows"], f"warmup drift: {symbol}/{timeframe}")
    frame = pd.concat([
        warmup.select(list(BASE_COLUMNS)).to_pandas(),
        loaded["table"].select(list(BASE_COLUMNS)).to_pandas(),
    ], ignore_index=True)
    expected = compute_all(frame).iloc[warmup.num_rows:].reset_index(drop=True)
    non_null = nulls = offset = 0
    for market_part, part in zip(loaded["tables"], loaded["partitions"], strict=True):
        rows = market_part.num_rows
        table = pq.read_table(stage / part["relative_path"], columns=list(FEATURE_COLUMNS)).combine_chunks()
        expected_part = expected.iloc[offset:offset + rows]
        for name in FEATURE_COLUMNS:
            good, missing = compare_values(table[name], expected_part[name].to_numpy(dtype=np.float64, copy=False), f"{symbol}/{timeframe}/{part['year']}/{name}")
            non_null += good
            nulls += missing
        offset += rows
    require(offset == loaded["table"].num_rows, f"validation slice mismatch: {symbol}/{timeframe}")
    return {"symbol": symbol, "timeframe": timeframe, "rows": offset, "partitions": len(loaded["partitions"]), "warmup_rows": warmup.num_rows, "non_null_values": non_null, "null_values": nulls}


def full_validation(qdh: Path, run: Path, manifest: dict[str, Any], structure: dict[str, Any], ch_url: str, workers: int) -> dict[str, Any]:
    control = run / "control"
    market_before = common.read_json(control / "market_before.json")
    warmup_before = common.read_json(control / "warmup_before.json")
    selected = manifest["selected_scope"]["sequences"]
    market_now = common.market_snapshot(qdh, workers=workers)
    require_market_profile(market_now)
    warmup_now = common.warmup_snapshot(ch_url, selected)
    require(market_now["semantic_sha256"] == market_before["semantic_sha256"], "market changed since build")
    require(warmup_now["semantic_sha256"] == warmup_before["semantic_sha256"], "warmup changed since build")
    payloads = [{"qdh": str(qdh), "stage": str(run / "stage" / "features"), "sequence": row, "warmup_snapshot": warmup_before, "ch_url": ch_url} for row in selected]
    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(validate_sequence, payload): payload["sequence"] for payload in payloads}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(json.dumps({"status": "SEQUENCE_VALIDATED", "symbol": result["symbol"], "timeframe": result["timeframe"], "completed": len(results), "total": len(payloads)}, ensure_ascii=False), flush=True)
    results.sort(key=lambda row: (row["symbol"], common.TIMEFRAMES.index(row["timeframe"])))
    require(len(results) == len(selected), "full validation sequence count mismatch")
    common.write_jsonl(control / "validation_sequences.jsonl", results)
    files = common.read_jsonl(control / "files.jsonl")
    return {
        "status": "PASS", "mode": "full", "validated_at_utc": common.now_utc(), "run_id": run.name,
        "publishable_full_scope": manifest["publishable_full_scope"],
        "sequences": len(results), "partitions": structure["partitions"], "rows": sum(row["rows"] for row in results),
        "columns": len(OUTPUT_COLUMNS), "feature_columns": len(FEATURE_COLUMNS), "column_order_sha256": COLUMN_ORDER_SHA256,
        "market_semantic_sha256": market_now["semantic_sha256"], "warmup_semantic_sha256": warmup_now["semantic_sha256"],
        "source_semantic_sha256": common.canonical_json_sha256(source_hashes()),
        "run_manifest_sha256": common.sha256_file(control / "manifest.json"), "build_complete_sha256": common.sha256_file(control / "build_complete.json"),
        "files_sha256": common.sha256_file(control / "files.jsonl"), "stage_tree_semantic_sha256": common.canonical_json_sha256(files),
        "structure_report_sha256": common.sha256_file(control / "validation_structure.json"),
        "sequence_results_sha256": common.sha256_file(control / "validation_sequences.jsonl"),
        "recomputed_values": sum(row["non_null_values"] + row["null_values"] for row in results),
        "non_null_values": sum(row["non_null_values"] for row in results), "null_values": sum(row["null_values"] for row in results),
        "infinite_values": 0, "pre_2020_rows": 0, "bitwise_recompute_match": True,
    }


def command_validate(args: argparse.Namespace) -> int:
    _, run = common.ensure_qdh_run_roots(args.qdh_root, args.run_root, require_run=True)
    with exclusive_run_lock(run):
        qdh, run, manifest, build, files = load_run(args.qdh_root, args.run_root)
        require(not (run / "control" / "READY").exists(), "READY run is immutable")
        structure = structure_validation(qdh, run, files, args.workers)
        common.atomic_write_json(run / "control" / "validation_structure.json", structure)
        report = structure
        if args.mode == "full":
            report = full_validation(qdh, run, manifest, structure, args.ch_url, args.workers)
            common.atomic_write_json(run / "control" / "validation_full.json", report)
            build["status"] = "VALIDATED"
            common.atomic_write_json(run / "control" / "build_complete.json", build)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def validate_full_evidence(control: Path, run: Path, manifest: dict[str, Any], build: dict[str, Any], full: dict[str, Any]) -> None:
    selected_counts = scope_counts(manifest["selected_scope"]["sequences"])
    require(full["status"] == "PASS" and full["mode"] == "full", "full validation did not PASS")
    require(full["run_id"] == run.name, "validation run mismatch")
    require(full["sequences"] == selected_counts["sequences"] and full["partitions"] == selected_counts["partitions"] and full["rows"] == selected_counts["rows"], "validation scope mismatch")
    require(full["column_order_sha256"] == COLUMN_ORDER_SHA256 and full["bitwise_recompute_match"] is True, "value validation contract mismatch")
    require(full["run_manifest_sha256"] == common.sha256_file(control / "manifest.json"), "manifest changed since validation")
    require(full["files_sha256"] == common.sha256_file(control / "files.jsonl"), "files changed since validation")
    require(full["stage_tree_semantic_sha256"] == build["stage_tree_semantic_sha256"], "stage tree identity mismatch")
    require(full["source_semantic_sha256"] == common.canonical_json_sha256(source_hashes()), "source changed since validation")


def command_finalize(args: argparse.Namespace) -> int:
    _, run = common.ensure_qdh_run_roots(args.qdh_root, args.run_root, require_run=True)
    with exclusive_run_lock(run):
        qdh, run, manifest, build, files = load_run(args.qdh_root, args.run_root)
        ready_path = run / "control" / "READY"
        require(not ready_path.exists(), "READY already exists")
        require(manifest["publishable_full_scope"] is True, "filtered pilot cannot be finalized or published")
        full_path = run / "control" / "validation_full.json"
        require(full_path.is_file(), "full validation evidence missing")
        full = common.read_json(full_path)
        validate_full_evidence(run / "control", run, manifest, build, full)
        market = common.market_snapshot(qdh, workers=args.workers)
        require_market_profile(market)
        warmup = common.warmup_snapshot(args.ch_url, manifest["selected_scope"]["sequences"])
        require(market["semantic_sha256"] == build["market_semantic_sha256"], "market drift before READY")
        require(warmup["semantic_sha256"] == build["warmup_semantic_sha256"], "warmup drift before READY")
        final_structure = structure_validation(qdh, run, files, args.workers)
        common.atomic_write_json(run / "control" / "validation_final_structure.json", final_structure)
        ready = {
            "schema_version": 1, "status": "READY", "sealed_at_utc": common.now_utc(), "run_id": run.name,
            "release_mode": "features-only", "meta_policy": "unchanged",
            "qdh_root": str(qdh), "stage_root": str(run / "stage" / "features"),
            "scope": manifest["global_scope"], "columns": manifest["columns"],
            "market_semantic_sha256": market["semantic_sha256"], "warmup_semantic_sha256": warmup["semantic_sha256"],
            "source_semantic_sha256": common.canonical_json_sha256(source_hashes()),
            "source_files": source_hashes(),
            "manifest_sha256": common.sha256_file(run / "control" / "manifest.json"),
            "build_complete_sha256": common.sha256_file(run / "control" / "build_complete.json"),
            "files_sha256": common.sha256_file(run / "control" / "files.jsonl"),
            "files": files,
            "stage_tree_semantic_sha256": common.canonical_json_sha256(files),
            "validation_full_sha256": common.sha256_file(full_path),
            "validation_final_structure_sha256": common.sha256_file(run / "control" / "validation_final_structure.json"),
            "bitwise_recompute_match": True,
        }
        common.atomic_write_json(ready_path, ready)
        result = {"status": "READY", "run_id": run.name, "ready_sha256": common.sha256_file(ready_path), "partitions": len(files), "rows": sum(row["rows"] for row in files), "columns": len(OUTPUT_COLUMNS)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--qdh-root", required=True); validate.add_argument("--run-root", required=True); validate.add_argument("--ch-url", required=True)
    validate.add_argument("--mode", choices=("structure", "full"), default="structure"); validate.add_argument("--workers", type=int, default=4)
    finalize = sub.add_parser("finalize")
    finalize.add_argument("--qdh-root", required=True); finalize.add_argument("--run-root", required=True); finalize.add_argument("--ch-url", required=True); finalize.add_argument("--workers", type=int, default=4)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return command_validate(args) if args.command == "validate" else command_finalize(args)


if __name__ == "__main__":
    raise SystemExit(main())
