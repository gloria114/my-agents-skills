# WH6 复现执行合同

## 锁定身份

- 公式族：97。
- 输出：198 个唯一 `wh6_` 列，顺序以 `scripts/wh6_formulas_v2.py::COLUMN_ORDER` 为准。
- 候选执行器 SHA256：`849c460a50864e05744211abe3e269b2e7e957312ee92ed2c432fbef4f89514e`。
- primitives SHA256：`9313b87f57138b9775ad502f8970d91bd81439e02f8056242561d2a822e39061`。
- 公式源码 SHA256：`e71c1d3be8c43c0c5e1ec0ac9fc204b471d07e527292b37571c08bc489439d8a`。
- 全量验收报告 SHA256：`02f091791c8d8568fdc6012f77cc5ed227634912c711be4d7e72899528d9ba93`。
- 已验收范围：558 个 symbol×timeframe 连续序列、3,555 个输出分区。

任何源码 hash 不同都表示新实现，必须重新完成 synthetic、pilot 和 full 差分验收；不得静默更新本合同。

## 精确运行时

所有 selftest、build、resume、validate 和 finalize 必须使用同一个解释器及以下精确版本：

| 组件 | 版本 |
|---|---|
| Python | `3.10.20` |
| NumPy | `2.2.6` |
| pandas | `2.3.3` |
| PyArrow | `23.0.1` |

任一版本不一致都必须失败，不得由 agent 自行选择另一个环境继续。同一 run 的 manifest、逐序列产物和验收证据必须来自这一 runtime identity。

## 输入合同

每个 symbol×timeframe 必须独立计算，并按 `trade_time` 严格升序拼接所有连续年份。禁止逐年冷启动或跨品种、跨周期共享状态。

基础字段绑定固定为：

| WH6 名称 | 输入列 |
|---|---|
| `OPEN` / `O` | `open` |
| `HIGH` / `H` | `high` |
| `LOW` / `L` | `low` |
| `CLOSE` / `C` / `SETTLE` | `close` |
| `VOL` / `CJLVOL` | `volume` |
| `CCL` | `open_interest` |

ClickHouse 只提供 `trade_date < 2020-01-01` 的 transient warmup：

- 使用对应周期的 `default.futures_market_data_*_tq FINAL`。
- HTTP 参数必须包含 `readonly=2`。
- 按 `contract_code` 过滤并按 `trade_time` 排序。
- warmup 只能进入内存计算，不能写入任何输出分区。
- warmup 与 live market 不能重叠；live 输出不得含 2020 年以前行。
- CH 中没有 pre-2020 行的序列是合法 cold start（当前 153 个）：记录为 cold start，并从首根 live bar 开始计算；零 warmup 行本身不是 preflight failure。

## 输出合同

- schema 恰好为 `trade_time + COLUMN_ORDER`，共 199 列。
- 198 个特征列必须为物理 `float64`；正负无穷必须在落盘前归一为 null。
- `trade_time` 的 Arrow 类型、行数和值必须与对应 market 分区完全一致。
- 保持 Hive 路径：`features/<symbol>/<timeframe>/<year>/data.parquet`。
- 只输出 2020-01-01 起的 market 行；warmup 只影响状态。
- 同一序列计算一次，再按原 market 年分区边界切片；禁止逐分区单独计算。

这里的输出是 WH6 单族候选。当前生产 features 固定为 `trade_time + 465`，共 466 列，只有 `qdh-features-reproduce` orchestrator 可以合并四个因子族、执行统一验收并发布。

## 位置无关命令

从当前已加载的 `SKILL.md` 所在目录解析 `<skill-root>`。不得从 agent 专属配置目录、用户目录、agent 类型或当前工作目录推断安装位置。以下占位符必须替换成调用环境的绝对值：

- `<python>`：符合精确运行时的解释器。
- `<skill-root>`：本 skill 包的绝对路径；只读。
- `<qdh-root>`：qdh 的绝对路径。
- `<run-root>`：qdh 外部、与 qdh 同卷、当前 agent 独占的唯一绝对路径。
- `<ch-url>`：只读 ClickHouse HTTP(S) endpoint。

每个 agent 必须使用不同的 `<run-root>`。同一 run 从 build 到 finalize 只能有一个操作者；禁止两个 agent 并发 resume、validate 或 finalize 同一 run。所有命令统一用 `-B` 禁止生成 `__pycache__`。

全局只读检查：

```text
<python> -B "<skill-root>/scripts/wh6_reproduce.py" preflight --qdh-root "<qdh-root>" --ch-url "<ch-url>" --workers 4
```

即使指定 `--symbols/--timeframes`，preflight 仍核查全局 558 个 market 序列及全局 CH warmup 快照；筛选只缩小报告中的 `selected_scope` 和随后 pilot build 的范围。

隔离构建：

```text
<python> -B "<skill-root>/scripts/wh6_reproduce.py" build --qdh-root "<qdh-root>" --run-root "<run-root>" --ch-url "<ch-url>" --workers 4
```

可选参数：`--symbols IM,rb`、`--timeframes 5m,1day`；build 可加 `--resume`，但只能由该 run 的唯一操作者执行。symbol 大小写必须与 qdh 现有分区完全一致，不得归一化。workers：preflight 1–8，build 1–4。

验证、封存和 live 核验：

```text
<python> -B "<skill-root>/scripts/wh6_validate.py" validate --mode structure --qdh-root "<qdh-root>" --run-root "<run-root>" --workers 4
<python> -B "<skill-root>/scripts/wh6_validate.py" validate --mode full --qdh-root "<qdh-root>" --run-root "<run-root>" --ch-url "<ch-url>" --workers 4
<python> -B "<skill-root>/scripts/wh6_validate.py" finalize --qdh-root "<qdh-root>" --run-root "<run-root>" --ch-url "<ch-url>" --workers 4
```

READY 只授权把 WH6 候选交给统一 orchestrator，不授权单族生产替换。生产交付规则见 [safety-policy.md](safety-policy.md)。以各脚本当前 `--help` 为最终 CLI 事实；文档与 `--help` 不一致时停止，不要猜参数。
