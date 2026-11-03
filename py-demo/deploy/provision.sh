#!/usr/bin/env bash
# 在阿里云 ECS 上初始化 / 幂等重跑：目录、venv、依赖、.env.production、systemd、nginx 站点。
#
#   py-demo/deploy/deploy.sh                                    # 先把代码同步上去
#   ssh zknow-aliyun bash /apps/live-sdk-mp-demo/py-demo/deploy/provision.sh   # 首次
#   ssh zknow-aliyun bash /apps/live-sdk-mp-demo/py-demo/deploy/provision.sh   # 证书签好后重跑（换成 443 配置）
#
# 不做的事：签发证书（证书要在 DNS A 记录生效后单独跑 certbot）、改 DNS。
set -euo pipefail

APP_DIR="${APP_DIR:-/apps/live-sdk-mp-demo/py-demo}"
SERVICE="${SERVICE:-live-demo-py}"
DOMAIN="${DOMAIN:-xiaoe-demo.david-tech.cn}"
PORT="${PORT:-8090}"
NGINX_SITE="/etc/nginx/sites-available/${DOMAIN}"
NGINX_LINK="/etc/nginx/sites-enabled/${DOMAIN}"
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # py-demo/deploy

log() { printf '\n== %s ==\n' "$*"; }
die() { printf 'FATAL: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "需要 root 运行"

# ---------------------------------------------------------------- 1. 目录
log "1/6 目录 $APP_DIR"
mkdir -p "$APP_DIR"
chmod 750 "$APP_DIR"

# ---------------------------------------------------------------- 2. venv 与依赖
log "2/6 Python 虚拟环境与依赖"
python3 -V
if [ ! -x "$APP_DIR/.venv/bin/python" ]; then
  python3 -m venv "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/python" -m pip install -q --disable-pip-version-check --upgrade pip
"$APP_DIR/.venv/bin/python" -m pip install -q --disable-pip-version-check -r "$APP_DIR/requirements.txt"
"$APP_DIR/.venv/bin/python" - <<'PY'
import fastapi, uvicorn, pydantic
print("fastapi", fastapi.__version__, "| uvicorn", uvicorn.__version__, "| pydantic", pydantic.VERSION)
PY

# ---------------------------------------------------------------- 3. .env.production
ENV_FILE="$APP_DIR/.env.production"
log "3/6 环境文件 $ENV_FILE"
# 不从同机其它服务借凭证：那些 .env.production 里的值要么是占位符（CHANGE_ME_PLEASE），
# 要么属于别的店铺。店铺级密钥只能由店铺持有人填真值。
if [ -s "$ENV_FILE" ]; then
  echo "已存在，保留不动（要重建请先备份删除）"
else
  echo "按模板生成：店铺 ID / 小程序 appid 已填，5 个密钥留空待填"
  sed "s/^PORT=.*/PORT=${PORT}/" "$DEPLOY_DIR/env.production.example" > "$ENV_FILE"
  sed -i 's/^HOST=.*/HOST=127.0.0.1/' "$ENV_FILE"
fi
chmod 600 "$ENV_FILE"
echo "键名清单："
sed -E 's/^([A-Z0-9_]+)=.*/\1=<hidden>/' "$ENV_FILE" | grep -E '^[A-Z0-9_]+='
echo "空值项（对应 /health 的 credentials 会显示 false，登录直接报缺少凭证）："
grep -E '^[A-Z0-9_]+=$' "$ENV_FILE" | cut -d= -f1 | tr '\n' ' '; echo

# ---------------------------------------------------------------- 4. systemd
log "4/6 systemd 单元 $SERVICE"
sed "s#/apps/live-sdk-mp-demo/py-demo#${APP_DIR}#g" "$DEPLOY_DIR/live-demo-py.service" \
  > "/etc/systemd/system/${SERVICE}.service"
systemctl daemon-reload
systemctl enable "$SERVICE" >/dev/null 2>&1 || true
systemctl restart "$SERVICE"

for i in $(seq 1 20); do
  if curl -fsS -m 2 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then break; fi
  sleep 0.5
done
systemctl is-active --quiet "$SERVICE" || { journalctl -u "$SERVICE" -n 30 --no-pager; die "服务未起来"; }
echo "服务状态：$(systemctl is-active "$SERVICE") / 开机自启：$(systemctl is-enabled "$SERVICE")"

# ---------------------------------------------------------------- 5. nginx
log "5/6 nginx 站点 $DOMAIN"
if [ -s "${CERT_DIR}/fullchain.pem" ]; then
  echo "证书已存在，安装带 443 的完整配置"
  SRC_CONF="$DEPLOY_DIR/nginx.conf"
else
  echo "证书未签发，只装 80（ACME 校验），签好后重跑本脚本切换"
  SRC_CONF="$DEPLOY_DIR/nginx.http-only.conf"
fi
sed "s#xiaoe-demo.david-tech.cn#${DOMAIN}#g" "$SRC_CONF" > "$NGINX_SITE"
ln -sfn "$NGINX_SITE" "$NGINX_LINK"
if nginx -t 2>/dev/null; then
  systemctl reload nginx
  echo "nginx 已 reload"
else
  nginx -t || true
  die "nginx 配置校验失败"
fi

# ---------------------------------------------------------------- 6. 自检
log "6/6 自检"
echo "-- 监听端口（应只有 127.0.0.1:${PORT}）"
ss -lntp | grep ":${PORT}" || echo "（未监听，请看 journalctl -u ${SERVICE}）"
echo "-- /health（直连）"
curl -s -m 5 "http://127.0.0.1:${PORT}/health"; echo
echo "-- 出网连通性（小鹅云 / 微信）"
curl -s -o /dev/null -m 8 -w "api.xiaoe-tech.com => %{http_code}\n" https://api.xiaoe-tech.com/ || echo "api.xiaoe-tech.com 不可达"
curl -s -o /dev/null -m 8 -w "api.weixin.qq.com  => %{http_code}\n" https://api.weixin.qq.com/ || echo "api.weixin.qq.com 不可达"
echo
echo "完成。证书状态：$([ -s "${CERT_DIR}/fullchain.pem" ] && echo 已就绪 || echo 未签发)"
