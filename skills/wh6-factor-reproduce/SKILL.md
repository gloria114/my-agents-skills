---
name: wh6-factor-reproduce
description: "用锁定的纯 Python 97 公式族安全复现并验证 198 个 WH6 因子。用于基于 qdh market 执行 selftest、preflight、pilot/full 外部 staging、ClickHouse pre-2020 warmup 核验、full validation 与 READY 封存，或为统一 qdh features orchestrator 准备 WH6 候选；默认只读，不直接发布当前 466 列生产 features。"
---

# WH6 因子复现

## 核心边界

复现固定的 198 个输出和 97 个公式族。把本 skill 中的纯 Python 源码视为执行实现，把 qdh 视为行情输入；不要向 qdh 写入公式、合同、解释器代码或临时文件。

默认只读。除非用户明确要求 build 或 finalize，否则只运行 selftest、preflight 或直接读取 Parquet 的验证。skill 目录始终只读，所有 staging、日志、临时文件和控制证据必须写入外部 run-root。

本实现只承诺 locked 默认参数及严格时序 pipeline 下的等价结果，不是支持任意参数、任意输入顺序的通用 WH6 解释器。

当前生产 features 合同为 `trade_time + 465`，共 466 列。只有 `qdh-features-reproduce` orchestrator 可以合并四个因子族并发布生产 features；本 skill 只交付 `trade_time + 198` 的 WH6 候选和验收证据。

## 位置、运行时与多 agent 合同

先从当前已加载的 `SKILL.md` 所在目录解析 `<skill-root>`；不得从用户目录、agent 名称、agent 专属配置目录、当前工作目录或固定安装路径推断。以下命令中的尖括号名称都是必须替换的参数：

- `<python>`：同一个受控解释器，其版本必须精确为 Python 3.10.20、NumPy 2.2.6、pandas 2.3.3、PyArrow 23.0.1。
- `<skill-root>`：本 skill 包的绝对路径。
- `<qdh-root>`：目标 qdh 的绝对路径。
- `<run-root>`：qdh 外部、与 qdh 同卷、由 orchestrator 或当前 agent 独占的唯一绝对路径。
- `<output>`：本 skill 的 WH6 候选根，固定为 `<run-root>/stage/features`，不得位于 qdh 或 skill 目录内。
- `<ch-url>`：只读 ClickHouse HTTP(S) endpoint。

所有阶段必须使用同一个 `<python>`。每个 agent 使用不同的 `<run-root>`；同一 run 从 build、resume、validate 到 finalize 只能由一个 agent 操作，不得并发共享或交叉接管。cc-switch 分发必须逐字节保留 skill 文件，不得改写换行或锁定源码。

## 开始前

1. 运行静态与合成自检；`-B` 禁止生成 `__pycache__`：

   ```text
   <python> -B "<skill-root>/scripts/wh6_selftest.py"
   ```

2. 自检必须确认精确运行时、源码/report hash、97/198 AST 合同、无运行时公式文件读取、acceptance mismatch 全零及确定性合成计算。
3. 读取 [execution-contract.md](references/execution-contract.md) 确认数据与命令合同。
4. 涉及任何写入、READY 或生产交付时，必须先读取 [safety-policy.md](references/safety-policy.md)。
5. 审阅公式、参数或 SAR/SAR1 时，读取 [formula-review-guide.md](references/formula-review-guide.md)。

## 工作流

### 只读 preflight

preflight 始终检查全局 558 个 market 序列及对应 CH warmup；筛选参数只缩小 `selected_scope` 和随后允许的 pilot build 范围，不缩小全局输入快照。CH 中没有 pre-2020 行的序列是合法、被记录的 cold start，从首根 live bar 开始计算，本身不是 preflight failure。

```text
<python> -B "<skill-root>/scripts/wh6_reproduce.py" preflight --qdh-root "<qdh-root>" --ch-url "<ch-url>" --workers 4
```

筛选 pilot 时追加 `--symbols IM,rb --timeframes 5m,1day`。symbol 大小写必须与 qdh 现有分区完全一致，不得归一化。

### 隔离 build

只写 `<run-root>`。实际运行必须分配新的唯一 run id；筛选范围沿用 `--symbols/--timeframes`，同一操作者续跑使用 `--resume`。

```text
<python> -B "<skill-root>/scripts/wh6_reproduce.py" build --qdh-root "<qdh-root>" --run-root "<run-root>" --ch-url "<ch-url>" --workers 4
```

pilot 允许 build 和 structure validate，但不得产生 READY。

### 验证与 READY

先做 structure 或 full 验证。只有无筛选的 full scope、最新 full PASS、输入未变且全部库存/hash 门禁通过时，才允许 finalize 原子写入 `<run-root>/control/READY`，且 READY 必须最后写。

```text
<python> -B "<skill-root>/scripts/wh6_validate.py" validate --mode full --qdh-root "<qdh-root>" --run-root "<run-root>" --ch-url "<ch-url>" --workers 4
<python> -B "<skill-root>/scripts/wh6_validate.py" finalize --qdh-root "<qdh-root>" --run-root "<run-root>" --ch-url "<ch-url>" --workers 4
```

### 交给统一 orchestrator

向 `qdh-features-reproduce` 提供同一个 `<run-root>`、当前 READY SHA256、WH6 staged inventory 和精确 runtime identity。不得把 WH6 单族目录移动到 `<qdh-root>/features`，不得调用单族脚本替换生产 features，也不得单独更新生产 meta。

## 报告规则

- 分开报告 runtime identity、源码身份、输入快照、staging、full validation、READY 和 orchestrator handoff 状态。
- 只有 full validation PASS 且 READY 已生成，才能说“WH6 候选可交付”。
- 只有统一 orchestrator execute 成功且 466 列 live verification PASS，才能说“生产 features 已发布”。
- pilot PASS 只能证明所选范围，不得外推到 558 序列或 3,555 分区。
- 不得把 locked-default 等价表述成通用 WH6 参数语义证明。
