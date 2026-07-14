"""Deterministic native-Python reproduction core for locked Indicator-PY 59.

The module is deliberately self-contained: runtime execution does not read an
audit skill, JSON contract, formula text, or qdh metadata.  Callers must supply
one continuous, strictly ordered sequence, including any transient warmup rows;
the caller is responsible for slicing warmup rows before persistence.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd


REQUIRED_BASE_COLUMNS = (
    "high",
    "low",
    "close",
    "volume",
    "open_interest",
)

REQUIRED_WH6_COLUMNS = (
    "wh6_MACD_MACD",
    "wh6_RSI_RSI2",
    "wh6_ATR_ATR",
    "wh6_Z_SCORE_Z_SCORE",
    "wh6_u_8b96f436_BBW",
)

# Composition-runtime compatibility name.  It is an immutable alias, not a
# second source of dependency truth.
WH6_DEPENDENCIES = REQUIRED_WH6_COLUMNS

COLUMN_ORDER = (
    "indicator_py_ret_1",
    "indicator_py_ret_3",
    "indicator_py_ret_5",
    "indicator_py_ret_10",
    "indicator_py_ret_20",
    "indicator_py_momentum_5",
    "indicator_py_momentum_10",
    "indicator_py_momentum_20",
    "indicator_py_ma5_slope",
    "indicator_py_close_to_ma5",
    "indicator_py_ma10_slope",
    "indicator_py_close_to_ma10",
    "indicator_py_ma20_slope",
    "indicator_py_close_to_ma20",
    "indicator_py_ma40_slope",
    "indicator_py_close_to_ma40",
    "indicator_py_ma60_slope",
    "indicator_py_close_to_ma60",
    "indicator_py_ma120_slope",
    "indicator_py_close_to_ma120",
    "indicator_py_ma5_ma10_gap",
    "indicator_py_ma5_ma20_gap",
    "indicator_py_ma10_ma20_gap",
    "indicator_py_ma20_ma40_gap",
    "indicator_py_ma20_ma60_gap",
    "indicator_py_ma40_ma120_gap",
    "indicator_py_macd_hist_diff",
    "indicator_py_ppo",
    "indicator_py_rsi_diff",
    "indicator_py_rsi_zscore_20",
    "indicator_py_hl_pct",
    "indicator_py_tr_ratio",
    "indicator_py_atr_norm",
    "indicator_py_volatility_5",
    "indicator_py_volatility_10",
    "indicator_py_volatility_20",
    "indicator_py_vol_ratio_5_20",
    "indicator_py_break_high_20",
    "indicator_py_break_low_20",
    "indicator_py_dist_prev_high_20",
    "indicator_py_dist_prev_low_20",
    "indicator_py_pos_in_range_20",
    "indicator_py_pos_in_range_60",
    "indicator_py_close_pos",
    "indicator_py_boll_pct_b",
    "indicator_py_boll_width",
    "indicator_py_zscore_close_20",
    "indicator_py_zscore_volume_20",
    "indicator_py_close_rank_60",
    "indicator_py_volume_rank_60",
    "indicator_py_vol_ratio_5",
    "indicator_py_vol_ratio_20",
    "indicator_py_volume_diff",
    "indicator_py_oi_diff",
    "indicator_py_oi_ratio_5",
    "indicator_py_price_up_vol_up",
    "indicator_py_price_down_vol_up",
    "indicator_py_price_up_oi_up",
    "indicator_py_price_down_oi_up",
)

# Historical oracle rows collapse near-constant RSI dispersion below this
# scale to a zero denominator.  The final result remains NaN; it is never
# replaced with a synthetic z-score of zero.
ZSCORE_ZERO_STD_EPSILON = 1e-10


class IndicatorEvaluationError(RuntimeError):
    """The locked Indicator-PY contract cannot be evaluated without guessing."""


def _series(frame: pd.DataFrame, name: str) -> pd.Series:
    try:
        result = pd.to_numeric(frame[name], errors="raise").astype("float64")
    except Exception as exc:  # pragma: no cover - exact pandas error is unstable
        raise IndicatorEvaluationError(f"{name} is not a numeric float64 input") from exc
    return result


def _rolling(series: pd.Series, window: int) -> Any:
    return series.rolling(window=window, min_periods=window)


def _ma(series: pd.Series, window: int) -> pd.Series:
    return _rolling(series, window).mean()


def _ema(series: pd.Series, span: int) -> pd.Series:
    # min_periods is part of the cold-start contract.  The recursive state is
    # still accumulated from the first row, but the first span-1 results are
    # unavailable, matching the historical PPO output.
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def _pct_change(series: pd.Series, periods: int = 1) -> pd.Series:
    return series.pct_change(periods=periods, fill_method=None)


def _stable_rolling_std(series: pd.Series, window: int, ddof: int) -> pd.Series:
    """Rolling std with an exact-zero constant-window rule.

    Pandas' incremental variance can emit tiny non-zero values for a window of
    exactly equal floating-point values.  Such windows are explicitly reset to
    zero so downstream ordinary division produces NaN for 0/0 rather than an
    unstable finite ratio.
    """

    rolling = _rolling(series, window)
    result = rolling.std(ddof=ddof)
    constant = (rolling.max() - rolling.min()) == 0.0
    return result.mask(constant, 0.0)


def _zscore(series: pd.Series, window: int) -> pd.Series:
    mean = _ma(series, window)
    std = _stable_rolling_std(series, window, ddof=0)
    # Near-zero recursive RSI windows in the legacy oracle are undefined.  Set
    # the denominator to exact zero, then preserve normal IEEE division; final
    # +/-Inf is normalized to NaN by compute().
    denominator = std.mask(std.abs() < ZSCORE_ZERO_STD_EPSILON, 0.0)
    return (series - mean) / denominator


def _rolling_rank_pct(series: pd.Series, window: int) -> pd.Series:
    # Explicit average-tie and ascending semantics.  A tied terminal value gets
    # the average one-based rank divided by the full window length.
    return _rolling(series, window).rank(method="average", ascending=True, pct=True)


def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    # Row-wise max ignores unavailable previous-close terms.  Thus a genuine
    # cold-start row uses high-low rather than becoming spuriously null.
    return pd.concat(
        (
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ),
        axis=1,
    ).max(axis=1, skipna=True)


def _mask_first_valid(series: pd.Series) -> pd.Series:
    """Preserve the historical one-row derived-RSI cold-start mask."""

    result = series.copy()
    valid = np.flatnonzero(result.notna().to_numpy())
    if len(valid):
        result.iloc[int(valid[0])] = np.nan
    return result


def _normalise_output(value: Any, index: pd.Index) -> pd.Series:
    if isinstance(value, pd.Series):
        result = value.reindex(index)
    elif np.isscalar(value):
        result = pd.Series(value, index=index)
    else:
        array = np.asarray(value)
        if len(array) != len(index):
            raise IndicatorEvaluationError("formula returned an array of the wrong length")
        result = pd.Series(array, index=index)
    result = pd.to_numeric(result, errors="raise").astype("float64")
    return result.replace([np.inf, -np.inf], np.nan)


def compute(frame: pd.DataFrame) -> pd.DataFrame:
    """Compute the locked 59 columns for one continuous input sequence."""

    if not isinstance(frame, pd.DataFrame):
        raise IndicatorEvaluationError("input must be a pandas DataFrame")
    required = REQUIRED_BASE_COLUMNS + REQUIRED_WH6_COLUMNS
    missing = [name for name in required if name not in frame.columns]
    if missing:
        raise IndicatorEvaluationError(f"missing input columns: {missing}")
    if not frame.index.is_unique:
        raise IndicatorEvaluationError("input index must be unique")

    high = _series(frame, "high")
    low = _series(frame, "low")
    close = _series(frame, "close")
    volume = _series(frame, "volume")
    open_interest = _series(frame, "open_interest")
    wh6_macd = _series(frame, "wh6_MACD_MACD")
    wh6_rsi2 = _series(frame, "wh6_RSI_RSI2")
    wh6_atr = _series(frame, "wh6_ATR_ATR")
    wh6_zscore = _series(frame, "wh6_Z_SCORE_Z_SCORE")
    wh6_bbw = _series(frame, "wh6_u_8b96f436_BBW")

    ma5 = _ma(close, 5)
    ma10 = _ma(close, 10)
    ma20 = _ma(close, 20)
    ma40 = _ma(close, 40)
    ma60 = _ma(close, 60)
    ma120 = _ma(close, 120)
    ret_1 = _pct_change(close)
    vol5 = _stable_rolling_std(ret_1, 5, ddof=1)
    vol10 = _stable_rolling_std(ret_1, 10, ddof=1)
    vol20 = _stable_rolling_std(ret_1, 20, ddof=1)
    previous_high20 = _rolling(high, 20).max().shift(1)
    previous_low20 = _rolling(low, 20).min().shift(1)
    high20 = _rolling(high, 20).max()
    low20 = _rolling(low, 20).min()
    high60 = _rolling(high, 60).max()
    low60 = _rolling(low, 60).min()
    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)
    true_range = _true_range(high, low, close)
    # Indicator-PY historically exposed ATR one row before the locked WH6 ATR
    # became available on a genuine cold start.  Prefer the canonical WH6
    # dependency everywhere it exists and fill only that unavailable prefix
    # from the equivalent 14-row market ATR.
    indicator_atr = wh6_atr.combine_first(_ma(true_range, 14))
    rsi_diff = _mask_first_valid(wh6_rsi2.diff())
    rsi_zscore = _mask_first_valid(_zscore(wh6_rsi2, 20))

    with np.errstate(all="ignore"):
        values: dict[str, Any] = {
            "indicator_py_ret_1": _pct_change(close, 1),
            "indicator_py_ret_3": _pct_change(close, 3),
            "indicator_py_ret_5": _pct_change(close, 5),
            "indicator_py_ret_10": _pct_change(close, 10),
            "indicator_py_ret_20": _pct_change(close, 20),
            "indicator_py_momentum_5": close - close.shift(5),
            "indicator_py_momentum_10": close - close.shift(10),
            "indicator_py_momentum_20": close - close.shift(20),
            "indicator_py_ma5_slope": _pct_change(ma5),
            "indicator_py_close_to_ma5": (close - ma5) / ma5,
            "indicator_py_ma10_slope": _pct_change(ma10),
            "indicator_py_close_to_ma10": (close - ma10) / ma10,
            "indicator_py_ma20_slope": _pct_change(ma20),
            "indicator_py_close_to_ma20": (close - ma20) / ma20,
            "indicator_py_ma40_slope": _pct_change(ma40),
            "indicator_py_close_to_ma40": (close - ma40) / ma40,
            "indicator_py_ma60_slope": _pct_change(ma60),
            "indicator_py_close_to_ma60": (close - ma60) / ma60,
            "indicator_py_ma120_slope": _pct_change(ma120),
            "indicator_py_close_to_ma120": (close - ma120) / ma120,
            "indicator_py_ma5_ma10_gap": (ma5 - ma10) / ma10,
            "indicator_py_ma5_ma20_gap": (ma5 - ma20) / ma20,
            "indicator_py_ma10_ma20_gap": (ma10 - ma20) / ma20,
            "indicator_py_ma20_ma40_gap": (ma20 - ma40) / ma40,
            "indicator_py_ma20_ma60_gap": (ma20 - ma60) / ma60,
            "indicator_py_ma40_ma120_gap": (ma40 - ma120) / ma120,
            "indicator_py_macd_hist_diff": (wh6_macd / 2.0).diff(),
            "indicator_py_ppo": (ema12 - ema26) / ema26,
            "indicator_py_rsi_diff": rsi_diff,
            "indicator_py_rsi_zscore_20": rsi_zscore,
            "indicator_py_hl_pct": (high - low) / close,
            "indicator_py_tr_ratio": true_range / close,
            "indicator_py_atr_norm": indicator_atr / close,
            "indicator_py_volatility_5": vol5,
            "indicator_py_volatility_10": vol10,
            "indicator_py_volatility_20": vol20,
            "indicator_py_vol_ratio_5_20": vol5 / vol20,
            "indicator_py_break_high_20": (close > previous_high20).astype("float64"),
            "indicator_py_break_low_20": (close < previous_low20).astype("float64"),
            "indicator_py_dist_prev_high_20": (close - previous_high20) / previous_high20,
            "indicator_py_dist_prev_low_20": (close - previous_low20) / previous_low20,
            "indicator_py_pos_in_range_20": (close - low20) / (high20 - low20),
            "indicator_py_pos_in_range_60": (close - low60) / (high60 - low60),
            "indicator_py_close_pos": (close - low) / (high - low),
            "indicator_py_boll_pct_b": 0.5 + wh6_zscore / 4.0,
            "indicator_py_boll_width": wh6_bbw,
            "indicator_py_zscore_close_20": wh6_zscore,
            "indicator_py_zscore_volume_20": _zscore(volume, 20),
            "indicator_py_close_rank_60": _rolling_rank_pct(close, 60),
            "indicator_py_volume_rank_60": _rolling_rank_pct(volume, 60),
            "indicator_py_vol_ratio_5": volume / _ma(volume, 5),
            "indicator_py_vol_ratio_20": volume / _ma(volume, 20),
            "indicator_py_volume_diff": volume.diff(),
            "indicator_py_oi_diff": open_interest.diff(),
            "indicator_py_oi_ratio_5": open_interest / _ma(open_interest, 5),
            "indicator_py_price_up_vol_up": (
                (close > close.shift(1)) & (volume > volume.shift(1))
            ).astype("float64"),
            "indicator_py_price_down_vol_up": (
                (close < close.shift(1)) & (volume > volume.shift(1))
            ).astype("float64"),
            "indicator_py_price_up_oi_up": (
                (close > close.shift(1)) & (open_interest > open_interest.shift(1))
            ).astype("float64"),
            "indicator_py_price_down_oi_up": (
                (close < close.shift(1)) & (open_interest > open_interest.shift(1))
            ).astype("float64"),
        }

    if tuple(values) != COLUMN_ORDER:
        raise IndicatorEvaluationError("internal output order no longer matches locked 59")
    result = pd.DataFrame(
        {name: _normalise_output(values[name], frame.index) for name in COLUMN_ORDER},
        index=frame.index,
    )
    if list(result.columns) != list(COLUMN_ORDER) or result.shape[1] != 59:
        raise IndicatorEvaluationError("output contract violation")
    return result


def selftest() -> dict[str, Any]:
    """Run deterministic, null, boolean, std, and rank semantic checks."""

    rows = 400
    x = np.arange(rows, dtype="float64")
    close = 100.0 + 0.03 * x + np.sin(x / 7.0)
    frame = pd.DataFrame(
        {
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1000.0 + (x % 17.0) * 10.0,
            "open_interest": 5000.0 + (x % 23.0),
            "wh6_MACD_MACD": np.sin(x / 11.0),
            "wh6_RSI_RSI2": 50.0 + 10.0 * np.sin(x / 13.0),
            "wh6_ATR_ATR": np.full(rows, 2.0),
            "wh6_Z_SCORE_Z_SCORE": np.sin(x / 5.0),
            "wh6_u_8b96f436_BBW": np.full(rows, 0.04),
        }
    )
    first = compute(frame)
    second = compute(frame.copy())
    if first.shape != (rows, 59) or tuple(first.columns) != COLUMN_ORDER:
        raise AssertionError("shape/order selftest failed")
    for column in COLUMN_ORDER:
        left = first[column].to_numpy(dtype="float64")
        right = second[column].to_numpy(dtype="float64")
        if not np.array_equal(np.isnan(left), np.isnan(right)):
            raise AssertionError(f"null determinism failed: {column}")
        valid = np.isfinite(left) & np.isfinite(right)
        if not np.array_equal(left[valid].view("uint64"), right[valid].view("uint64")):
            raise AssertionError(f"bit determinism failed: {column}")
        if np.isinf(left).any() or first[column].dtype != np.dtype("float64"):
            raise AssertionError(f"float64/Inf contract failed: {column}")

    constant = frame.copy()
    constant[["high", "low", "close"]] = (101.0, 99.0, 100.0)
    constant["volume"] = 1000.0
    constant_result = compute(constant)
    if not np.isnan(constant_result.loc[25, "indicator_py_vol_ratio_5_20"]):
        raise AssertionError("constant-return 0/0 must be NaN")
    if not np.isnan(constant_result.loc[25, "indicator_py_zscore_volume_20"]):
        raise AssertionError("constant-volume z-score must be NaN")
    if constant_result.loc[0, "indicator_py_tr_ratio"] != 0.02:
        raise AssertionError("cold-start true range must use high-low")
    if not np.isnan(constant_result.loc[24, "indicator_py_ppo"]):
        raise AssertionError("PPO must preserve its 26-row cold-start mask")
    if constant_result.loc[25, "indicator_py_ppo"] != 0.0:
        raise AssertionError("PPO first valid constant result must be zero")

    boolean_columns = (
        "indicator_py_break_high_20",
        "indicator_py_break_low_20",
        "indicator_py_price_up_vol_up",
        "indicator_py_price_down_vol_up",
        "indicator_py_price_up_oi_up",
        "indicator_py_price_down_oi_up",
    )
    for column in boolean_columns:
        values = set(first[column].dropna().unique())
        if not values.issubset({0.0, 1.0}) or first[column].isna().any():
            raise AssertionError(f"boolean encoding failed: {column}")

    tied = pd.Series(np.arange(60, dtype="float64"))
    tied.iloc[1] = tied.iloc[2]
    rank = _rolling_rank_pct(tied, 60).iloc[-1]
    if rank != 1.0:
        raise AssertionError("rank terminal maximum selftest failed")
    tied.iloc[-1] = tied.iloc[-2]
    expected_average_rank = 59.5 / 60.0
    if _rolling_rank_pct(tied, 60).iloc[-1] != expected_average_rank:
        raise AssertionError("average-tie rolling rank selftest failed")

    return {
        "status": "PASS",
        "implementation": "native_python_indicator_locked_59_v1",
        "rows": rows,
        "columns": len(COLUMN_ORDER),
        "required_base_columns": list(REQUIRED_BASE_COLUMNS),
        "required_wh6_columns": list(REQUIRED_WH6_COLUMNS),
        "runtime_contract_reads": False,
        "checks": [
            "repeat_bitwise",
            "float64_no_inf",
            "constant_std_zero_then_0_over_0_nan",
            "ppo_cold_start_mask",
            "true_range_cold_start",
            "boolean_float64",
            "rank_average_ties",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(selftest(), ensure_ascii=False, indent=2))
