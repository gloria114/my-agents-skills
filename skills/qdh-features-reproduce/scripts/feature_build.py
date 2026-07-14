"""Build a complete 466-column qdh features candidate outside qdh.

The builder is deliberately release-oriented: it computes every selected
symbol/timeframe as one continuous warmup+live sequence, slices off warmup,
and only then restores the market Hive partitions.  Filtered builds are useful
for pilots but are marked non-publishable.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import multiprocessing as mp
import msvcrt
import os
import platform
import shutil
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from skill_paths import activate_import_paths, source_hashes

activate_import_paths()
import wh6_common as common  # noqa: E402
from feature_runtime import (  # noqa: E402
    BASE_COLUMNS,
    COLUMN_ORDER_SHA256,
    FEATURE_COLUMNS,
    OUTPUT_COLUMNS,
    compute_all,
    selftest as runtime_selftest,
)


MIN_FULL_FREE_BYTES = 60 * 1024**3
MAX_TASKS_PER_CHILD = 8
PROFILE_SYMBOLS = (
    "AP", "CF", "CJ", "FG", "IC", "IM", "MA", "OI", "PF", "PK", "PR",
    "PX", "RM", "SA", "SF", "SH", "SM", "SR", "TA", "TL", "UR", "a",
    "ag", "al", "ao", "au", "b", "bc", "br", "bu", "c", "cs", "cu",
    "eb", "ec", "eg", "fu", "hc", "i", "j", "jd", "jm", "l", "lc",
    "lg", "lh", "lu", "m", "nr", "p", "pb", "pp", "ps", "rb", "ru",
    "sc", "si", "sn", "ss", "v", "y", "zn",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _pool_probe(value: int) -> int:
    return value * value


def worker_pool_selftest() -> dict[str, Any]:
    """Exercise the same spawn pool used by full builds."""

    context = mp.get_context("spawn")
    with context.Pool(processes=2, maxtasksperchild=2) as pool:
        observed = sorted(pool.imap_unordered(_pool_probe, range(6), chunksize=1))
    require(observed == [0, 1, 4, 9, 16, 25], "spawn worker-pool result drift")
    return {
        "status": "PASS",
        "start_method": context.get_start_method(),
        "maxtasksperchild": MAX_TASKS_PER_CHILD,
    }


def runtime_identity() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "pyarrow": pa.__version__,
    }


def require_market_profile(snapshot: dict[str, Any]) -> None:
    require(tuple(snapshot["symbols"]) == PROFILE_SYMBOLS, "market symbol set differs from locked JQ62 profile")
    require(tuple(snapshot["timeframes"]) == tuple(common.TIMEFRAMES), "market timeframe set differs from locked nine-timeframe profile")


def warmup_row(snapshot: dict[str, Any], symbol: str, timeframe: str) -> dict[str, Any]:
    rows = [
        row for row in snapshot["sequences"]
        if row["symbol"] == symbol and row["timeframe"] == timeframe
    ]
    require(len(rows) == 1, f"warmup identity mismatch: {symbol}/{timeframe}")
    return rows[0]


def scope_counts(rows: Sequence[dict[str, Any]]) -> dict[str, int]:
    return {
        "symbols": len({row["symbol"] for row in rows}),
        "timeframes": len({row["timeframe"] for row in rows}),
        "sequences": len(rows),
        "partitions": sum(int(row["partitions"]) for row in rows),
        "rows": sum(int(row["rows"]) for row in rows),
    }


def parse_csv(value: str | None) -> list[str] | None:
    if value is None:
        return None
    result = [item.strip() for item in value.split(",") if item.strip()]
    require(bool(result), "scope filter cannot be empty")
    require(len(result) == len(set(result)), "scope filter contains duplicates")
    return result


@contextlib.contextmanager
def exclusive_run_lock(run: Path):
    control = run / "control"
    control.mkdir(parents=True, exist_ok=True)
    path = control / "RUN_LOCK"
    path.touch(exist_ok=True)
    with path.open("r+b") as handle:
        if path.stat().st_size == 0:
            handle.write(b"0")
            handle.flush()
            os.fsync(handle.fileno())
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError(f"another process holds {path}") from exc
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def write_partition(table: pa.Table, destination: Path, stage: Path) -> None:
    stage_resolved = stage.resolve(strict=True)
    relative = destination.resolve(strict=False).relative_to(stage_resolved)
    require(
        len(relative.parts) == 4 and relative.name == "data.parquet",
        f"invalid stage path: {relative.as_posix()}",
    )
    common._reject_reparse_chain(destination.parent, "stage partition")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name("data.parquet.partial")
    if partial.exists():
        partial.unlink()
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
    os.replace(partial, destination)


def build_sequence(payload: dict[str, Any]) -> dict[str, Any]:
    qdh = Path(payload["qdh"])
    stage = Path(payload["stage"])
    sequence = payload["sequence"]
    symbol = sequence["symbol"]
    timeframe = sequence["timeframe"]
    loaded = common.load_market_sequence(qdh, symbol, timeframe)
    warmup = common.load_warmup_sequence(
        payload["ch_url"], sequence["contract_code"], timeframe
    )
    expected_warmup = warmup_row(payload["warmup_snapshot"], symbol, timeframe)
    require(warmup.num_rows == expected_warmup["rows"], f"warmup row drift: {symbol}/{timeframe}")
    warmup_data_sha256 = common.arrow_table_sha256(warmup)

    warm = warmup.select(list(BASE_COLUMNS)).to_pandas()
    live_base = loaded["table"].select(list(BASE_COLUMNS)).to_pandas()
    calculated = compute_all(pd.concat([warm, live_base], ignore_index=True))
    live = calculated.iloc[warmup.num_rows:].reset_index(drop=True)
    require(len(live) == loaded["table"].num_rows, f"row mismatch: {symbol}/{timeframe}")

    files: list[dict[str, Any]] = []
    offset = 0
    for market_table, part in zip(loaded["tables"], loaded["partitions"], strict=True):
        rows = market_table.num_rows
        frame = live.iloc[offset:offset + rows].reset_index(drop=True).copy()
        frame.insert(0, "trade_time", market_table["trade_time"].to_pandas())
        table = pa.Table.from_pandas(frame.loc[:, list(OUTPUT_COLUMNS)], preserve_index=False)
        require(table.schema.names == list(OUTPUT_COLUMNS), "output column order changed")
        require(
            table.schema.field("trade_time").type
            == market_table.schema.field("trade_time").type,
            f"trade_time type changed: {part['relative_path']}",
        )
        require(
            all(table.schema.field(name).type == pa.float64() for name in FEATURE_COLUMNS),
            f"feature dtype changed: {part['relative_path']}",
        )
        destination = stage / part["relative_path"]
        write_partition(table, destination, stage)
        files.append({
            "relative_path": part["relative_path"],
            "bytes": destination.stat().st_size,
            "rows": rows,
            "feature_sha256": common.sha256_file(destination),
            "market_sha256": part["market_file_sha256"],
        })
        offset += rows
    require(offset == loaded["table"].num_rows, f"partition slice mismatch: {symbol}/{timeframe}")
    return {
        "schema_version": 1,
        "status": "COMPLETE",
        "completed_at_utc": common.now_utc(),
        "run_id": payload["run_id"],
        "symbol": symbol,
        "contract_code": sequence["contract_code"],
        "timeframe": timeframe,
        "live_rows": offset,
        "warmup_rows": warmup.num_rows,
        "warmup_data_sha256": warmup_data_sha256,
        "market_semantic_sha256": payload["market_semantic_sha256"],
        "warmup_semantic_sha256": payload["warmup_semantic_sha256"],
        "source_semantic_sha256": payload["source_semantic_sha256"],
        "files": files,
    }


def record_path(run: Path, sequence: dict[str, Any]) -> Path:
    return run / "control" / "sequence_records" / f"{sequence['symbol']}__{sequence['timeframe']}.json"


def record_is_valid(
    record: dict[str, Any], sequence: dict[str, Any], run: Path,
    qdh: Path, manifest: dict[str, Any], warmup_sha: str,
) -> bool:
    try:
        require(record["status"] == "COMPLETE", "record status")
        require(record["run_id"] == run.name, "record run")
        require(record["symbol"] == sequence["symbol"], "record symbol")
        require(record["timeframe"] == sequence["timeframe"], "record timeframe")
        require(record["warmup_data_sha256"] == warmup_sha, "record warmup")
        require(record["market_semantic_sha256"] == manifest["sources"]["market_semantic_sha256"], "record market")
        require(record["warmup_semantic_sha256"] == manifest["sources"]["warmup_semantic_sha256"], "record warmup snapshot")
        require(record["source_semantic_sha256"] == manifest["sources"]["source_semantic_sha256"], "record source")
        require([row["relative_path"] for row in record["files"]] == sequence["partition_paths"], "record paths")
        for row in record["files"]:
            feature = run / "stage" / "features" / row["relative_path"]
            market = qdh / "market" / row["relative_path"]
            require(feature.is_file() and feature.stat().st_size == row["bytes"], "record file")
            require(common.sha256_file(feature) == row["feature_sha256"], "record feature hash")
            require(common.sha256_file(market) == row["market_sha256"], "record market hash")
        return True
    except (KeyError, RuntimeError, OSError):
        return False


def preflight(qdh_root: str, ch_url: str, workers: int = 4) -> dict[str, Any]:
    qdh = Path(qdh_root).resolve(strict=True)
    require((qdh / "market").is_dir(), f"market missing: {qdh / 'market'}")
    runtime = runtime_selftest()
    sources = source_hashes()
    market = common.market_snapshot(qdh, workers=workers)
    require_market_profile(market)
    warmup = common.warmup_snapshot(ch_url, market["sequences"])
    return {
        "status": "PASS",
        "mode": "preflight",
        "write_count": 0,
        "qdh_root": str(qdh),
        "ch_endpoint": common.redact_ch_url(ch_url),
        "runtime": runtime,
        "source_semantic_sha256": common.canonical_json_sha256(sources),
        "market": {"semantic_sha256": market["semantic_sha256"], "counts": market["counts"], "cutoff_trade_date": market["cutoff_trade_date"]},
        "warmup": {"semantic_sha256": warmup["semantic_sha256"], "counts": warmup["counts"]},
    }


def command_build(args: argparse.Namespace) -> int:
    qdh, run = common.ensure_qdh_run_roots(args.qdh_root, args.run_root, require_run=args.resume)
    if not args.resume:
        require(not run.exists(), f"new run root already exists: {run}")
        run.mkdir(parents=True)
    with exclusive_run_lock(run):
        require(not (run / "control" / "READY").exists(), "READY run is immutable")
        runtime_selftest()
        sources = source_hashes()
        source_semantic = common.canonical_json_sha256(sources)
        control = run / "control"
        stage = run / "stage" / "features"
        records = control / "sequence_records"
        stage.mkdir(parents=True, exist_ok=True)
        records.mkdir(parents=True, exist_ok=True)

        manifest_path = control / "manifest.json"
        if args.resume:
            require(manifest_path.is_file(), "resume manifest missing")
            manifest = common.read_json(manifest_path)
            market_before = common.read_json(control / "market_before.json")
            require_market_profile(market_before)
            warmup_before = common.read_json(control / "warmup_before.json")
            require(manifest["qdh_root"] == str(qdh), "resume qdh mismatch")
            require(manifest["sources"]["source_semantic_sha256"] == source_semantic, "source changed since build")
            require(manifest["ch_url_sha256"] == common.canonical_json_sha256({"url": common.normalize_ch_url(args.ch_url)}), "CH endpoint changed")
            selected = manifest["selected_scope"]["sequences"]
        else:
            market_before = common.market_snapshot(qdh, workers=args.workers)
            require_market_profile(market_before)
            selected = common.select_sequences(
                market_before,
                parse_csv(args.symbols),
                parse_csv(args.timeframes),
            )
            warmup_before = common.warmup_snapshot(args.ch_url, selected)
            full_keys = {(row["symbol"], row["timeframe"]) for row in market_before["sequences"]}
            selected_keys = {(row["symbol"], row["timeframe"]) for row in selected}
            full_scope = selected_keys == full_keys
            if full_scope:
                require(shutil.disk_usage(run).free >= MIN_FULL_FREE_BYTES, "less than 60 GiB free for full build")
            manifest = {
                "schema_version": 1,
                "status": "BUILDING",
                "created_at_utc": common.now_utc(),
                "run_id": run.name,
                "qdh_root": str(qdh),
                "run_root": str(run),
                "ch_endpoint": common.redact_ch_url(args.ch_url),
                "ch_url_sha256": common.canonical_json_sha256({"url": common.normalize_ch_url(args.ch_url)}),
                "publishable_full_scope": full_scope,
                "global_scope": {"counts": market_before["counts"], "symbols": market_before["symbols"], "timeframes": market_before["timeframes"]},
                "selected_scope": {"counts": scope_counts(selected), "sequences": selected},
                "columns": {"count": len(OUTPUT_COLUMNS), "feature_count": len(FEATURE_COLUMNS), "names": list(OUTPUT_COLUMNS), "order_sha256": COLUMN_ORDER_SHA256},
                "sources": {"files": sources, "source_semantic_sha256": source_semantic, "market_semantic_sha256": market_before["semantic_sha256"], "warmup_semantic_sha256": warmup_before["semantic_sha256"]},
                "runtime": runtime_identity(),
            }
            common.atomic_write_json(control / "market_before.json", market_before)
            common.atomic_write_json(control / "warmup_before.json", warmup_before)
            common.atomic_write_json(manifest_path, manifest)

        pending: list[dict[str, Any]] = []
        complete: list[dict[str, Any]] = []
        for sequence in selected:
            path = record_path(run, sequence)
            if path.is_file():
                warmup = common.load_warmup_sequence(
                    args.ch_url, sequence["contract_code"], sequence["timeframe"]
                )
                expected = warmup_row(
                    warmup_before, sequence["symbol"], sequence["timeframe"]
                )
                require(
                    warmup.num_rows == expected["rows"],
                    f"warmup drift: {sequence['symbol']}/{sequence['timeframe']}",
                )
                warmup_sha = common.arrow_table_sha256(warmup)
                record = common.read_json(path)
                if record_is_valid(record, sequence, run, qdh, manifest, warmup_sha):
                    complete.append(record)
                    continue
            pending.append({
                "qdh": str(qdh), "stage": str(stage), "run_id": run.name,
                "ch_url": args.ch_url, "sequence": sequence,
                "warmup_snapshot": warmup_before,
                "market_semantic_sha256": market_before["semantic_sha256"],
                "warmup_semantic_sha256": warmup_before["semantic_sha256"],
                "source_semantic_sha256": source_semantic,
            })

        if pending:
            context = mp.get_context("spawn")
            with context.Pool(
                processes=max(1, args.workers),
                maxtasksperchild=MAX_TASKS_PER_CHILD,
            ) as pool:
                for record in pool.imap_unordered(build_sequence, pending, chunksize=1):
                    common.atomic_write_json(record_path(run, record), record)
                    complete.append(record)
                    print(json.dumps({"status": "SEQUENCE_BUILT", "symbol": record["symbol"], "timeframe": record["timeframe"], "completed": len(complete), "total": len(selected)}, ensure_ascii=False), flush=True)

        complete.sort(key=lambda row: (row["symbol"], common.TIMEFRAMES.index(row["timeframe"])))
        require(len(complete) == len(selected), "not all selected sequences completed")
        files = [file for record in complete for file in record["files"]]
        files.sort(key=lambda row: row["relative_path"])
        common.write_jsonl(control / "files.jsonl", files)
        market_after = common.market_snapshot(qdh, workers=args.workers)
        require_market_profile(market_after)
        warmup_after = common.warmup_snapshot(args.ch_url, selected)
        require(market_after["semantic_sha256"] == market_before["semantic_sha256"], "market changed during build")
        require(warmup_after["semantic_sha256"] == warmup_before["semantic_sha256"], "warmup changed during build")
        require(source_hashes() == sources, "source changed during build")
        common.atomic_write_json(control / "market_after.json", market_after)
        common.atomic_write_json(control / "warmup_after.json", warmup_after)
        build = {
            "schema_version": 1, "status": "BUILD_COMPLETE_NOT_VALIDATED",
            "completed_at_utc": common.now_utc(), "run_id": run.name,
            "publishable_full_scope": manifest["publishable_full_scope"],
            "sequences": len(complete), "partitions": len(files),
            "rows": sum(row["rows"] for row in files), "columns": len(OUTPUT_COLUMNS),
            "column_order_sha256": COLUMN_ORDER_SHA256,
            "files_sha256": common.sha256_file(control / "files.jsonl"),
            "stage_tree_semantic_sha256": common.canonical_json_sha256(files),
            "market_semantic_sha256": market_before["semantic_sha256"],
            "warmup_semantic_sha256": warmup_before["semantic_sha256"],
            "source_semantic_sha256": source_semantic,
        }
        common.atomic_write_json(control / "build_complete.json", build)
        manifest["status"] = "BUILD_COMPLETE_NOT_VALIDATED"
        common.atomic_write_json(manifest_path, manifest)
        print(json.dumps(build, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qdh-root", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--ch-url", required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--symbols")
    parser.add_argument("--timeframes")
    parser.add_argument("--resume", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    return command_build(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
