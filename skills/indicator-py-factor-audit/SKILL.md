---
name: indicator-py-factor-audit
description: 审计本地 indicator_py_ 因子数据是否符合锁定的 59 列公式合同。用于核实 indicator_py 列、解释公式来源、校验 CSV/Parquet 行情特征数据、或检查未来数据是否复现 locked 59 合同；默认只读，不追加或重写行情数据。
---

# Indicator PY 因子审计

## 目标

这个 skill 用于核实 `indicator_py_` 开头的 59 个本地 Python 指标是否符合已经锁定的公式合同。

默认前提：这 59 个 `indicator_py_` 指标已经完成反推、验证和锁定；后续任务的重点是检查新的数据文件是否仍然复现同一套公式，而不是重新发明或改写公式。

## 适用场景

使用本 skill，当用户要求：

- 核实 CSV 或 Parquet 中的 `indicator_py_` 列是否准确。
- 查看或解释 `indicator_py_` 指标公式。
- 比较未来行情特征数据是否仍然符合 locked 59 合同。
- 确认 `indicator_py_` 列数量、顺序、命名、公式依赖是否一致。
- 迁移到新的 data hub 后，检查 `indicator_py_` 因子是否仍然可审计。

## 工作原则

- 默认只读：不要向用户的行情数据、特征数据或 data hub 追加列、重写文件、覆盖文件。
- 以 `references/indicator-py-locked-59-contract.json` 为机器可读合同。
- 需要解释公式时，读取 `references/indicator-py-formulas.md`。
- 需要执行核验时，优先运行 `scripts/indicator_py_audit.py`。
- 不假设数据根目录固定；用户可以提供任意 CSV、Parquet 文件或目录。
- 如果行情数据和特征数据分开存储，先确认当前可见数据是否已经包含核验所需列；缺失依赖时只报告缺失项。

## 快速流程

1. 先读取 `references/indicator-py-audit-policy.md`，确认审计边界。
2. 读取 `references/indicator-py-locked-59-contract.json`，获得 locked 59 列清单与依赖。
3. 如果用户只问公式或来源，读取 `references/indicator-py-formulas.md` 并用中文说明。
4. 如果用户给出数据路径，运行：

```powershell
python -X utf8 C:\Users\maolulu\.codex\skills\indicator-py-factor-audit\scripts\indicator_py_audit.py check-data --data "<数据文件或目录>"
```

5. 输出结论时区分：
   - `PASS`：列合同和数值合同通过。
   - `FAIL`：存在缺列、额外列、顺序不一致或数值不一致。
   - `SKIP_VALUES`：列合同可检查，但缺少数值复算依赖。

## 常用命令

查看 locked 59 概览：

```powershell
python -X utf8 C:\Users\maolulu\.codex\skills\indicator-py-factor-audit\scripts\indicator_py_audit.py summary
```

检查单个 CSV 或 Parquet：

```powershell
python -X utf8 C:\Users\maolulu\.codex\skills\indicator-py-factor-audit\scripts\indicator_py_audit.py check-data --data "<file.csv>"
python -X utf8 C:\Users\maolulu\.codex\skills\indicator-py-factor-audit\scripts\indicator_py_audit.py check-data --data "<file.parquet>"
```

检查目录中的样本文件：

```powershell
python -X utf8 C:\Users\maolulu\.codex\skills\indicator-py-factor-audit\scripts\indicator_py_audit.py check-data --data "<目录>" --limit 5
```

只检查列合同：

```powershell
python -X utf8 C:\Users\maolulu\.codex\skills\indicator-py-factor-audit\scripts\indicator_py_audit.py check-data --data "<数据路径>" --mode schema
```

## 输出口径

向用户汇报时保持简洁：

- 说明检查了多少个文件、多少个 `indicator_py_` 列。
- 说明是否完整命中 locked 59。
- 如果失败，列出最重要的缺失列、额外列或数值不一致列。
- 不要把审计失败写成公式错误；先判断是数据列缺失、依赖列缺失、文件格式差异，还是值真的不一致。

