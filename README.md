# jump-xiaoe-live-demo

跳转小鹅通「鹅直播」的**前后端演示工程**：

- `mp-demo/` uni-app 前端（Vue3 + vite，H5 + 微信小程序）
- `py-demo/` Python 后端（FastAPI），分层骨架沿用团队现有 SDK 服务的写法（config / providers / http / services）

首页两个按钮「进入直播」「进入录播」走**同一条页面路径**，只有直播间 `aliveId` 不同。
**跳转参数与 path 全部在前端**：`aliveId`、目标小程序写死在 `mp-demo/src/config/live.ts`，`envVersion` 在跳转调用处写死 `release`，
path 也由小程序自己拼；后端只管登录态（ko_token）与用户资料。

---

## 一、快速启动

### 0. 前置要求

| 依赖 | 版本 | 检查 |
| --- | --- | --- |
| Node.js | **22.22.0**（固定在 `engines`） | `node -v` |
| pnpm | **10.15.0**（固定在 `packageManager`） | `pnpm -v` |
| Python | ≥ 3.9 | `python3 -V` |
| 微信开发者工具 | 最新稳定版（只在跑小程序时需要） | — |

前端工具链已锁版本：`package.json` 里 `packageManager: pnpm@10.15.0`、`engines.node: >=22.22.0 <23`，
`mp-demo/.npmrc` 打开 `engine-strict=true`，版本不对会直接报错。用 corepack 拿指定版本：

```bash
corepack enable
corepack prepare pnpm@10.15.0 --activate
node -v      # v22.22.0
pnpm -v      # 10.15.0
```

```bash
cd jump-xiaoe-live-demo

npm run front:install        # 前端依赖（= pnpm --dir mp-demo install）
npm run server:setup         # 后端依赖（建 venv + 装 fastapi / uvicorn）
```

### 1. 先建环境文件（必做，仓库里没有 env）

`.gitignore` 里 `.env.*` 全忽略，**仓库不含任何 env 文件**，克隆后要自己创建。下面的命令直接可复制：

```bash
cd jump-xiaoe-live-demo

# ① 后端生产配置：本地调试与部署都用它（密钥填这里，文件不会入库）
cat > py-demo/.env.production <<'EOF'
XIAOE_APP_ID=appq6jjgwoo7664
CLIENT_ID=填写开放平台 client_id
CLIENT_SECRET=填写开放平台 client_secret
SDK_APP_ID=填写 SDK 应用标识
SDK_SECRET=填写 SDK 应用密钥
WECHAT_API_BASE_URL=https://api.weixin.qq.com
WX_APP_ID=wx4d356f6b38a0fa42
WX_APP_SECRET=填写小程序 AppSecret
PORT=8090
HOST=0.0.0.0
REQUEST_TIMEOUT_MS=10000
EOF

# ② 后端 development / test：只留键名，不放假密钥（跑测试、看接口形状用）
for env in development test; do
  port=8090; [ "$env" = "test" ] && port=8091
  cat > "py-demo/.env.$env" <<EOF
XIAOE_APP_ID=
CLIENT_ID=
CLIENT_SECRET=
SDK_APP_ID=
SDK_SECRET=
WECHAT_API_BASE_URL=https://api.weixin.qq.com
WX_APP_ID=
WX_APP_SECRET=
PORT=$port
HOST=0.0.0.0
REQUEST_TIMEOUT_MS=10000
EOF
done

# ③ 前端：三份都指向同一个后端地址（本地调试用 localhost）
for env in development test production; do
  cat > "mp-demo/.env.$env" <<EOF
VITE_ENV=$env
VITE_XIAOE_APP_ID=appq6jjgwoo7664
VITE_WX_APP_ID=wx4d356f6b38a0fa42
VITE_API_BASE=http://127.0.0.1:8090
VITE_H5_BASE=https://xiaoe.david-tech.cn
VITE_LIVE_MP_WX_APP_ID=wx13a74d0d3ab0942e
EOF
done
```

| 变量 | 说明 |
| --- | --- |
| `CLIENT_ID` / `CLIENT_SECRET` | 小鹅云开放平台凭证，换 `access_token` |
| `SDK_APP_ID` / `SDK_SECRET` | SDK 应用标识与密钥（`SDK_SECRET` 当前仅校验，未参与调用） |
| `WX_APP_SECRET` | 小程序 AppSecret，`code2session` 换 `union_id` |
| `VITE_API_BASE` | 小程序请求的后端地址；本地调试用 `http://127.0.0.1:8090` |

> 发布到正式域名时，把 `VITE_API_BASE` 改成后端部署域名，并去掉 localhost。
> 环境选择：后端用 `--env`（`production` / `test` / `development`），也可用进程变量 `APP_ENV`；两者都没给默认 development。
> `API_BASE_URL`（小鹅云开放平台地址，默认 `https://api.xiaoe-tech.com`）不进 env 文件，需要改时用进程变量覆盖。

### 2. 启动后端（必须先起）

密钥在 `.env.production`，所以本地也用 production 环境跑：

```bash
cd jump-xiaoe-live-demo
npm run server:prod-env      # = cd py-demo && .venv/bin/python run.py --env production
```

- 监听 **http://127.0.0.1:8090**（`HOST=0.0.0.0`，局域网/真机也可访问）
- 换端口：改 `py-demo/.env.production` 的 `PORT`
- 自检：

```bash
curl http://127.0.0.1:8090/health
# {"code":0,"msg":"ok","data":{"env":"production","apiBaseUrl":"https://api.xiaoe-tech.com",
#  "credentials":{"clientId":true,"clientSecret":true,"sdkAppId":true,"sdkSecret":true,
#  "wxAppSecret":true,...},"configFile":".env.production"}}
```

`credentials` 里哪项是 `false`，就是对应变量没填，登录时会直接报错（例如「缺少微信小程序凭证」）。

### 3. 启动前端

#### A. 微信小程序（主要演示方式）

```bash
npm run dev:mp-weixin        # 产物：mp-demo/dist/dev/mp-weixin
```

微信开发者工具 → 导入项目 → 选 `mp-demo/dist/dev/mp-weixin`：

1. AppID 填自己的（`mp-demo/src/manifest.json` 的 `mp-weixin.appid` 为空，导入时也可选「测试号」）
2. 详情 → 本地设置 → 勾选**「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」**
3. 真机调试时把 `mp-demo/.env.development` 的 `VITE_API_BASE` 改成电脑局域网地址（如 `http://192.168.31.212:8090`），手机与电脑同 Wi-Fi

进入小程序后的完整流程：

```
点「去登录」→ 登录页勾选协议 → 授权登录（wx.login → /api/login → 写 storage）
点「进入直播 / 进入录播」
  ├─ 未登录 → 跳登录页，登录成功后自动继续进入该直播间
  ├─ 未绑定手机号 → 弹「为了给您更好地直播体验，请授权手机号」
  │     └─ 手机号已属其他账号 → 二次确认「确认合并账号」→ 合并成功继续进入
  └─ 已登录已绑定 → 直接跳转鹅直播（pages/webView/webView?appId=…&aliveId=…&ko_token=…）
```

#### B. H5（浏览器，只看页面与接口连通性）

```bash
npm run dev:h5               # → http://127.0.0.1:5174
```

H5 没有 `wx.login` 与 `getPhoneNumber`，点登录/授权会如实失败（提示去微信里试），
但可以看到配置、path、日志，以及 `/api/*` 是否连通（vite 代理到 `VITE_API_BASE`）。

### 4. 跑测试

```bash
npm run server:test          # Python unittest 31 条：登录链路、手机号绑定/合并、接口约定、env 解析
```

前端纯函数（path 拼装、session 读写）用 node 跑断言脚本，见 README 末尾「验证到了什么」。

### 5. 启动前要填的直播间

`mp-demo/src/config/live.ts`：

```ts
export const ROOMS = [
  { key: 'live',   title: '进入直播', desc: '直播中的直播间', aliveId: 'l_xxx' }, // ← 直播的 aliveId
  { key: 'replay', title: '进入录播', desc: '录播 / 直播回放', aliveId: 'l_yyy' }, // ← 录播的 aliveId
]
```

`aliveId` 取法：后台打开该直播间 H5 链接 `.../v2/course/alive/<alive_id>?...`，`alive/` 后面那一段。
没填时按钮会提示「未配置 aliveId」，不会带空参数去跳。

### 6. 常见问题

| 现象 | 原因 / 处理 |
| --- | --- |
| 点按钮没反应 | 包里是旧构建。重新 `npm run build:mp-weixin` / `dev:mp-weixin` 并在开发者工具里重新编译 |
| 请求打到 `xiaoe-api.david-tech.cn/api/login` 返回 404 | 包用了线上地址。把 `mp-demo/.env.production` 的 `VITE_API_BASE` 改成 `http://127.0.0.1:8090` 后重新构建（该域名是 SDK 服务的域名，没有 `/api/login`） |
| `url not in domain list` | 开发者工具没勾「不校验合法域名…」 |
| 登录报 `40029 invalid code` | `code` 只能用一次，重新点登录；或 `VITE_WX_APP_ID` 与后端 `WX_APP_ID` 不一致 |
| 登录报「缺少…凭证」 | `py-demo/.env.production` 里对应变量没填，看 `/health` 的 `credentials` |
| 后端重启后前端提示登录态失效 | 会话存在后端内存里（未引入 Redis），重启即清空，重新登录即可 |
| 端口被占用 | 后端 `lsof -i :8090`；H5 dev 会自己换端口，注意别同时开多个实例（否则看到的是旧包） |
| 跳进去是「另一个人」 | 没带 `ko_token`（未登录或过期）；两个小程序 union_id 不同，必须带 token 才同身份 |

## 二、职责边界

| 谁 | 负责 | 不负责 |
| --- | --- | --- |
| 前端 `mp-demo` | 写死两个 aliveId / 目标小程序，跳转时写死 `envVersion: 'release'`；拼 `pages/webView/webView?appId=..&aliveId=..&ko_token=..`；决定要不要带 ko_token；调起跳转 | 不伪造任何数据；H5 没有 `wx.login` 就如实报错 |
| 后端 `py-demo` | **自己实现登录核心接口，直连小鹅云**：微信 `code2session` → `xe.user.register` → `xe.sdk.account.login` 换 `ko_token`；校验登录态、查用户资料 | **不下发任何跳转参数，也不拼 path**（`/api/config`、`/api/live-path` 都已下线，测试里专门断言） |

前后端都**没有 mock 分支**。登录链路（后端自己实现，不经过任何中间 SDK 服务）：

```
uni.login 的 code
  → 微信 /sns/jscode2session          取 union_id（身份键）
  → 小鹅云 GET /token                  client_credential 换 access_token（进程内缓存）
  → 小鹅云 POST /xe.user.register/1.0.0     注册（幂等，user_exists 表示已存在）
  → 小鹅云 POST /xe.sdk.account.login/1.0.0 SDK 登录 → ko_token（token_value）
```

`access_token` 过期（业务码 2008）会自动刷新并重试一次。

**登录态校验**：小鹅云的 `xe.user.info.get` 按 `user_id` / `wx_union_id` / `wx_open_id` / `phone` 之一查资料，
**并不校验 `ko_token`**（实测：假 Cookie + 真 user_id 仍返回数据）。所以本工程自己记一份登录态：
登录成功时把 `ko_token → user_id`（带过期时间）写进**进程内会话表**，`/api/session/check` 与 `/api/profile` 都查这张表。

> 代价（明确说明）：会话存内存，**后端重启后前端需要重新登录**；多实例部署不共享会话。
> 要跨实例共享就得引入 Redis —— 当前按要求不引入。

## 三、后端骨架

```
py-demo/
├── run.py                        启动入口（python3 run.py [--env test]）
├── requirements.txt
├── .env.development / .env.test / .env.production   各自写全 11 个变量（凭证 + 运行参数）
└── app/
    ├── main.py                   create_app()：初始化 providers、挂中间件、注册路由（对齐 routes.LoadRouter + bootstrap.Init）
    ├── config.py                 Settings + load_settings（对齐 config/env）
    ├── providers.py              配置与日志单例（对齐 providers/kernel_providers）
    ├── http/
    │   ├── middleware.py         trace_id / 访问日志 / 异常兜底（对齐 http/middleware）
    │   ├── response.py           {code,msg,data,trace_id} 信封（对齐 http/response）
    │   └── routers/              health · login · notfound（对齐 http/routes + controller）
    └── services/
        ├── login_service.py      业务：登录、手机号绑定/合并、用户资料
        ├── session_store.py      进程内会话表（ko_token → user_id）与 bind_token
        └── client_service/
            ├── xiaoe_client.py   小鹅云开放平台调用
            └── wechat_client.py  微信小程序接口调用
```

响应统一 `{code, msg, data, trace_id}`：`code=0` 成功、`code=-1` 失败，HTTP 恒为 200；
`trace_id` 由中间件注入，响应头同时带 `X-Trace-ID`。

## 四、环境配置（只有 `.env.<mode>`，没有基线 `.env`）

三个文件各自**写全所有变量**，互不依赖，也没有 `.env` 兜底：选哪个文件完全由 mode 决定。

前端 `mp-demo/`（`uni -m <mode>` 决定）：

| 文件 | 变量数 | `VITE_ENV` | `VITE_API_BASE` |
| --- | --- | --- | --- |
| `.env.development` | 6 | development | `http://127.0.0.1:8090` |
| `.env.test` | 6 | test | `https://xiaoe-api.david-tech.cn` |
| `.env.production` | 6 | production | `https://xiaoe-api.david-tech.cn` |

> 三份都**不入库**（`.gitignore` 里 `.env.*` 全忽略），按上表在本地自行创建。

| 变量 | 含义 | 对应前端同名变量 |
| --- | --- | --- |
| `VITE_XIAOE_APP_ID` | 小鹅通店铺 ID（path 的 appId、ko_token 归属店铺） | `VITE_XIAOE_APP_ID` |
| `VITE_WX_APP_ID` | 微信小程序 appid：**只取环境文件的值**，作为 `wx_app_id` 入参传给后端（不读运行时 appid） | `VITE_WX_APP_ID` |
| `VITE_API_BASE` | 后端接口地址（小程序端必填，H5 走同源代理） | `VITE_XIAOE_SDK_BASE_URL` |
| `VITE_H5_BASE` | 业务 H5 / 微页面自定义域名（唯一来源，没有兜底域名） | `VITE_BASE_URL` |
| `VITE_LIVE_MP_WX_APP_ID` | 跳转目标小程序 live-mp（正式 `wx13a74d0d3ab0942e` / 测试 `wxb58a41ffda339bf5`） | — |

`VITE_*` 会被内联进小程序包，**禁止写任何密钥**。

环境变量统一收口在 `mp-demo/src/utils/config.ts` 的 `globalData`：

```ts
import { globalData, currentWxAppId } from '@/utils/config'

globalData.ENV          // development / test / production
globalData.API_BASE     // 后端接口地址（H5 为空串，走同源）
globalData.H5_BASE      // 业务 H5 / 微页面域名
globalData.APP_ID       // 小鹅通店铺 ID
globalData.wx_app_id    // 微信小程序 appid
globalData.APP_ENV_TYPE // mini_program_wechat_sdk
globalData.LIVE_MP_WX_APP_ID // 跳转目标小程序（live-mp）
```

`App.vue` 里也把它挂到了小程序端 `getApp().globalData`；H5 端没有 `getApp`，请直接 `import { globalData }`。

后端 `py-demo/`（`--env` / `APP_ENV` 决定，默认 development）：

| 文件 | 变量数 | 差异 |
| --- | --- | --- |
| `.env.development` | 11 | PORT 8090 / 超时 15000 |
| `.env.test` | 11 | PORT 8091 |
| `.env.production` | 11 | PORT 8090 |

文件里的变量分三组：

| 分组 | 变量 |
| --- | --- |
| ① 小鹅云（自己实现登录所需） | `XIAOE_APP_ID`、`CLIENT_ID`、`CLIENT_SECRET`、`SDK_APP_ID`、`SDK_SECRET`（开放平台地址 `API_BASE_URL` 有代码默认值，不进 env） |
| ② 微信小程序 | `WECHAT_API_BASE_URL`、`WX_APP_ID`、`WX_APP_SECRET` |
| ③ 本工程运行参数 | `PORT`、`HOST`、`REQUEST_TIMEOUT_MS` |

### 补充：前端工具链（pnpm）

| 项 | 值 |
| --- | --- |
| Node | `22.22.0`（`engines.node: >=22.22.0 <23`） |
| pnpm | `10.15.0`（`packageManager: pnpm@10.15.0`） |
| 锁文件 | `mp-demo/pnpm-lock.yaml`（npm 的 `package-lock.json` 已删除） |
| 扁平依赖 | `mp-demo/.npmrc` 里 `node-linker=hoisted` —— TDesign 的 easycom 用 `@tdesign/uniapp/dist/<name>/<name>.vue` 真实路径解析，pnpm 默认的符号链接结构会失败 |

```bash
pnpm --dir mp-demo install                 # 装依赖
pnpm --dir mp-demo install --frozen-lockfile   # CI 用，锁定版本
pnpm --dir mp-demo run build:mp-weixin     # 构建小程序
pnpm --dir mp-demo run dev:h5              # H5 调试
```

`package.json` 顶层的 `front:install` / `dev:h5` / `build:mp-weixin` 等脚本内部已改成 `pnpm --dir mp-demo …`。

## 五、请求约定

所有业务参数都走**请求体**，前端不发任何自定义请求头（只有 `Content-Type: application/json`）：

| 参数 | 用在哪 | 说明 |
| --- | --- | --- |
| `wx_app_id` | `/api/login`、`/api/login-url` | 小程序 appid，取环境文件里的 `VITE_WX_APP_ID` |
| `code` | `/api/login`、`/api/login-url` | `uni.login` 拿到的 js_code |
| `redirect_uri` | `/api/login-url` | H5 登录后回跳地址 |
| `token` | `/api/session/check`、`/api/profile` | ko_token |
| `app_env_type` | 以上全部 | 内嵌环境标识（`mini_program_wechat_sdk`） |

- 后端**不读任何自定义请求头**（只把上游透传的 `X-Trace-ID` 当作 trace 提示，响应里回写）
- 后端 → 小鹅云的请求头只有 `Content-Type: application/json`，用户级调用再加 `Cookie: ko_token=...`，与前端无关
- **`mp_app_id` 全工程已不再出现**：本工程直接调小鹅云，身份键用 `union_id`，小程序身份用 `wx_app_id`，
  店铺身份用 `XIAOE_APP_ID`（`WX_APP_ID` / `WX_APP_SECRET` 只在 `wechat_client.py` 内部使用）

## 五点三、登录页

登录在独立页面 `mp-demo/src/pages/login/index.vue` 完成，首页只给「去登录」入口：

| 环节 | 行为 |
| --- | --- |
| 进入方式 | 首页「去登录 / 重新登录」→ `navigateTo('/pages/login/index?redirect_uri=...')`；未登录点「跳转」也会被导到登录页 |
| 页面内容 | 标题 + 协议勾选 + 「授权登录」按钮 + 「稍后再说」 |
| 未勾协议 | toast「请先阅读并同意协议」，不发请求 |
| 授权登录 | `uni.login` → `POST /api/login` → `saveSession({token,userId,expiresIn,appId})`（写入 5 个 storage 键） |
| 成功后 | 有 `redirect_uri` 就 `redirectTo`，否则返回上一页；页面栈只有自己时 `reLaunch` 首页 |
| 回到首页继续 | 未登录点「跳转」时会把房间带过去（`redirect_uri=/pages/index/index?autoJump=live`），登录成功回首页后 `onShow` 自动继续进入该直播间 |
| 失败 | 停留在登录页，展示错误（H5 会显示「uni.login not supported」）并可「重新登录」 |

## 五点四、登录态存储

`mp-demo/src/utils/session.ts` 在登录后写入这些 uni storage 键：

| 键 | 内容 | 何时写 |
| --- | --- | --- |
| `ko_token` | 店铺登录态 | 登录成功 |
| `user_id` | 小鹅通用户 ID | 登录成功 |
| `ko_token_expires_at` | 过期时间戳（ms） | 登录成功 |
| `APPID` | 店铺 app_id（`VITE_XIAOE_APP_ID`） | 登录成功；登出保留 |
| `LOGIN_DATA` | `{ user_id, app_id, token }` | 登录成功；登出清除 |
| `wx_user_profile` | `{ nickname, avatar }` | 调「查用户资料」成功后 |
| `anony_token` | 匿名 token（本工程后端暂不返回，预留） | — |

登出只清会话相关（`ko_token` / `user_id` / `ko_token_expires_at` / `LOGIN_DATA`），`APPID` 属于环境配置保留。
读取统一走 `getSession()` / `getLoginData()` / `getWxUserProfile()`，不要直接 `uni.getStorageSync`。

## 五点五、手机号绑定弹窗（前端）

`mp-demo/src/components/bind-phone-popup/index.vue`（TDesign `t-popup` + 原生 `open-type="getPhoneNumber"` 按钮）：

| 触发方式 | 条件 | 行为 |
| --- | --- | --- |
| **点「跳转」时检查**（主路径） | 点「进入直播/录播」→ 未登录则拦截；已登录则 `POST /api/check-bind-phone`，`isBindPhone=false` 才弹窗 | 拦截本次跳转，弹出绑定弹窗；绑定成功后自动继续进入该直播间 |
| 手动弹 | 账号区「绑定手机号」（未绑定）/「更换·合并手机号」（已绑定） | 直接打开弹窗 |

> 登录后**不会**自动弹窗（按产品要求）：只在用户点「跳转」进入直播时检查手机号是否已绑定。

弹窗内两阶段：

1. 点「授权手机号」（文案：为了给您更好地直播体验，请授权手机号）→ `POST /api/bind-or-merge-phone { token, code }`
2. 若返回 `needMergeConfirm` → 弹窗切到「确认合并账号」，展示脱敏手机号与**权益合并**说明
   → 点「确认合并」→ `{ token, bind_token, confirm_merge: true }` → 提示「账号已合并」
3. 无冲突则直接绑定成功，提示「手机号绑定成功」，账号区手机号变为脱敏号码

H5 里没有 `getPhoneNumber`，点授权会失败并提示，属预期；真机/开发者工具里才能走通。

## 五点六、用到的上游接口（清单在代码里）

Python 端把用到的上游接口收成了常量 + 清单，改调用就必须同步这里：

| 文件 | 常量 / 清单 |
| --- | --- |
| `py-demo/app/services/client_service/xiaoe_client.py` | `PATH_*` + `ENDPOINTS`（小鹅云开放平台） |
| `py-demo/app/services/client_service/wechat_client.py` | `PATH_*` + `ENDPOINTS`（微信小程序） |

小鹅云开放平台（6 个）：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/token` | `client_credential` 换 `access_token`（进程内缓存） |
| POST | `/xe.user.register/1.0.0` | 注册用户（幂等，`user_exists` 表示已存在） |
| POST | `/xe.sdk.account.login/1.0.0` | SDK 登录 → `ko_token`（`token_value`） |
| POST | `/xe.user.info.get/1.0.0` | 查用户资料；身份键四选一：`user_id` / `wx_union_id` / `wx_open_id` / `phone` |
| POST | `/xe.account-platform.uaccount.bind_or_merge_phone/1.0.0` | 手机号绑定 / 合并 |
| POST | `/xe.login.url/1.0.0` | H5 一次性登录地址 |

微信小程序（3 个）：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/sns/jscode2session` | `uni.login` 的 code → `open_id` / `union_id` |
| POST | `/cgi-bin/stable_token` | 小程序全局 `access_token`（换手机号要用） |
| POST | `/wxa/business/getuserphonenumber` | `getPhoneNumber` 的 code → 手机号（校验水印 appid） |

## 六、接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 健康检查（回显 env / 配置来源 / 凭证是否配齐，仅布尔） |
| POST | `/api/login` | `{ wx_app_id, code }` → `{ koToken, userId, expiresIn }`，上游报错原样透出 |
| POST | `/api/session/check` | `{ token }` → `{ valid, userId, msg }` |
| POST | `/api/profile` | `{ token }` → `{ userId, isBindPhone, maskedPhone }` |
| POST | `/api/login-url` | `{ wx_app_id, code, redirect_uri }` → `{ loginUrl }`（内嵌 H5 登录态中转，代理 `user.login_url/2.0.0`） |

`/api/docs` 是 FastAPI 自带接口文档。**后端只提供 API，不托管任何静态产物**：未知路径（含 `/`、`/index.html`）统一返回 JSON 信封 `没有这个路径：...`。

## 七、跳转鹅直播的参数

入口只有一个页面：`pages/webView/webView?appId=<店铺 app_id>&aliveId=<直播间 id>&ko_token=<店铺登录态>`，
**直播 / 录播 / 回放是同一个参数 `aliveId`**，页面内部自己分流。

三个参数都必传：`ko_token` 不带会走新用户注册（身份与品牌侧不一致），未登录 / 跨店铺 / token 过期一律不发跳转。

完整参数表、其他入口形态（`params` / `scene` / `content_app_id`）与踩坑提醒见 `docs/链接拼写规则.md` 第 5 节。

| 参数 | 说明 | 我们是否使用 |
| --- | --- | --- |
| `ko_token` | **必传**：店铺登录态，按 appId 存进 live-mp `#koTokenMap`，不带会走新用户注册 | ✅ 必带 |
| `shareUserId` / `share_user_id` | 分享人 user_id（归因/分销） | ⛔ |
| `shareMoments` | 朋友圈分享场景（`1`/`0`） | ⛔ |
| `broadcastPassword` | 加密直播密码 | ⛔ |
| `retry` | 登录异常中转的重试标记 | ⛔ |
| `isFull` | 全屏互动模式 | ⛔ |
| `fullTime` | 全屏互动回放进度同步 | ⛔ |
| `forceWebview` | 强制 webview 形态直播间 | ⛔ |
