#!/usr/bin/env bash
# integrate_update.sh
# 把一个工作台更新(.zip / 文件夹 / 单文件) 以隔离 worktree 集成进 git 仓库。
# 默认目标仓库: ~/workspace/hermes-env/hermes_quant  (可用 --repo 覆盖)
# 默认受保护路径(永不覆盖/删除): 02_data/weighted, 03_features/data
# 默认保留项(覆盖后若缺失,自动从 HEAD 恢复): .gitignore
#
# 模式:
#   默认(diff) : 建 worktree -> 覆盖更新 -> 完整性检查 -> 出 diff -> 停下
#   --merge    : 提交 worktree 改动 -> 合并进仓库当前分支 -> 清理 worktree
#   --discard  : 删除 worktree + 分支
#   --dry-run  : 只校验和打印计划, 不建 worktree (零副作用)
#
# 合并/丢弃是 human-gated: 必须显式 --merge / --discard 才执行。
# zip 用 python3 解压(不依赖系统 unzip),并自动剥掉单层包裹文件夹(如顶层 hermes_quant/)。
# 完整性: --keep 的文件覆盖后若没了自动从 HEAD 恢复; 并报告版本盖章(harness_sha)是否存活。
#   注: 重盖 SHA 是 agent 的认知任务(见 SKILL.md), 脚本只"恢复+报告", 不擅自改代码。
# ⚠️ 本脚本应在 WSL 里运行(仓库在 WSL)。
set -euo pipefail

DEFAULT_REPO="$HOME/workspace/hermes-env/hermes_quant"
DEFAULT_PROTECT="02_data/weighted,03_features/data"
DEFAULT_KEEP=".gitignore"

MODE="diff"
REPO=""
INPUT=""
PROTECT=""
KEEP=""
BRANCH=""
WORKTREE=""
NO_DELETE=0
DRY_RUN=0

SELF="$(cd "$(dirname "$0")" 2>/dev/null && pwd)/$(basename "$0")"
[[ "$SELF" == "/"* ]] || SELF="$0"

usage() {
  cat <<'EOF'
用法:
  integrate_update.sh --input <更新包> [选项]                 # 建 worktree + 完整性 + 出 diff
  integrate_update.sh --merge   --worktree-path <路径>        # 合并进当前分支 + 清理
  integrate_update.sh --discard --worktree-path <路径>        # 丢弃 worktree + 分支

选项:
  --input <path>         更新包: .zip / 文件夹 / 单文件
  --repo <path>          目标仓库(默认 ~/workspace/hermes-env/hermes_quant)
  --protect <a,b,c>      受保护路径,逗号分隔(默认 02_data/weighted,03_features/data)
  --keep <a,b,c>         保留项,覆盖后若缺失则从 HEAD 恢复(默认 .gitignore)
  --branch <name>        worktree 分支名(默认 integrate/<输入名>-<时间戳>)
  --worktree-path <path> worktree 目录(默认 仓库同级 <repo>-integrate-<时间戳>)
  --no-delete            覆盖时不删旧文件(部分更新/打补丁时用; 整包重构别加)
  --dry-run              只校验+打印计划, 不建 worktree
  -h, --help             帮助
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --input)         INPUT="$2"; shift 2;;
    --repo)          REPO="$2"; shift 2;;
    --protect)       PROTECT="$2"; shift 2;;
    --keep)          KEEP="$2"; shift 2;;
    --branch)        BRANCH="$2"; shift 2;;
    --worktree-path) WORKTREE="$2"; shift 2;;
    --no-delete)     NO_DELETE=1; shift;;
    --merge)         MODE="merge"; shift;;
    --discard)       MODE="discard"; shift;;
    --dry-run)       DRY_RUN=1; shift;;
    -h|--help)       usage; exit 0;;
    *) echo "未知参数: $1" >&2; usage; exit 1;;
  esac
done

REPO="${REPO:-$DEFAULT_REPO}"
PROTECT="${PROTECT:-$DEFAULT_PROTECT}"
KEEP="${KEEP:-$DEFAULT_KEEP}"

# 受保护路径 -> rsync --exclude 列表(永远也排除 .git)
build_excludes() {
  echo "--exclude=.git"
  local IFS=','
  for p in $PROTECT; do [[ -n "$p" ]] && echo "--exclude=$p"; done
}

check_repo() {
  if ! git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERR: $REPO 不是 git 仓库" >&2; exit 1
  fi
}

run_rsync() {  # $1=src(带尾斜线) $2=dst
  local delete_flag=("--delete")
  [[ $NO_DELETE -eq 1 ]] && delete_flag=()
  rsync -a "${delete_flag[@]}" "${EXCLUDES[@]}" "$1" "$2"
}

# 用 python3 解压 zip(不依赖系统 unzip)
extract_zip_py() {  # $1=zip $2=dest
  python3 - "$1" "$2" <<'PY'
import zipfile, sys
with zipfile.ZipFile(sys.argv[1]) as z:
    z.extractall(sys.argv[2])
PY
}

# 若目录下只有一个子目录(单层包裹),echo 其名;否则 echo 空
single_top_dir() {
  local d="$1" names cnt name
  names="$(find "$d" -mindepth 1 -maxdepth 1 -printf '%f\n' 2>/dev/null)"
  cnt="$(printf '%s\n' "$names" | grep -c . || true)"
  [[ "$cnt" -eq 1 ]] || { echo ""; return; }
  name="$(printf '%s\n' "$names" | head -1)"
  [[ -d "$d/$name" ]] && echo "$name" || echo ""
}

# 完整性检查: 恢复 --keep 里缺失的文件(从 worktree 自己的 HEAD=合并前 main), 并报告版本盖章
integrity_check() {
  echo "### 2.5) 完整性: 保留项 + 版本标记"
  local keep_arr kp
  IFS=',' read -ra keep_arr <<< "$KEEP"
  for kp in "${keep_arr[@]}"; do
    [ -z "$kp" ] && continue
    if [ -e "$WORKTREE/$kp" ]; then
      echo "    保留 [$kp]: 已存在(zip 带了)"
    elif git -C "$WORKTREE" cat-file -e "HEAD:$kp" 2>/dev/null; then
      mkdir -p "$WORKTREE/$(dirname "$kp")"
      git -C "$WORKTREE" show "HEAD:$kp" > "$WORKTREE/$kp"
      echo "    保留 [$kp]: zip 里没有, 已从 HEAD 自动恢复 ✓"
    else
      echo "    保留 [$kp]: 缺失且 HEAD 也没有 ⚠️(需人工)"
    fi
  done
  if grep -q harness_sha "$WORKTREE/00_orchestrator/ledger.py" 2>/dev/null; then
    echo "    版本盖章 [harness_sha in ledger.py]: 存在 ✓"
  else
    echo "    版本盖章 [harness_sha in ledger.py]: 缺失 ⚠️ —— 需 agent 在新代码上重新盖(见 SKILL.md)"
  fi
}

do_discard() {
  [[ -n "$WORKTREE" ]] || { echo "ERR: --discard 需要 --worktree-path" >&2; exit 1; }
  check_repo
  local branch=""
  branch="$(git -C "$WORKTREE" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
  echo "### 丢弃: 删除 worktree $WORKTREE"
  git -C "$REPO" worktree remove --force "$WORKTREE"
  [[ -n "$branch" ]] && { git -C "$REPO" branch -D "$branch" || true; echo "### 已删分支 $branch"; }
  echo "DISCARD_DONE"
}

do_merge() {
  [[ -n "$WORKTREE" ]] || { echo "ERR: --merge 需要 --worktree-path" >&2; exit 1; }
  check_repo
  local branch; branch="$(git -C "$WORKTREE" rev-parse --abbrev-ref HEAD)"
  echo "### 1) 提交 worktree 改动 (分支 $branch)"
  git -C "$WORKTREE" add -A
  if git -C "$WORKTREE" diff --cached --quiet; then
    echo "    (没有改动可提交)"
  else
    git -C "$WORKTREE" commit -q -m "integrate update (branch $branch)"
  fi
  echo "### 2) 合并进 $REPO 的当前分支"
  git -C "$REPO" merge --no-ff "$branch" -m "merge: integrate update from $branch"
  echo "### 3) 清理 worktree + 分支"
  git -C "$REPO" worktree remove "$WORKTREE"
  git -C "$REPO" branch -d "$branch"
  echo "MERGE_DONE  (当前分支现已包含更新)"
}

do_diff() {
  [[ -n "$INPUT" ]] || { echo "ERR: 默认模式需要 --input" >&2; usage; exit 1; }
  [[ -e "$INPUT" ]] || { echo "ERR: --input 不存在: $INPUT" >&2; exit 1; }
  check_repo

  local input_abs input_type base ts repo_parent repo_name
  input_abs="$(cd "$(dirname "$INPUT")" && pwd)/$(basename "$INPUT")"
  if   [[ "$INPUT" == *.zip ]];   then input_type="zip"
  elif [[ -d "$INPUT" ]];         then input_type="dir"
  elif [[ -f "$INPUT" ]];         then input_type="file"
  else echo "ERR: 无法识别 --input 类型: $INPUT" >&2; exit 1; fi

  base="$(basename "$INPUT")"; base="${base%.zip}"; base="${base// /_}"; base="${base//\//_}"
  ts="$(date +%Y%m%d-%H%M%S)"
  BRANCH="${BRANCH:-integrate/${base}-${ts}}"
  repo_parent="$(dirname "$(cd "$REPO" && pwd -P)")"
  repo_name="$(basename "$(cd "$REPO" && pwd -P)")"
  WORKTREE="${WORKTREE:-$repo_parent/$repo_name-integrate-$ts}"

  mapfile -t EXCLUDES < <(build_excludes)

  echo "### 计划"
  echo "  仓库      : $REPO"
  echo "  输入      : $INPUT ($input_type)"
  echo "  分支      : $BRANCH"
  echo "  worktree  : $WORKTREE"
  echo "  受保护    : $PROTECT  (永不覆盖/删除)"
  echo "  保留项    : $KEEP  (缺失则从 HEAD 恢复)"
  echo "  删除旧文件: $([[ $NO_DELETE -eq 1 ]] && echo 否 || echo 是)"
  echo "WORKTREE_PATH=$WORKTREE"
  echo "WORKTREE_BRANCH=$BRANCH"

  if [[ $DRY_RUN -eq 1 ]]; then
    echo "### [dry-run] 不创建 worktree, 结束。"
    echo "DRY_RUN_DONE"; return
  fi

  local wt_parent; wt_parent="$(cd "$(dirname "$WORKTREE")" 2>/dev/null && pwd || echo "")"
  if [[ -n "$wt_parent" && "$wt_parent" != "$repo_parent" ]]; then
    echo "⚠️ 警告: worktree 不在仓库同级($repo_parent)。若受保护路径是相对符号链接, 可能失效。" >&2
  fi
  [[ -e "$WORKTREE" ]] && { echo "ERR: worktree 已存在: $WORKTREE (先 --discard 或换 --worktree-path)" >&2; exit 1; }

  echo; echo "### 1) 创建 worktree"
  git -C "$REPO" worktree add "$WORKTREE" -b "$BRANCH"

  echo "### 2) 覆盖更新到 worktree"
  local tmp="" src child
  if [[ "$input_type" == "zip" ]]; then
    tmp="$(mktemp -d)"
    extract_zip_py "$input_abs" "$tmp"
    src="$tmp"
    child="$(single_top_dir "$tmp")"
    if [[ -n "$child" ]]; then
      src="$tmp/$child"
      echo "    (检测到单层包裹文件夹 '$child', 已自动剥掉)"
    fi
    run_rsync "$src/" "$WORKTREE/"
  elif [[ "$input_type" == "dir" ]]; then
    run_rsync "$input_abs/" "$WORKTREE/"
  else
    echo "    (单文件模式: 复制到 worktree 根; 要放到子目录请改用文件夹输入)"
    cp "$input_abs" "$WORKTREE/"
  fi
  [[ -n "$tmp" && -d "$tmp" ]] && rm -rf "$tmp"

  integrity_check

  echo; echo "### 3) Diff (新增/修改/删除)"
  git -C "$WORKTREE" status -s || true
  echo "--- 改动规模 ---"
  git -C "$WORKTREE" diff --stat -- ':!*.pyc' 2>/dev/null || true

  echo; echo "### ✅ 已就绪: worktree=$WORKTREE (分支 $BRANCH)"
  echo "### 在里面测试(如 python 00_orchestrator/run.py --preflight), 然后:"
  echo "    合并 → bash \"$SELF\" --merge   --worktree-path \"$WORKTREE\""
  echo "    丢弃 → bash \"$SELF\" --discard --worktree-path \"$WORKTREE\""
  echo "DIFF_DONE"
}

case "$MODE" in
  discard) do_discard;;
  merge)   do_merge;;
  diff)    do_diff;;
esac
