# TV 因子审计口径

## 只读边界

- 只读取用户提供的数据文件、目录、审计清单或 TV 指标库。
- 不向 CSV、Parquet、data hub 或 TV 指标库写入内容。
- 不自动补列、不重算落盘、不覆盖原始数据。

## 合同范围

- locked 合同只覆盖当前 CSV 中已纳入的 142 个 `tv_` computed 指标。
- `TV指标库` docx 中共有更多 TradingView 源码条目；未纳入 CSV 的条目属于 audit-only 索引，不要求在数据中出现。
- 当前合同默认用于核实已有 142 列是否准确，不用于自动发现或追加新 TV 指标。

## 数值口径

- 普通 rolling、EMA、ATR、MACD、BOLL、RSI、DMI、VWAP 等列按当前行及历史行复算。
- 默认跳过足够 warmup 行；短历史文件保留尾部窗口比较，并使用列级容忍处理递归初始化微差。
- 累计型列使用递推/增量合同：
  - `tv_obv`：校验每根增量是否为 `sign(close - close[1]) * volume`。
  - `tv_obv_ema_20`：校验是否满足 `EMA(tv_obv, 20)` 递推。
  - `tv_adl`：校验每根增量是否为 `CLV * volume`。
  - `tv_pvt`：校验每根增量是否为 `volume * close.pct_change()`。
  - `tv_pvi`：校验成交量上升时按收益率递推，否则保持不变。
  - `tv_nvi`：校验成交量下降时按收益率递推，否则保持不变。

## 判定

- `PASS`：locked 142 列完整，且数值/递推检查通过。
- `FAIL`：列合同失败，或数值差异超过容忍。
- `SKIP_VALUES`：基础行情列缺失，无法复算数值，只能检查 schema。
