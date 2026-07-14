# Locked 59 Indicator PY 公式

基础约定：

- `MA(x,n)` = `x.rolling(n).mean()`
- `EMA(x,n)` = `x.ewm(span=n, adjust=False).mean()`
- `RET(n)` = `close.pct_change(n)`
- `STD(x,n)` = `x.rolling(n).std()`
- `PSTD(x,n)` = `x.rolling(n).std(ddof=0)`
- `RANK(x,n)` = `x.rolling(n).rank(pct=True)`

## 收益和动量

| 列名 | 公式 |
|---|---|
| `indicator_py_ret_1` | `close.pct_change(1)` |
| `indicator_py_ret_3` | `close.pct_change(3)` |
| `indicator_py_ret_5` | `close.pct_change(5)` |
| `indicator_py_ret_10` | `close.pct_change(10)` |
| `indicator_py_ret_20` | `close.pct_change(20)` |
| `indicator_py_momentum_5` | `close - close.shift(5)` |
| `indicator_py_momentum_10` | `close - close.shift(10)` |
| `indicator_py_momentum_20` | `close - close.shift(20)` |

## 均线结构

| 列名 | 公式 |
|---|---|
| `indicator_py_ma5_slope` | `MA(close,5).pct_change()` |
| `indicator_py_close_to_ma5` | `(close - MA(close,5)) / MA(close,5)` |
| `indicator_py_ma10_slope` | `MA(close,10).pct_change()` |
| `indicator_py_close_to_ma10` | `(close - MA(close,10)) / MA(close,10)` |
| `indicator_py_ma20_slope` | `MA(close,20).pct_change()` |
| `indicator_py_close_to_ma20` | `(close - MA(close,20)) / MA(close,20)` |
| `indicator_py_ma40_slope` | `MA(close,40).pct_change()` |
| `indicator_py_close_to_ma40` | `(close - MA(close,40)) / MA(close,40)` |
| `indicator_py_ma60_slope` | `MA(close,60).pct_change()` |
| `indicator_py_close_to_ma60` | `(close - MA(close,60)) / MA(close,60)` |
| `indicator_py_ma120_slope` | `MA(close,120).pct_change()` |
| `indicator_py_close_to_ma120` | `(close - MA(close,120)) / MA(close,120)` |
| `indicator_py_ma5_ma10_gap` | `(MA(close,5) - MA(close,10)) / MA(close,10)` |
| `indicator_py_ma5_ma20_gap` | `(MA(close,5) - MA(close,20)) / MA(close,20)` |
| `indicator_py_ma10_ma20_gap` | `(MA(close,10) - MA(close,20)) / MA(close,20)` |
| `indicator_py_ma20_ma40_gap` | `(MA(close,20) - MA(close,40)) / MA(close,40)` |
| `indicator_py_ma20_ma60_gap` | `(MA(close,20) - MA(close,60)) / MA(close,60)` |
| `indicator_py_ma40_ma120_gap` | `(MA(close,40) - MA(close,120)) / MA(close,120)` |

## WH6 派生

| 列名 | 公式 |
|---|---|
| `indicator_py_macd_hist_diff` | `(wh6_MACD_MACD / 2).diff()` |
| `indicator_py_ppo` | `(EMA(close,12) - EMA(close,26)) / EMA(close,26)` |
| `indicator_py_rsi_diff` | `wh6_RSI_RSI2.diff()` |
| `indicator_py_rsi_zscore_20` | `(wh6_RSI_RSI2 - MA(wh6_RSI_RSI2,20)) / PSTD(wh6_RSI_RSI2,20)` |

## 波动、区间和布林

| 列名 | 公式 |
|---|---|
| `indicator_py_hl_pct` | `(high - low) / close` |
| `indicator_py_tr_ratio` | `max(high-low, abs(high-close.shift(1)), abs(low-close.shift(1))) / close` |
| `indicator_py_atr_norm` | `wh6_ATR_ATR / close` |
| `indicator_py_volatility_5` | `close.pct_change().rolling(5).std()` |
| `indicator_py_volatility_10` | `close.pct_change().rolling(10).std()` |
| `indicator_py_volatility_20` | `close.pct_change().rolling(20).std()` |
| `indicator_py_vol_ratio_5_20` | `indicator_py_volatility_5 / indicator_py_volatility_20` |
| `indicator_py_break_high_20` | `close > high.rolling(20).max().shift(1)` |
| `indicator_py_break_low_20` | `close < low.rolling(20).min().shift(1)` |
| `indicator_py_dist_prev_high_20` | `(close - high.rolling(20).max().shift(1)) / high.rolling(20).max().shift(1)` |
| `indicator_py_dist_prev_low_20` | `(close - low.rolling(20).min().shift(1)) / low.rolling(20).min().shift(1)` |
| `indicator_py_pos_in_range_20` | `(close - low.rolling(20).min()) / (high.rolling(20).max() - low.rolling(20).min())` |
| `indicator_py_pos_in_range_60` | `(close - low.rolling(60).min()) / (high.rolling(60).max() - low.rolling(60).min())` |
| `indicator_py_close_pos` | `(close - low) / (high - low)` |
| `indicator_py_boll_pct_b` | `0.5 + wh6_Z_SCORE_Z_SCORE / 4` |
| `indicator_py_boll_width` | `wh6_u_8b96f436_BBW` |
| `indicator_py_zscore_close_20` | `wh6_Z_SCORE_Z_SCORE` |

## 成交量、持仓和条件状态

| 列名 | 公式 |
|---|---|
| `indicator_py_zscore_volume_20` | `(volume - MA(volume,20)) / PSTD(volume,20)` |
| `indicator_py_close_rank_60` | `RANK(close,60)` |
| `indicator_py_volume_rank_60` | `RANK(volume,60)` |
| `indicator_py_vol_ratio_5` | `volume / MA(volume,5)` |
| `indicator_py_vol_ratio_20` | `volume / MA(volume,20)` |
| `indicator_py_volume_diff` | `volume.diff()` |
| `indicator_py_oi_diff` | `open_interest.diff()` |
| `indicator_py_oi_ratio_5` | `open_interest / MA(open_interest,5)` |
| `indicator_py_price_up_vol_up` | `(close > close.shift(1)) & (volume > volume.shift(1))` |
| `indicator_py_price_down_vol_up` | `(close < close.shift(1)) & (volume > volume.shift(1))` |
| `indicator_py_price_up_oi_up` | `(close > close.shift(1)) & (open_interest > open_interest.shift(1))` |
| `indicator_py_price_down_oi_up` | `(close < close.shift(1)) & (open_interest > open_interest.shift(1))` |
