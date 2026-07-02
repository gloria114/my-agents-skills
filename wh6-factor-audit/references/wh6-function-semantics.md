# WH6 函数语义

内置数值锚点验证器实现了以下稳定基础函数，用来捕捉悄悄发生的计算漂移：

- `REF(X,N)`：向前平移 `N` 行。
- `MA(X,N)`：完整 `N` 行窗口的滚动简单平均。
- `EMA(X,N)`：指数移动平均，`alpha = 2 / (N + 1)`，递归形式。
- `SMA(X,N,M)`：文华风格递归平滑，`alpha = M / N`；初始化后，缺失输入沿用上一状态。
- `SUM(X,N)`：滚动求和；`SUM(X,0)` 表示累计求和。
- `HHV(X,N)` / `LLV(X,N)`：滚动最大值/最小值。
- `STD(X,N)`：滚动总体标准差，`ddof=0`。
- `AVEDEV(X,N)`：相对滚动均值的平均绝对偏差。
- `COUNT(cond,N)`：滚动统计真值数量。
- `IF` / `IFELSE`：向量化条件选择。

目前数值锚点覆盖 MA、EMA、DEMA、SMA、MACD、KD、KDJ、RSI、ATR、BIAS、ROC、BOLL、CCI、DMI、OBV 增量、VWMA、Z-SCORE、ADTM 等公式族中的列。

以下区域属于未支持或部分支持，应报告为边界，而不是直接报告为失败：

- 文华专有行情字段或函数，例如 `CCL`、`CJLVOL`、`SETTLE`、`FORCAST`、`VOLATILITY`、`SAR`、`SAR1`。
- 绘图、颜色、文字、声音、图标、样式命令。
- 198 列全量逐单元格证明；除非后续加入并实际运行完整 WH6 解释器。
