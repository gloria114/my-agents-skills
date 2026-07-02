# TV locked 142 公式参考

## 来源

- TV 指标源码库：`TV指标库` 文件夹中的 `TV指标库_自动抓取_*.docx`。
- CSV 写入列：各行情文件旁的 `_indicator_audit.csv` 中 `source=tv,status=computed` 的 142 行。
- 源码库中其余 TradingView 条目属于 audit-only，不属于 locked 142 输出列。

## 基础约定

- 输入列：`open, high, low, close, volume`。
- `TR = max(high-low, abs(high-close[1]), abs(low-close[1]))`。
- `EMA(x,N)` 使用 pandas/Pine 等价递推 `ewm(span=N, adjust=False)`。
- `RMA(x,N)` 使用 Wilder 平滑 `ewm(alpha=1/N, adjust=False)`。
- `SMA/STD/HHV/LLV/SUM` 均为向后 rolling，不使用未来行。

## 自定义 TV 源码映射

- `tv_squeeze_momentum_lb`：LazyBear/Tyler Squeeze Momentum 风格；BB 长度 20、倍数 2，KC 长度 20、倍数 1.5，动量为 `linreg(close - avg(avg(HHV,LLV),SMA(close,20)),20)`。
- `tv_squeeze_on/off`：BB 与 KC 包含关系。
- `tv_supertrend_14_4_line/dir`：TradingView Supertrend，ATR 14，mult 4。
- `tv_williams_vix_fix_22`：`(HHV(close,22)-low)/HHV(close,22)*100`。
- `tv_williams_vix_fix_upper_band`：Williams Vix Fix 的 20 期 Bollinger upper band。
- `tv_wavetrend_*`：LazyBear WaveTrend，`ap=hlc3,n1=10,n2=21,wt2=SMA(wt1,4)`。
- `tv_utbot_*`：UT Bot Alerts，ATR 10，key value 1，不使用 Heikin Ashi。
- `tv_macd_custom_*`：当前周期 MACD，fast 12、slow 26、signal 9。

## 标准趋势与均线

- `tv_ema_8/21/34/55`：`EMA(close,N)`。
- `tv_sma_10/50/100`：`SMA(close,N)`。
- `tv_close_to_ema_*`：`close / EMA(close,N) - 1`。
- `tv_ema_8_21_gap`：`EMA(close,8) / EMA(close,21) - 1`。
- `tv_ema_21_55_gap`：`EMA(close,21) / EMA(close,55) - 1`。
- `tv_close_to_sma_50`：`close / SMA(close,50) - 1`。
- `tv_sma_20_50_gap`：`SMA(close,20) / SMA(close,50) - 1`。
- `tv_wma_21`：线性权重 WMA。
- `tv_hma_21`：`WMA(2*WMA(close,10)-WMA(close,21),sqrt(21))`。
- `tv_alma_20`：ALMA，offset 0.85，sigma 6。
- `tv_vwma_20/50`：`SUM(close*volume,N)/SUM(volume,N)`。
- `tv_linreg_20/50`：rolling linear regression 当前值。
- `tv_linreg_slope_20/50`：rolling linear regression slope。
- `tv_psar_002_02/dir`：Parabolic SAR，start 0.02，increment 0.02，max 0.2。
- `tv_supertrend_10_3_*`、`tv_supertrend_21_3_*`：Supertrend 变体。
- `tv_ichimoku_*`：Tenkan 9、Kijun 26、Span A raw、Span B raw 52；不做未来位移。

## 波动率与通道

- `tv_atr_14`：`RMA(TR,14)`。
- `tv_atr_pct_14`：`ATR14 / close`。
- `tv_natr_14`：`100 * ATR14 / close`。
- `tv_bb_20_*`：Bollinger 20，2 倍总体标准差。
- `tv_bb_50_percent_b/width`：Bollinger 50。
- `tv_kc_20_upper/lower/width`：`SMA(close,20) ± 1.5*SMA(TR,20)`，width 为 `3*SMA(TR,20)/SMA(close,20)`。
- `tv_donchian_20/55_*`：HHV/LLV/mid。
- `tv_chandelier_long_22_3`：`HHV(high,22)-3*ATR14`。
- `tv_chandelier_short_22_3`：`LLV(low,22)+3*ATR14`。
- `tv_historical_volatility_20/60`：`STD(close.pct_change(),N) * sqrt(252)`。
- `tv_ulcer_index_14`：14 期 close drawdown 平方均值开方。
- `tv_true_range_pct`：`TR / close`。
- `tv_range_percentile_20`：`high-low` 在 20 根窗口内的平均排名百分位。

## 动量与震荡

- `tv_rsi_7/14/21`：Wilder RSI。
- `tv_rsi_14_ma_9`：`SMA(RSI14,9)`。
- `tv_stoch_k_14/d_3`：Stochastic K 和 `SMA(K,3)`。
- `tv_stoch_rsi_k_14/d_3`：raw StochRSI K 和 `SMA(K,3)`。
- `tv_williams_r_14`、`tv_cci_20`、`tv_mfi_14`、`tv_roc_10/20`、`tv_momentum_10`：标准公式。
- `tv_awesome_oscillator`：`SMA(hl2,5)-SMA(hl2,34)`。
- `tv_accelerator_oscillator`：AO 减 `SMA(AO,5)`。
- `tv_ppo_*`：PPO 12/26/9。
- `tv_zero_lag_macd/signal`：`DEMA(close,12)-DEMA(close,26)`，signal 为 EMA 9。
- `tv_tsi_25_13/signal_13`：TSI 与 EMA signal。
- `tv_dpo_20`：`close - SMA(close,20)[11]`。
- `tv_fisher_10/trigger`：Fisher Transform，source 为 close，范围使用 high/low。
- `tv_cmo_14`、`tv_ultimate_oscillator`、`tv_vortex_*`、`tv_aroon_*`、`tv_dmi_*`、`tv_adx_14`、`tv_schaff_trend_cycle`：按脚本中的标准实现复算。

## 成交量与蜡烛

- `tv_obv`、`tv_obv_ema_20`、`tv_adl`、`tv_pvt`、`tv_pvi`、`tv_nvi`：按审计口径用递推/增量校验。
- `tv_chaikin_osc_3_10`：`EMA(ADL,3)-EMA(ADL,10)`。
- `tv_cmf_20`、`tv_force_index_13`、`tv_eom_14`、`tv_volume_osc_5_20`：标准公式；volume osc 使用 SMA 5 与 SMA 20。
- `tv_rolling_vwap_20/50`：`SUM(hlc3*volume,N)/SUM(volume,N)`。
- `tv_vwap_distance_20`：`close / rolling_vwap_20 - 1`。
- `tv_volume_zscore_20`：`(volume-SMA(volume,20))/STD(volume,20)`。
- `tv_dollar_volume_ma20`：`SMA(close*volume,20)`。
- `tv_relative_volume_20/50`：`volume/SMA(volume,N)`。
- `tv_uptick_volume_ratio_20`：`SUM(volume where close>close[1],20) / SUM(volume where close!=close[1],20)`。
- `tv_candle_body_pct`、`tv_candle_upper_wick_pct`、`tv_candle_lower_wick_pct`、`tv_close_location_value`、`tv_gap_pct`、`tv_intrabar_return`：标准单根 K 线公式。
- `tv_trend_bar_up`：`close > open AND close > close[1]`。
- `tv_inside_bar`、`tv_outside_bar`：严格内包/外包。
- `tv_breakout_high_20_prev`：`close > HHV(high,20)[1]`。
- `tv_breakdown_low_20_prev`：`close < LLV(low,20)[1]`。
- `tv_consecutive_up_bars/down_bars`：按 close 与前一根 close 比较递推计数。
