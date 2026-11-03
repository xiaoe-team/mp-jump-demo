# py-demo 部署到阿里云 ECS（systemd + nginx + certbot）

目标机：`zknow-aliyun` = `120.27.194.130`（Alibaba Cloud Linux 4 / Python 3.11.6 / nginx 1.30.4 / certbot 5.7.0）
公网域名：`xiaoe-demo.david-tech.cn`（TLS 由 nginx 终结，uvicorn 只听 `127.0.0.1:8090`）

```
小程序 / H5
   │  https://xiaoe-demo.david-tech.cn
   ▼
nginx :443 ──(sites-enabled/xiaoe-demo.david-tech.cn)──▶ 127.0.0.1:8090 uvicorn（单进程）
                                                          │
                                                          ├─▶ https://api.weixin.qq.com   jscode2session / 手机号
                                                          └─▶ https://api.xiaoe-tech.com  token / register / sdk login / user info
```

部署位置与同机其它服务保持一致：

| 项 | 值 |
| --- | --- |
| 代码 + venv | `/apps/live-sdk-mp-demo/py-demo` |
| 环境文件 | `/apps/live-sdk-mp-demo/py-demo/.env.production`（`600`，不入库） |
| systemd 单元 | `/etc/systemd/system/live-demo-py.service`（开机自启） |
| 运行日志 | `/apps/live-sdk-mp-demo/py-demo/service.log`（`journalctl -u live-demo-py` 也有） |
| nginx 站点 | `/etc/nginx/sites-available/xiaoe-demo.david-tech.cn` → `sites-enabled` |
| 反代片段 | 复用 `/etc/nginx/snippets/xiaoe-sdk-proxy.conf`（顺带注入 `X-Trace-ID`，正好对上后端的 trace 中间件） |
| 证书 | `/etc/letsencrypt/live/xiaoe-demo.david-tech.cn/`（certbot 自动续期） |

---

## 一、首次部署

```bash
cd live-sdk-mp-demo
py-demo/deploy/deploy.sh                                   # ① 同步代码（首次也会建目录）
ssh zknow-aliyun bash /apps/live-sdk-mp-demo/py-demo/deploy/provision.sh   # ② 建 venv / 依赖 / env / systemd / nginx
```

`provision.sh` 是幂等的，可以反复跑。它做六件事：目录 → venv+依赖 → `.env.production` → systemd → nginx 站点 → 自检。
证书不存在时它会装 `nginx.http-only.conf`（只开 80 的 ACME 校验，业务路径返回 503），证书就绪后再跑一次就切成带 443 的 `nginx.conf`。

### ① 填 5 个密钥（必须，否则登录直接失败）

在服务器上编辑（**不要**贴进聊天/文档）：

```bash
ssh zknow-aliyun
vi /apps/live-sdk-mp-demo/py-demo/.env.production
systemctl restart live-demo-py
```

| 键 | 来源 |
| --- | --- |
| `CLIENT_ID` / `CLIENT_SECRET` | 小鹅云开放平台 → 应用凭证 |
| `SDK_APP_ID` / `SDK_SECRET` | 小鹅云 SDK 应用标识 / 密钥 |
| `WX_APP_SECRET` | 微信小程序后台 → 开发管理 → 开发设置 → AppSecret |

`XIAOE_APP_ID`（`appq6jjgwoo7664`）与 `WX_APP_ID`（`wx4d356f6b38a0fa42`）是公开标识，模板里已经填好。

> 在本地把 `.env.production` 改好后要**单独**传上去 —— `deploy.sh` 的 rsync 明确排除了 `.env.*`（密钥不该随代码走），
> 只改本地文件、不 scp，服务读到的还是服务器上那份旧文件：
>
> ```bash
> scp py-demo/.env.production zknow-aliyun:/apps/live-sdk-mp-demo/py-demo/.env.production
> ssh zknow-aliyun 'chmod 600 /apps/live-sdk-mp-demo/py-demo/.env.production && systemctl restart live-demo-py'
> ```
>
> 生产文件的 `HOST` 必须是 `127.0.0.1`（公网由 nginx 终结 TLS）；写成 `0.0.0.0` 会让 uvicorn 直接对外监听 8090。

填完看 `/health` 的 `credentials`，每一项都应为 `true`：

```bash
curl -s http://127.0.0.1:8090/health | python3 -m json.tool
```

小鹅云开放平台地址用 `XIAOE_API_BASE_URL`（默认 `https://api.xiaoe-tech.com`，旧键 `API_BASE_URL` 兼容）；
上游接口路径可用 `API_PATH_*` / `WX_PATH_*` 覆盖（版本升级、指向沙箱时用）。
`/health` 的 `upstreams` 会回显当前实际使用的路径，`overridden` 列出被环境变量改过的项 ——
改完 path 只要看这两个字段就能确认有没有生效。

### ② DNS：给域名加 A 记录（必须，证书签不出来就是卡在这里）

在阿里云 DNS 控制台（`dns3/4/7/8.hichina.com` 那套）为 `david-tech.cn` 添加：

| 记录类型 | 主机记录 | 记录值 |
| --- | --- | --- |
| A | `xiaoe-demo` | `120.27.194.130` |

校验（本机）：

```bash
dig +short xiaoe-demo.david-tech.cn A     # 应输出 120.27.194.130
```

> **为什么不用 `david-tech.top`**（2026-11-03 实测结论）：`.top` 域名虽然能解析到本机，
> 但 80 端口所有请求都被阿里云按「未备案域名」拦截 —— 返回 `Server: Beaver` + `Non-compliance ICP Filing` 403 页，
> 请求根本到不了 nginx，所以 Let's Encrypt 的 HTTP-01 校验必然失败；微信小程序后台的 request 合法域名也要求域名已备案。
> 已备案的 `david-tech.cn` 各子域名（`www` / `api` / `xiaoe-api` …）同机实测均正常（301/200）。
> 要用 `.top` 得先完成 ICP 备案，之后把 nginx 配置和 `provision.sh` 的 `DOMAIN` 换掉重跑即可。
>
> 也别和已有的 `xiaoe-api.david-tech.cn` 混了 —— 那个域名和证书已被另一个服务（127.0.0.1:8081）占用。

### ③ 签证书并切到 HTTPS

```bash
ssh zknow-aliyun 'certbot certonly --webroot -w /var/www/certbot -d xiaoe-demo.david-tech.cn \
  --non-interactive --agree-tos --email <你的邮箱>'
ssh zknow-aliyun bash /apps/live-sdk-mp-demo/py-demo/deploy/provision.sh   # 重跑：自动切成 443 配置
curl -s https://xiaoe-demo.david-tech.cn/health
```

续期：`/etc/cron.d/certbot` 已在跑，与本机其它站点一致，不用额外配。

### ④ 前端指向新域名

`mp-demo/.env.production` 里：

```
VITE_API_BASE=https://xiaoe-demo.david-tech.cn
```

然后 `npm run build:mp-weixin` 重新出包，并把 `xiaoe-demo.david-tech.cn` 加进
微信小程序后台「开发管理 → 服务器域名 → request 合法域名」（小程序只认 https + 已备案域名 + 白名单域名）。

---

## 二、日常发布

```bash
py-demo/deploy/deploy.sh
```

`rsync -az --delete` 同步代码，服务器上重装依赖、`systemctl restart live-demo-py`、跑一次 `/health`。
`.env.production`、`.venv`、`service.log` 都在排除列表里（`--delete` 下受保护，不会被删）。

> 重启会清空内存会话表，**已经在用的人需要重新登录**。要避免就上 Redis（本工程按设计没引入）。

## 三、回滚

```bash
# 代码回滚
cd live-sdk-mp-demo && git checkout <上一个提交> && py-demo/deploy/deploy.sh

# 只重启 / 只重载 nginx（不动代码）
ssh zknow-aliyun 'systemctl restart live-demo-py'
ssh zknow-aliyun 'nginx -t && systemctl reload nginx'
```

## 四、故障定位

| 现象 | 查什么 |
| --- | --- |
| `systemctl status live-demo-py` 不是 active | `journalctl -u live-demo-py -n 50`，或 `tail -50 /apps/live-sdk-mp-demo/py-demo/service.log` |
| 起不来且日志提示 `.env.production` 相关 | systemd 的 `EnvironmentFile=` 缺文件会直接失败；确认文件存在且 `600` |
| `https://…/health` 502 | 后端没监听：`ss -lntp \| grep 8090`，再看服务状态 |
| `https://…/health` 404 | 请求打到了别的站点：`nginx -T \| grep -n server_name`，确认 `sites-enabled` 里有本域名软链 |
| 登录返回「缺少…凭证」 | `.env.production` 对应键为空；`/health` 的 `credentials` 对应项为 `false` |
| 登录返回 `40029 invalid code` | `code` 只能用一次，重新登录；或 `VITE_WX_APP_ID` 与后端 `WX_APP_ID` 不一致 |
| 登录返回 `40125 invalid appsecret` | `WX_APP_SECRET` 填错或已在小程序后台重置 |
| 登录成功但每次都要重登 | 服务被重启过（内存会话表清空）；单进程才能保持会话，`ps -ef \| grep run.py` 应只有 1 个进程 |
| 600 秒后合并手机号失败 | `bind_token` 存在进程内存里，10 分钟一次性；期间重启过服务就重新授权 |
| 外部访问超时 | 阿里云安全组需放行 80/443（现有站点在跑，一般已放行） |

## 五、已知限制 / 需要注意

1. **必须单进程、单实例**：`ko_token → user_id` 的会话表和手机号合并意图（`bind_token`）都只在进程内存里。
   `--workers N`、多副本、蓝绿双实例都会让登录态只落在一个进程上。要扩就得先换 Redis。
2. **重启即掉登录态**：这是设计里明说的代价，`Restart=on-failure` 触发重启同样会掉。
3. **`/health` 回显 `configFile` 绝对路径**（`/apps/live-sdk-mp-demo/py-demo/.env.production`），公网可读。演示可接受；介意就把 `health_router.py` 里那个字段去掉。
4. **`/api/docs` 公网可访问**（FastAPI 自带 Swagger）。要关就在 `main.py` 里把 `docs_url`/`openapi_url` 设成 `None`，或 nginx 里 `location = /api/docs { return 404; }`。
5. **`credential_status()` 只判非空**：填了占位符（如 `CHANGE_ME_PLEASE`）也会显示 `configured`。所以别往 `.env.production` 里留占位符。
6. **CORS 是 `*`**：小程序走原生请求不受影响，H5 域名上线后建议收敛到白名单。
7. **上游是同步 `urllib`**：FastAPI 把同步路由丢线程池跑，单进程默认 40 线程，演示量级没问题；上游超时 10s（`REQUEST_TIMEOUT_MS`）。

## 六、文件清单

| 文件 | 作用 |
| --- | --- |
| `deploy/deploy.sh` | 本地：rsync + 装依赖 + 重启 + 自检 |
| `deploy/provision.sh` | 服务器：目录 / venv / env / systemd / nginx（幂等） |
| `deploy/live-demo-py.service` | systemd 单元（单进程、`MemoryMax=1G`、日志落盘、收紧权限） |
| `deploy/nginx.conf` | 完整站点（80 ACME + 301 + 443 反代 `/health`、`/api/`，其余 404） |
| `deploy/nginx.http-only.conf` | 证书签发前的最小站点（只开 80） |
| `deploy/env.production.example` | `.env.production` 模板（密钥留空） |
