# WH6 公式审阅指南

## 能够声称什么

当前实现是 locked-198、locked 默认参数、严格时序 pipeline 下的纯 Python 复现：

- `wh6_formulas_v2.py` 含 97 个显式 `formula_000`–`formula_096` 函数。
- 198 个输出均以显式 `outputs['wh6_*'] = ...` 赋值，并与 `COLUMN_ORDER` 一致。
- 公式必须保留原生 Python `BinOp` / `Compare` 表达式；`ctx.binary`、`ctx.resolve`、`ctx.unary` 调度调用必须为零。
- `wh6_primitives.py` 提供已锁定函数语义；运行时无公式解析、JSON/.XTRD 读取、`eval` 或动态 import。
- 三份核心源码不得 import `json`、`pathlib`、`requests`、`importlib`、`qdh` 或旧 `wh6_formula_engine`。
- 全量差分报告证明锁定范围内 legacy、候选和 live features bitwise 一致。

不要声称它支持任意公式、任意参数、任意行顺序或完整通用 WH6 解释器语义。

## 审阅顺序

1. 先运行 `python -B "$skillRoot\scripts\wh6_selftest.py"`（`$skillRoot` 按 `SKILL.md` 设置），确认三份源码和 full report hash 未变。
2. 检查 `FORMULA_GROUPS` 是否仍是 97 个连续编号函数。
3. 检查 `FORMULA_GROUP_METADATA` 的每组输出是否与函数中的显式 `outputs[...]` 集合一致。
4. 检查所有显式输出的并集是否恰好等于 198 列 `COLUMN_ORDER`。
5. 检查字段绑定和 Inf→null 仍在 candidate 执行路径中。
6. 对 primitives 或公式的任何改动重新跑 synthetic、warmup/no-warmup/partial-warmup pilots 及 558/3,555 full 差分。

## 参数边界

以下参数在 locked 来源中已声明，但不影响锁定数值输出或只服务绘图。保留当前默认实现，不要为了“让参数看起来生效”而改公式：

- `BOLL.P`
- `VWMA.N1`、`VWMA.N2`、`VWMA.N4`、`VWMA.N5`、`VWMA.N6`
- `WTD.N`
- `formula083.P`
- `formula093.M`
- `formula096.K`

若要让这些参数产生新数值行为，应作为新合同和新验收任务，不得静默改变 locked-198。

## SAR / SAR1

当前 `SAR` 与 `SAR1` 只在锁定默认参数与已验收输入上证明等价。primitive 没有建立任意 window 或 `sar1` 模式的一般语义差异，因此：

- 可以说两列在 locked full 数据上与 legacy/live bitwise 一致。
- 不可以说实现支持任意 SAR/SAR1 参数，或已证明两种模式在所有输入上具有平台通用语义。
- 修改 SAR/SAR1 primitive 前必须增加独立边界向量并重跑全量差分。
