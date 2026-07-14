---
name: tv-factor-reproduce
description: 用锁定的纯 Python 核心安全复现 142 个 tv_ TradingView 因子。用于对核心做自检、从一个完整连续的 warmup+live Parquet 序列生成 trade_time+142 的外部 staging 候选、核实 warmup 切片与累计锚点，或审阅复现合同；默认只读，只有显式提供外部 output 才写入，禁止直接覆盖 qdh 的 466 列统一 features。
---

# TV 因子复现

## 执行环境

- 将当前加载的 `SKILL.md` 所在目录解析为 `<skill-root>`；所有脚本与 references 均从该目录按相对路径定位，不假定任何 agent 的主目录或技能安装目录。
- `<python>` 必须是 Python 3.10.20，并且安装 NumPy 2.2.6、pandas 2.3.3、PyArrow 23.0.1。运行 `selftest` 或 `compute` 时必须通过 CLI 的精确版本检查。
- `<skill-root>` 及其全部 bundled 文件保持只读。输入、staging、日志和运行证据必须位于 skill 目录之外。
- 多 agent 并行时，每个 agent 只处理分配给自己的单一 symbol/timeframe 序列，并使用唯一且尚不存在的 `<output>`。允许共享 staging 根目录，不允许共享输出目标。
- `<qdh-root>`、`<input>` 和 `<output>` 均表示由调用方解析并传入的绝对路径。

## 固定边界

- 默认只运行 `selftest`，不写任何数据。
- 仅使用本 skill 内的 `scripts/factor_tv.py`；不得依赖外部公式源码或 audit skill。
- 输入必须是一条按 `trade_time` 严格递增的完整 symbol-timeframe 历史。默认必须同时包含 warmup 与 live；只有上层已确认 ClickHouse 不存在更早行时，才可显式使用 `--allow-cold-start`。
- 必须在完整历史上一次计算，再按 `--live-start` 丢弃 warmup；不得按年份或分区重启递归状态。
- `compute` 只生成 `trade_time + 142 tv_` 的单族候选。它不是 qdh 466 列发布器，不得写入显式受保护的 `--qdh-root "<qdh-root>"` 或任何另行识别的 qdh 根目录。
- qdh 的 466 列合并、全量验收、READY、原子发布与回滚只能由 orchestrator 完成。

## 自检

```text
<python> -B -X utf8 "<skill-root>/scripts/tv_factor_reproduce.py" selftest
```

自检必须通过核心 SHA、locked 142 顺序、float64、无 Inf/负零、位级确定性、prefix invariance、PSAR 因果冷启动、累计锚点/递推和 warmup 切片。
同时必须验证零 warmup 默认失败、显式 cold-start 才放行，且输出不泄漏 `live-start` 之前的行。

## 生成外部 staging 候选

显式指定一个尚不存在、且位于 qdh 之外的输出文件：

```text
<python> -B -X utf8 "<skill-root>/scripts/tv_factor_reproduce.py" compute --input "<input>" --live-start "2020-01-01 00:00:00+08:00" --output "<output>" --qdh-root "<qdh-root>"
```

若某条序列已由上层核实 ClickHouse 确实没有 `live-start` 之前的行情，且输入首行就是 live 行，可追加：

```text
--allow-cold-start
```

该开关只是显式确认“上游无 warmup”，不会自行查询 ClickHouse；默认仍 fail-closed。

输出父目录必须由上层预先创建；CLI 不会隐式创建目录。命令拒绝覆盖已有文件、拒绝输入输出同路径、拒绝 qdh 内路径，先写入 PID+UUID 唯一临时文件，再以 hard-link no-clobber 方式发布。输出只含 live 行，列顺序固定为 `trade_time` 后接 locked 142。

## References 路由

- 需要机器可读列合同时，读取 `references/tv-locked-142-contract.json`。
- 需要解释公式时，读取 `references/tv-formulas.md`。
- 需要理解审计边界时，读取 `references/tv-audit-policy.md`。
- 需要核实复现/发布边界时，读取 `references/tv-reproduce-policy.md`。
- 需要核实当前验收结果与核心身份时，读取 `references/tv-acceptance.json` 与 `references/tv-core-lock.json`。

## 汇报口径

报告核心 SHA、输入/输出行数、warmup 行数、首个 live 时间、142 列顺序和输出 SHA。明确说明产物只是外部单族 staging，不是 qdh READY 或已发布 features。
