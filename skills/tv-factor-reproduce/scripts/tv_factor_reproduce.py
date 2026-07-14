#!/usr/bin/env python3
"""Safe CLI for the locked 142-column TV factor core.

The default selftest is read-only.  The compute command writes only when an
absolute, non-existing output path outside a detected qdh root is supplied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import factor_tv  # noqa: E402


SKILL_ROOT = HERE.parent
CONTRACT_PATH = SKILL_ROOT / "references" / "tv-locked-142-contract.json"
CORE_LOCK_PATH = SKILL_ROOT / "references" / "tv-core-lock.json"
CORE_PATH = HERE / "factor_tv.py"
OUTPUT_COLUMNS = ("trade_time", *factor_tv.COLUMN_ORDER)
REQUIRED_RUNTIME = {
    "python": "3.10.20",
    "numpy": "2.2.6",
    "pandas": "2.3.3",
    "pyarrow": "23.0.1",
}


class ReproduceError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReproduceError(message)


def verify_runtime() -> dict[str, str]:
    actual = {
        "python": ".".join(str(part) for part in sys.version_info[:3]),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "pyarrow": pa.__version__,
    }
    require(
        actual == REQUIRED_RUNTIME,
        f"runtime mismatch: required={REQUIRED_RUNTIME}, actual={actual}",
    )
    return actual


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strict_json(path: Path) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReproduceError(f"duplicate JSON key {key!r}: {path}")
            result[key] = value
        return result

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=reject_duplicates)


def verify_locked_core() -> dict[str, Any]:
    contract = strict_json(CONTRACT_PATH)
    lock = strict_json(CORE_LOCK_PATH)
    require(lock.get("required_runtime") == REQUIRED_RUNTIME, "TV runtime contract drift")
    runtime = verify_runtime()
    core_sha = sha256_file(CORE_PATH)
    contract_sha = sha256_file(CONTRACT_PATH)
    require(lock["status"] == "LOCKED", "TV core is not locked")
    require(lock["core_file"] == "scripts/factor_tv.py", "TV core path drift")
    require(
        lock["contract_file"] == "references/tv-locked-142-contract.json",
        "TV contract path drift",
    )
    require(core_sha == lock["core_sha256"], f"TV core SHA drift: {core_sha}")
    require(contract_sha == lock["contract_sha256"], f"TV contract SHA drift: {contract_sha}")
    require(contract.get("column_count") == 142, "locked contract count is not 142")
    require(tuple(contract.get("columns", ())) == factor_tv.COLUMN_ORDER, "locked column order drift")
    encoded = json.dumps(factor_tv.COLUMN_ORDER, ensure_ascii=False).encode("utf-8")
    column_sha = hashlib.sha256(encoded).hexdigest()
    require(column_sha == lock["column_order_sha256"], f"column-order SHA drift: {column_sha}")
    return {
        "status": lock["status"],
        "core_sha256": core_sha,
        "contract_sha256": contract_sha,
        "column_count": len(factor_tv.COLUMN_ORDER),
        "column_order_sha256": column_sha,
        "runtime": runtime,
    }


def _detected_qdh_root(path: Path) -> Path | None:
    current = path.parent
    while True:
        if (current / "market").is_dir() and (current / "meta" / "features_snapshot.json").is_file():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    configured = os.environ.get("QUANT_DATA_ROOT")
    if configured:
        configured_root = Path(configured).resolve(strict=False)
        try:
            path.relative_to(configured_root)
            return configured_root
        except ValueError:
            pass
    return None


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def assert_output_safe(
    input_path: Path,
    output_path: Path,
    protected_qdh_root: Path,
) -> tuple[Path, Path]:
    require(input_path.is_absolute(), "input path must be absolute")
    require(output_path.is_absolute(), "output path must be absolute")
    require(protected_qdh_root.is_absolute(), "qdh root must be absolute")
    source = input_path.resolve(strict=True)
    destination = output_path.resolve(strict=False)
    protected = protected_qdh_root.resolve(strict=False)
    require(source.is_file(), f"input parquet is missing: {source}")
    require(source != destination, "input and output paths must differ")
    require(destination.suffix.lower() == ".parquet", "output must end in .parquet")
    require(not destination.exists(), f"output already exists; overwrite is forbidden: {destination}")
    require(
        destination.parent.is_dir(),
        f"output parent must already exist; create the staging directory explicitly: {destination.parent}",
    )
    require(
        not _is_within(destination, protected),
        f"direct qdh writes are forbidden: {destination} is below protected root {protected}",
    )
    skill_root = SKILL_ROOT.resolve(strict=True)
    require(
        not _is_within(destination, skill_root),
        f"skill bundle is read-only: {destination} is below {skill_root}",
    )
    qdh_root = _detected_qdh_root(destination)
    require(qdh_root is None, f"direct qdh writes are forbidden: {destination} is below {qdh_root}")
    return source, destination


def _normalize_boundary(value: str | pd.Timestamp, times: pd.DatetimeIndex) -> pd.Timestamp:
    boundary = pd.Timestamp(value)
    if times.tz is None:
        require(boundary.tzinfo is None, "timezone-aware live-start cannot be used with naive trade_time")
    elif boundary.tzinfo is None:
        boundary = boundary.tz_localize(times.tz)
    else:
        boundary = boundary.tz_convert(times.tz)
    return boundary


def validate_continuous_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    required = ["trade_time", *factor_tv.BASE_COLUMNS]
    missing = [name for name in required if name not in frame.columns]
    require(not missing, f"input is missing required columns: {missing}")
    require(not frame.columns.duplicated().any(), "input contains duplicate column names")
    require(len(frame) > 1, "input must contain warmup and live rows")

    times = pd.DatetimeIndex(pd.to_datetime(frame["trade_time"], errors="raise"))
    require(not times.hasnans, "trade_time contains null")
    raw_times = times.asi8
    require(bool(np.all(raw_times[1:] > raw_times[:-1])), "trade_time must be strictly increasing and unique")

    normalized = frame.loc[:, list(factor_tv.BASE_COLUMNS)].copy()
    for name in factor_tv.BASE_COLUMNS:
        values = pd.to_numeric(normalized[name], errors="coerce").to_numpy(dtype=np.float64)
        require(bool(np.isfinite(values).all()), f"{name} contains null or non-finite values")
        normalized[name] = values
    return normalized, times


def compute_live_output(
    frame: pd.DataFrame,
    live_start: str | pd.Timestamp,
    *,
    allow_cold_start: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Compute once on full history, then return the live suffix."""

    normalized, times = validate_continuous_frame(frame)
    boundary = _normalize_boundary(live_start, times)
    # Keep the comparison inside pandas so the boundary and DatetimeIndex use
    # the same internal resolution.  Pandas 3 may store the index in
    # microseconds while Timestamp.value remains nanoseconds.
    live_index = int(times.searchsorted(boundary, side="left"))
    require(
        live_index > 0 or allow_cold_start,
        "live-start leaves no warmup rows; pass --allow-cold-start only after confirming ClickHouse has no earlier rows",
    )
    require(live_index < len(frame), "live-start leaves no live rows")

    factors = factor_tv.compute(normalized)
    live = factors.iloc[live_index:].reset_index(drop=True)
    live.insert(0, "trade_time", pd.Series(times[live_index:]).reset_index(drop=True))
    require(tuple(live.columns) == OUTPUT_COLUMNS, "live output order drifted")
    require(all(dtype == np.dtype("float64") for dtype in live.iloc[:, 1:].dtypes), "factor dtype drifted")
    values = live.iloc[:, 1:].to_numpy(dtype=np.float64, copy=False)
    require(not np.isinf(values).any(), "live output contains Inf")
    require(not np.signbit(values[values == 0.0]).any(), "live output contains negative zero")
    metadata = {
        "input_rows": len(frame),
        "warmup_rows": live_index,
        "live_rows": len(live),
        "cold_start": live_index == 0,
        "allow_cold_start": bool(allow_cold_start),
        "requested_live_start": boundary.isoformat(),
        "first_live_trade_time": times[live_index].isoformat(),
        "last_live_trade_time": times[-1].isoformat(),
    }
    return live, metadata


def read_sequence(path: Path) -> tuple[pd.DataFrame, pa.DataType, dict[str, Any]]:
    parquet = pq.ParquetFile(path)
    names = parquet.schema_arrow.names
    require(len(names) == len(set(names)), "input parquet schema contains duplicate names")
    required = ["trade_time", *factor_tv.BASE_COLUMNS]
    missing = [name for name in required if name not in names]
    require(not missing, f"input parquet is missing columns: {missing}")
    trade_type = parquet.schema_arrow.field("trade_time").type
    require(pa.types.is_timestamp(trade_type), f"trade_time must be Arrow timestamp, got {trade_type}")

    identity_columns = [name for name in ("symbol", "timeframe", "period", "contract_code") if name in names]
    table = parquet.read(columns=[*required, *identity_columns]).combine_chunks()
    frame = table.select(required).to_pandas()
    identity: dict[str, Any] = {}
    for name in identity_columns:
        values = table[name].to_pylist()
        unique = {value for value in values}
        require(None not in unique and len(unique) == 1, f"{name} must identify exactly one continuous sequence")
        identity[name] = next(iter(unique))
    return frame, trade_type, identity


def write_candidate(
    input_path: Path,
    output_path: Path,
    live_start: str,
    *,
    protected_qdh_root: Path,
    allow_cold_start: bool = False,
) -> dict[str, Any]:
    source, destination = assert_output_safe(input_path, output_path, protected_qdh_root)
    lock = verify_locked_core()
    frame, trade_type, identity = read_sequence(source)
    live, slice_metadata = compute_live_output(
        frame,
        live_start,
        allow_cold_start=allow_cold_start,
    )
    table = pa.Table.from_pandas(live, preserve_index=False)
    if table.schema.field("trade_time").type != trade_type:
        table = table.set_column(0, "trade_time", pc.cast(table["trade_time"], trade_type))
    require(table.schema.names == list(OUTPUT_COLUMNS), "Arrow output order drifted")
    require(table.schema.field("trade_time").type == trade_type, "trade_time Arrow type drifted")
    require(
        all(table.schema.field(name).type == pa.float64() for name in factor_tv.COLUMN_ORDER),
        "Arrow factor dtype drifted",
    )

    temporary = destination.parent / (
        f".{destination.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )
    require(not temporary.exists(), "temporary staging collision")
    try:
        pq.write_table(
            table,
            temporary,
            compression="snappy",
            version="2.6",
            use_dictionary=True,
            write_statistics=True,
            row_group_size=max(1, table.num_rows),
        )
        with temporary.open("r+b") as handle:
            os.fsync(handle.fileno())
        written = pq.ParquetFile(temporary)
        try:
            require(written.metadata.num_rows == table.num_rows, "written row count mismatch")
            require(written.schema_arrow.names == list(OUTPUT_COLUMNS), "written schema order mismatch")
        finally:
            written.close()
        try:
            os.link(temporary, destination)
        except FileExistsError as exc:
            raise ReproduceError("output appeared concurrently; refusing to overwrite") from exc
        except OSError as exc:
            raise ReproduceError(
                "atomic no-clobber publish failed; staging filesystem must support hard links"
            ) from exc
        temporary.unlink()
    finally:
        if temporary.exists():
            temporary.unlink()

    require(destination.is_file(), "published output is missing")

    return {
        "status": "STAGED",
        "input": str(source),
        "output": str(destination),
        "output_sha256": sha256_file(destination),
        **slice_metadata,
        "columns": len(OUTPUT_COLUMNS),
        "feature_columns": len(factor_tv.COLUMN_ORDER),
        "identity": identity,
        "protected_qdh_root": str(protected_qdh_root.resolve(strict=False)),
        **lock,
        "publishable_by_itself": False,
        "writer_boundary": "external trade_time+142 staging only; qdh 466-column unified writer required",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reproduce the locked 142 TV factors safely")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest", help="run read-only locked-core tests")
    compute = sub.add_parser("compute", help="write one external trade_time+142 staging parquet")
    compute.add_argument("--input", required=True, type=Path)
    compute.add_argument("--live-start", required=True)
    compute.add_argument("--output", required=True, type=Path)
    compute.add_argument(
        "--qdh-root",
        type=Path,
        required=True,
        help="protected qdh root; an explicit absolute path is required",
    )
    compute.add_argument(
        "--allow-cold-start",
        action="store_true",
        help="allow zero warmup rows only after upstream ClickHouse history was confirmed absent",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "selftest":
            from skill_selftest import run_selftest

            payload = run_selftest()
        else:
            payload = write_candidate(
                args.input,
                args.output,
                args.live_start,
                allow_cold_start=args.allow_cold_start,
                protected_qdh_root=args.qdh_root,
            )
    except Exception as exc:
        print(
            json.dumps(
                {"status": "FAIL", "error_type": type(exc).__name__, "error": str(exc)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
