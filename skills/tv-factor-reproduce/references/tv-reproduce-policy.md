# TV locked 142 复现边界

## 默认行为

- 默认只读；`selftest` 不创建数据文件。
- 只有 `compute --output "<output>"` 授权写入该外部候选文件；`<output>` 必须是外部绝对路径，父目录必须预先存在，CLI 不负责创建目录。
- 不覆盖已有输出，不修改输入，不读取 ClickHouse，不访问 qdh API。
- `--qdh-root "<qdh-root>"` 是必填的显式受保护根目录；目录特征与 `QUANT_DATA_ROOT` 检测是附加防线，不能替代显式根。
- 将当前加载的 `SKILL.md` 所在目录解析为 `<skill-root>`，并保持该目录及 bundled 文件只读。
- `<python>` 必须精确为 Python 3.10.20、NumPy 2.2.6、pandas 2.3.3、PyArrow 23.0.1。
- 多 agent 并行时，每个 agent 必须使用唯一且尚不存在的 `<output>`；临时文件使用 PID+UUID 唯一名称，并以 hard-link no-clobber 方式发布。

## 输入合同

- 一个 Parquet 文件必须代表一个完整、连续的 symbol-timeframe 历史。
- 必需列为 `trade_time, open, high, low, close, volume`。
- `trade_time` 必须为无空值的 Arrow timestamp，严格递增且唯一。
- OHLCV 必须可转换为有限 float64。
- 默认必须同时存在至少一行 warmup 和一行 live。
- 仅当上层已确认 ClickHouse 对该序列没有更早行情时，允许显式 `--allow-cold-start`；不开启时零 warmup 必须失败。

## Warmup 与累计锚点

- 在 warmup+live 全历史上调用核心一次，然后输出 `trade_time >= live_start` 的后缀。
- OBV、ADL、PVT 在最早输入行锚定为 0；PVI、NVI 锚定为 1000。
- 不得在 live-start、年份边界或 Hive 分区处重新初始化。
- 合法 cold start 从输入首行按既定 0/1000 锚点初始化；输出仍严格满足 `trade_time >= live_start`，不得写出更早行。

## 输出合同

- 输出恰为 143 列：`trade_time` 加 locked 142，顺序固定。
- 142 个因子均为 nullable float64，无有效 Inf，无负零。
- 输出路径必须尚不存在，并且不得位于显式受保护或可识别的 qdh 根目录内。

## 统一 writer 边界

本 skill 只产生 TV 单族外部候选，不负责把它拼接到 WH6、indicator_py 或 Excel 因子。qdh 的 466 列 schema、Hive 分区、全量 bitwise 验收、READY 密封、原子切换和回滚只由 orchestrator 执行；不得用本 CLI 直接替换 `qdh/features/**/data.parquet`。
