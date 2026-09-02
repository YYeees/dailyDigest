#!/usr/bin/env bash
# 生成公开站产物(export_public.py)并推到 github.com/YYeees/AIDailyNews。
#
# 为什么单独一个脚本而不是在两个workflow里各写一遍:digest.yml和trending.yml都会改
# docs/data/,两边都得跟着更新公开站。同一段逻辑抄两份,迟早改了一边忘了另一边。
#
# 认证:CI里走AIDAILYNEWS_DEPLOY_KEY(只对AIDailyNews有写权限的deploy key,拿不到私有仓
# 这边的任何东西)。本地手动跑时这个变量为空,直接用HTTPS走系统已有的git凭证。
#
# 推送方式是**全量替换**:先清空目标仓(.git除外)再拷贝public/。公开站是产物镜像,私有站
# 这边删掉/过滤掉的内容,那边必须跟着消失——增量add只会让撤下来的内容永远留在公开仓里。
set -euo pipefail

cd "$(dirname "$0")/.."

python3 export_public.py

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

if [ -n "${AIDAILYNEWS_DEPLOY_KEY:-}" ]; then
  KEY="$WORKDIR/deploy_key"
  # 写进mktemp目录而不是~/.ssh:跑完随trap一起删掉,不在runner上留私钥
  printf '%s\n' "$AIDAILYNEWS_DEPLOY_KEY" > "$KEY"
  chmod 600 "$KEY"
  export GIT_SSH_COMMAND="ssh -i $KEY -o StrictHostKeyChecking=accept-new -o IdentitiesOnly=yes"
  REMOTE="git@github.com:YYeees/AIDailyNews.git"
else
  REMOTE="https://github.com/YYeees/AIDailyNews.git"
fi

CLONE="$WORKDIR/repo"
git clone --depth 1 "$REMOTE" "$CLONE"

find "$CLONE" -mindepth 1 -maxdepth 1 -not -name .git -exec rm -rf {} +
cp -R public/. "$CLONE"/

cd "$CLONE"
git add -A
if git diff --cached --quiet; then
  echo "[跳过] 公开站内容没有变化，不推送"
  exit 0
fi

git -c user.name="github-actions[bot]" \
    -c user.email="github-actions[bot]@users.noreply.github.com" \
    commit -m "Publish site $(date -u +%Y-%m-%dT%H:%MZ)"
git push
echo "[OK] 已推送到 AIDailyNews"
