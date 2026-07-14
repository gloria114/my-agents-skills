# WH6 复现安全策略

## 默认只读

- 未获明确写入授权时，只运行 `wh6_selftest.py`、`preflight`、验证器只读模式或直接 Parquet 审计。
- 只读审计直接读取 `market/`、`features/` 和 meta 文件；不要调用公共 `qd` API，以免写入 qdh `access_log.jsonl`。
- 不向 qdh 写入公式、合同、Python 执行器或临时报告。
- 不修改、追加或删除 qdh market。

## ClickHouse

- 只允许 `SELECT ... FINAL`，请求必须设置 `readonly=2`。
- 禁止 INSERT、ALTER、DELETE、TRUNCATE、DROP、OPTIMIZE 或任何 DDL/DML。
- pre-2020 warmup 只存在于进程内存，不落盘、不进入 stage/live features。

## Staging

- run-root 必须是绝对路径、位于 qdh 外部、与 qdh 同卷，且不是 symlink/reparse point。
- skill-root 永远只读；run-root、quarantine、临时文件、日志和控制证据都不得位于 skill-root 内或覆盖它。
- 每个 agent 必须使用唯一 run-root；同一 run 只能由一个 agent 从 build/resume 操作到 validate/finalize，禁止共享写入。
- 所有阶段必须使用精确 runtime：Python 3.10.20、NumPy 2.2.6、pandas 2.3.3、PyArrow 23.0.1。
- build 只能写 `<run-root>`，不得直接写 `<qdh-root>/features` 或生产 meta。
- 输入 market、ClickHouse warmup、源码 hash 任一在构建期间变化，立即失败；不要续用该 run。
- `--resume` 只能复用逐文件 hash 已验证的完成记录；不得信任仅有“完成”标记的文件。
- pilot/filter run 永远不能生成 READY。

## 验证与 READY

- structure validation 只用于 pilot 或快速结构检查，不能授权发布。
- full validation 必须覆盖未筛选的完整 scope，并复核路径全集、schema、行数、时间键、null/Inf、源码、market 与 warmup 快照。
- finalize 只能消费最新 full PASS；它必须通过 `--ch-url` 再快照 qdh market 与 CH warmup，重新复核所有证据后原子写 `control/READY`，READY 必须最后写。
- READY 之后任何 stage/control/source 变化都使 READY 失效。

## 统一发布边界

- WH6 READY 只封存 `trade_time + 198` 单族候选，不授权直接替换生产 features。
- 当前生产 features 固定为 `trade_time + 465`，共 466 列；只有 `qdh-features-reproduce` orchestrator 可以合并 WH6、Indicator-PY、Excel、TV，完成统一验收并执行原子发布或回滚。
- handoff 必须包含唯一 run-root、READY SHA256、staged inventory、输入快照和精确 runtime identity。
- 不得运行单族发布器覆盖 `<qdh-root>/features`，不得单独更新生产 manifest/snapshot，不得绕过 orchestrator READY 与用户确认门控。
- 只有 orchestrator execute 成功且 466 列 live verification PASS，才能宣布生产发布完成。
