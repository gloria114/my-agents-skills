#!/usr/bin/env python3
"""Verify and reproduce the locked Excel 66 family into external staging.

The default ``selftest`` command is read-only.  ``compute`` accepts exactly one
complete sequence with every available warmup row, or an explicitly authorized
cold start when CH preflight found none, and writes one new Parquet only below
an external staging root.  It never assembles or publishes qdh features.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq


HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
REFERENCES = SKILL_ROOT / "references"
CORE_PATH = HERE / "factor_excel.py"
LOCK_PATH = REFERENCES / "core-lock.json"

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import factor_excel  # noqa: E402


LOCKED_CORE_SHA256 = "6792fd6d0c394a214012edc4a758b76342e30e91658752312c3cab1475e414e3"
LOCKED_COLUMNS_SHA256 = "0ecc7828fe015b5b1a705ff169fa65f407e6d443090eda1c3182bf955b820210"
EXPECTED_ARTIFACTS = {
    "core": (
        "scripts/factor_excel.py",
        LOCKED_CORE_SHA256,
    ),
    "contract": (
        "references/excel-locked-66-contract.json",
        "b88be9f680c17fa3e7375c8df9ead1b7e95953a7127f2813f10b1cca00dd58e2",
    ),
    "formulas": (
        "references/excel-formulas.md",
        "b55a3c3a1c1dc0d12ee5adab460273ad50562c9104266d60f72e0684721773f1",
    ),
    "audit_policy": (
        "references/excel-audit-policy.md",
        "c10d357260ec50f0b6d4e70e78c215acba9a3736b97a57f658c5353015f26f89",
    ),
    "migration_acceptance": (
        "references/excel-migration-acceptance.json",
        "2c1ef23e41fc90d90319c794cd0b3be018f5fad40feb5ae849528f1ef54a5169",
    ),
}
OUTPUT_COLUMNS = ("trade_time",) + tuple(factor_excel.COLUMN_ORDER)
REQUIRED_RUNTIME = {
    "python": "3.10.20",
    "numpy": "2.2.6",
    "pandas": "2.3.3",
    "pyarrow": "23.0.1",
}


class ReproduceError(RuntimeError):
    """The bundle, input, staging path, or output violates the locked contract."""


@dataclass(frozen=True)
class BuiltOutput:
    table: pa.Table
    expected_trade: pa.Array
    expected_features: pd.DataFrame
    source_rows: int
    warmup_rows: int
    live_rows: int
    live_start: pd.Timestamp
    cold_start: bool


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReproduceError(message)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReproduceError(f"invalid JSON: {path}") from exc
    _require(isinstance(value, dict), f"JSON root must be an object: {path}")
    return value


def _verify_runtime() -> dict[str, str]:
    actual = {
        "python": ".".join(str(part) for part in sys.version_info[:3]),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "pyarrow": pa.__version__,
    }
    _require(
        actual == REQUIRED_RUNTIME,
        f"runtime mismatch: required={REQUIRED_RUNTIME}, actual={actual}",
    )
    return actual


def _columns_sha256(columns: Sequence[str]) -> str:
    payload = json.dumps(
        tuple(columns), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _verify_bundle() -> dict[str, Any]:
    """Fail closed unless the self-contained bundle matches every locked hash."""

    _require(Path(factor_excel.__file__).resolve() == CORE_PATH, "core import was shadowed")
    lock = _load_json(LOCK_PATH)
    _require(lock.get("status") == "LOCKED", "core lock is not LOCKED")
    _require(
        lock.get("runtime_dependency_policy", {}).get("required_runtime")
        == REQUIRED_RUNTIME,
        "core lock runtime contract mismatch",
    )
    runtime = _verify_runtime()
    locked_artifacts = lock.get("artifacts")
    _require(isinstance(locked_artifacts, dict), "core lock artifacts are missing")

    actual_hashes: dict[str, str] = {}
    for key, (relative, expected_sha256) in EXPECTED_ARTIFACTS.items():
        path = SKILL_ROOT / relative
        _require(path.is_file(), f"locked artifact is missing: {relative}")
        actual = _sha256_file(path)
        _require(actual == expected_sha256, f"locked artifact hash mismatch: {relative}")
        entry = locked_artifacts.get(key)
        _require(isinstance(entry, dict), f"core lock entry is missing: {key}")
        _require(entry.get("path") == relative, f"core lock path mismatch: {key}")
        _require(
            entry.get("sha256") == expected_sha256,
            f"core lock digest mismatch: {key}",
        )
        actual_hashes[key] = actual

    _require(CORE_PATH.stat().st_size == 16805, "locked core byte length mismatch")
    _require(factor_excel.CORE_VERSION == "excel-locked-66-production-v1", "core version mismatch")

    contract = _load_json(REFERENCES / "excel-locked-66-contract.json")
    contract_columns = contract.get("columns")
    _require(isinstance(contract_columns, list), "contract columns are missing")
    _require(contract.get("column_count") == 66, "contract count is not 66")
    _require(tuple(contract_columns) == tuple(factor_excel.COLUMN_ORDER), "contract/core order mismatch")
    column_hash = _columns_sha256(contract_columns)
    _require(column_hash == LOCKED_COLUMNS_SHA256, "locked column-order hash mismatch")
    _require(lock.get("columns", {}).get("count") == 66, "core lock column count mismatch")
    _require(
        lock.get("columns", {}).get("order_sha256") == column_hash,
        "core lock column order mismatch",
    )

    acceptance = _load_json(REFERENCES / "excel-migration-acceptance.json")
    artifact = acceptance.get("artifact", {})
    locked_source = acceptance.get("locked_source", {})
    _require(
        acceptance.get("status") == "PASS_MIGRATION_CORE_READY",
        "migration acceptance is not PASS_MIGRATION_CORE_READY",
    )
    _require(artifact.get("sha256") == LOCKED_CORE_SHA256, "acceptance/core hash mismatch")
    _require(artifact.get("runtime_formula_file_reads") is False, "core is not self-contained")
    _require(locked_source.get("columns") == 66, "acceptance column count mismatch")
    _require(
        locked_source.get("columns_sha256") == LOCKED_COLUMNS_SHA256,
        "acceptance column order mismatch",
    )

    core_report = factor_excel.selftest()
    _require(core_report.get("status") == "PASS", "locked core selftest failed")
    _require(core_report.get("columns") == 66, "core selftest count mismatch")
    _require(
        core_report.get("columns_sha256") == LOCKED_COLUMNS_SHA256,
        "core selftest order mismatch",
    )
    _require(core_report.get("deterministic_bitwise") is True, "core is not deterministic")

    return {
        "status": "PASS",
        "core_sha256": actual_hashes["core"],
        "contract_sha256": actual_hashes["contract"],
        "migration_acceptance_sha256": actual_hashes["migration_acceptance"],
        "columns": 66,
        "columns_sha256": column_hash,
        "self_contained": True,
        "runtime": runtime,
        "core_selftest": core_report,
    }


def _normalize_live_start(value: str, trade_type: pa.TimestampType) -> pd.Timestamp:
    try:
        result = pd.Timestamp(value)
    except Exception as exc:
        raise ReproduceError(f"invalid --live-start: {value}") from exc
    _require(not pd.isna(result), "--live-start cannot be NaT")
    if trade_type.tz:
        if result.tzinfo is None:
            try:
                result = result.tz_localize(
                    trade_type.tz, ambiguous="raise", nonexistent="raise"
                )
            except Exception as exc:
                raise ReproduceError("--live-start cannot be localized to trade_time timezone") from exc
        else:
            result = result.tz_convert(trade_type.tz)
    else:
        _require(
            result.tzinfo is None,
            "timezone-aware --live-start cannot be used with timezone-naive trade_time",
        )
    return result


def _validate_single_identity(table: pa.Table) -> None:
    for name in ("symbol", "contract_code", "timeframe"):
        if name not in table.column_names:
            continue
        value = table.column(name).combine_chunks()
        _require(value.null_count == 0, f"{name} contains null")
        try:
            unique = pc.unique(value)
        except Exception as exc:
            raise ReproduceError(f"cannot validate single-sequence identity: {name}") from exc
        _require(len(unique) == 1, f"input mixes multiple {name} values")


def _float_bitwise_equal(left: np.ndarray, right: np.ndarray) -> bool:
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    if a.shape != b.shape:
        return False
    a_null = np.isnan(a)
    b_null = np.isnan(b)
    if not np.array_equal(a_null, b_null):
        return False
    valid = ~(a_null | b_null)
    return np.array_equal(a[valid].view(np.uint64), b[valid].view(np.uint64))


def _arrow_float_values(value: pa.ChunkedArray | pa.Array) -> np.ndarray:
    array = value.combine_chunks() if isinstance(value, pa.ChunkedArray) else value
    filled = pc.fill_null(array, pa.scalar(np.nan, type=pa.float64()))
    return filled.to_numpy(zero_copy_only=False)


def _validate_output_table(table: pa.Table, built: BuiltOutput) -> None:
    _require(tuple(table.column_names) == OUTPUT_COLUMNS, "output column order mismatch")
    _require(table.num_columns == 67, "output must contain trade_time plus 66 factors")
    _require(table.num_rows == built.live_rows, "output live-row count mismatch")
    trade = table.column("trade_time").combine_chunks()
    _require(trade.type == built.expected_trade.type, "trade_time type changed")
    _require(trade.null_count == 0, "output trade_time contains null")
    _require(trade.equals(built.expected_trade), "output trade_time keys changed")

    output_times = pd.DatetimeIndex(trade.to_pandas())
    _require(len(output_times) > 0, "output cannot be empty")
    _require(output_times[0] >= built.live_start, "warmup row leaked into output")

    for name in factor_excel.COLUMN_ORDER:
        column = table.column(name)
        _require(pa.types.is_float64(column.type), f"output dtype is not float64: {name}")
        infinite = pc.any(pc.is_inf(column)).as_py()
        _require(not bool(infinite), f"output contains infinity: {name}")
        actual = _arrow_float_values(column)
        expected = built.expected_features[name].to_numpy(dtype=np.float64, copy=False)
        _require(_float_bitwise_equal(actual, expected), f"output bit mismatch: {name}")


def _build_output(
    table: pa.Table, live_start_value: str, allow_cold_start: bool = False
) -> BuiltOutput:
    _require(table.num_rows > 0, "input Parquet is empty")
    _require(
        len(table.column_names) == len(set(table.column_names)),
        "input contains duplicate column names",
    )
    required = ("trade_time",) + tuple(factor_excel.REQUIRED_COLUMNS)
    missing = [name for name in required if name not in table.column_names]
    _require(not missing, f"input is missing required columns: {missing}")
    _validate_single_identity(table)

    trade = table.column("trade_time").combine_chunks()
    _require(pa.types.is_timestamp(trade.type), "trade_time must be an Arrow timestamp")
    _require(trade.null_count == 0, "trade_time contains null")
    times = pd.DatetimeIndex(trade.to_pandas())
    _require(not times.has_duplicates, "trade_time contains duplicates")
    keys = times.asi8
    _require(
        len(keys) == 1 or bool(np.all(keys[1:] > keys[:-1])),
        "trade_time must be strictly increasing",
    )
    live_start = _normalize_live_start(live_start_value, trade.type)
    live_mask = np.asarray(times >= live_start, dtype=bool)
    live_positions = np.flatnonzero(live_mask)
    _require(len(live_positions) > 0, "input contains no live rows")
    offset = int(live_positions[0])
    if offset == 0:
        _require(
            allow_cold_start,
            "input contains no pre-live warmup rows; use --allow-cold-start only after CH preflight confirms zero rows",
        )
    else:
        _require(
            not allow_cold_start,
            "--allow-cold-start conflicts with available pre-live warmup rows",
        )
    _require(bool(np.all(~live_mask[:offset])), "warmup/live ordering is invalid")
    _require(bool(np.all(live_mask[offset:])), "warmup/live rows are interleaved")

    frame = pd.DataFrame(
        {
            name: table.column(name).combine_chunks().to_pandas()
            for name in factor_excel.REQUIRED_COLUMNS
        }
    ).reset_index(drop=True)
    features = factor_excel.compute(frame)
    live_features = features.iloc[offset:].reset_index(drop=True)
    expected_trade = trade.slice(offset)
    arrays: list[pa.Array] = [expected_trade]
    for name in factor_excel.COLUMN_ORDER:
        values = live_features[name].to_numpy(dtype=np.float64, copy=False)
        arrays.append(pa.array(values, type=pa.float64(), from_pandas=True))
    output = pa.Table.from_arrays(arrays, names=list(OUTPUT_COLUMNS))
    metadata = {
        b"excel_factor_reproduce": json.dumps(
            {
                "core_sha256": LOCKED_CORE_SHA256,
                "columns_sha256": LOCKED_COLUMNS_SHA256,
                "live_start": live_start.isoformat(),
                "warmup_rows": offset,
                "live_rows": len(live_features),
                "cold_start": offset == 0,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    }
    output = output.replace_schema_metadata(metadata)
    built = BuiltOutput(
        table=output,
        expected_trade=expected_trade,
        expected_features=live_features,
        source_rows=table.num_rows,
        warmup_rows=offset,
        live_rows=len(live_features),
        live_start=live_start,
        cold_start=offset == 0,
    )
    _validate_output_table(output, built)
    return built


def _is_within(root: Path, candidate: Path) -> bool:
    return candidate == root or root in candidate.parents


def _prepare_paths(
    input_value: str, staging_value: str, output_value: str, qdh_value: str
) -> tuple[Path, Path, Path, Path]:
    input_raw = Path(input_value)
    staging_raw = Path(staging_value)
    output_raw = Path(output_value)
    qdh_raw = Path(qdh_value)
    _require(input_raw.is_absolute(), "--input must be an absolute path")
    _require(staging_raw.is_absolute(), "--staging-root must be an absolute path")
    _require(output_raw.is_absolute(), "--output must be an absolute path")
    _require(qdh_raw.is_absolute(), "--qdh-root must be an absolute path")

    input_path = input_raw.resolve(strict=True)
    staging_root = staging_raw.resolve(strict=True)
    output_parent = output_raw.parent.resolve(strict=True)
    output_path = output_parent / output_raw.name
    qdh_root = qdh_raw.resolve(strict=False)
    skill_root = SKILL_ROOT.resolve(strict=True)

    _require(input_path.is_file(), "--input must name one Parquet file")
    _require(input_path.suffix.lower() == ".parquet", "--input must be .parquet")
    _require(staging_root.is_dir(), "--staging-root must be an existing directory")
    _require(output_parent.is_dir(), "--output parent must be an existing directory")
    _require(output_path.suffix.lower() == ".parquet", "--output must be .parquet")
    _require(_is_within(staging_root, output_path), "--output is outside --staging-root")
    _require(not _is_within(skill_root, staging_root), "staging root cannot be inside the read-only skill bundle")
    _require(not _is_within(skill_root, output_path), "output cannot be inside the read-only skill bundle")
    _require(not _is_within(qdh_root, staging_root), "staging root cannot be inside qdh")
    _require(not _is_within(qdh_root, output_path), "output cannot be inside qdh")
    _require(output_path != input_path, "input and output paths must differ")
    _require(not output_path.exists(), "output already exists; staging is immutable")
    return input_path, staging_root, output_path, qdh_root


def _write_new_parquet(output_path: Path, built: BuiltOutput) -> str:
    """Validate a temp file, then publish it atomically without clobbering."""

    temporary = output_path.parent / (
        f".{output_path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )
    _require(not temporary.exists(), "temporary staging collision")
    try:
        pq.write_table(
            built.table,
            temporary,
            compression="zstd",
            use_dictionary=False,
            write_statistics=True,
        )
        reread = pq.read_table(temporary)
        _validate_output_table(reread, built)
        try:
            os.link(temporary, output_path)
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
    _require(output_path.is_file(), "published output is missing")
    return _sha256_file(output_path)


def _synthetic_table() -> pa.Table:
    rows = 900
    position = np.arange(rows, dtype=np.float64)
    close = 100.0 + 0.019 * position + np.sin(position / 11.0)
    open_ = close + 0.13 * np.cos(position / 7.0)
    spread = 0.5 + 0.1 * np.sin(position / 13.0) ** 2
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    volume = 1000.0 + (position % 37.0) * 11.0

    # Put zero denominators in the live range so Arrow null conversion is tested.
    open_[500:525] = close[500:525]
    high[500:525] = close[500:525]
    low[500:525] = close[500:525]
    volume[430] = 0.0
    volume[650:675] = 0.0
    trade_time = pd.date_range(
        "2019-12-15 00:00:00", periods=rows, freq="h", tz="Asia/Shanghai"
    )
    return pa.table(
        {
            "trade_time": pa.array(trade_time),
            "open": pa.array(open_),
            "high": pa.array(high),
            "low": pa.array(low),
            "close": pa.array(close),
            "volume": pa.array(volume),
        }
    )


def command_selftest(_: argparse.Namespace) -> dict[str, Any]:
    bundle = _verify_bundle()
    source = _synthetic_table()
    built = _build_output(source, "2020-01-01")

    cold_source = source.slice(built.warmup_rows)
    cold_default_rejected = False
    try:
        _build_output(cold_source, "2020-01-01")
    except ReproduceError as exc:
        cold_default_rejected = "--allow-cold-start" in str(exc)
    _require(cold_default_rejected, "cold start was not rejected by default")
    cold_built = _build_output(
        cold_source, "2020-01-01", allow_cold_start=True
    )
    _require(cold_built.cold_start, "explicit cold start was not marked")
    _require(cold_built.warmup_rows == 0, "cold start unexpectedly has warmup rows")
    cold_first = pd.Timestamp(cold_built.expected_trade[0].as_py())
    _require(cold_first >= cold_built.live_start, "cold start emitted pre-live data")

    frame = source.select(list(factor_excel.REQUIRED_COLUMNS)).to_pandas().reset_index(drop=True)
    full = factor_excel.compute(frame)
    repeat = factor_excel.compute(frame.copy())
    for name in factor_excel.COLUMN_ORDER:
        _require(
            _float_bitwise_equal(
                full[name].to_numpy(dtype=np.float64, copy=False),
                repeat[name].to_numpy(dtype=np.float64, copy=False),
            ),
            f"wrapper determinism failed: {name}",
        )

    close = frame["close"].astype("float64")
    expected_ema = close.ewm(span=12, adjust=False).mean().to_numpy(dtype=np.float64)
    actual_ema = full["excel_EXPMA_12"].to_numpy(dtype=np.float64, copy=False)
    _require(_float_bitwise_equal(actual_ema, expected_ema), "EMA adjust=False mismatch")
    adjusted_ema = close.ewm(span=12, adjust=True).mean().to_numpy(dtype=np.float64)
    _require(
        not _float_bitwise_equal(actual_ema, adjusted_ema),
        "EMA selftest does not distinguish adjust=False from adjust=True",
    )

    high = frame["high"].to_numpy(dtype=np.float64, copy=False)
    expected_sma_second = (high[1] + 19.0 * high[0]) / 20.0
    _require(
        full.loc[1, "excel_PAC_upper_20"] == expected_sma_second,
        "recursive SMA recurrence mismatch",
    )
    _require(np.isnan(full.loc[510, "excel_ROCVOL_80"]), "zero ROCVOL denominator is not NaN")
    _require(np.isnan(full.loc[519, "excel_BOP_20"]), "zero range did not become NaN")
    _require(
        not np.isinf(full.to_numpy(dtype=np.float64)).any(),
        "core output contains infinity",
    )

    live_only = factor_excel.compute(frame.iloc[built.warmup_rows :].reset_index(drop=True))
    full_first = np.asarray(
        [full.loc[built.warmup_rows, "excel_EXPMA_12"]], dtype=np.float64
    )
    live_first = np.asarray([live_only.loc[0, "excel_EXPMA_12"]], dtype=np.float64)
    _require(
        not _float_bitwise_equal(full_first, live_first),
        "warmup selftest did not affect the first live EMA",
    )
    _require(
        built.table.column("excel_BOP_20").null_count > 0
        and built.table.column("excel_ROCVOL_80").null_count > 0,
        "NaN was not serialized as Arrow null",
    )

    return {
        "status": "PASS",
        "command": "selftest",
        "writes": 0,
        "bundle": bundle,
        "wrapper": {
            "source_rows": built.source_rows,
            "warmup_rows": built.warmup_rows,
            "live_rows": built.live_rows,
            "output_columns": built.table.num_columns,
            "feature_columns": 66,
            "feature_dtype": "float64",
            "ema_adjust_false": True,
            "recursive_sma": True,
            "zero_denominator_to_null": True,
            "infinite_values": 0,
            "deterministic_bitwise": True,
            "warmup_slice": True,
            "cold_start_default_rejected": True,
            "cold_start_explicit_allowed": True,
            "cold_start_pre_live_rows_written": 0,
            "first_output_time": pd.Timestamp(
                built.expected_trade[0].as_py()
            ).isoformat(),
        },
    }


def command_compute(args: argparse.Namespace) -> dict[str, Any]:
    bundle = _verify_bundle()
    input_path, staging_root, output_path, qdh_root = _prepare_paths(
        args.input, args.staging_root, args.output, args.qdh_root
    )
    try:
        source = pq.read_table(input_path)
    except Exception as exc:
        raise ReproduceError(f"cannot read input Parquet: {input_path}") from exc
    built = _build_output(
        source, args.live_start, allow_cold_start=args.allow_cold_start
    )
    output_sha256 = _write_new_parquet(output_path, built)
    return {
        "status": "PASS",
        "command": "compute",
        "input": str(input_path),
        "input_sha256": _sha256_file(input_path),
        "staging_root": str(staging_root),
        "output": str(output_path),
        "output_sha256": output_sha256,
        "protected_qdh_root": str(qdh_root),
        "source_rows": built.source_rows,
        "warmup_rows": built.warmup_rows,
        "live_rows": built.live_rows,
        "live_start": built.live_start.isoformat(),
        "output_columns": 67,
        "feature_columns": 66,
        "feature_dtype": "float64",
        "infinite_values": 0,
        "warmup_rows_written": 0,
        "cold_start": built.cold_start,
        "allow_cold_start": bool(args.allow_cold_start),
        "bundle": {
            "core_sha256": bundle["core_sha256"],
            "columns_sha256": bundle["columns_sha256"],
            "runtime": bundle["runtime"],
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reproduce locked Excel 66 factors into external staging"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    selftest_parser = subparsers.add_parser(
        "selftest", help="read-only bundle and numerical selftest"
    )
    selftest_parser.set_defaults(handler=command_selftest)

    compute_parser = subparsers.add_parser(
        "compute", help="write one new external trade_time+66 staging Parquet"
    )
    compute_parser.add_argument("--input", required=True)
    compute_parser.add_argument("--staging-root", required=True)
    compute_parser.add_argument("--output", required=True)
    compute_parser.add_argument("--live-start", default="2020-01-01")
    compute_parser.add_argument(
        "--allow-cold-start",
        action="store_true",
        help="allow zero warmup rows only after upstream CH preflight confirms none exist",
    )
    compute_parser.add_argument(
        "--qdh-root",
        required=True,
        help="protected qdh root; output below this path is always refused",
    )
    compute_parser.set_defaults(handler=command_compute)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.handler(args)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
