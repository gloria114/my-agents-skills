---
name: wh6-factor-audit
description: "审计文华 WH6 因子数据是否符合锁定的 198 列公式合同。用于核实 wh6_ 列、检查 .XTRD 公式来源、校验 WH6 公式/代码 hash、比较未来 K 线数据与 locked 198 合同，或说明 WH6 因子审计边界；默认只读，不追加或重写行情数据。"
---

# WH6 因子审计

## 用途

用这个 skill 审计现有 `wh6_` 因子列是否符合锁定的 WH6 198 列合同。默认采用只读核实：除非用户明确要求进入新增指标或重算模式，否则不要追加列、重写生产数据，也不要把新发现的 WH6 指标自动纳入合同。

核心不变量是：

```text
.XTRD 公式定义 locked 198 列的含义。
Python 审计脚本核实来源完整性、CSV schema 是否存在这些列，以及稳定公式族的数值锚点。
skill 只报告证据和边界，不静默接受，也不静默修改数据。
```

## 默认流程

1. 识别用户给出的行情 CSV 路径、`.XTRD` 公式路径，或两者。
2. 需要确认内置合同时，运行 `scripts/wh6_audit.py summary`。
3. 如果有 `.XTRD` 公式根目录，运行 `check-xtrd`。
4. 如果有 CSV 文件或文件夹，运行 `check-csv`。
5. 当 CSV 含有 OHLCV 字段且需要数值抽查时，加上 `--numeric-anchors`。
6. 报告精确证据：缺失列、额外 `wh6_` 列、hash 不匹配、数值锚点不匹配，以及未覆盖的公式族。

常用命令：

```bash
python scripts/wh6_audit.py summary
python scripts/wh6_audit.py check-xtrd --xtrd-root "E:/path/to/wh6-formulas"
python scripts/wh6_audit.py check-csv --csv "E:/.../factor_a_10min.csv"
python scripts/wh6_audit.py check-csv --csv "E:/.../factor_data" --numeric-anchors --limit 5
```

## 合同

锁定合同是 `references/wh6-locked-198-contract.json`。

它包含 198 条从已核实 WH6 审计证据中固化下来的条目：

- `column`：锁定的 `wh6_` 列名。
- `indicator` 和 `output`：原始审计映射。
- `xtrd_relative_path`：相对于 WH6 公式根目录的公式文件。
- `param_text` 和 `code_text`：从 `.XTRD` 中提取的参数块和代码块。
- `param_sha256`、`code_sha256`、`xtrd_file_sha256`：用于检测漂移的 hash。
- `output_kind`：`explicit_named` 或 `anonymous_or_sanitized`。

不要把其他 `.XTRD` 文件自动视为本 skill 的审计范围。默认模式只审计 locked 198 列。

## References

按需读取这些文件：

- `references/wh6-xtrd-format.md`：`.XTRD` 文本结构和输出命名规则。
- `references/wh6-function-semantics.md`：已支持的 WH6 基础函数语义和数值锚点边界。
- `references/wh6-audit-policy.md`：不同审计证据等级下允许说到什么程度。

## 报告规则

措辞要保守：

- 只有 `check-xtrd` 通过时，才能说“公式来源合同吻合”。
- 只有 `check-csv` 没有报告缺失或额外 `wh6_` 列时，才能说“CSV schema 符合 locked 198 列”。
- 只有 `--numeric-anchors` 通过时，才能说“数值锚点吻合”。
- 除非实际运行了完整 WH6 解释器或等价验证器，否则不要声称“198 个指标每一个单元格都被完整重新解释并验证”。
- 如果用户要求新增 WH6 指标，把它视为单独的 onboarding 任务，不要静默修改 locked 合同。
