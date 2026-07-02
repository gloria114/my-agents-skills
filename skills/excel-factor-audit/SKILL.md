---
name: excel-factor-audit
description: 审计本地 excel_ 因子数据是否符合锁定的 66 列 Excel 指标公式合同。用于核实 excel_ 列、检查各类技术指标合集.xlsx 公式来源、校验 CSV/Parquet 行情特征数据、或确认未来 data hub 是否复现 locked 66 合同；默认只读，不追加或重写行情数据。
---

# Excel 因子审计

## 目标

这个 skill 用于核实 `excel_` 开头的 66 个指标是否符合 `各类技术指标合集.xlsx` 中可计算公式整理出的 locked 66 合同。

默认前提：这 66 个 `excel_` 指标已经完成来源核验、公式复算和锁定；后续任务的重点是检查新的数据文件是否仍然复现同一套公式。

## 工作原则

- 默认只读：不要向行情数据、特征数据或 data hub 追加列、重写文件、覆盖文件。
- 以 `references/excel-locked-66-contract.json` 为机器可读合同。
- 需要解释公式时，读取 `references/excel-formulas.md`。
- 需要执行核验时，优先运行 `scripts/excel_factor_audit.py`。
- 不假设数据根目录固定；用户可以提供任意 CSV、Parquet 文件或目录。
- 若行情数据和特征数据分开存储，先确认当前视图是否包含基础行情列和 `excel_` 列；缺失依赖时只报告缺失项。

## 快速流程

1. 读取 `references/excel-audit-policy.md`，确认审计边界。
2. 读取 `references/excel-locked-66-contract.json`，获得 locked 66 列清单。
3. 如果用户只问公式或来源，读取 `references/excel-formulas.md` 并用中文说明。
4. 如果用户给出数据路径，运行：

```powershell
python -X utf8 C:\Users\maolulu\.codex\skills\excel-factor-audit\scripts\excel_factor_audit.py check-data --data "<数据文件或目录>"
```

5. 输出结论时区分：
   - `PASS`：列合同和数值合同通过。
   - `FAIL`：存在缺列、额外列、顺序不一致或数值不一致。
   - `SKIP_VALUES`：列合同可检查，但缺少数值复算依赖。

## 常用命令

查看 locked 66 概览：

```powershell
python -X utf8 C:\Users\maolulu\.codex\skills\excel-factor-audit\scripts\excel_factor_audit.py summary
```

检查单个 CSV 或 Parquet：

```powershell
python -X utf8 C:\Users\maolulu\.codex\skills\excel-factor-audit\scripts\excel_factor_audit.py check-data --data "<file.csv>"
python -X utf8 C:\Users\maolulu\.codex\skills\excel-factor-audit\scripts\excel_factor_audit.py check-data --data "<file.parquet>"
```

检查目录中的样本文件：

```powershell
python -X utf8 C:\Users\maolulu\.codex\skills\excel-factor-audit\scripts\excel_factor_audit.py check-data --data "<目录>" --limit 5
```

只检查列合同：

```powershell
python -X utf8 C:\Users\maolulu\.codex\skills\excel-factor-audit\scripts\excel_factor_audit.py check-data --data "<数据路径>" --mode schema
```

需要查看逐列比较明细时：

```powershell
python -X utf8 C:\Users\maolulu\.codex\skills\excel-factor-audit\scripts\excel_factor_audit.py check-data --data "<数据路径>" --include-columns
```

## 输出口径

向用户汇报时保持简洁：

- 说明检查了多少个文件、多少个 `excel_` 列。
- 说明是否完整命中 locked 66。
- 如果失败，列出最重要的缺失列、额外列或数值不一致列。
- 不要把审计失败直接写成公式错误；先判断是数据列缺失、依赖列缺失、文件格式差异、初始化/warmup 差异，还是值真的不一致。

