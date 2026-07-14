#!/usr/bin/env python3
"""Deterministic, file-read-only self-test for factor_tv."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import factor_tv


ROOT = Path(__file__).resolve().parent
FACTOR_SOURCE = ROOT / "factor_tv.py"
EXPECTED_COLUMN_SHA256 = "d19bfc5fe9380f1d2cf6767e15634d2fa33fd259754c30bc1da2f71f5e2f7538"


class SelfTestFailure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SelfTestFailure(message)


def strict_compare(actual: pd.Series, expected: pd.Series, atol: float = 1e-12) -> dict[str, int]:
    """Require exact null-mask agreement and compare every finite value."""

    a = pd.to_numeric(actual, errors="coerce").replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)
    b = pd.to_numeric(expected, errors="coerce").replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)
    require(len(a) == len(b), "strict comparison length mismatch")
    null_mismatches = int(np.logical_xor(np.isnan(a), np.isnan(b)).sum())
    finite = np.isfinite(a) & np.isfinite(b)
    numeric_mismatches = int((np.abs(a[finite] - b[finite]) > atol).sum())
    return {
        "null_mismatches": null_mismatches,
        "numeric_mismatches": numeric_mismatches,
        "bad": null_mismatches + numeric_mismatches,
    }


def synthetic_frame(rows: int = 600) -> pd.DataFrame:
    x = np.arange(rows, dtype=np.float64)
    close = 100.0 + 0.02 * x + np.sin(x / 11.0)
    open_ = close + 0.15 * np.cos(x / 7.0)
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) + 0.8,
            "low": np.minimum(open_, close) - 0.9,
            "close": close,
            "volume": 1000.0 + (x % 37.0) * 11.0,
        },
        dtype="float64",
    )


def verify_static_contract() -> dict[str, Any]:
    require(len(factor_tv.COLUMN_ORDER) == 142, "COLUMN_ORDER count is not 142")
    require(len(set(factor_tv.COLUMN_ORDER)) == 142, "COLUMN_ORDER contains duplicates")
    require(all(name.startswith("tv_") for name in factor_tv.COLUMN_ORDER), "non-tv output name")
    encoded = json.dumps(factor_tv.COLUMN_ORDER, ensure_ascii=False).encode("utf-8")
    column_sha = hashlib.sha256(encoded).hexdigest()
    require(column_sha == EXPECTED_COLUMN_SHA256, f"COLUMN_ORDER hash drift: {column_sha}")

    tree = ast.parse(FACTOR_SOURCE.read_text(encoding="utf-8"), filename=str(FACTOR_SOURCE))
    banned_modules = {"argparse", "importlib", "json", "pathlib", "requests", "qdh"}
    banned_calls = {"eval", "exec", "compile", "open", "__import__"}
    banned_attrs = {"open", "read_text", "read_bytes", "write_text", "write_bytes"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in banned_modules, f"banned import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            require((node.module or "").split(".")[0] not in banned_modules, f"banned import: {node.module}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                require(node.func.id not in banned_calls, f"banned call: {node.func.id}")
            elif isinstance(node.func, ast.Attribute):
                require(node.func.attr not in banned_attrs, f"banned file method: {node.func.attr}")
    return {"columns": 142, "columns_sha256": column_sha, "runtime_file_reads": False}


def verify_runtime() -> dict[str, Any]:
    frame = synthetic_frame()
    first = factor_tv.compute(frame)
    second = factor_tv.compute(frame.copy(deep=True))
    require(first.shape == (600, 142), f"unexpected output shape: {first.shape}")
    require(tuple(first.columns) == factor_tv.COLUMN_ORDER, "output order mismatch")
    require(first.index.equals(frame.index), "input index was not preserved")
    require(all(dtype == np.dtype("float64") for dtype in first.dtypes), "non-float64 output")
    a = first.to_numpy(dtype=np.float64, copy=True)
    b = second.to_numpy(dtype=np.float64, copy=True)
    require(np.array_equal(np.isnan(a), np.isnan(b)), "rerun null-mask mismatch")
    finite = np.isfinite(a)
    require(
        np.array_equal(
            np.ascontiguousarray(a[finite]).view(np.uint64),
            np.ascontiguousarray(b[finite]).view(np.uint64),
        ),
        "rerun bitwise mismatch",
    )
    require(not np.isinf(a).any(), "output contains infinity")
    require(not np.signbit(a[a == 0.0]).any(), "output contains negative zero")

    seeds = {
        "tv_obv": 0.0,
        "tv_adl": 0.0,
        "tv_pvt": 0.0,
        "tv_pvi": 1000.0,
        "tv_nvi": 1000.0,
    }
    for name, expected in seeds.items():
        require(first[name].iloc[0] == expected, f"bad cumulative seed: {name}")

    psar_starts_long = frame["close"].iloc[0] >= (
        frame["high"].iloc[0] + frame["low"].iloc[0]
    ) / 2.0
    expected_psar0 = frame["low"].iloc[0] if psar_starts_long else frame["high"].iloc[0]
    require(first["tv_psar_002_02"].iloc[0] == expected_psar0, "PSAR first state drift")
    expected_psar_dir0 = 1.0 if frame["close"].iloc[0] >= expected_psar0 else -1.0
    require(first["tv_psar_dir"].iloc[0] == expected_psar_dir0, "PSAR direction contract drift")
    tr0 = frame["high"].iloc[0] - frame["low"].iloc[0]
    hl2_0 = (frame["high"].iloc[0] + frame["low"].iloc[0]) / 2.0
    for line_name, dir_name, multiplier in (
        ("tv_supertrend_14_4_line", "tv_supertrend_14_4_dir", 4.0),
        ("tv_supertrend_10_3_line", "tv_supertrend_10_3_dir", 3.0),
        ("tv_supertrend_21_3_line", "tv_supertrend_21_3_dir", 3.0),
    ):
        require(first[dir_name].iloc[0] == 1.0, f"Supertrend first direction drift: {dir_name}")
        require(first[line_name].iloc[0] == hl2_0 + multiplier * tr0, f"Supertrend first line drift: {line_name}")
    expected_utbot0 = frame["close"].iloc[0] - tr0
    require(first["tv_utbot_trailing_stop_10_1"].iloc[0] == expected_utbot0, "UTBot first trail drift")
    require(first["tv_utbot_signal_10_1"].iloc[0] == 0.0, "UTBot first signal drift")
    require(first["tv_consecutive_up_bars"].iloc[0] == 0.0, "up-counter seed drift")
    require(first["tv_consecutive_down_bars"].iloc[0] == 0.0, "down-counter seed drift")
    ema_first_valid = {
        "tv_wavetrend_wt1_10_21": 38,
        "tv_wavetrend_wt2_4": 41,
        "tv_wavetrend_hist": 41,
        "tv_macd_custom_macd_12_26": 25,
        "tv_macd_custom_signal_9": 33,
        "tv_macd_custom_hist": 33,
        "tv_ema_8": 7,
        "tv_ema_21": 20,
        "tv_ema_34": 33,
        "tv_ema_55": 54,
        "tv_close_to_ema_21": 20,
        "tv_close_to_ema_55": 54,
        "tv_ema_8_21_gap": 20,
        "tv_ema_21_55_gap": 54,
        "tv_ppo_12_26": 25,
        "tv_ppo_signal_9": 33,
        "tv_ppo_hist": 33,
        "tv_zero_lag_macd": 50,
        "tv_zero_lag_signal": 58,
        "tv_tsi_25_13": 37,
        "tv_tsi_signal_13": 49,
        "tv_schaff_trend_cycle": 71,
        "tv_obv_ema_20": 19,
        "tv_chaikin_osc_3_10": 9,
        "tv_force_index_13": 13,
    }
    for name, first_valid in ema_first_valid.items():
        require(
            first[name].first_valid_index() == first_valid,
            f"EMA min_periods boundary drift: {name}",
        )
    require(first["tv_fisher_10"].iloc[:9].isna().all(), "Fisher emitted before its 10-row range")
    stc = first["tv_schaff_trend_cycle"].dropna()
    require(first["tv_schaff_trend_cycle"].first_valid_index() == 71, "STC first-valid boundary drift")
    require(stc.iloc[0] == 100.0, "STC first state drift")
    require(((stc >= 0.0) & (stc <= 100.0)).all(), "STC escaped [0, 100]")

    prefix_lengths = (1, 2, 10, 25, 200)
    for length in prefix_lengths:
        prefix = factor_tv.compute(frame.iloc[:length].copy())
        expected_prefix = first.iloc[:length]
        for name in factor_tv.COLUMN_ORDER:
            left = prefix[name].to_numpy(dtype=np.float64, copy=False)
            right = expected_prefix[name].to_numpy(dtype=np.float64, copy=False)
            require(np.array_equal(np.isnan(left), np.isnan(right)), f"prefix null drift: {name}@{length}")
            finite_prefix = np.isfinite(left)
            require(
                np.array_equal(
                    np.ascontiguousarray(left[finite_prefix]).view(np.uint64),
                    np.ascontiguousarray(right[finite_prefix]).view(np.uint64),
                ),
                f"future data changed prefix: {name}@{length}",
            )
    return {
        "rows": 600,
        "deterministic_bitwise": True,
        "prefix_invariance_lengths": list(prefix_lengths),
        "ema_min_periods_columns": len(ema_first_valid),
        "seeds": seeds,
    }


def verify_ema_and_mfi_policies() -> dict[str, Any]:
    values = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], dtype="float64")
    actual = factor_tv.ema(values, 4)
    expected = values.ewm(span=4, adjust=False, min_periods=4).mean()
    require(actual.iloc[:3].isna().all(), "EMA emitted before four observations")
    require(actual.first_valid_index() == 3, "EMA first-valid index drift")
    require(strict_compare(actual, expected, atol=0.0)["bad"] == 0, "EMA min_periods contract drift")

    leading_null = pd.Series([np.nan, 1.0, 2.0, 3.0, 4.0], dtype="float64")
    require(
        factor_tv.ema(leading_null, 4).first_valid_index() == 4,
        "EMA did not count non-null observations for min_periods",
    )
    actual_rma = factor_tv.rma(values, 4)
    expected_rma = values.ewm(alpha=1 / 4, adjust=False).mean()
    require(
        strict_compare(actual_rma, expected_rma, atol=0.0)["bad"] == 0,
        "RMA startup semantics changed with EMA",
    )

    rows = 20
    rising = pd.Series(np.arange(1, rows + 1, dtype=np.float64))
    falling = rising.iloc[::-1].reset_index(drop=True)
    flat = pd.Series(np.ones(rows, dtype=np.float64))
    volume = pd.Series(np.full(rows, 100.0, dtype=np.float64))
    zero_volume = pd.Series(np.zeros(rows, dtype=np.float64))
    rising_mfi = factor_tv.mfi(rising, rising, rising, volume, 14)
    falling_mfi = factor_tv.mfi(falling, falling, falling, volume, 14)
    flat_mfi = factor_tv.mfi(flat, flat, flat, zero_volume, 14)
    require(rising_mfi.iloc[13] == 100.0, "MFI positive-only window no longer resolves to 100")
    require(falling_mfi.iloc[13] == 0.0, "MFI negative-only window no longer resolves to 0")
    require(pd.isna(flat_mfi.iloc[13]), "MFI zero-over-zero window no longer resolves to null")
    return {
        "ema_min_periods": "period",
        "ema_leading_nulls_count_as_observations": False,
        "rma_startup_unchanged": True,
        "mfi_positive_only": 100.0,
        "mfi_negative_only": 0.0,
        "mfi_zero_over_zero": "null",
    }


def verify_flat_and_zero_boundaries() -> dict[str, Any]:
    frame = synthetic_frame(70)
    flat_at = 24
    flat_close = frame.loc[flat_at, "close"]
    frame.loc[flat_at, ["open", "high", "low", "close"]] = flat_close
    result = factor_tv.compute(frame)

    require(result["tv_cmf_20"].iloc[flat_at : flat_at + 20].isna().all(), "CMF flat-range null window drift")
    require(result["tv_cmf_20"].iloc[flat_at - 1] == result["tv_cmf_20"].iloc[flat_at - 1], "CMF pre-edge is null")
    require(result["tv_cmf_20"].iloc[flat_at + 20] == result["tv_cmf_20"].iloc[flat_at + 20], "CMF did not recover")
    require(result["tv_eom_14"].iloc[flat_at : flat_at + 14].isna().all(), "EOM flat-range null window drift")
    require(result["tv_close_location_value"].iloc[flat_at] != result["tv_close_location_value"].iloc[flat_at], "flat CLV is not null")
    require(result["tv_adl"].iloc[flat_at] == result["tv_adl"].iloc[flat_at - 1], "ADL flat candle increment is not zero")

    zero_volume = synthetic_frame(70)
    zero_at = 30
    zero_volume.loc[zero_at, "volume"] = 0.0
    zero_result = factor_tv.compute(zero_volume)
    require(zero_result["tv_eom_14"].iloc[zero_at : zero_at + 14].isna().all(), "EOM zero-volume null window drift")

    fisher_frame = synthetic_frame(60)
    fisher_frame.loc[20:34, ["open", "high", "low", "close"]] = 110.0
    fisher_full = factor_tv.compute(fisher_frame)
    require(fisher_full["tv_fisher_10"].iloc[29:35].isna().all(), "Fisher flat-window null contract drift")
    require(pd.notna(fisher_full["tv_fisher_10"].iloc[35]), "Fisher did not resume after flat window")
    require(pd.isna(fisher_full["tv_fisher_trigger"].iloc[35]), "Fisher trigger did not preserve shifted null")
    require(
        fisher_full["tv_fisher_trigger"].iloc[36] == fisher_full["tv_fisher_10"].iloc[35],
        "Fisher trigger resume contract drift",
    )
    fisher_restart = factor_tv.compute(fisher_frame.iloc[20:].reset_index(drop=True))
    require(
        fisher_full["tv_fisher_10"].iloc[35] != fisher_restart["tv_fisher_10"].iloc[15],
        "Fisher state was reset across a flat window",
    )

    one_sided = strict_compare(pd.Series([np.nan]), pd.Series([1.0]))
    require(one_sided == {"null_mismatches": 1, "numeric_mismatches": 0, "bad": 1}, "one-sided null was not rejected")
    return {
        "flat_index": flat_at,
        "zero_volume_index": zero_at,
        "fisher_flat_state_persisted": True,
        "one_sided_null_rejected": True,
    }


def main() -> int:
    try:
        payload = {
            "status": "PASS",
            "static": verify_static_contract(),
            "runtime": verify_runtime(),
            "ema_and_mfi_policies": verify_ema_and_mfi_policies(),
            "boundaries": verify_flat_and_zero_boundaries(),
        }
    except Exception as exc:
        payload = {"status": "FAIL", "error_type": type(exc).__name__, "error": str(exc)}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
