"""小鹅云客户端：access_token、注册、SDK 登录、用户信息、登录 URL。"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

DEFAULT_API_BASE_URL = "https://api.xiaoe-tech.com"

# ---------------------------------------------------------------------------
# 本工程用到的小鹅云开放平台接口（只有这 6 个，改这里就要同步改调用处）
#   1. GET  /token                                                client_credential 换 access_token
#   2. POST /xe.user.register/1.0.0                               注册用户（幂等，user_exists 表示已存在）
#   3. POST /xe.sdk.account.login/1.0.0                           SDK 登录 → ko_token（token_value）
#   4. POST /xe.user.info.get/1.0.0                               查用户资料；身份键四选一：user_id / wx_union_id / wx_open_id / phone
#   5. POST /xe.account-platform.uaccount.bind_or_merge_phone/1.0.0  手机号绑定或合并
#   6. POST /xe.login.url/1.0.0                                   H5 一次性登录地址
# 说明：不带 ko_token 也能查资料（身份键足够即可），所以登录态由本工程的会话表维护。
# ---------------------------------------------------------------------------
PATH_TOKEN = "/token"
PATH_USER_REGISTER = "/xe.user.register/1.0.0"
PATH_SDK_ACCOUNT_LOGIN = "/xe.sdk.account.login/1.0.0"
PATH_USER_INFO_GET = "/xe.user.info.get/1.0.0"
PATH_BIND_OR_MERGE_PHONE = "/xe.account-platform.uaccount.bind_or_merge_phone/1.0.0"
PATH_LOGIN_URL = "/xe.login.url/1.0.0"

ENDPOINTS = {
    "token": ("GET", PATH_TOKEN),
    "register": ("POST", PATH_USER_REGISTER),
    "sdkLogin": ("POST", PATH_SDK_ACCOUNT_LOGIN),
    "userInfo": ("POST", PATH_USER_INFO_GET),
    "bindOrMergePhone": ("POST", PATH_BIND_OR_MERGE_PHONE),
    "loginUrl": ("POST", PATH_LOGIN_URL),
}


def resolved_paths(overrides: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """把「清单默认路径」和「环境变量覆盖」合成实际使用的路径表。

    覆盖键必须是 ENDPOINTS 里的 name；未知键忽略（拼错不至于把接口打成空路径）。
    环境变量可以写成 `xe.user.register/1.0.0` 这种不带前导斜杠的形式，这里统一补上。
    """
    paths = {name: path for name, (_method, path) in ENDPOINTS.items()}
    for name, path in (overrides or {}).items():
        text = str(path or "").strip()
        if not text or name not in paths:
            continue
        paths[name] = text if text.startswith("/") else "/" + text
    return paths

# 小鹅云业务码：access token 过期/不存在
CODE_ACCESS_TOKEN_EXPIRED = 2008

Transport = Any


def urllib_transport(url: str, method: str, headers: Dict[str, str], body: Optional[bytes], timeout: float) -> Tuple[int, str]:
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:  # 4xx/5xx 也把响应体交给上层解析
        return error.code, error.read().decode("utf-8", "replace")


class XiaoeError(RuntimeError):
    """小鹅云调用失败。"""


class AccessTokenExpired(XiaoeError):
    """access_token 过期（业务码 2008），上层可刷新后重试。"""


@dataclass
class XiaoeConfig:
    api_base_url: str
    app_id: str  # 小鹅通店铺 ID
    client_id: str
    client_secret: str
    sdk_app_id: str
    timeout_ms: int = 10000
    # 接口路径覆盖：键名取 ENDPOINTS 的 name（token / register / sdkLogin / userInfo /
    # bindOrMergePhone / loginUrl），未覆盖的沿用 ENDPOINTS 里的默认路径
    paths: Optional[Dict[str, str]] = None


@dataclass
class UserInfo:
    user_id: str = ""
    nickname: str = ""
    avatar: str = ""
    phone: str = ""
    phone_resource: str = ""


class XiaoeClient:
    def __init__(self, config: XiaoeConfig, transport: Optional[Transport] = None):
        self.config = config
        self._transport = transport or urllib_transport
        # 实际使用的接口路径：ENDPOINTS 默认值 + 环境变量覆盖
        self._paths = resolved_paths(config.paths)
        self._token_lock = threading.Lock()
        self._access_token = ""
        self._access_token_expire_at = 0.0

    # ---------- 基础 ----------

    def _path(self, name: str) -> str:
        """按清单 name 取实际路径。"""
        return self._paths.get(name) or ENDPOINTS[name][1]

    def paths(self) -> Dict[str, str]:
        """当前生效的接口路径表（给 /health 之类的自检回显用）。"""
        return dict(self._paths)

    def _url(self, path: str, query: Optional[Dict[str, str]] = None) -> str:
        base = (self.config.api_base_url or DEFAULT_API_BASE_URL).rstrip("/")
        url = base + path
        if query:
            url += "?" + urllib.parse.urlencode({k: v for k, v in query.items() if v})
        return url

    def _post(self, path: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        all_headers = {"Content-Type": "application/json"}
        all_headers.update(headers or {})
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        status, text = self._transport(
            self._url(path), "POST", all_headers, body, max(self.config.timeout_ms, 1000) / 1000.0
        )
        try:
            data = json.loads(text)
        except ValueError as error:
            raise XiaoeError("小鹅云返回非 JSON（HTTP %s）：%s" % (status, text[:200])) from error
        if not isinstance(data, dict):
            raise XiaoeError("小鹅云返回结构异常")
        return data

    def _get(self, path: str, query: Dict[str, str]) -> Dict[str, Any]:
        status, text = self._transport(
            self._url(path, query), "GET", {}, None, max(self.config.timeout_ms, 1000) / 1000.0
        )
        try:
            data = json.loads(text)
        except ValueError as error:
            raise XiaoeError("小鹅云返回非 JSON（HTTP %s）：%s" % (status, text[:200])) from error
        if not isinstance(data, dict):
            raise XiaoeError("小鹅云返回结构异常")
        return data

    # ---------- access_token ----------

    def get_access_token(self, force_refresh: bool = False) -> str:
        """取 access_token（process 内缓存，提前 60 秒过期）。"""
        if not self.config.client_id or not self.config.client_secret or not self.config.app_id:
            raise XiaoeError("缺少小鹅通平台认证配置：APP_ID / CLIENT_ID / CLIENT_SECRET")

        with self._token_lock:
            if not force_refresh and self._access_token and time.time() < self._access_token_expire_at:
                return self._access_token

            data = self._get(
                self._path("token"),
                {
                    "app_id": self.config.app_id,
                    "client_id": self.config.client_id,
                    "secret_key": self.config.client_secret,
                    "grant_type": "client_credential",
                },
            )
            if data.get("code") != 0:
                raise XiaoeError(data.get("msg") or "获取小鹅通 access_token 失败")

            payload = data.get("data") or {}
            token = str(payload.get("access_token") or "")
            if not token:
                raise XiaoeError("小鹅通未返回 access_token")
            expires_in = int(payload.get("expires_in") or 7200)
            self._access_token = token
            self._access_token_expire_at = time.time() + max(expires_in - 60, 60)
            return token

    # ---------- 用户 ----------

    def register_user(self, access_token: str, union_id: str, sdk_user_id: str) -> Dict[str, Any]:
        """注册用户（幂等）。返回 data（含 user_id / user_exists）。"""
        data = self._post(
            self._path("register"),
            {
                "access_token": access_token,
                "data": {
                    "wx_union_id": union_id,
                    "sdk_user_id": sdk_user_id,
                    "sdk_app_id": self.config.sdk_app_id,
                },
            },
        )
        if data.get("code") == CODE_ACCESS_TOKEN_EXPIRED:
            raise AccessTokenExpired(data.get("msg") or "access_token 已过期")
        if data.get("code") != 0:
            raise XiaoeError("注册小鹅通用户失败：%s" % (data.get("msg") or data.get("code")))
        return data.get("data") or {}

    def sdk_account_login(self, access_token: str, app_user_id: str, union_id: str) -> Dict[str, Any]:
        """SDK 账号登录 → ko_token。返回 data（token_key / token_value / user_id / expires）。"""
        data = self._post(
            self._path("sdkLogin"),
            {
                "app_user_id": app_user_id,
                "access_token": access_token,
                "sdk_app_id": self.config.sdk_app_id,
                "user_info": {"union_id": union_id},
            },
        )
        if data.get("code") == CODE_ACCESS_TOKEN_EXPIRED:
            raise AccessTokenExpired(data.get("msg") or "access_token 已过期")
        if data.get("code") != 0:
            raise XiaoeError("小鹅通 SDK 登录失败：%s" % (data.get("msg") or data.get("code")))

        payload = data.get("data") or {}
        if not payload.get("token_value") or not payload.get("user_id"):
            raise XiaoeError("小鹅通 SDK 登录未返回 ko_token 或 user_id")
        return payload

    def get_user_info(
        self,
        access_token: str,
        ko_token: str = "",
        user_id: str = "",
        union_id: str = "",
        open_id: str = "",
        phone: str = "",
        fields: Optional[list] = None,
    ) -> UserInfo:
        """查用户资料；带 ko_token 时同时起到登录态校验作用。"""
        headers = {"Cookie": "ko_token=" + ko_token} if ko_token else None
        data = self._post(
            self._path("userInfo"),
            {
                "access_token": access_token,
                "user_id": user_id,
                "data": {
                    "field_list": fields or ["nickname", "avatar", "phone"],
                    "wx_union_id": union_id,
                    "wx_open_id": open_id,
                    "phone": phone,
                },
            },
            headers,
        )
        if data.get("code") != 0:
            raise XiaoeError(data.get("msg") or "查询小鹅通用户资料失败")

        payload = data.get("data") or {}
        return UserInfo(
            user_id=str(payload.get("user_id") or ""),
            nickname=str(payload.get("nickname") or payload.get("name") or ""),
            avatar=str(payload.get("avatar") or ""),
            phone=str(payload.get("phone") or ""),
            phone_resource=str(payload.get("phone_resource") or ""),
        )

    def find_user_by_phone(self, access_token: str, phone: str) -> str:
        """按手机号查已有用户，返回 user_id（不存在返回空串）。"""
        if not (phone or "").strip():
            return ""
        data = self._post(
            self._path("userInfo"),
            {
                "access_token": access_token,
                "data": {"field_list": ["phone"], "phone": phone, "wx_union_id": "", "wx_open_id": ""},
            },
        )
        if data.get("code") != 0:
            # 查不到通常返回业务错误码，按"该手机号没有对应用户"处理
            return ""
        payload = data.get("data") or {}
        return str(payload.get("user_id") or "")

    def bind_or_merge_phone(self, access_token: str, user_id: str, phone: str, ko_token: str = "") -> dict:
        """手机号绑定 / 合并（小鹅云按手机号决定绑定还是合并）。"""
        headers = {"Cookie": "ko_token=" + ko_token} if ko_token else None
        data = self._post(
            self._path("bindOrMergePhone"),
            {"access_token": access_token, "user_id": user_id, "phone": phone},
            headers,
        )
        if data.get("code") != 0:
            raise XiaoeError(data.get("msg") or "手机号绑定/合并失败")
        return data.get("data") or {}

    def get_login_url(self, access_token: str, user_id: str, redirect_uri: str, wx_app_id: str = "") -> str:
        """H5 一次性登录地址。"""
        data = self._post(
            self._path("loginUrl"),
            {
                "access_token": access_token,
                "user_id": user_id,
                "data": {
                    # login_type 决定换回来的地址长什么样（2026-11-03 实测）：
                    #   1 / 2 / 5 → https://{店铺}.pc.xiaoe-tech.com/login_cooperate/pc_login（PC 登录页）
                    #   3         → https://h5.xiaoecloud.com/platform/login_cooperate/h5_login（平台 H5 登录页）
                    #   4         → 直接把 redirect_uri 换回业务页，附带 state（H5 用它落登录态）
                    # web-view 内嵌只能用 4：塞 PC 登录页进 web-view 会停在登录页出不来。
                    "login_type": 4,
                    "redirect_uri": redirect_uri,
                    "extra_info": {"wx_app_id": wx_app_id},
                },
            },
        )
        if data.get("code") != 0:
            raise XiaoeError(data.get("msg") or "获取 H5 登录地址失败")
        payload = data.get("data") or {}
        url = str(payload.get("login_url") or payload.get("url") or "")
        if not url:
            raise XiaoeError("小鹅通未返回 login_url")
        return url
