---
name: tv-factor-audit
description: 审计本地 tv_ TradingView 因子数据是否符合锁定的 142 列公式合同。用于核实 tv_ 列、检查 TV指标库 docx 源码来源、校验 CSV/Parquet 行情特征数据、确认未来 data hub 是否复现 locked 142 合同，或说明 TV 因子审计边界；默认只读，不追加或重写行情数据。
---

# TV 因子审计

## 目标

这个 skill 用于核实 `tv_` 开头的 142 个 TradingView 衍生指标是否符合 locked 142 公式合同。

默认前提：这 142 个 `tv_` 指标已经完成来源盘点、公式复算和数值核验；后续任务的重点是检查新文件或新 data hub 是否仍然复现同一套合同。

## 工作原则

- 默认只读：不要向行情数据、特征数据或 data hub 追加列、重写文件、覆盖文件。
- 以 `references/tv-locked-142-contract.json` 为机器可读合同。
- 需要解释公式来源时，读取 `references/tv-formulas.md`。
- 需要确认审计口径时，读取 `references/tv-audit-policy.md`。
- 需要执行核验时，优先运行 `scripts/tv_factor_audit.py`。
- 不假设数据根目录固定；用户可以提供任意 CSV、Parquet 文件或目录。
- 如果行情数据和特征数据分开存储，先确认当前视图同时包含基础行情列和 `tv_` 列；缺少依赖时只报告缺失项。

## 快速流程

1. 读取 `references/tv-audit-policy.md`，确认只读边界和累计列口径。
2. 读取 `references/tv-locked-142-contract.json`，获得 locked 142 列清单。
3. 如果用户只问公式或来源，读取 `references/tv-formulas.md` 并用中文说明。
4. 如果用户给出数据路径，运行：

```powershell
python -X utf8 C:\Users\maolulu\.codex\skills\tv-factor-audit\scripts\tv_factor_audit.py check-data --data "<数据文件或目录>"
```

5. 输出结论时区分：
   - `PASS`：列合同和数值合同通过。
   - `FAIL`：存在缺列、额外列、顺序不一致或数值不一致。
   - `SKIP_VALUES`：列合同可检查，但缺少数值复算依赖。

## 常用命令

查看 locked 142 概览：

```powershell
python -X utf8 C:\Users\maolulu\.codex\skills\tv-factor-audit\scripts\tv_factor_audit.py summary
```

检查单个 CSV 或 Parquet：

```powershell
python -X utf8 C:\Users\maolulu\.codex\skills\tv-factor-audit\scripts\tv_factor_audit.py check-data --data "<file.csv>"
python -X utf8 C:\Users\maolulu\.codex\skills\tv-factor-audit\scripts\tv_factor_audit.py check-data --data "<file.parquet>"
```

只检查列合同：

```powershell
python -X utf8 C:\Users\maolulu\.codex\skills\tv-factor-audit\scripts\tv_factor_audit.py check-data --data "<数据路径>" --mode schema
```

检查目录中的样本文件：

```powershell
python -X utf8 C:\Users\maolulu\.codex\skills\tv-factor-audit\scripts\tv_factor_audit.py check-data --data "<目录>" --limit 5
```

查看逐列比较明细：

```powershell
python -X utf8 C:\Users\maolulu\.codex\skills\tv-factor-audit\scripts\tv_factor_audit.py check-data --data "<数据路径>" --include-columns
```

## 输出口径

向用户汇报时保持简洁：

- 说明检查了多少个文件、多少个 `tv_` 列。
- 说明是否完整命中 locked 142。
- 如果失败，列出最重要的缺失列、额外列或数值不一致列。
- 对 `tv_obv`、`tv_obv_ema_20`、`tv_adl`、`tv_pvt`、`tv_pvi`、`tv_nvi` 使用递推/增量校验口径；不要把历史累计基准导致的绝对值偏移误判为公式错误。
- 对短历史递归指标先考虑 warmup/初始化差异，再判断是否真的数值不一致。
