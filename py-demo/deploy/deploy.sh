#!/usr/bin/env bash
# 日常发布：本地 rsync 代码 → 服务器装依赖 → 重启服务 → 自检。
#   py-demo/deploy/deploy.sh                # 发布到 zknow-aliyun
#   HOST=other-host py-demo/deploy/deploy.sh
#
# 不会动服务器上的 .env.production / .venv / service.log（rsync 排除项在 --delete 下受保护）。
set -euo pipefail

HOST="${HOST:-zknow-aliyun}"
APP_DIR="${APP_DIR:-/apps/live-sdk-mp-demo/py-demo}"
SERVICE="${SERVICE:-live-demo-py}"
PORT="${PORT:-8090}"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # py-demo

echo "== 同步代码 $LOCAL_DIR → $HOST:$APP_DIR =="
ssh "$HOST" "mkdir -p '$APP_DIR'"
rsync -az --delete \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.env.*' \
  --exclude 'service.log' \
  "$LOCAL_DIR/" "$HOST:$APP_DIR/"

echo "== 安装依赖 =="
ssh "$HOST" "cd '$APP_DIR' && .venv/bin/python -m pip install -q --disable-pip-version-check -r requirements.txt"

echo "== 重启 $SERVICE =="
ssh "$HOST" "systemctl restart '$SERVICE'"

for i in $(seq 1 20); do
  if ssh "$HOST" "curl -fsS -m 2 http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then break; fi
  sleep 0.5
done

echo "== 自检 =="
ssh "$HOST" "systemctl is-active '$SERVICE' && curl -s -m 5 http://127.0.0.1:${PORT}/health"
echo
echo "完成。日志：ssh $HOST 'tail -f $APP_DIR/service.log'"
