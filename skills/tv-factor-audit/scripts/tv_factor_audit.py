#!/usr/bin/env python3
"""只读审计 locked 142 个 tv_ TradingView 因子。"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SKILL_DIR = Path(__file__).resolve().parents[1]
CONTRACT_PATH = SKILL_DIR / "references" / "tv-locked-142-contract.json"

BASE_COLUMNS = ["open", "high", "low", "close", "volume"]
CUMULATIVE_COLUMNS = {
    "tv_obv",
    "tv_obv_ema_20",
    "tv_adl",
    "tv_pvt",
    "tv_pvi",
    "tv_nvi",
}

COLUMN_ABS_TOL = {
    # 短历史文件上 DEMA/EMA 递归初始化会留下极小尾差。
    "tv_zero_lag_macd": 1e-3,
    "tv_zero_lag_signal": 1e-3,
    # STC 在长时间 0/100 饱和后会出现少量 Pine 状态边界微差。
    "tv_schaff_trend_cycle": 5e-1,
}

EXCLUDE_FILE_NAMES = {
    "all_symbols_all_periods_summary.csv",
    "liquidity_screen.csv",
}
EXCLUDE_SUFFIXES = (
    "_indicator_audit.csv",
    "_null_summary.csv",
    "_summary.csv",
)


def load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


CONTRACT = load_contract()
TV_COLUMNS = list(CONTRACT["columns"])


def clean_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").replace([np.inf, -np.inf], np.nan)


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rma(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1 / n, adjust=False).mean()


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def stdev(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).std(ddof=0)


def highest(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).max()


def lowest(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).min()


def wma(s: pd.Series, n: int) -> pd.Series:
    weights = np.arange(1, n + 1, dtype=float)
    denom = weights.sum()
    return s.rolling(n, min_periods=n).apply(lambda a: float(np.dot(a, weights) / denom), raw=True)


def hma(s: pd.Series, n: int) -> pd.Series:
    return wma(2 * wma(s, int(n / 2)) - wma(s, n), int(math.sqrt(n)))


def alma(s: pd.Series, n: int, offset: float = 0.85, sigma: float = 6.0) -> pd.Series:
    m = offset * (n - 1)
    ss = n / sigma
    weights = np.exp(-((np.arange(n) - m) ** 2) / (2 * ss * ss))
    weights = weights / weights.sum()
    return s.rolling(n, min_periods=n).apply(lambda a: float(np.dot(a, weights)), raw=True)


def rolling_linreg_value(s: pd.Series, n: int, offset: int = 0) -> pd.Series:
    x = np.arange(n, dtype=float)
    sx = x.sum()
    sx2 = (x * x).sum()
    denom = n * sx2 - sx * sx

    def calc(a: np.ndarray) -> float:
        sy = a.sum()
        slope = (n * np.dot(x, a) - sx * sy) / denom
        intercept = (sy - slope * sx) / n
        return float(intercept + slope * (n - 1 - offset))

    return s.rolling(n, min_periods=n).apply(calc, raw=True)


def rolling_linreg_slope(s: pd.Series, n: int) -> pd.Series:
    x = np.arange(n, dtype=float)
    sx = x.sum()
    sx2 = (x * x).sum()
    denom = n * sx2 - sx * sx
    return s.rolling(n, min_periods=n).apply(
        lambda a: float((n * np.dot(x, a) - sx * a.sum()) / denom),
        raw=True,
    )


def range_percentile_last(a: np.ndarray) -> float:
    last = a[-1]
    lt = np.sum(a < last)
    eq = np.sum(a == last)
    return float((lt + (eq + 1) / 2) / len(a))


def true_range(h: pd.Series, l: pd.Series, c: pd.Series) -> pd.Series:
    return pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)


def parabolic_sar(h: pd.Series, l: pd.Series, c: pd.Series) -> tuple[pd.Series, pd.Series]:
    out = pd.Series(np.nan, index=c.index, dtype=float)
    direction = pd.Series(np.nan, index=c.index, dtype=float)
    if len(c) < 2:
        return out, direction

    long_pos = c.iloc[1] > c.iloc[0]
    ep = h.iloc[0] if long_pos else l.iloc[0]
    sar = l.iloc[0] if long_pos else h.iloc[0]
    af = 0.02
    out.iloc[0] = sar
    direction.iloc[0] = 1 if long_pos else -1

    for i in range(1, len(c)):
        sar = sar + af * (ep - sar)
        if long_pos:
            sar = min(sar, l.iloc[i - 1], l.iloc[i - 2] if i > 1 else l.iloc[i - 1])
            if l.iloc[i] < sar:
                long_pos = False
                sar = ep
                ep = l.iloc[i]
                af = 0.02
            elif h.iloc[i] > ep:
                ep = h.iloc[i]
                af = min(af + 0.02, 0.2)
        else:
            sar = max(sar, h.iloc[i - 1], h.iloc[i - 2] if i > 1 else h.iloc[i - 1])
            if h.iloc[i] > sar:
                long_pos = True
                sar = ep
                ep = h.iloc[i]
                af = 0.02
            elif l.iloc[i] < ep:
                ep = l.iloc[i]
                af = min(af + 0.02, 0.2)
        out.iloc[i] = sar
        direction.iloc[i] = 1 if long_pos else -1
    return out, direction


def supertrend(
    h: pd.Series,
    l: pd.Series,
    c: pd.Series,
    atr_values: pd.Series,
    period: int,
    mult: float,
) -> tuple[pd.Series, pd.Series]:
    hl2 = (h + l) / 2
    upper = hl2 + mult * atr_values
    lower = hl2 - mult * atr_values
    final_upper = pd.Series(np.nan, index=c.index, dtype=float)
    final_lower = pd.Series(np.nan, index=c.index, dtype=float)
    line = pd.Series(np.nan, index=c.index, dtype=float)
    direction = pd.Series(np.nan, index=c.index, dtype=float)

    for i in range(len(c)):
        if i == 0:
            final_upper.iloc[i] = upper.iloc[i]
            final_lower.iloc[i] = lower.iloc[i]
            line.iloc[i] = upper.iloc[i]
            direction.iloc[i] = 1
            continue

        final_upper.iloc[i] = (
            upper.iloc[i]
            if upper.iloc[i] < final_upper.iloc[i - 1] or c.iloc[i - 1] > final_upper.iloc[i - 1]
            else final_upper.iloc[i - 1]
        )
        final_lower.iloc[i] = (
            lower.iloc[i]
            if lower.iloc[i] > final_lower.iloc[i - 1] or c.iloc[i - 1] < final_lower.iloc[i - 1]
            else final_lower.iloc[i - 1]
        )

        if line.iloc[i - 1] == final_upper.iloc[i - 1]:
            line.iloc[i] = final_lower.iloc[i] if c.iloc[i] > final_upper.iloc[i] else final_upper.iloc[i]
        else:
            line.iloc[i] = final_upper.iloc[i] if c.iloc[i] < final_lower.iloc[i] else final_lower.iloc[i]
        direction.iloc[i] = 1 if line.iloc[i] == final_lower.iloc[i] else -1

    return line, direction


def fisher_transform(h: pd.Series, l: pd.Series, c: pd.Series, n: int = 10) -> tuple[pd.Series, pd.Series]:
    val = pd.Series(np.nan, index=c.index, dtype=float)
    fish = pd.Series(np.nan, index=c.index, dtype=float)
    hh = highest(h, n)
    ll = lowest(l, n)
    state_val = np.nan
    state_fish = np.nan
    for i in range(len(c)):
        if pd.isna(hh.iloc[i]) or hh.iloc[i] == ll.iloc[i]:
            continue
        prev_val = 0.0 if pd.isna(state_val) else state_val
        raw = 0.66 * ((c.iloc[i] - ll.iloc[i]) / (hh.iloc[i] - ll.iloc[i]) - 0.5) + 0.67 * prev_val
        raw = max(min(raw, 0.999), -0.999)
        state_val = raw
        val.iloc[i] = raw
        prev_fish = 0.0 if pd.isna(state_fish) else state_fish
        state_fish = 0.5 * math.log((1 + raw) / (1 - raw)) + 0.5 * prev_fish
        fish.iloc[i] = state_fish
    return fish, fish.shift(1)


def rsi(close: pd.Series, n: int) -> pd.Series:
    change = close.diff()
    up = change.clip(lower=0)
    down = (-change).clip(lower=0)
    rs = rma(up, n) / rma(down, n)
    return 100 - 100 / (1 + rs)


def cci(h: pd.Series, l: pd.Series, c: pd.Series, n: int = 20) -> pd.Series:
    tp = (h + l + c) / 3
    ma = sma(tp, n)
    mean_dev = tp.rolling(n, min_periods=n).apply(lambda a: float(np.mean(np.abs(a - a.mean()))), raw=True)
    return (tp - ma) / (0.015 * mean_dev)


def mfi(h: pd.Series, l: pd.Series, c: pd.Series, v: pd.Series, n: int = 14) -> pd.Series:
    tp = (h + l + c) / 3
    money_flow = tp * v
    positive = money_flow.where(tp > tp.shift(), 0.0)
    negative = money_flow.where(tp < tp.shift(), 0.0)
    ratio = positive.rolling(n, min_periods=n).sum() / negative.rolling(n, min_periods=n).sum()
    return 100 - 100 / (1 + ratio)


def dmi(
    h: pd.Series,
    l: pd.Series,
    c: pd.Series,
    tr_values: pd.Series,
    n: int = 14,
    signal: int = 14,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    up = h.diff()
    down = -l.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=c.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=c.index)
    atr_values = rma(tr_values, n)
    plus = 100 * rma(plus_dm, n) / atr_values
    minus = 100 * rma(minus_dm, n) / atr_values
    dx = 100 * (plus - minus).abs() / (plus + minus)
    adx = rma(dx, signal)
    return plus, minus, adx


def compute_tv(df: pd.DataFrame) -> dict[str, pd.Series]:
    work = df.reset_index(drop=True)
    o = clean_series(work["open"])
    h = clean_series(work["high"])
    l = clean_series(work["low"])
    c = clean_series(work["close"])
    v = clean_series(work["volume"])
    idx = work.index
    calc: dict[str, pd.Series] = {}

    tr_values = true_range(h, l, c)
    atr14 = rma(tr_values, 14)
    hl2 = (h + l) / 2
    hlc3 = (h + l + c) / 3

    basis20 = sma(c, 20)
    dev20 = 2 * stdev(c, 20)
    bb20_upper = basis20 + dev20
    bb20_lower = basis20 - dev20
    kc_range20 = sma(tr_values, 20)
    kc20_upper = basis20 + 1.5 * kc_range20
    kc20_lower = basis20 - 1.5 * kc_range20
    sq_avg = ((highest(h, 20) + lowest(l, 20)) / 2 + basis20) / 2
    calc["tv_squeeze_momentum_lb"] = rolling_linreg_value(c - sq_avg, 20)
    calc["tv_squeeze_on"] = ((bb20_lower > kc20_lower) & (bb20_upper < kc20_upper)).astype(float)
    calc["tv_squeeze_off"] = ((bb20_lower < kc20_lower) & (bb20_upper > kc20_upper)).astype(float)

    st14_line, st14_dir = supertrend(h, l, c, atr14, 14, 4)
    calc["tv_supertrend_14_4_line"] = st14_line
    calc["tv_supertrend_14_4_dir"] = st14_dir

    wvf = (highest(c, 22) - l) / highest(c, 22) * 100
    calc["tv_williams_vix_fix_22"] = wvf
    calc["tv_williams_vix_fix_upper_band"] = sma(wvf, 20) + 2 * stdev(wvf, 20)

    esa = ema(hlc3, 10)
    wave_d = ema((hlc3 - esa).abs(), 10)
    ci = (hlc3 - esa) / (0.015 * wave_d)
    wt1 = ema(ci, 21)
    wt2 = sma(wt1, 4)
    calc["tv_wavetrend_wt1_10_21"] = wt1
    calc["tv_wavetrend_wt2_4"] = wt2
    calc["tv_wavetrend_hist"] = wt1 - wt2

    ut_stop, ut_signal = utbot(c, atr_values=rma(tr_values, 10))
    calc["tv_utbot_trailing_stop_10_1"] = ut_stop
    calc["tv_utbot_signal_10_1"] = ut_signal

    macd = ema(c, 12) - ema(c, 26)
    macd_signal = ema(macd, 9)
    calc["tv_macd_custom_macd_12_26"] = macd
    calc["tv_macd_custom_signal_9"] = macd_signal
    calc["tv_macd_custom_hist"] = macd - macd_signal

    calc["tv_relative_volume_20"] = v / sma(v, 20)
    for n in (8, 21, 34, 55):
        calc[f"tv_ema_{n}"] = ema(c, n)
    for n in (10, 50, 100):
        calc[f"tv_sma_{n}"] = sma(c, n)

    calc["tv_close_to_ema_21"] = c / ema(c, 21) - 1
    calc["tv_close_to_ema_55"] = c / ema(c, 55) - 1
    calc["tv_ema_8_21_gap"] = ema(c, 8) / ema(c, 21) - 1
    calc["tv_ema_21_55_gap"] = ema(c, 21) / ema(c, 55) - 1
    calc["tv_close_to_sma_50"] = c / sma(c, 50) - 1
    calc["tv_sma_20_50_gap"] = sma(c, 20) / sma(c, 50) - 1

    calc["tv_wma_21"] = wma(c, 21)
    calc["tv_hma_21"] = hma(c, 21)
    calc["tv_alma_20"] = alma(c, 20)
    calc["tv_vwma_20"] = (c * v).rolling(20, min_periods=20).sum() / v.rolling(20, min_periods=20).sum()
    calc["tv_vwma_50"] = (c * v).rolling(50, min_periods=50).sum() / v.rolling(50, min_periods=50).sum()
    calc["tv_linreg_20"] = rolling_linreg_value(c, 20)
    calc["tv_linreg_slope_20"] = rolling_linreg_slope(c, 20)
    calc["tv_linreg_50"] = rolling_linreg_value(c, 50)
    calc["tv_linreg_slope_50"] = rolling_linreg_slope(c, 50)

    psar, _psar_state_dir = parabolic_sar(h, l, c)
    calc["tv_psar_002_02"] = psar
    calc["tv_psar_dir"] = pd.Series(np.where(c >= psar, 1.0, -1.0), index=idx)

    st10_line, st10_dir = supertrend(h, l, c, rma(tr_values, 10), 10, 3)
    st21_line, st21_dir = supertrend(h, l, c, rma(tr_values, 21), 21, 3)
    calc["tv_supertrend_10_3_line"] = st10_line
    calc["tv_supertrend_10_3_dir"] = st10_dir
    calc["tv_supertrend_21_3_line"] = st21_line
    calc["tv_supertrend_21_3_dir"] = st21_dir

    tenkan = (highest(h, 9) + lowest(l, 9)) / 2
    kijun = (highest(h, 26) + lowest(l, 26)) / 2
    calc["tv_ichimoku_tenkan_9"] = tenkan
    calc["tv_ichimoku_kijun_26"] = kijun
    calc["tv_ichimoku_span_a_raw"] = (tenkan + kijun) / 2
    calc["tv_ichimoku_span_b_raw"] = (highest(h, 52) + lowest(l, 52)) / 2

    calc["tv_atr_14"] = atr14
    calc["tv_atr_pct_14"] = atr14 / c
    calc["tv_natr_14"] = 100 * atr14 / c
    calc["tv_bb_20_basis"] = basis20
    calc["tv_bb_20_upper"] = bb20_upper
    calc["tv_bb_20_lower"] = bb20_lower
    calc["tv_bb_20_percent_b"] = (c - bb20_lower) / (bb20_upper - bb20_lower)
    calc["tv_bb_20_width"] = (bb20_upper - bb20_lower) / basis20

    basis50 = sma(c, 50)
    bb50_upper = basis50 + 2 * stdev(c, 50)
    bb50_lower = basis50 - 2 * stdev(c, 50)
    calc["tv_bb_50_percent_b"] = (c - bb50_lower) / (bb50_upper - bb50_lower)
    calc["tv_bb_50_width"] = (bb50_upper - bb50_lower) / basis50

    calc["tv_kc_20_upper"] = kc20_upper
    calc["tv_kc_20_lower"] = kc20_lower
    calc["tv_kc_20_width"] = 3 * kc_range20 / basis20

    for n in (20, 55):
        hh = highest(h, n)
        ll = lowest(l, n)
        calc[f"tv_donchian_{n}_upper"] = hh
        calc[f"tv_donchian_{n}_lower"] = ll
        calc[f"tv_donchian_{n}_mid"] = (hh + ll) / 2

    calc["tv_chandelier_long_22_3"] = highest(h, 22) - 3 * atr14
    calc["tv_chandelier_short_22_3"] = lowest(l, 22) + 3 * atr14

    returns = c.pct_change()
    calc["tv_historical_volatility_20"] = stdev(returns, 20) * math.sqrt(252)
    calc["tv_historical_volatility_60"] = stdev(returns, 60) * math.sqrt(252)
    drawdown = (c / highest(c, 14) - 1) * 100
    calc["tv_ulcer_index_14"] = np.sqrt(sma(drawdown * drawdown, 14))
    calc["tv_true_range_pct"] = tr_values / c
    calc["tv_range_percentile_20"] = (h - l).rolling(20, min_periods=20).apply(range_percentile_last, raw=True)

    for n in (7, 14, 21):
        calc[f"tv_rsi_{n}"] = rsi(c, n)
    calc["tv_rsi_14_ma_9"] = sma(calc["tv_rsi_14"], 9)
    stoch_k = 100 * (c - lowest(l, 14)) / (highest(h, 14) - lowest(l, 14))
    calc["tv_stoch_k_14"] = stoch_k
    calc["tv_stoch_d_3"] = sma(stoch_k, 3)
    rsi14 = calc["tv_rsi_14"]
    stoch_rsi = 100 * (rsi14 - lowest(rsi14, 14)) / (highest(rsi14, 14) - lowest(rsi14, 14))
    calc["tv_stoch_rsi_k_14"] = stoch_rsi
    calc["tv_stoch_rsi_d_3"] = sma(stoch_rsi, 3)
    calc["tv_williams_r_14"] = -100 * (highest(h, 14) - c) / (highest(h, 14) - lowest(l, 14))
    calc["tv_cci_20"] = cci(h, l, c, 20)
    calc["tv_mfi_14"] = mfi(h, l, c, v, 14)
    calc["tv_roc_10"] = 100 * (c / c.shift(10) - 1)
    calc["tv_roc_20"] = 100 * (c / c.shift(20) - 1)
    calc["tv_momentum_10"] = c - c.shift(10)
    ao = sma(hl2, 5) - sma(hl2, 34)
    calc["tv_awesome_oscillator"] = ao
    calc["tv_accelerator_oscillator"] = ao - sma(ao, 5)
    ppo = (ema(c, 12) - ema(c, 26)) / ema(c, 26) * 100
    ppo_signal = ema(ppo, 9)
    calc["tv_ppo_12_26"] = ppo
    calc["tv_ppo_signal_9"] = ppo_signal
    calc["tv_ppo_hist"] = ppo - ppo_signal

    dema = lambda s, n: 2 * ema(s, n) - ema(ema(s, n), n)
    zero_lag = dema(c, 12) - dema(c, 26)
    calc["tv_zero_lag_macd"] = zero_lag
    calc["tv_zero_lag_signal"] = ema(zero_lag, 9)

    momentum = c.diff()
    tsi = 100 * ema(ema(momentum, 25), 13) / ema(ema(momentum.abs(), 25), 13)
    calc["tv_tsi_25_13"] = tsi
    calc["tv_tsi_signal_13"] = ema(tsi, 13)
    calc["tv_dpo_20"] = c - sma(c, 20).shift(11)
    fisher, fisher_trigger = fisher_transform(h, l, c, 10)
    calc["tv_fisher_10"] = fisher
    calc["tv_fisher_trigger"] = fisher_trigger

    upsum = c.diff().clip(lower=0).rolling(14, min_periods=14).sum()
    downsum = (-c.diff()).clip(lower=0).rolling(14, min_periods=14).sum()
    calc["tv_cmo_14"] = 100 * (upsum - downsum) / (upsum + downsum)
    bp = c - pd.concat([l, c.shift()], axis=1).min(axis=1)
    true_high = pd.concat([h, c.shift()], axis=1).max(axis=1)
    true_low = pd.concat([l, c.shift()], axis=1).min(axis=1)
    uo_tr = true_high - true_low
    uo_avg = lambda n: bp.rolling(n, min_periods=n).sum() / uo_tr.rolling(n, min_periods=n).sum()
    calc["tv_ultimate_oscillator"] = 100 * (4 * uo_avg(7) + 2 * uo_avg(14) + uo_avg(28)) / 7
    calc["tv_vortex_plus_14"] = (h - l.shift()).abs().rolling(14, min_periods=14).sum() / tr_values.rolling(14, min_periods=14).sum()
    calc["tv_vortex_minus_14"] = (l - h.shift()).abs().rolling(14, min_periods=14).sum() / tr_values.rolling(14, min_periods=14).sum()

    bars_since_high = h.rolling(25, min_periods=25).apply(lambda a: float(24 - np.argmax(a)), raw=True)
    bars_since_low = l.rolling(25, min_periods=25).apply(lambda a: float(24 - np.argmin(a)), raw=True)
    calc["tv_aroon_up_25"] = 100 * (25 - bars_since_high) / 25
    calc["tv_aroon_down_25"] = 100 * (25 - bars_since_low) / 25
    calc["tv_aroon_osc_25"] = calc["tv_aroon_up_25"] - calc["tv_aroon_down_25"]
    pdi, mdi, adx = dmi(h, l, c, tr_values, 14, 14)
    calc["tv_dmi_plus_14"] = pdi
    calc["tv_dmi_minus_14"] = mdi
    calc["tv_adx_14"] = adx

    macd_stc = ema(c, 23) - ema(c, 50)
    k1 = 100 * (macd_stc - lowest(macd_stc, 10)) / (highest(macd_stc, 10) - lowest(macd_stc, 10))
    d1 = ema(k1, 3)
    k2 = 100 * (d1 - lowest(d1, 10)) / (highest(d1, 10) - lowest(d1, 10))
    calc["tv_schaff_trend_cycle"] = ema(k2, 3)

    sign_change = np.sign(c.diff().fillna(0))
    obv = (sign_change * v).cumsum()
    calc["tv_obv"] = obv
    calc["tv_obv_ema_20"] = ema(obv, 20)
    clv = ((c - l) - (h - c)) / (h - l).replace(0, np.nan)
    money_flow_volume = clv.fillna(0) * v
    adl = money_flow_volume.cumsum()
    calc["tv_adl"] = adl
    calc["tv_chaikin_osc_3_10"] = ema(adl, 3) - ema(adl, 10)
    calc["tv_cmf_20"] = money_flow_volume.rolling(20, min_periods=20).sum() / v.rolling(20, min_periods=20).sum()
    calc["tv_force_index_13"] = ema(c.diff() * v, 13)
    eom_raw = (hl2 - hl2.shift()) * (h - l) / v.replace(0, np.nan)
    calc["tv_eom_14"] = sma(eom_raw, 14)
    calc["tv_volume_osc_5_20"] = (sma(v, 5) - sma(v, 20)) / sma(v, 20) * 100

    pvi = pd.Series(np.nan, index=idx, dtype=float)
    nvi = pd.Series(np.nan, index=idx, dtype=float)
    if len(c):
        pvi.iloc[0] = 1000
        nvi.iloc[0] = 1000
    for i in range(1, len(c)):
        ret = (c.iloc[i] - c.iloc[i - 1]) / c.iloc[i - 1]
        pvi.iloc[i] = pvi.iloc[i - 1] * (1 + ret) if v.iloc[i] > v.iloc[i - 1] else pvi.iloc[i - 1]
        nvi.iloc[i] = nvi.iloc[i - 1] * (1 + ret) if v.iloc[i] < v.iloc[i - 1] else nvi.iloc[i - 1]
    calc["tv_pvi"] = pvi
    calc["tv_nvi"] = nvi
    calc["tv_pvt"] = (v * c.pct_change()).fillna(0).cumsum()

    calc["tv_rolling_vwap_20"] = (hlc3 * v).rolling(20, min_periods=20).sum() / v.rolling(20, min_periods=20).sum()
    calc["tv_rolling_vwap_50"] = (hlc3 * v).rolling(50, min_periods=50).sum() / v.rolling(50, min_periods=50).sum()
    calc["tv_vwap_distance_20"] = c / calc["tv_rolling_vwap_20"] - 1
    calc["tv_volume_zscore_20"] = (v - sma(v, 20)) / stdev(v, 20)
    calc["tv_dollar_volume_ma20"] = sma(c * v, 20)
    calc["tv_relative_volume_50"] = v / sma(v, 50)
    calc["tv_uptick_volume_ratio_20"] = (
        v.where(c > c.shift(), 0).rolling(20, min_periods=20).sum()
        / v.where(c != c.shift(), 0).rolling(20, min_periods=20).sum()
    )

    candle_range = (h - l).replace(0, np.nan)
    calc["tv_candle_body_pct"] = (c - o).abs() / candle_range
    calc["tv_candle_upper_wick_pct"] = (h - pd.concat([o, c], axis=1).max(axis=1)) / candle_range
    calc["tv_candle_lower_wick_pct"] = (pd.concat([o, c], axis=1).min(axis=1) - l) / candle_range
    calc["tv_close_location_value"] = clv
    calc["tv_gap_pct"] = o / c.shift() - 1
    calc["tv_intrabar_return"] = c / o - 1
    calc["tv_trend_bar_up"] = ((c > o) & (c > c.shift())).astype(float)
    calc["tv_inside_bar"] = ((h < h.shift()) & (l > l.shift())).astype(float)
    calc["tv_outside_bar"] = ((h > h.shift()) & (l < l.shift())).astype(float)
    calc["tv_breakout_high_20_prev"] = (c > highest(h, 20).shift()).astype(float)
    calc["tv_breakdown_low_20_prev"] = (c < lowest(l, 20).shift()).astype(float)

    consecutive_up = pd.Series(0.0, index=idx)
    consecutive_down = pd.Series(0.0, index=idx)
    for i in range(1, len(c)):
        consecutive_up.iloc[i] = consecutive_up.iloc[i - 1] + 1 if c.iloc[i] > c.iloc[i - 1] else 0
        consecutive_down.iloc[i] = consecutive_down.iloc[i - 1] + 1 if c.iloc[i] < c.iloc[i - 1] else 0
    calc["tv_consecutive_up_bars"] = consecutive_up
    calc["tv_consecutive_down_bars"] = consecutive_down

    return calc


def utbot(close: pd.Series, atr_values: pd.Series) -> tuple[pd.Series, pd.Series]:
    trail = pd.Series(np.nan, index=close.index, dtype=float)
    signal = pd.Series(0.0, index=close.index, dtype=float)
    for i in range(len(close)):
        src = close.iloc[i]
        prev = 0.0 if i == 0 or pd.isna(trail.iloc[i - 1]) else trail.iloc[i - 1]
        src_prev = close.iloc[i - 1] if i > 0 else np.nan
        loss = atr_values.iloc[i]
        if src > prev and not pd.isna(src_prev) and src_prev > prev:
            trail.iloc[i] = max(prev, src - loss)
        elif src < prev and not pd.isna(src_prev) and src_prev < prev:
            trail.iloc[i] = min(prev, src + loss)
        elif src > prev:
            trail.iloc[i] = src - loss
        else:
            trail.iloc[i] = src + loss

        if i > 0:
            if close.iloc[i] > trail.iloc[i] and close.iloc[i - 1] <= trail.iloc[i - 1]:
                signal.iloc[i] = 1
            elif close.iloc[i] < trail.iloc[i] and close.iloc[i - 1] >= trail.iloc[i - 1]:
                signal.iloc[i] = -1
    return trail, signal


def data_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    files: list[Path] = []
    for pattern in ("*.csv", "*.parquet"):
        for fp in path.rglob(pattern):
            name = fp.name
            if name in EXCLUDE_FILE_NAMES or any(name.endswith(suffix) for suffix in EXCLUDE_SUFFIXES):
                continue
            files.append(fp)
    return sorted(files)


def read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    raise ValueError(f"unsupported file type: {path}")


def read_schema_frame(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, nrows=0)
    return read_table(path)


def schema_check(df: pd.DataFrame) -> dict[str, Any]:
    actual = [c for c in df.columns if c.startswith("tv_")]
    missing = [c for c in TV_COLUMNS if c not in actual]
    extra = [c for c in actual if c not in TV_COLUMNS]
    order_ok = [c for c in actual if c in TV_COLUMNS] == TV_COLUMNS
    return {
        "status": "PASS" if not missing and not extra and order_ok else "FAIL",
        "tv_column_count": len(actual),
        "expected_count": len(TV_COLUMNS),
        "missing": missing,
        "extra": extra,
        "order_ok": order_ok,
    }


def start_for_compare(row_count: int, warmup: int, tail_rows: int) -> int:
    if row_count > warmup + tail_rows:
        return warmup
    return max(0, row_count - tail_rows)


def compare_series(
    observed: pd.Series,
    expected: pd.Series,
    *,
    abs_tol: float,
    rel_tol: float,
) -> dict[str, Any]:
    a = clean_series(observed).reset_index(drop=True)
    b = clean_series(expected).reset_index(drop=True)
    both_na = a.isna() & b.isna()
    mask = ~both_na
    if not mask.any():
        return {"bad": 0, "max_abs_diff": 0.0, "checked": 0}
    diff = (a[mask] - b[mask]).abs()
    tolerance = np.maximum(abs_tol, rel_tol * a[mask].abs())
    bad_mask = diff > tolerance
    return {
        "bad": int(bad_mask.sum()),
        "checked": int(mask.sum()),
        "max_abs_diff": float(diff.max()) if len(diff) else 0.0,
    }


def compare_cumulative(df: pd.DataFrame, start: int, abs_tol: float, rel_tol: float) -> list[dict[str, Any]]:
    o = clean_series(df["open"]).reset_index(drop=True)
    h = clean_series(df["high"]).reset_index(drop=True)
    l = clean_series(df["low"]).reset_index(drop=True)
    c = clean_series(df["close"]).reset_index(drop=True)
    v = clean_series(df["volume"]).reset_index(drop=True)
    clv = ((c - l) - (h - c)) / (h - l).replace(0, np.nan)
    money_flow_volume = clv.fillna(0) * v

    checks: list[tuple[str, pd.Series, pd.Series]] = []
    if "tv_obv" in df:
        checks.append(("tv_obv_delta", clean_series(df["tv_obv"]).diff(), np.sign(c.diff()) * v))
    if "tv_adl" in df:
        checks.append(("tv_adl_delta", clean_series(df["tv_adl"]).diff(), money_flow_volume))
    if "tv_pvt" in df:
        checks.append(("tv_pvt_delta", clean_series(df["tv_pvt"]).diff(), v * c.pct_change()))
    if "tv_obv_ema_20" in df and "tv_obv" in df:
        alpha = 2 / (20 + 1)
        obv_ema = clean_series(df["tv_obv_ema_20"])
        expected = alpha * clean_series(df["tv_obv"]) + (1 - alpha) * obv_ema.shift()
        checks.append(("tv_obv_ema_20_recur", obv_ema, expected))
    if "tv_pvi" in df:
        pvi = clean_series(df["tv_pvi"])
        expected = pd.Series(
            np.where(v > v.shift(), pvi.shift() * (1 + c.pct_change()), pvi.shift()),
            index=pvi.index,
        )
        checks.append(("tv_pvi_recur", pvi, expected))
    if "tv_nvi" in df:
        nvi = clean_series(df["tv_nvi"])
        expected = pd.Series(
            np.where(v < v.shift(), nvi.shift() * (1 + c.pct_change()), nvi.shift()),
            index=nvi.index,
        )
        checks.append(("tv_nvi_recur", nvi, expected))

    rows: list[dict[str, Any]] = []
    for name, observed, expected in checks:
        result = compare_series(
            observed.iloc[max(start, 1) :],
            expected.iloc[max(start, 1) :],
            abs_tol=abs_tol,
            rel_tol=rel_tol,
        )
        result["column"] = name
        rows.append(result)
    return rows


def check_file(
    path: Path,
    *,
    mode: str,
    warmup: int,
    tail_rows: int,
    abs_tol: float,
    rel_tol: float,
    include_columns: bool,
) -> dict[str, Any]:
    df = read_schema_frame(path) if mode == "schema" else read_table(path)
    schema = schema_check(df)
    result: dict[str, Any] = {
        "file": str(path),
        "row_count": None if mode == "schema" and path.suffix.lower() == ".csv" else int(len(df)),
        "schema": schema,
    }

    if mode == "schema":
        result["status"] = schema["status"]
        return result
    if schema["status"] != "PASS":
        result["status"] = "FAIL"
        return result

    missing_base = [c for c in BASE_COLUMNS if c not in df.columns]
    if missing_base:
        result["status"] = "SKIP_VALUES"
        result["missing_base_columns"] = missing_base
        return result

    calc = compute_tv(df)
    start = start_for_compare(len(df), warmup, tail_rows)
    value_rows: list[dict[str, Any]] = []
    failed_columns: list[str] = []

    for col in TV_COLUMNS:
        if col in CUMULATIVE_COLUMNS:
            continue
        col_tol = max(abs_tol, COLUMN_ABS_TOL.get(col, abs_tol))
        cmp_result = compare_series(
            df[col].iloc[start:],
            calc[col].iloc[start:],
            abs_tol=col_tol,
            rel_tol=rel_tol,
        )
        cmp_result["column"] = col
        if cmp_result["bad"]:
            failed_columns.append(col)
        if include_columns or cmp_result["bad"]:
            value_rows.append(cmp_result)

    cumulative_rows = compare_cumulative(df, start, abs_tol=abs_tol, rel_tol=rel_tol)
    for row in cumulative_rows:
        if row["bad"]:
            failed_columns.append(row["column"])
        if include_columns or row["bad"]:
            value_rows.append(row)

    result.update(
        {
            "status": "FAIL" if failed_columns else "PASS",
            "compare_start_row": int(start),
            "checked_columns": len(TV_COLUMNS),
            "failed_columns": failed_columns,
        }
    )
    if include_columns or failed_columns:
        result["columns"] = value_rows
    return result


def summarize() -> None:
    payload = {
        "status": "PASS",
        "contract": CONTRACT["contract_name"],
        "version": CONTRACT["version"],
        "column_prefix": CONTRACT["column_prefix"],
        "column_count": len(TV_COLUMNS),
        "cumulative_columns": sorted(CUMULATIVE_COLUMNS),
        "source_library": CONTRACT["source_library"],
        "columns_sha256": __import__("hashlib").sha256(
            json.dumps(TV_COLUMNS, ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def check_data(args: argparse.Namespace) -> None:
    target = Path(args.data)
    files = data_files(target)
    if args.limit:
        files = files[: args.limit]
    results = [
        check_file(
            fp,
            mode=args.mode,
            warmup=args.warmup,
            tail_rows=args.tail_rows,
            abs_tol=args.abs_tol,
            rel_tol=args.rel_tol,
            include_columns=args.include_columns,
        )
        for fp in files
    ]

    statuses = [r["status"] for r in results]
    status = "PASS"
    if any(s == "FAIL" for s in statuses):
        status = "FAIL"
    elif any(s == "SKIP_VALUES" for s in statuses):
        status = "SKIP_VALUES"

    payload = {
        "status": status,
        "mode": args.mode,
        "files_total": len(results),
        "files_passed": sum(1 for s in statuses if s == "PASS"),
        "files_failed": sum(1 for s in statuses if s == "FAIL"),
        "files_skipped_values": sum(1 for s in statuses if s == "SKIP_VALUES"),
        "contract_columns": len(TV_COLUMNS),
        "results": results if args.include_files or status != "PASS" else results[:3],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit locked 142 tv_ TradingView factors.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("summary")

    check = sub.add_parser("check-data")
    check.add_argument("--data", required=True, help="CSV/Parquet file or directory.")
    check.add_argument("--mode", choices=["schema", "values"], default="values")
    check.add_argument("--limit", type=int, default=0)
    check.add_argument("--warmup", type=int, default=2000)
    check.add_argument("--tail-rows", type=int, default=100)
    check.add_argument("--abs-tol", type=float, default=1e-6)
    check.add_argument("--rel-tol", type=float, default=1e-9)
    check.add_argument("--include-columns", action="store_true")
    check.add_argument("--include-files", action="store_true")

    args = parser.parse_args()
    if args.command == "summary":
        summarize()
    elif args.command == "check-data":
        check_data(args)


if __name__ == "__main__":
    main()
