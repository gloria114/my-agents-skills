#!/usr/bin/env python3
"""Self-contained, guarded reproduction CLI for locked Indicator-PY 59."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import uuid
from pathlib import Path
from typing import Any

try:
    import numpy as np
    import pandas as pd
except ImportError as exc:  # pragma: no cover - environment dependent
    print(
        json.dumps(
            {
                "status": "ERROR",
                "message": f"missing runtime dependency: {exc.name}",
            },
            ensure_ascii=False,
            indent=2,
        ),
        file=sys.stderr,
    )
    raise SystemExit(2)


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


SCRIPT_ROOT = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_ROOT.parent
VENDOR_ROOT = SCRIPT_ROOT / "vendor"

# The vendored WH6 modules intentionally use their original top-level imports.
# Add only the local, hash-locked vendor directory; no external WH6 skill or
# migration workspace is imported at runtime.
sys.path.insert(0, str(VENDOR_ROOT))

import factor_indicator as indicator_core  # noqa: E402
import wh6_candidate  # noqa: E402


BASE_COLUMNS = (
    "open",
    "high",
    "low",
    "close",
    "volume",
    "open_interest",
)
WH6_DEPENDENCIES = (
    "wh6_MACD_MACD",
    "wh6_RSI_RSI2",
    "wh6_ATR_ATR",
    "wh6_Z_SCORE_Z_SCORE",
    "wh6_u_8b96f436_BBW",
)
OUTPUT_COLUMNS = ("trade_time",) + tuple(indicator_core.COLUMN_ORDER)
EARLIEST_OUTPUT_DATE = "2020-01-01"
EXPECTED_RUNTIME = {
    "python": "3.10.20",
    "numpy": "2.2.6",
    "pandas": "2.3.3",
    "pyarrow": "23.0.1",
}

LOCKED_FILES = {
    "scripts/factor_indicator.py": (
        "817b6531f19e33c5dea3307afca56314a8396f01034b03f53205e87ac49dc2d1"
    ),
    "scripts/vendor/wh6_candidate.py": (
        "849c460a50864e05744211abe3e269b2e7e957312ee92ed2c432fbef4f89514e"
    ),
    "scripts/vendor/wh6_formulas_v2.py": (
        "e71c1d3be8c43c0c5e1ec0ac9fc204b471d07e527292b37571c08bc489439d8a"
    ),
    "scripts/vendor/wh6_primitives.py": (
        "9313b87f57138b9775ad502f8970d91bd81439e02f8056242561d2a822e39061"
    ),
    "references/indicator-py-locked-59-contract.json": (
        "633bf61bf71e7ef8d75cea3e65621a69177ce20bd3d856f72ed9ea777d3e9097"
    ),
    "references/indicator-py-formulas.md": (
        "69ef6c57d9e8063fb3671da382c43605e289bb6b870ae47e9f35796165672d39"
    ),
    "references/indicator-py-audit-policy.md": (
        "67224613b8f62b4028b70353557368daa19348cb1fddfedf26ea71235ff43746"
    ),
    "assets/acceptance/indicator_migration.json": (
        "2e9a280271b805a093276ff725734ed64d144ac6a64b9b6ef6f8bd7ef45dff58"
    ),
}


class ReproductionError(RuntimeError):
    """A locked contract or safe-staging precondition was violated."""


def require_exact_runtime() -> dict[str, str]:
    try:
        import pyarrow as pa
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ReproductionError(f"missing runtime dependency: {exc.name}") from exc
    observed = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "pyarrow": pa.__version__,
    }
    if observed != EXPECTED_RUNTIME:
        raise ReproductionError(
            "runtime version mismatch: "
            f"expected={EXPECTED_RUNTIME}, observed={observed}"
        )
    return observed


def emit(payload: dict[str, Any], *, stream: Any = None) -> None:
    print(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        file=stream or sys.stdout,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_locked_sources() -> dict[str, str]:
    observed: dict[str, str] = {}
    for relative, expected in LOCKED_FILES.items():
        path = SKILL_ROOT / Path(relative)
        if not path.is_file():
            raise ReproductionError(f"locked file is missing: {relative}")
        actual = sha256_file(path)
        observed[relative] = actual
        if actual != expected:
            raise ReproductionError(
                f"locked SHA-256 mismatch: {relative}: expected={expected}, actual={actual}"
            )

    acceptance_path = SKILL_ROOT / "assets" / "acceptance" / "indicator_migration.json"
    with acceptance_path.open("r", encoding="utf-8") as handle:
        acceptance = json.load(handle)
    accepted_core = acceptance.get("implementation", {}).get("sha256")
    if accepted_core != LOCKED_FILES["scripts/factor_indicator.py"]:
        raise ReproductionError("migration evidence does not lock the vendored Indicator core")
    accepted_wh6 = (
        acceptance.get("wh6_dependency_lock", {}).get("core_files", {})
    )
    for filename in (
        "wh6_candidate.py",
        "wh6_formulas_v2.py",
        "wh6_primitives.py",
    ):
        relative = f"scripts/vendor/{filename}"
        if accepted_wh6.get(filename) != LOCKED_FILES[relative]:
            raise ReproductionError(
                f"migration evidence does not lock vendored WH6 source: {filename}"
            )

    contract_path = (
        SKILL_ROOT / "references" / "indicator-py-locked-59-contract.json"
    )
    with contract_path.open("r", encoding="utf-8") as handle:
        contract = json.load(handle)
    contract_columns = tuple(item["name"] for item in contract["columns"])
    if int(contract["column_count"]) != 59 or len(contract_columns) != 59:
        raise ReproductionError("locked contract does not contain exactly 59 columns")
    if contract_columns != tuple(indicator_core.COLUMN_ORDER):
        raise ReproductionError("Indicator core column order differs from locked contract")
    if tuple(contract["required_wh6_columns"]) != WH6_DEPENDENCIES:
        raise ReproductionError("WH6 dependency order differs from locked contract")
    if tuple(indicator_core.REQUIRED_WH6_COLUMNS) != WH6_DEPENDENCIES:
        raise ReproductionError("Indicator core WH6 dependencies differ from lock")
    return observed


def compute_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Compute all WH6 columns internally, select five, then compute locked 59."""

    if not isinstance(frame, pd.DataFrame):
        raise ReproductionError("input must be a pandas DataFrame")
    missing = [column for column in BASE_COLUMNS if column not in frame.columns]
    if missing:
        raise ReproductionError(f"missing market inputs: {missing}")
    if not frame.index.is_unique:
        raise ReproductionError("input row index must be unique")

    engine = wh6_candidate.load_engine()
    wh6_frame = engine.compute(frame.loc[:, BASE_COLUMNS])
    missing_wh6 = [name for name in WH6_DEPENDENCIES if name not in wh6_frame.columns]
    if missing_wh6:
        raise ReproductionError(f"vendored WH6 engine missed dependencies: {missing_wh6}")

    indicator_input = frame.loc[
        :, ("high", "low", "close", "volume", "open_interest")
    ].copy()
    for name in WH6_DEPENDENCIES:
        indicator_input[name] = wh6_frame[name]
    result = indicator_core.compute(indicator_input)

    if tuple(result.columns) != tuple(indicator_core.COLUMN_ORDER):
        raise ReproductionError("output column order does not match locked 59")
    if result.shape != (len(frame), 59):
        raise ReproductionError(
            f"output shape violation: expected=({len(frame)}, 59), actual={result.shape}"
        )
    non_float64 = [name for name in result if result[name].dtype != np.dtype("float64")]
    if non_float64:
        raise ReproductionError(f"non-float64 feature columns: {non_float64}")
    values = result.to_numpy(dtype="float64", copy=False)
    if np.isinf(values).any():
        raise ReproductionError("output contains +/-Inf instead of null")
    return result


def _synthetic_market(rows: int = 720) -> pd.DataFrame:
    x = np.arange(rows, dtype="float64")
    trend = 100.0 + 0.027 * x
    close = trend + 1.7 * np.sin(x / 9.0) + 0.35 * np.cos(x / 23.0)
    open_ = close + 0.12 * np.sin(x / 5.0)
    high = np.maximum(open_, close) + 0.8 + 0.03 * (x % 5.0)
    low = np.minimum(open_, close) - 0.75 - 0.02 * (x % 7.0)
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000.0 + 11.0 * (x % 31.0) + 0.7 * x,
            "open_interest": 5000.0 + 2.0 * (x % 47.0) + 0.2 * x,
        }
    )


def _assert_bitwise_equal(left: pd.DataFrame, right: pd.DataFrame) -> None:
    if left.shape != right.shape or tuple(left.columns) != tuple(right.columns):
        raise AssertionError("repeat output shape/order differs")
    left_values = left.to_numpy(dtype="float64", copy=True)
    right_values = right.to_numpy(dtype="float64", copy=True)
    if not np.array_equal(left_values.view("uint64"), right_values.view("uint64")):
        raise AssertionError("repeat output is not bitwise deterministic")


def run_selftest() -> dict[str, Any]:
    runtime = require_exact_runtime()
    locked = verify_locked_sources()
    migration_selftest = indicator_core.selftest()
    if migration_selftest.get("status") != "PASS":
        raise AssertionError("accepted Indicator migration core selftest failed")

    frame = _synthetic_market()
    first = compute_features(frame)
    second = compute_features(frame.copy())
    _assert_bitwise_equal(first, second)

    cut = 320
    full_then_slice = first.iloc[cut:].reset_index(drop=True)
    recomputed_full_then_slice = compute_features(frame).iloc[cut:].reset_index(drop=True)
    _assert_bitwise_equal(full_then_slice, recomputed_full_then_slice)

    cold = compute_features(frame.iloc[cut:].reset_index(drop=True))
    if full_then_slice.equals(cold):
        raise AssertionError("warmup guard failed: cold recompute unexpectedly equals warm state")

    # Exercise an explicit finite-over-zero path in the accepted Indicator
    # core.  Its final normalizer must turn the resulting infinity into NaN.
    engine = wh6_candidate.load_engine()
    wh6 = engine.compute(frame.loc[:, BASE_COLUMNS])
    pathological = frame.loc[
        :, ("high", "low", "close", "volume", "open_interest")
    ].copy()
    for name in WH6_DEPENDENCIES:
        pathological[name] = wh6[name]
    pathological.loc[250, "close"] = 0.0
    normalized = indicator_core.compute(pathological)
    if not np.isnan(normalized.loc[250, "indicator_py_hl_pct"]):
        raise AssertionError("+/-Inf was not normalized to null")
    if np.isinf(normalized.to_numpy(dtype="float64", copy=False)).any():
        raise AssertionError("normalized output still contains +/-Inf")

    if len(wh6.columns) != 198:
        raise AssertionError("vendored WH6 engine no longer exposes locked 198")
    if tuple(indicator_core.WH6_DEPENDENCIES) != WH6_DEPENDENCIES:
        raise AssertionError("locked five-WH6 dependency selection changed")

    warm_times = pd.date_range(
        "2019-12-30", periods=len(frame), freq="5min", tz="Asia/Shanghai"
    )
    warm_positions = _validate_live_boundary(
        warm_times,
        pd.Timestamp("2020-01-01", tz="Asia/Shanghai"),
        allow_cold_start=False,
    )
    if not len(warm_positions) or warm_positions[0] == 0:
        raise AssertionError("pre-2020 warmup slice selftest failed")
    if (warm_times[warm_positions] < pd.Timestamp("2020-01-01", tz="Asia/Shanghai")).any():
        raise AssertionError("pre-2020 row escaped into output")
    try:
        import pyarrow as pa
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise AssertionError("pyarrow is required for staging selftest") from exc
    input_arrays = [
        pa.array(warm_times, type=pa.timestamp("ns", tz="Asia/Shanghai")),
        *(pa.array(frame[name], type=pa.float64()) for name in BASE_COLUMNS),
    ]
    input_table = pa.Table.from_arrays(
        input_arrays, names=["trade_time", *BASE_COLUMNS]
    )
    staged_table = _build_output_table(input_table, first, warm_positions)
    if staged_table.schema.field("trade_time").type != input_table.schema.field(
        "trade_time"
    ).type:
        raise AssertionError("trade_time Arrow type was not preserved")
    if tuple(staged_table.schema.names) != OUTPUT_COLUMNS:
        raise AssertionError("Arrow staging order is not trade_time + locked 59")

    cold_times = pd.date_range(
        "2020-01-02", periods=120, freq="5min", tz="Asia/Shanghai"
    )
    cold_start_rejected = False
    try:
        _validate_live_boundary(
            cold_times,
            pd.Timestamp("2020-01-01", tz="Asia/Shanghai"),
            allow_cold_start=False,
        )
    except ReproductionError:
        cold_start_rejected = True
    if not cold_start_rejected:
        raise AssertionError("zero-warmup input must fail closed by default")
    cold_positions = _validate_live_boundary(
        cold_times,
        pd.Timestamp("2020-01-01", tz="Asia/Shanghai"),
        allow_cold_start=True,
    )
    if len(cold_positions) != len(cold_times) or cold_positions[0] != 0:
        raise AssertionError("explicit CH zero-history cold start was not accepted")
    pre2020_rejected = False
    try:
        _validate_live_boundary(
            warm_times,
            pd.Timestamp("2019-12-31", tz="Asia/Shanghai"),
            allow_cold_start=True,
        )
    except ReproductionError:
        pre2020_rejected = True
    if not pre2020_rejected:
        raise AssertionError("pre-2020 output boundary must be rejected")

    return {
        "status": "PASS",
        "writes_performed": False,
        "runtime": runtime,
        "rows": len(frame),
        "output_columns": len(OUTPUT_COLUMNS),
        "feature_columns": len(indicator_core.COLUMN_ORDER),
        "feature_dtype": "float64",
        "wh6_internal_columns": len(wh6.columns),
        "wh6_selected_dependencies": list(WH6_DEPENDENCIES),
        "migration_core_byte_equivalent": True,
        "locked_source_hashes": locked,
        "checks": [
            "locked_source_sha256",
            "migration_acceptance_hash_equivalence",
            "locked_column_count_and_order",
            "all_feature_columns_float64",
            "infinity_normalized_to_null",
            "repeat_run_bitwise_determinism",
            "full_sequence_then_warmup_slice",
            "cold_recompute_differs_from_warm_state",
            "full_wh6_compute_then_locked_five_selection",
            "default_reject_zero_warmup",
            "explicit_allow_ch_zero_history_cold_start",
            "never_output_pre_2020_rows",
            "arrow_trade_time_type_and_trade_time_plus_59",
        ],
    }


def _is_within(path: Path, root: Path) -> bool:
    try:
        normalized_path = os.path.normcase(str(path))
        normalized_root = os.path.normcase(str(root))
        return os.path.commonpath((normalized_path, normalized_root)) == normalized_root
    except ValueError:
        return False


def _safe_paths(input_arg: str, output_arg: str, qdh_root_arg: str) -> tuple[Path, Path, Path]:
    input_path = Path(input_arg).expanduser()
    if not input_path.is_file() or input_path.suffix.lower() != ".parquet":
        raise ReproductionError("--input must be an existing Parquet file")
    input_path = input_path.resolve(strict=True)

    output_path = Path(output_arg).expanduser()
    if not output_path.is_absolute():
        raise ReproductionError("--output must be an absolute path")
    if output_path.suffix.lower() != ".parquet":
        raise ReproductionError("--output must end with .parquet")
    output_path = output_path.resolve(strict=False)
    if output_path.exists():
        raise ReproductionError("refusing to overwrite an existing output")
    if output_path == input_path:
        raise ReproductionError("input and output must differ")

    qdh_root = Path(qdh_root_arg).expanduser()
    if not qdh_root.is_absolute() or not qdh_root.is_dir():
        raise ReproductionError("--qdh-root must be an existing absolute directory")
    qdh_root = qdh_root.resolve(strict=True)
    if _is_within(output_path, qdh_root):
        raise ReproductionError("output must be outside qdh root")
    if _is_within(output_path, SKILL_ROOT.resolve(strict=True)):
        raise ReproductionError("output must be outside the skill directory")
    return input_path, output_path, qdh_root


def _load_continuous_input(path: Path) -> tuple[Any, pd.DataFrame, pd.DatetimeIndex]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ReproductionError(f"missing Parquet dependency: {exc.name}") from exc

    parquet = pq.ParquetFile(path)
    names = parquet.schema_arrow.names
    required = ["trade_time", *BASE_COLUMNS]
    missing = [name for name in required if name not in names]
    if missing:
        raise ReproductionError(f"input Parquet is missing columns: {missing}")
    if len(names) != len(set(names)):
        raise ReproductionError("input Parquet contains duplicate column names")
    trade_field = parquet.schema_arrow.field("trade_time")
    if not pa.types.is_timestamp(trade_field.type):
        raise ReproductionError("trade_time must use an Arrow timestamp type")

    table = pq.read_table(path, columns=required)
    if table.num_rows == 0:
        raise ReproductionError("input Parquet contains no rows")
    trade_array = table.column("trade_time").combine_chunks()
    if trade_array.null_count:
        raise ReproductionError("trade_time contains null values")
    trade_values = pd.DatetimeIndex(trade_array.to_pandas())
    if trade_values.has_duplicates:
        raise ReproductionError("trade_time must be unique")
    if not trade_values.is_monotonic_increasing:
        raise ReproductionError("trade_time must be strictly increasing")

    frame = table.select(list(BASE_COLUMNS)).to_pandas()
    frame.index = pd.RangeIndex(len(frame))
    for column in BASE_COLUMNS:
        try:
            frame[column] = pd.to_numeric(frame[column], errors="raise").astype("float64")
        except Exception as exc:
            raise ReproductionError(f"{column} must be numeric float64-compatible") from exc
    if not np.isfinite(frame.to_numpy(dtype="float64", copy=False)).all():
        raise ReproductionError("market inputs must be finite and non-null")
    return table, frame, trade_values


def _normalise_live_start(value: str, trade_values: pd.DatetimeIndex) -> pd.Timestamp:
    try:
        live_start = pd.Timestamp(value)
    except Exception as exc:
        raise ReproductionError("--live-start must be a valid ISO-8601 timestamp") from exc
    trade_tz = trade_values.tz
    if trade_tz is None:
        if live_start.tzinfo is not None:
            raise ReproductionError(
                "timezone-aware --live-start cannot be used with naive trade_time"
            )
    elif live_start.tzinfo is None:
        live_start = live_start.tz_localize(trade_tz)
    else:
        live_start = live_start.tz_convert(trade_tz)
    return live_start


def _validate_live_boundary(
    trade_values: pd.DatetimeIndex,
    live_start: pd.Timestamp,
    *,
    allow_cold_start: bool,
) -> np.ndarray:
    earliest = pd.Timestamp(EARLIEST_OUTPUT_DATE)
    if trade_values.tz is not None:
        earliest = earliest.tz_localize(trade_values.tz)
    if live_start < earliest:
        raise ReproductionError(
            f"--live-start cannot be earlier than {EARLIEST_OUTPUT_DATE}"
        )

    live_mask = np.asarray(trade_values >= live_start, dtype=bool)
    live_positions = np.flatnonzero(live_mask).astype("int64", copy=False)
    if not len(live_positions):
        raise ReproductionError("--live-start is after the final trade_time")
    first_live = int(live_positions[0])
    if first_live == 0 and not allow_cold_start:
        raise ReproductionError(
            "input has no rows before --live-start; confirm ClickHouse has zero "
            "earlier history, then repeat with --allow-cold-start"
        )
    if (trade_values[live_positions] < earliest).any():
        raise ReproductionError("pre-2020 rows are forbidden in output")
    return live_positions


def _build_output_table(
    input_table: Any,
    features: pd.DataFrame,
    live_positions: np.ndarray,
) -> Any:
    import pyarrow as pa
    import pyarrow.compute as pc

    trade_field = input_table.schema.field("trade_time")
    take_indices = pa.array(live_positions, type=pa.int64())
    trade_array = pc.take(
        input_table.column("trade_time").combine_chunks(), take_indices
    )
    arrays = [trade_array]
    fields = [trade_field]
    for name in indicator_core.COLUMN_ORDER:
        values = features[name].to_numpy(dtype="float64", copy=False)[live_positions]
        arrays.append(pa.array(values, type=pa.float64(), from_pandas=True))
        fields.append(pa.field(name, pa.float64(), nullable=True))
    table = pa.Table.from_arrays(arrays, schema=pa.schema(fields))
    _validate_output_table(table, expected_rows=len(live_positions))
    return table


def _validate_output_table(table: Any, *, expected_rows: int) -> None:
    import pyarrow as pa

    if table.num_rows != expected_rows:
        raise ReproductionError("staging table row count changed")
    if tuple(table.schema.names) != OUTPUT_COLUMNS:
        raise ReproductionError("staging table column order changed")
    for name in indicator_core.COLUMN_ORDER:
        if not pa.types.is_float64(table.schema.field(name).type):
            raise ReproductionError(f"staging feature is not Arrow float64: {name}")
        values = table.column(name).to_numpy(zero_copy_only=False)
        if np.isinf(values).any():
            raise ReproductionError(f"staging feature contains +/-Inf: {name}")


def _atomic_write_parquet(table: Any, output_path: Path) -> None:
    import pyarrow.parquet as pq

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise ReproductionError("output appeared after preflight; refusing overwrite")
    temporary = output_path.with_name(
        f".{output_path.name}.{uuid.uuid4().hex}.tmp"
    )
    try:
        pq.write_table(
            table,
            temporary,
            compression="zstd",
            use_dictionary=True,
            write_statistics=True,
        )
        reread = pq.read_table(temporary)
        _validate_output_table(reread, expected_rows=table.num_rows)
        with temporary.open("r+b") as handle:
            os.fsync(handle.fileno())
        if output_path.exists():
            raise ReproductionError("output appeared during validation; refusing overwrite")
        # A sibling hard link is an atomic no-clobber commit on supported local
        # filesystems. It fails if another agent creates the destination first.
        try:
            os.link(temporary, output_path)
        except FileExistsError as exc:
            raise ReproductionError(
                "output appeared during atomic commit; refusing overwrite"
            ) from exc
        except OSError as exc:
            raise ReproductionError(f"atomic hard-link commit failed: {exc}") from exc
    finally:
        if temporary.exists():
            temporary.unlink()


def command_summary(_args: argparse.Namespace) -> int:
    runtime = require_exact_runtime()
    hashes = verify_locked_sources()
    emit(
        {
            "status": "PASS",
            "writes_performed": False,
            "runtime": runtime,
            "input_columns": ["trade_time", *BASE_COLUMNS],
            "output_columns": len(OUTPUT_COLUMNS),
            "feature_columns": list(indicator_core.COLUMN_ORDER),
            "wh6_selected_dependencies": list(WH6_DEPENDENCIES),
            "default_mode": "read_only",
            "writer_boundary": "external staging only; never qdh features",
            "locked_source_hashes": hashes,
        }
    )
    return 0


def command_selftest(_args: argparse.Namespace) -> int:
    emit(run_selftest())
    return 0


def command_build(args: argparse.Namespace) -> int:
    runtime = require_exact_runtime()
    hashes = verify_locked_sources()
    input_path, output_path, qdh_root = _safe_paths(
        args.input, args.output, args.qdh_root
    )
    input_table, market, trade_values = _load_continuous_input(input_path)
    live_start = _normalise_live_start(args.live_start, trade_values)
    live_positions = _validate_live_boundary(
        trade_values,
        live_start,
        allow_cold_start=bool(args.allow_cold_start),
    )
    first_live = int(live_positions[0])

    features = compute_features(market)
    output_table = _build_output_table(input_table, features, live_positions)
    plan: dict[str, Any] = {
        "status": "VALIDATED",
        "executed": bool(args.execute),
        "runtime": runtime,
        "input": str(input_path),
        "output": str(output_path),
        "qdh_root": str(qdh_root),
        "input_rows": len(market),
        "warmup_rows": first_live,
        "cold_start_explicitly_allowed": bool(args.allow_cold_start),
        "live_rows": len(live_positions),
        "input_first_trade_time": trade_values[0].isoformat(),
        "input_last_trade_time": trade_values[-1].isoformat(),
        "live_start": live_start.isoformat(),
        "output_first_trade_time": trade_values[first_live].isoformat(),
        "output_columns": len(output_table.schema.names),
        "feature_dtype": "float64",
        "locked_source_hashes": hashes,
    }
    if not args.execute:
        plan["status"] = "DRY_RUN_PASS"
        plan["writes_performed"] = False
        emit(plan)
        return 0

    _atomic_write_parquet(output_table, output_path)
    plan["status"] = "STAGED"
    plan["writes_performed"] = True
    plan["output_sha256"] = sha256_file(output_path)
    emit(plan)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reproduce locked Indicator-PY 59 from one continuous warmup+live "
            "market Parquet sequence. No command writes by default."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    summary = subparsers.add_parser("summary", help="Show locked contract and hashes.")
    summary.set_defaults(func=command_summary)

    selftest = subparsers.add_parser(
        "selftest", help="Run deterministic in-memory checks; never writes."
    )
    selftest.set_defaults(func=command_selftest)

    build = subparsers.add_parser(
        "build",
        help="Validate a continuous input and optionally write external staging.",
    )
    build.add_argument("--input", required=True, help="Continuous warmup+live Parquet.")
    build.add_argument(
        "--output", required=True, help="New absolute Parquet path outside qdh."
    )
    build.add_argument(
        "--qdh-root",
        required=True,
        help="Existing absolute qdh root used only as a write-exclusion boundary.",
    )
    build.add_argument(
        "--live-start",
        required=True,
        help="First live timestamp; earlier input rows are compute-only warmup.",
    )
    build.add_argument(
        "--execute",
        action="store_true",
        help="Perform one guarded atomic staging write. Omit for dry-run.",
    )
    build.add_argument(
        "--allow-cold-start",
        action="store_true",
        help=(
            "Allow zero warmup rows only after upstream confirms ClickHouse has "
            "no earlier history for this sequence."
        ),
    )
    build.set_defaults(func=command_build)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        require_exact_runtime()
        return int(args.func(args))
    except (ReproductionError, AssertionError, ValueError, KeyError) as exc:
        emit(
            {
                "status": "ERROR",
                "writes_performed": False,
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
            stream=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
