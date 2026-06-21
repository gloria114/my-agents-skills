---
name: integrate-update
description: 把一个工作台更新(整包 .zip / 文件夹 / 单个或多个文件)以隔离 worktree 分支集成进 git 仓库——建 worktree、覆盖更新(保护共享数据符号链接不被破坏)、出 diff 给用户审,用户明确点头后才合并或丢弃。用于用户想把一个新版本/补丁"集成/测试/合并"进工作台(如 hermes_quant)且不伤 main 分支。目标仓库在 WSL 中,需在 WSL 里运行脚本。
---

# integrate-update

把外部更新以**隔离 worktree** 集成进 git 仓库;main 分支在用户批准前绝不被动。
**所有危险操作(git worktree / rsync / merge)都封装在脚本里**,你只负责读 diff + 决策。

## ⚠️ 运行环境(关键)

目标仓库(默认 hermes_quant)在 **WSL** 里。脚本 `integrate_update.sh`(与本文件同目录)**必须在 WSL 中运行**:
- 你若在 WSL 里(Claude Code WSL 会话 / Hermes): `bash integrate_update.sh ...`
- 你若是 Windows 侧 agent: 用 `wsl -d Ubuntu-22.04 -- bash <脚本的WSL绝对路径> ...` 包一层。

## 何时用

用户给了一个工作台更新——可能是:
- 整包 `.zip`(如 workbench 2.0 重构),
- 一个文件夹(部分文件),
- 单个或多个文件(.py/.md/...)
——并想把它"集成/测试/合并"进仓库。默认目标 `~/workspace/hermes-env/hermes_quant`(可用 `--repo` 覆盖)。

## 工作方式

默认流程(不带 `--merge`/`--discard`):
1. 从仓库当前分支建一个 worktree(新分支),位置在**仓库同级目录**(保证相对符号链接仍解析)。
2. 把更新覆盖到 worktree:
   - `.zip` / 文件夹 → `rsync --delete`(默认)覆盖,捕获增/改/删;**排除 `.git` 和受保护路径**;
   - 单文件 → 复制到 worktree 根(要放子目录请用文件夹输入);
   - `--no-delete` → 不删旧文件(部分更新/打补丁)。
3. 打印 `git status` + `git diff --stat` 供审查。
4. **停下**。不自动提交、不自动合并。

受保护路径(`--protect`,默认 `02_data/weighted,03_features/data`)是**指向共享数据的符号链接**,脚本**永不覆盖或删除**它们。

## 你(agent)的执行流程

1. 跑默认模式(脚本路径换成实际安装位置):
   `bash integrate_update.sh --input <更新包>`
   (Windows 侧: `wsl -d Ubuntu-22.04 -- bash ~/.claude/skills/integrate-update/integrate_update.sh --input <更新包>`)
2. 读取脚本输出里的 `WORKTREE_PATH=...`,把 diff 摘要用大白话讲给用户:新增/删除/改了什么。
3. 建议用户在那个 worktree 里测试(如 `python 00_orchestrator/run.py --preflight`)。
4. 问用户: **合并进 main,还是丢弃?**
   - 合并 → `bash integrate_update.sh --merge   --worktree-path <WORKTREE_PATH>`
   - 丢弃 → `bash integrate_update.sh --discard --worktree-path <WORKTREE_PATH>`
5. 汇报结果。

## 安全红线(不可破)

- **合并 / 丢弃由人把关**:脚本只在显式 `--merge` / `--discard` 时执行;默认只到 diff。
- **受保护路径永不被覆盖/删除**(符号链接)。
- **worktree 必须建在仓库同级**,否则相对符号链接(指向 `../../_shared/`)会失效——脚本默认就这么放,改 `--worktree-path` 时要小心。
- 整包重构(zip/文件夹)用默认 `--delete`;只打几个补丁用 `--no-delete`。
- 先 `--dry-run` 可零副作用预览计划。

## 脚本接口

```
bash integrate_update.sh --input <zip|文件夹|文件> [选项]
  [--repo <path>]          默认 ~/workspace/hermes-env/hermes_quant
  [--protect <a,b,c>]      默认 02_data/weighted,03_features/data
  [--branch <name>]        默认 integrate/<输入名>-<时间戳>
  [--worktree-path <path>] 默认 仓库同级 <repo>-integrate-<时间戳>
  [--no-delete]            覆盖时不删旧文件
  [--dry-run]              只校验+打印计划,不建 worktree
bash integrate_update.sh --merge   --worktree-path <路径>
bash integrate_update.sh --discard --worktree-path <路径>
```

## 多个文件的注意

单文件模式只放到 worktree 根。要替换**特定子路径下的多个文件**(如 `00_orchestrator/run.py` 和 `01_config/gates.yaml`),把它们按目标结构放进一个文件夹(如 `patch/00_orchestrator/run.py`、`patch/01_config/gates.yaml`),用 `--input patch --no-delete`,脚本会按相对路径覆盖到正确位置。
