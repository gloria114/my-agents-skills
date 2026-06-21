---
name: integrate-update
description: 把一个工作台更新(整包 .zip / 文件夹 / 单个或多个文件)以隔离 worktree 分支集成进 git 仓库——建 worktree、覆盖更新(保护共享数据符号链接)、自动恢复 .gitignore、出 diff,并在 agent 侧重新盖上 harness 版本标记、把 diff 分类汇总给用户,用户明确点头后才合并或丢弃。用于用户想把一个新版本/补丁"集成/测试/合并"进工作台(如 hermes_quant)且不伤 main 分支。目标仓库在 WSL 中,需在 WSL 里运行脚本。
---

# integrate-update

把外部更新以**隔离 worktree** 集成进 git 仓库;main 分支在用户批准前绝不被动。
**所有危险操作(git worktree / rsync / merge)都封装在脚本里**,你(agent)负责完整性修复 + 把 diff 讲给用户 + 等用户拍板。

## ⚠️ 运行环境(关键)

目标仓库(默认 hermes_quant)在 **WSL** 里。脚本 `integrate_update.sh`(与本文件同目录)**必须在 WSL 中运行**:
- 你若在 WSL 里(Claude Code WSL 会话 / Hermes): `bash integrate_update.sh ...`
- 你若是 Windows 侧 agent: 用 `wsl -d Ubuntu-22.04 -- bash <脚本的WSL绝对路径> ...` 包一层。

## 何时用

用户给了一个工作台更新——可能是:
- 整包 `.zip`(如 workbench v0.3 重构),
- 一个文件夹(部分文件),
- 单个或多个文件(.py/.md/...)
——并想把它"集成/测试/合并"进仓库。默认目标 `~/workspace/hermes-env/hermes_quant`(可用 `--repo` 覆盖)。

## 工作方式

默认流程(不带 `--merge`/`--discard`):
1. 从仓库当前分支建一个 worktree(新分支),位置在**仓库同级目录**(保证相对符号链接仍解析)。
2. 把更新覆盖到 worktree:
   - `.zip` / 文件夹 → `rsync --delete`(默认)覆盖,捕获增/改/删;**排除 `.git` 和受保护路径**;zip 用 python3 解压(无需系统 unzip),并自动剥掉单层包裹文件夹(如顶层 `hermes_quant/`);
   - 单文件 → 复制到 worktree 根(要放子目录请用文件夹输入);
   - `--no-delete` → 不删旧文件(部分更新/打补丁)。
3. **完整性检查**(脚本自动 + agent 认知,见下节)。
4. 打印 `git status` + `git diff --stat` 供审查。
5. **停下**。不自动提交、不自动合并。

受保护路径(`--protect`,默认 `02_data/weighted,03_features/data`)是**指向共享数据的符号链接**,脚本**永不覆盖或删除**。

## 完整性检查与自动修复(agent 必做)

覆盖后脚本会打印一段「### 2.5) 完整性」报告。**你必须读它并按需修复**:

- **保留项 [.gitignore]**: 脚本已用 `--keep` 处理——zip 没带就**自动从 HEAD 恢复**。看到"已从 HEAD 自动恢复 ✓"即可,无需你动手。
- **版本盖章 [harness_sha in ledger.py]**(溯源"哪个版本→哪个效果"的关键):
  - 报告"存在 ✓" → 无事。
  - 报告"缺失 ⚠️" → 这个 zip 基于盖章**之前**的代码。你需要在 worktree 里**重新盖**:
    1. 看 main 上盖章长啥样: `git -C <WORKTREE> show <主分支>:00_orchestrator/ledger.py`(主分支通常是 main)。
    2. 把这些**移植**到 zip 的新版本上:
       - `ledger.py`: `_git_describe()` 函数 + `import subprocess`、`Ledger.__init__` 里的 `self.harness_version = _git_describe(self.root)`、`record_trial()` 行字典里的 `harness_sha/branch/dirty` 三字段;
       - `run.py`: `_echo_harness_version()` 函数 + `main()` 里对它的调用。
    3. 验证: `python3 -m py_compile 00_orchestrator/ledger.py 00_orchestrator/run.py`,通过即告 "已重盖并验证 ✓"。
    4. **若 zip 把 ledger.py 改得太狠、盖章实在接不上 → 标红告诉用户,不要硬接、绝不自动合并**(等人决定)。

> 为什么重盖归 agent 而不是脚本: 盖章是几处代码片段,而 zip 会改同一文件的上下文, deterministic 的 `git apply` 会因上下文漂移冲突——这种"在新代码上重新落特性"是 agent 的活。

## 给用户的 diff 分类摘要(减负)

汇报 diff 时**不要**把原始 N 行改动甩给用户,而是**分组各一句**:
- 🔧 **基础设施(已自动)**: `.gitignore` 已恢复 / SHA 盖章已重盖(或标红)。
- ✨ **新增模块**: 如 `11_discovery/`、`04_skills/fast_engine_house_rules/`。
- 🗑️ **删除(请确认)**: 如 `proposal*.yaml`、`calendar/*.parquet`——**标红**,让用户确认是不是真该删。
- 🧠 **harness 逻辑改动(重点看)**: 如 `state_machine.py +358`、`run.py +141`。

结尾给一句**优先级**: "你只需重点看 X"。让用户从审 N 行 → 审 1 句摘要 + 1 个重点文件。

## 你(agent)的执行流程

1. 跑默认模式(脚本路径换成实际安装位置):
   `bash integrate_update.sh --input <更新包>`
   (Windows 侧: `wsl -d Ubuntu-22.04 -- bash ~/.claude/skills/integrate-update/integrate_update.sh --input <更新包>`)
2. 读「完整性」报告;若 `harness_sha 缺失` → 按《完整性检查》节重盖 + py_compile 验证。
3. 按上面《分类摘要》把 diff 讲给用户。
4. 建议用户在那个 worktree 里测试(如 `python 00_orchestrator/run.py --preflight`)。
5. 问用户: **合并进 main,还是丢弃?**
   - 合并 → `bash integrate_update.sh --merge   --worktree-path <WORKTREE_PATH>`
   - 丢弃 → `bash integrate_update.sh --discard --worktree-path <WORKTREE_PATH>`
6. 汇报结果。

## 安全红线(不可破)

- **合并 / 丢弃由人把关**:脚本只在显式 `--merge` / `--discard` 时执行;默认只到 diff。
- **受保护路径永不被覆盖/删除**(符号链接)。
- **`.gitignore` 等 --keep 项缺失自动恢复**(脚本);**SHA 重盖是 agent 做 + 验证 + 报告**,接不上就标红,不静默合并。
- **worktree 必须建在仓库同级**,否则相对符号链接(指向 `../../_shared/`)会失效——脚本默认就这么放,改 `--worktree-path` 时要小心。
- 整包重构(zip/文件夹)用默认 `--delete`;只打几个补丁用 `--no-delete`。
- 先 `--dry-run` 可零副作用预览计划。

## 脚本接口

```
bash integrate_update.sh --input <zip|文件夹|文件> [选项]
  [--repo <path>]          默认 ~/workspace/hermes-env/hermes_quant
  [--protect <a,b,c>]      默认 02_data/weighted,03_features/data   (永不覆盖/删除)
  [--keep <a,b,c>]         默认 .gitignore   (覆盖后若缺失, 从 HEAD 恢复)
  [--branch <name>]        默认 integrate/<输入名>-<时间戳>
  [--worktree-path <path>] 默认 仓库同级 <repo>-integrate-<时间戳>
  [--no-delete]            覆盖时不删旧文件
  [--dry-run]              只校验+打印计划,不建 worktree
bash integrate_update.sh --merge   --worktree-path <路径>
bash integrate_update.sh --discard --worktree-path <路径>
```

## 多个文件的注意

单文件模式只放到 worktree 根。要替换**特定子路径下的多个文件**(如 `00_orchestrator/run.py` 和 `01_config/gates.yaml`),把它们按目标结构放进一个文件夹(如 `patch/00_orchestrator/run.py`、`patch/01_config/gates.yaml`),用 `--input patch --no-delete`,脚本会按相对路径覆盖到正确位置。
