"""Locked runtime composition for the qdh 465-feature release.

This module deliberately lives outside qdh and composes four locked,
source-visible Python formula cores.  Runtime inputs are the sealed skill
artifacts and the supplied market sequence.
"""

from __future__ import annotations

import hashlib
import json
import platform
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa


from skill_paths import activate_import_paths


RUNTIME_CONTRACT = {
    "python": "3.10.20",
    "numpy": "2.2.6",
    "pandas": "2.3.3",
    "pyarrow": "23.0.1",
}


def runtime_identity() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "pyarrow": pa.__version__,
    }


def verify_runtime_contract() -> dict[str, str]:
    actual = runtime_identity()
    if actual != RUNTIME_CONTRACT:
        raise RuntimeError(
            "runtime contract mismatch: "
            f"expected={RUNTIME_CONTRACT}, actual={actual}"
        )
    return actual


# Resolve all four sibling skills relative to this installed skill (or an
# explicit QDH_FEATURE_SKILLS_ROOT).  No user-profile or external-workspace
# path is embedded in the runtime.
verify_runtime_contract()
activate_import_paths()

from wh6_candidate import load_engine  # noqa: E402
from wh6_formulas_v2 import COLUMN_ORDER as WH6_COLUMNS  # noqa: E402

from factor_excel import COLUMN_ORDER as EXCEL_COLUMNS, compute as compute_excel
from factor_indicator import (
    COLUMN_ORDER as INDICATOR_COLUMNS,
    WH6_DEPENDENCIES,
    compute as compute_indicator,
)
from factor_tv import COLUMN_ORDER as TV_COLUMNS, compute as compute_tv


BASE_COLUMNS = ("open", "high", "low", "close", "volume", "open_interest")
FEATURE_COLUMNS = (
    *tuple(WH6_COLUMNS),
    *tuple(INDICATOR_COLUMNS),
    *tuple(EXCEL_COLUMNS),
    *tuple(TV_COLUMNS),
)
OUTPUT_COLUMNS = ("trade_time", *FEATURE_COLUMNS)


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


COLUMN_ORDER_SHA256 = hashlib.sha256(
    json.dumps(list(OUTPUT_COLUMNS), ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
).hexdigest()


def _canonical_float_frame(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    if tuple(frame.columns) != columns:
        raise RuntimeError(
            f"output order mismatch: expected {len(columns)}, got {len(frame.columns)}"
        )
    result: dict[str, pd.Series] = {}
    for name in columns:
        series = pd.to_numeric(frame[name], errors="raise").astype("float64")
        values = series.to_numpy(dtype=np.float64, copy=True)
        values[np.isinf(values)] = np.nan
        result[name] = pd.Series(values, index=frame.index, dtype="float64")
    return pd.DataFrame(result, index=frame.index)


def compute_all(frame: pd.DataFrame) -> pd.DataFrame:
    """Compute all 465 features over one full warmup+live sequence."""

    verify_runtime_contract()
    missing = [name for name in BASE_COLUMNS if name not in frame.columns]
    if missing:
        raise RuntimeError(f"missing market inputs: {missing}")
    if not frame.index.is_unique:
        raise RuntimeError("input index must be unique")

    base = frame.loc[:, list(BASE_COLUMNS)].copy()
    with np.errstate(all="ignore"):
        wh6 = load_engine().compute(base)
        if tuple(wh6.columns) != tuple(WH6_COLUMNS):
            raise RuntimeError("WH6 output contract changed")

        indicator_input = base.copy()
        for name in WH6_DEPENDENCIES:
            indicator_input[name] = wh6[name]
        indicator = compute_indicator(indicator_input)
        excel = compute_excel(base)
        tv = compute_tv(base)

    combined = pd.concat([wh6, indicator, excel, tv], axis=1)
    return _canonical_float_frame(combined, tuple(FEATURE_COLUMNS))


def selftest() -> dict[str, Any]:
    runtime = verify_runtime_contract()
    expected_counts = {
        "wh6": 198,
        "indicator_py": 59,
        "excel": 66,
        "tv": 142,
        "features": 465,
        "columns": 466,
    }
    actual_counts = {
        "wh6": len(WH6_COLUMNS),
        "indicator_py": len(INDICATOR_COLUMNS),
        "excel": len(EXCEL_COLUMNS),
        "tv": len(TV_COLUMNS),
        "features": len(FEATURE_COLUMNS),
        "columns": len(OUTPUT_COLUMNS),
    }
    if actual_counts != expected_counts:
        raise RuntimeError(f"column-count contract changed: {actual_counts}")
    if len(set(FEATURE_COLUMNS)) != len(FEATURE_COLUMNS):
        raise RuntimeError("duplicate feature column")
    expected_hash = "75f719fc1d2d4312a66a96de994afe1293da02fa1f96d6d54fc838229c8e4d88"
    if COLUMN_ORDER_SHA256 != expected_hash:
        raise RuntimeError(
            f"column-order hash changed: {COLUMN_ORDER_SHA256} != {expected_hash}"
        )

    rows = 800
    index = pd.RangeIndex(rows)
    x = np.arange(rows, dtype=np.float64)
    close = 100.0 + 0.03 * x + np.sin(x / 11.0)
    sample = pd.DataFrame(
        {
            "open": close + np.sin(x / 7.0) * 0.2,
            "high": close + 1.0 + (x % 5) * 0.01,
            "low": close - 1.0 - (x % 3) * 0.01,
            "close": close,
            "volume": 1000.0 + (x % 37) * 17.0,
            "open_interest": 5000.0 + (x % 53) * 9.0,
        },
        index=index,
    )
    first = compute_all(sample)
    second = compute_all(sample)
    if tuple(first.columns) != tuple(FEATURE_COLUMNS):
        raise RuntimeError("synthetic output order mismatch")
    for name in FEATURE_COLUMNS:
        left = first[name].to_numpy(dtype=np.float64, copy=False)
        right = second[name].to_numpy(dtype=np.float64, copy=False)
        if not np.array_equal(np.isnan(left), np.isnan(right)):
            raise RuntimeError(f"non-deterministic null mask: {name}")
        mask = ~np.isnan(left)
        if not np.array_equal(left[mask].view(np.uint64), right[mask].view(np.uint64)):
            raise RuntimeError(f"non-deterministic values: {name}")
        if np.isinf(left).any():
            raise RuntimeError(f"synthetic Inf: {name}")
    return {
        "status": "PASS",
        "counts": actual_counts,
        "column_order_sha256": COLUMN_ORDER_SHA256,
        "synthetic_rows": rows,
        "deterministic_bitwise": True,
        "runtime": runtime,
    }


if __name__ == "__main__":
    print(json.dumps(selftest(), ensure_ascii=False, indent=2))
