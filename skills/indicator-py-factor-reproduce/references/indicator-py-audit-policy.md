# Indicator PY 因子审计边界

## 锁定对象

本 skill 锁定的是当前 59 个 `indicator_py_` 指标列。它们来自本地 Python 指标体系和扩展因子，并已通过历史 CSV 数据反推和验证。

后续审计默认把这 59 列视为标准合同：

- 列名必须一致。
- 列数量必须一致。
- 推荐列顺序一致。
- 数值应能由合同公式复现。

## Source of Truth

机器可读合同：

- `references/indicator-py-locked-59-contract.json`

人类可读公式说明：

- `references/indicator-py-formulas.md`

执行脚本：

- `scripts/indicator_py_audit.py`

## 只读约束

除非用户明确要求生成报告文件，否则审计过程只输出终端结果，不修改任何行情数据或特征数据。

不要执行：

- 向 CSV 或 Parquet 追加 `indicator_py_` 列。
- 覆盖用户 data hub。
- 自动生成新的指标列合同。
- 把额外发现的指标纳入 locked 59。

## 数据形态

脚本支持 CSV 和 Parquet。数据可以是单文件，也可以是目录。

核验数值时，文件内需要包含公式所需基础列和 WH6 依赖列。若当前数据把行情和特征分开存储，应先在调用侧准备一张可核验视图，或只执行列合同检查。

