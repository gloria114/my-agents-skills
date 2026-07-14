#!/usr/bin/env python3
"""Deterministic production core for the locked 66 ``excel_`` factors.

The caller must provide one complete, strictly ordered symbol/timeframe
sequence containing every available pre-2020 ClickHouse warmup row followed by
the live market rows.  This module computes the whole sequence; the caller is
responsible for slicing warmup rows before output.

Formula semantics are embedded directly in Python.  Runtime execution never
reads the audit skill, its JSON contract, the source workbook, or any formula
file.  EMA always means pandas ``ewm(span=N, adjust=False)`` with the ordinary
full-history seed; there is no masked/auto alternative.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np
import pandas as pd


CORE_VERSION = "excel-locked-66-production-v1"
SEMANTICS = "full-history-ch-warmup/plain-ewm-adjust-false/float64"
REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")

COLUMN_ORDER = (
    "excel_ER_bull_power_20",
    "excel_ER_bear_power_20",
    "excel_TII_40_21",
    "excel_TII_signal_9",
    "excel_PO_9_26",
    "excel_MADisplaced_20_10",
    "excel_POS_100",
    "excel_PAC_upper_20",
    "excel_PAC_lower_20",
    "excel_ZLMACD_20_100",
    "excel_TMA_20",
    "excel_TYP",
    "excel_TYPMA1_10",
    "excel_TYPMA2_30",
    "excel_VMA_20",
    "excel_WMA_20",
    "excel_HMA_high_20",
    "excel_SROC_13_21",
    "excel_EXPMA_12",
    "excel_EXPMA_50",
    "excel_DC_upper_20",
    "excel_DC_lower_20",
    "excel_DC_middle_20",
    "excel_VIDYA_10",
    "excel_Qstick_20",
    "excel_FB_upper_1_618",
    "excel_FB_lower_1_618",
    "excel_FB_upper_2_618",
    "excel_FB_lower_2_618",
    "excel_FB_upper_4_236",
    "excel_FB_lower_4_236",
    "excel_DEMA_60",
    "excel_APZ_upper_10_20",
    "excel_APZ_lower_10_20",
    "excel_KC_upper_14_20",
    "excel_KC_lower_14_20",
    "excel_BOP_20",
    "excel_ENV_upper_25_5pct",
    "excel_ENV_lower_25_5pct",
    "excel_RSIH_40_120",
    "excel_HLMA_high_20",
    "excel_HLMA_low_20",
    "excel_TRIX_20",
    "excel_WC_ema20",
    "excel_WC_ema40",
    "excel_Demarker_20",
    "excel_TSI_25_13",
    "excel_IMI_14",
    "excel_CMO_20",
    "excel_OSC_40",
    "excel_OSCMA_20",
    "excel_CLV",
    "excel_CLVMA_60",
    "excel_TEMA_20",
    "excel_TEMA_40",
    "excel_PVO_12_26",
    "excel_BIASVOL_6",
    "excel_BIASVOL_12",
    "excel_BIASVOL_24",
    "excel_MACDVOL_20_40",
    "excel_MACDVOL_signal_10",
    "excel_ROCVOL_80",
    "excel_VWAP_20",
    "excel_FI_13",
    "excel_MAAMT_40",
    "excel_SROCVOL_20_10",
)


class ExcelFactorError(RuntimeError):
    """The input or output violates the locked production contract."""


def _series(frame: pd.DataFrame, name: str) -> pd.Series:
    try:
        result = pd.to_numeric(frame[name], errors="raise").astype("float64")
    except Exception as exc:
        raise ExcelFactorError(f"{name} cannot be converted to float64") from exc
    values = result.to_numpy(dtype=np.float64, copy=False)
    if not np.isfinite(values).all():
        raise ExcelFactorError(f"{name} contains null, NaN, or infinite input")
    return result


def _ma(value: pd.Series, window: int) -> pd.Series:
    return value.rolling(window, min_periods=window).mean()


def _ema(value: pd.Series, span: int) -> pd.Series:
    return value.ewm(span=span, adjust=False).mean()


def _sum(value: pd.Series, window: int) -> pd.Series:
    return value.rolling(window, min_periods=window).sum()


def _highest(value: pd.Series, window: int) -> pd.Series:
    return value.rolling(window, min_periods=window).max()


def _lowest(value: pd.Series, window: int) -> pd.Series:
    return value.rolling(window, min_periods=window).min()


def _safe_divide(numerator: Any, denominator: Any) -> pd.Series:
    """Divide as float64, mapping zero/non-finite denominators to NaN."""

    if isinstance(numerator, pd.Series):
        index = numerator.index
    elif isinstance(denominator, pd.Series):
        index = denominator.index
    else:  # Every production call has at least one Series; keep failure clear.
        raise ExcelFactorError("safe division requires a Series operand")
    left = pd.Series(numerator, index=index, dtype="float64")
    right = pd.Series(denominator, index=index, dtype="float64")
    invalid = right.isna() | ~np.isfinite(right) | right.eq(0.0)
    with np.errstate(all="ignore"):
        result = left / right.mask(invalid)
    return result.replace([np.inf, -np.inf], np.nan).astype("float64")


def _smooth_sma(value: pd.Series, window: int, weight: int = 1) -> pd.Series:
    """Wenhua/Tongdaxin recursive SMA with first-valid-value seeding."""

    raw = value.to_numpy(dtype=np.float64, copy=False)
    output = np.full(len(raw), np.nan, dtype=np.float64)
    previous = np.nan
    for index, current in enumerate(raw):
        if np.isnan(current):
            output[index] = previous
            continue
        previous = (
            current
            if np.isnan(previous)
            else (weight * current + (window - weight) * previous) / window
        )
        output[index] = previous
    return pd.Series(output, index=value.index, dtype="float64")


def _wma(value: pd.Series, window: int) -> pd.Series:
    weights = np.arange(1, window + 1, dtype=np.float64)
    denominator = float(weights.sum())
    return value.rolling(window, min_periods=window).apply(
        lambda rows: float(np.dot(rows, weights) / denominator), raw=True
    )


def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    return pd.concat(
        (high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()),
        axis=1,
    ).max(axis=1, skipna=True)


def _finite_output(value: Any, index: pd.Index) -> pd.Series:
    result = pd.Series(value, index=index, dtype="float64")
    return result.replace([np.inf, -np.inf], np.nan).astype("float64")


def compute(frame: pd.DataFrame) -> pd.DataFrame:
    """Compute locked Excel 66 factors for one complete ordered sequence."""

    if not isinstance(frame, pd.DataFrame):
        raise ExcelFactorError("frame must be a pandas DataFrame")
    missing = [name for name in REQUIRED_COLUMNS if name not in frame.columns]
    if missing:
        raise ExcelFactorError(f"missing input columns: {missing}")
    if frame.empty:
        raise ExcelFactorError("frame must contain at least one history row")
    if not frame.index.is_unique:
        raise ExcelFactorError("frame index must be unique")
    if not frame.index.is_monotonic_increasing:
        raise ExcelFactorError("frame must be ordered from oldest to newest")

    open_ = _series(frame, "open")
    high = _series(frame, "high")
    low = _series(frame, "low")
    close = _series(frame, "close")
    volume = _series(frame, "volume")
    index = frame.index
    output: dict[str, pd.Series] = {}

    ema20 = _ema(close, 20)
    output["excel_ER_bull_power_20"] = high - ema20
    output["excel_ER_bear_power_20"] = low - ema20

    close_ma40 = _ma(close, 40)
    deviation = close - close_ma40
    positive_deviation = deviation.where(deviation > 0, 0.0)
    negative_deviation = (-deviation).where(deviation < 0, 0.0)
    positive_sum = _sum(positive_deviation, 21)
    negative_sum = _sum(negative_deviation, 21)
    tii = 100.0 * _safe_divide(positive_sum, positive_sum + negative_sum)
    output["excel_TII_40_21"] = tii
    output["excel_TII_signal_9"] = _ema(tii, 9)

    ema9 = _ema(close, 9)
    ema26 = _ema(close, 26)
    output["excel_PO_9_26"] = 100.0 * _safe_divide(ema9 - ema26, ema26)
    output["excel_MADisplaced_20_10"] = _ma(close, 20).shift(10)

    price100 = _safe_divide(close - close.shift(100), close.shift(100))
    price100_low = _lowest(price100, 100)
    price100_high = _highest(price100, 100)
    output["excel_POS_100"] = _safe_divide(
        price100 - price100_low, price100_high - price100_low
    )

    output["excel_PAC_upper_20"] = _smooth_sma(high, 20, 1)
    output["excel_PAC_lower_20"] = _smooth_sma(low, 20, 1)

    dema20 = 2.0 * _ema(close, 20) - _ema(_ema(close, 20), 20)
    dema100 = 2.0 * _ema(close, 100) - _ema(_ema(close, 100), 100)
    output["excel_ZLMACD_20_100"] = dema20 - dema100
    output["excel_TMA_20"] = _ma(_ma(close, 20), 20)

    typical = (close + high + low) / 3.0
    output["excel_TYP"] = typical
    output["excel_TYPMA1_10"] = _ema(typical, 10)
    output["excel_TYPMA2_30"] = _ema(typical, 30)
    output["excel_VMA_20"] = _ma((high + low + open_ + close) / 4.0, 20)
    output["excel_WMA_20"] = _wma(close, 20)
    output["excel_HMA_high_20"] = _ma(high, 20)

    ema13 = _ema(close, 13)
    output["excel_SROC_13_21"] = _safe_divide(
        ema13 - ema13.shift(21), ema13.shift(21)
    )
    output["excel_EXPMA_12"] = _ema(close, 12)
    output["excel_EXPMA_50"] = _ema(close, 50)

    dc_upper = _highest(high, 20)
    dc_lower = _lowest(low, 20)
    output["excel_DC_upper_20"] = dc_upper
    output["excel_DC_lower_20"] = dc_lower
    output["excel_DC_middle_20"] = (dc_upper + dc_lower) / 2.0

    variability = _safe_divide(
        (close - close.shift(10)).abs(), _sum((close - close.shift(1)).abs(), 10)
    )
    output["excel_VIDYA_10"] = variability * close + (1.0 - variability) * close.shift(1)
    output["excel_Qstick_20"] = _ma(close - open_, 20)

    true_range = _true_range(high, low, close)
    atr20 = _ma(true_range, 20)
    middle20 = _ma(close, 20)
    for multiplier, label in ((1.618, "1_618"), (2.618, "2_618"), (4.236, "4_236")):
        output[f"excel_FB_upper_{label}"] = middle20 + multiplier * atr20
        output[f"excel_FB_lower_{label}"] = middle20 - multiplier * atr20

    ema60 = _ema(close, 60)
    output["excel_DEMA_60"] = 2.0 * ema60 - _ema(ema60, 60)

    apz_volatility = _ema(_ema(high - low, 10), 10)
    apz_base = _ema(_ema(close, 20), 20)
    output["excel_APZ_upper_10_20"] = apz_base + 2.0 * apz_volatility
    output["excel_APZ_lower_10_20"] = apz_base - 2.0 * apz_volatility

    atr14 = _ma(true_range, 14)
    kc_middle = _ema(close, 20)
    output["excel_KC_upper_14_20"] = kc_middle + 2.0 * atr14
    output["excel_KC_lower_14_20"] = kc_middle - 2.0 * atr14
    output["excel_BOP_20"] = _ma(_safe_divide(close - open_, high - low), 20)

    envelope = _ma(close, 25)
    output["excel_ENV_upper_25_5pct"] = envelope * 1.05
    output["excel_ENV_lower_25_5pct"] = envelope * 0.95

    difference = close - close.shift(1)
    upward = difference.where(difference > 0, 0.0)
    upward.loc[difference.isna()] = np.nan
    rsi = 100.0 * _safe_divide(
        _smooth_sma(upward, 40, 1), _smooth_sma(difference.abs(), 40, 1)
    )
    output["excel_RSIH_40_120"] = rsi - _ema(rsi, 120)
    output["excel_HLMA_high_20"] = _ma(high, 20)
    output["excel_HLMA_low_20"] = _ma(low, 20)

    triple_ema = _ema(_ema(_ema(close, 20), 20), 20)
    output["excel_TRIX_20"] = _safe_divide(
        triple_ema - triple_ema.shift(1), triple_ema.shift(1)
    )

    weighted_close = (high + low + 2.0 * close) / 4.0
    output["excel_WC_ema20"] = _ema(weighted_close, 20)
    output["excel_WC_ema40"] = _ema(weighted_close, 40)

    demax = (high - high.shift(1)).where((high - high.shift(1)) > 0, 0.0)
    demin = (low.shift(1) - low).where((low.shift(1) - low) > 0, 0.0)
    demax20 = _ma(demax, 20)
    demin20 = _ma(demin, 20)
    output["excel_Demarker_20"] = _safe_divide(demax20, demax20 + demin20)

    momentum = close - close.shift(1)
    output["excel_TSI_25_13"] = 100.0 * _safe_divide(
        _ema(_ema(momentum, 25), 13), _ema(_ema(momentum.abs(), 25), 13)
    )

    increase = (close - open_).where(close > open_, 0.0)
    decrease = (open_ - close).where(open_ > close, 0.0)
    increase14 = _sum(increase, 14)
    decrease14 = _sum(decrease, 14)
    output["excel_IMI_14"] = _safe_divide(increase14, increase14 + decrease14)

    upward_sum = _sum(difference.clip(lower=0), 20)
    downward_sum = _sum((-difference).clip(lower=0), 20)
    output["excel_CMO_20"] = 100.0 * _safe_divide(
        upward_sum - downward_sum, upward_sum + downward_sum
    )

    oscillator = close - _ma(close, 40)
    output["excel_OSC_40"] = oscillator
    output["excel_OSCMA_20"] = _ma(oscillator, 20)
    clv = _safe_divide(2.0 * close - low - high, high - low)
    output["excel_CLV"] = clv
    output["excel_CLVMA_60"] = _ma(clv, 60)

    for window in (20, 40):
        ema1 = _ema(close, window)
        ema2 = _ema(ema1, window)
        ema3 = _ema(ema2, window)
        output[f"excel_TEMA_{window}"] = 3.0 * ema1 - 3.0 * ema2 + ema3

    volume_ema12 = _ema(volume, 12)
    volume_ema26 = _ema(volume, 26)
    output["excel_PVO_12_26"] = _safe_divide(
        volume_ema12 - volume_ema26, volume_ema26
    )
    for window in (6, 12, 24):
        volume_ma = _ma(volume, window)
        output[f"excel_BIASVOL_{window}"] = _safe_divide(
            volume - volume_ma, volume_ma
        )

    volume_ema20 = _ema(volume, 20)
    macd_volume = volume_ema20 - _ema(volume, 40)
    output["excel_MACDVOL_20_40"] = macd_volume
    output["excel_MACDVOL_signal_10"] = _ma(macd_volume, 10)
    output["excel_ROCVOL_80"] = _safe_divide(
        volume - volume.shift(80), volume.shift(80)
    )
    output["excel_VWAP_20"] = _safe_divide(
        _sum(volume * typical, 20), _sum(volume, 20)
    )
    output["excel_FI_13"] = _ema((close - close.shift(1)) * volume, 13)
    output["excel_MAAMT_40"] = _ma(close * volume, 40)
    output["excel_SROCVOL_20_10"] = _safe_divide(
        volume_ema20 - volume_ema20.shift(10), volume_ema20.shift(10)
    )

    if tuple(output) != COLUMN_ORDER:
        raise ExcelFactorError("internal output binding/order mismatch")
    result = pd.DataFrame(
        {name: _finite_output(output[name], index) for name in COLUMN_ORDER},
        index=index,
    )
    if tuple(result.columns) != COLUMN_ORDER or result.shape[1] != 66:
        raise ExcelFactorError("locked 66 output contract violation")
    if any(dtype != np.dtype("float64") for dtype in result.dtypes):
        raise ExcelFactorError("all outputs must be float64")
    return result


def _bitwise_equal(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    for name in COLUMN_ORDER:
        a = left[name].to_numpy(dtype=np.float64, copy=False)
        b = right[name].to_numpy(dtype=np.float64, copy=False)
        if not np.array_equal(np.isnan(a), np.isnan(b)):
            return False
        valid = ~(np.isnan(a) | np.isnan(b))
        if not np.array_equal(a[valid].view(np.uint64), b[valid].view(np.uint64)):
            return False
    return True


def selftest() -> dict[str, Any]:
    """Run deterministic structural and edge-case checks without file I/O."""

    rows = 800
    position = np.arange(rows, dtype=np.float64)
    close = 100.0 + 0.017 * position + np.sin(position / 11.0)
    open_ = close + 0.15 * np.cos(position / 7.0)
    spread = 0.5 + 0.1 * np.sin(position / 13.0) ** 2
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    volume = 1000.0 + (position % 37.0) * 11.0
    # Exercise every zero-denominator path without introducing invalid input.
    high[120:145] = close[120:145]
    low[120:145] = close[120:145]
    volume[0] = 0.0
    volume[260:285] = 0.0
    frame = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=pd.RangeIndex(rows),
    )
    first = compute(frame)
    second = compute(frame.copy())
    if not _bitwise_equal(first, second):
        raise ExcelFactorError("repeated computation is not bitwise deterministic")
    if np.isinf(first.to_numpy(dtype=np.float64)).any():
        raise ExcelFactorError("selftest produced an infinite output")
    if first.loc[0, "excel_EXPMA_12"] != close[0]:
        raise ExcelFactorError("plain EMA did not seed from the first history row")
    if first.loc[0, "excel_PAC_upper_20"] != high[0]:
        raise ExcelFactorError("recursive SMA seed mismatch")
    if not np.isnan(first.loc[80, "excel_ROCVOL_80"]):
        raise ExcelFactorError("zero ROCVOL denominator did not become NaN")
    if not np.isnan(first.loc[139, "excel_BOP_20"]):
        raise ExcelFactorError("zero candle-range denominator did not propagate NaN")
    columns_sha256 = hashlib.sha256(
        json.dumps(COLUMN_ORDER, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "status": "PASS",
        "core_version": CORE_VERSION,
        "semantics": SEMANTICS,
        "rows": rows,
        "columns": len(COLUMN_ORDER),
        "columns_sha256": columns_sha256,
        "deterministic_bitwise": True,
        "infinite_values": 0,
        "zero_denominator_to_nan": True,
    }


if __name__ == "__main__":
    print(json.dumps(selftest(), ensure_ascii=False, indent=2))
