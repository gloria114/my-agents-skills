---
name: excel-factor-reproduce
description: 用锁定的纯 Python 公式安全复现 66 个 excel_ 因子。用于校验技能核心、对一个包含全部可得 pre-2020 warmup 与 live 行情的连续 Parquet 序列计算 trade_time+66 外部 staging、在 CH 已确认零 warmup 时显式 cold start，或准备交给统一 features writer 的 Excel 因子族产物；默认只读，不用于审计既有因子、新增指标、覆盖 qdh 或直接发布宽表。
---

# Excel 因子复现

## 执行环境

- 将当前加载的 `SKILL.md` 所在目录解析为 `<skill-root>`；所有脚本与 references 均从该目录按相对路径定位，不假定任何 agent 的主目录或技能安装目录。
- `<python>` 必须是 Python 3.10.20，并且安装 NumPy 2.2.6、pandas 2.3.3、PyArrow 23.0.1。运行 `selftest` 或 `compute` 时必须通过 CLI 的精确版本检查。
- `<skill-root>` 及其全部 bundled 文件保持只读。输入、staging、日志和运行证据必须位于 skill 目录之外。
- 多 agent 并行时，每个 agent 只处理分配给自己的单一 symbol/timeframe 序列，并使用唯一且尚不存在的 `<output>`。允许共享 staging 根目录，不允许共享输出目标。
- `<qdh-root>`、`<input>`、`<staging-root>` 和 `<output>` 均表示由调用方解析并传入的绝对路径。

## 固定边界

- 默认只运行 `selftest`；除非用户明确给出 `compute`、外部 staging 根目录和新输出文件，否则不要写文件。
- 只把 `scripts/factor_excel.py` 作为 66 列计算核心；先校验 `references/core-lock.json`，不要改公式、参数、列名或顺序。
- 只接收一个 symbol/timeframe 的完整有序序列：全部可得 pre-2020 warmup 行必须位于 live 行之前。若上层 CH preflight 已确认该序列 pre-2020 为零，才可对该序列显式使用 `--allow-cold-start`；不要把此开关全局套用，也不要拼接多个品种或周期。
- 禁止把本 skill 的输出写到 qdh 根目录、`market`、现有 `features` 或任何 Hive 分区中，也不要覆盖已有 staging 文件。
- 把 `trade_time+66` 视为单因子族的外部中间产物。orchestrator 独占统一 466 列拼接、Hive 分区、全量验收、原子发布和回滚职责；不要绕过它直接发布。
- 不读取或依赖 skill 包之外的公式源码、audit skill、工作簿或 `.XTRD` 执行公式。

## 标准流程

1. 运行无写入自检：

```text
<python> -B -X utf8 "<skill-root>/scripts/excel_factor_reproduce.py" selftest
```

2. 确认输入是单个完整连续序列，至少包含 `trade_time, open, high, low, close, volume`，时间严格递增。默认要求同时含 warmup 与 live；CH preflight 为零的合法 cold-start 序列除外。
3. 仅向已经存在的外部 staging 目录写一个全新 Parquet：

```text
<python> -B -X utf8 "<skill-root>/scripts/excel_factor_reproduce.py" compute --input "<input>" --staging-root "<staging-root>" --output "<output>" --live-start "2020-01-01" --qdh-root "<qdh-root>"
```

CH preflight 明确返回该序列 pre-2020 行数为 0 时，使用同一命令并追加：

```text
--allow-cold-start
```

4. 保留 CLI 的 JSON 摘要作为该序列证据；常规序列确认 `warmup_rows > 0`，cold-start 序列确认 `cold_start=true`、`warmup_rows=0` 且已有 CH 零行证据；所有序列均确认输出首键不早于 `live_start`、列数为 67、66 个特征均为 `float64`、无 Inf。
5. 将外部产物交给 orchestrator 做全族拼接与发布；不要自行复制到 qdh。

## 失败即停止

- 核心、合同或迁移证据 hash 不匹配时停止。
- 缺列、空输入、重复/乱序时间、没有 live、非有限输入或混合 symbol/timeframe 时停止。没有 warmup 时默认停止；只有逐序列 CH 零行证据和显式 `--allow-cold-start` 才放行。
- staging/output 不是绝对路径、输出不在 staging 根目录内、输出位于 qdh 内、父目录不存在或目标已经存在时停止。
- 不要用 live-only 数据替代 warmup+live，也不要把 warmup 行写入输出。

## 按需读取

- 解释公式时读取 `references/excel-formulas.md`。
- 核实 locked 66 列时读取 `references/excel-locked-66-contract.json`。
- 核实自包含性和文件 hash 时读取 `references/core-lock.json`。
