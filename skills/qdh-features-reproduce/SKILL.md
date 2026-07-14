---
name: qdh-features-reproduce
description: 编排四套锁定的纯 Python 因子复现 skill，从 qdh market 与 ClickHouse pre-2020 warmup 安全构建、位级验收并发布 trade_time+465（共 466 列）features。用于 market 新增或修订后全量重算，或对指定 symbol/timeframe 做外部 pilot；支持 WH6 198、indicator_py 59、Excel 66、TV 142 的统一列顺序、READY 密封、features-only dry-run/确认门控发布和崩溃恢复。默认不修改 qdh，禁止静默更新 meta。
---

# QDH Features Reproduce

这是四套公式 skill 之上的可移植编排层。公式权威在四个兄弟 skill 中；本 skill 锁定其当前源码和合同 hash，直接生成完整 466 列。

## 安装与运行身份

- `<skill-root>` 是当前加载的 `SKILL.md` 所在目录。不得从工作目录、用户名或特定 agent 的配置目录推断它。
- 五个 skill 必须作为同一套同级目录同时分发并启用：`wh6-factor-reproduce`、`indicator-py-factor-reproduce`、`excel-factor-reproduce`、`tv-factor-reproduce`、`qdh-features-reproduce`。
- 标准同级布局会自动发现。其他布局必须将 `QDH_FEATURE_SKILLS_ROOT` 设为包含这五个目录的绝对路径。
- `<python>` 必须明确指向 Python 3.10.20、NumPy 2.2.6、pandas 2.3.3、PyArrow 23.0.1 的解释器。自检和所有计算都会拒绝其他版本。
- skill 目录在运行期间只读。每个 agent 使用唯一的外部 `run-root`；同一 `run-root` 只允许一个操作者。不同 run 可在资源允许时并行，生产发布只能由一个操作者执行。

## 固定合同

- 范围：当前 62 个 JQ 品种、9 个周期；年份分区和总行数动态取自本轮 market snapshot。
- 输出：严格 `trade_time + 198 wh6_ + 59 indicator_py_ + 66 excel_ + 142 tv_`。
- 每个 symbol×timeframe 必须将全部 pre-2020 warmup 与 2020 至今 market 连成一个序列计算，再丢弃 warmup，最后按原年份 Hive 分区切回。
- ClickHouse 只允许 `readonly=2`、`SELECT FINAL`；warmup 只作临时输入，绝不进入正式输出。
- 部分 scope 只能作为 pilot，不能生成 READY 或发布。正式发布必须覆盖当前 market 的完整路径集合。
- 发布模式固定为 `features-only`：只替换 `<qdh-root>/features`，不修改 `meta`、catalog、schema、治理文档或 access log。

完整合同见 [execution-contract.md](references/execution-contract.md)，安全边界见 [safety-policy.md](references/safety-policy.md)，可移植部署见 [portability.md](references/portability.md)。

## 必须先做

1. 明确用户给出的绝对 `qdh-root`、外部 `run-root` 和 ClickHouse HTTP endpoint。
2. 告知用户正在使用本 skill；在任何写入或发布动作前说明边界。
3. 运行 `selftest`。它不得写数据，并必须通过四族数量、源码锁、列顺序和确定性检查。
4. 运行 `preflight`。它完整读取 market 并核实 CH warmup，但写入数为 0。

入口：

```text
<python> -B -X utf8 "<skill-root>/scripts/qdh_features.py" selftest
<python> -B -X utf8 "<skill-root>/scripts/qdh_features.py" preflight --qdh-root "<qdh-root>" --ch-url "<ch-url>" --workers 4
```

## Pilot

Pilot 必须写到 qdh 外部、同卷的新 run root。选择一个或多个完整 symbol×timeframe 序列：

```text
<python> -B -X utf8 "<skill-root>/scripts/qdh_features.py" build --qdh-root "<qdh-root>" --run-root "<new-run-root>" --ch-url "<ch-url>" --symbols SA --timeframes 1day --workers 1
<python> -B -X utf8 "<skill-root>/scripts/qdh_features.py" validate --qdh-root "<qdh-root>" --run-root "<run-root>" --ch-url "<ch-url>" --mode full --workers 1
```

Pilot 通过后，应验证 `finalize` 明确拒绝过滤 scope。不要把 pilot 目录合并进 live。

## 全量重建

使用全新的外部 run root，不传 scope filter：

```text
<python> -B -X utf8 "<skill-root>/scripts/qdh_features.py" build --qdh-root "<qdh-root>" --run-root "<new-run-root>" --ch-url "<ch-url>" --workers 4
<python> -B -X utf8 "<skill-root>/scripts/qdh_features.py" validate --qdh-root "<qdh-root>" --run-root "<run-root>" --ch-url "<ch-url>" --mode structure --workers 4
<python> -B -X utf8 "<skill-root>/scripts/qdh_features.py" validate --qdh-root "<qdh-root>" --run-root "<run-root>" --ch-url "<ch-url>" --mode full --workers 4
<python> -B -X utf8 "<skill-root>/scripts/qdh_features.py" finalize --qdh-root "<qdh-root>" --run-root "<run-root>" --ch-url "<ch-url>" --workers 4
```

中断后只有在源码、market、warmup 和既有 sequence record 全部仍匹配时才可加 `build --resume`。READY 一旦存在，stage、构建证据和验证证据不可再改；publisher 只可追加 journal、receipt 和 quarantine。

## 发布

始终先 dry-run：

```text
<python> -B -X utf8 "<skill-root>/scripts/qdh_features.py" publish --qdh-root "<qdh-root>" --run-root "<run-root>" --ch-url "<ch-url>" --workers 4
```

只有用户在看到 dry-run 后，明确给出本轮 `run_id` 与 `READY_SHA256` 并授权只切换 features，才可执行：

```text
<python> -B -X utf8 "<skill-root>/scripts/qdh_features.py" publish --qdh-root "<qdh-root>" --run-root "<run-root>" --ch-url "<ch-url>" --workers 4 --execute --confirm-run-id <run-id> --confirm-ready-sha256 <ready-sha256>
```

发布前 live 必须保留在同卷 quarantine，不自动删除。目录切换是带 journal 的两次 rename：可崩溃恢复，但不承诺未遵守维护锁的裸文件读取者看不到极短的目录切换窗口。

崩溃恢复本身也是 live 写操作，必须使用同一个 `run_id + READY_SHA256` 双确认：

```text
<python> -B -X utf8 "<skill-root>/scripts/qdh_features.py" recover --qdh-root "<qdh-root>" --run-root "<run-root>" --ch-url "<ch-url>" --workers 4 --confirm-run-id <run-id> --confirm-ready-sha256 <ready-sha256>
```

## 禁止事项

- 不把现有 features 当作公式 ground truth。
- 不在 qdh 内创建 staging、日志、READY 或临时文件。
- 不发布部分 scope，不在 live 上逐分区覆盖。
- 不在没有精确 `run_id + READY_SHA256` 授权时执行发布。
- 不因当前 meta 与 466 列 live 暂时不一致而静默修复 meta。
- 不绕过任何 source、market、warmup、路径集合、schema、trade_time、float64 位级或 Inf 门禁。
