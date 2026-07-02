# Excel 因子审计边界

## 锁定对象

本 skill 锁定当前 66 个 `excel_` 指标列。它们来自 `各类技术指标合集.xlsx` 中可计算公式整理出的实际落地列，而不是整本工作簿中的全部指标。

后续审计默认把这 66 列视为标准合同：

- 列名必须一致。
- 列数量必须一致。
- 推荐列顺序一致。
- 数值应能由合同公式复现。

## Source of Truth

人类可读来源：

- `各类技术指标合集.xlsx`

机器可读合同：

- `references/excel-locked-66-contract.json`

人类可读公式说明：

- `references/excel-formulas.md`

执行脚本：

- `scripts/excel_factor_audit.py`

## 重要口径

`各类技术指标合集.xlsx` 中的公式是文本说明，不是 Excel `=...` 单元格公式。审计时不要依赖 Excel 计算引擎，应以 locked 66 合同和脚本实现为准。

EMA 递推类指标存在初始化/warmup 口径。脚本默认使用自动核验策略，兼容历史 CSV 中带隐藏 warmup 的长文件，以及从上市起点开始的短历史文件。

## 只读约束

除非用户明确要求生成报告文件，否则审计过程只输出终端结果，不修改任何行情数据或特征数据。

不要执行：

- 向 CSV 或 Parquet 追加 `excel_` 列。
- 覆盖用户 data hub。
- 自动生成新的指标列合同。
- 把工作簿里的其他 metadata-only 指标纳入 locked 66。

