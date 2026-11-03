"""微信客户端：code2session 换 open_id / union_id。"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.services.client_service.xiaoe_client import Transport, urllib_transport

DEFAULT_WECHAT_API_BASE_URL = "https://api.weixin.qq.com"

# ---------------------------------------------------------------------------
# 本工程用到的微信小程序接口（只有这 3 个）
#   1. GET  /sns/jscode2session                  uni.login 的 code → open_id / union_id / session_key
#   2. POST /cgi-bin/stable_token                小程序全局 access_token（换手机号要用）
#   3. POST /wxa/business/getuserphonenumber      getPhoneNumber 的 code → 手机号（校验水印 appid）
# ---------------------------------------------------------------------------
PATH_JSCODE2SESSION = "/sns/jscode2session"
PATH_STABLE_TOKEN = "/cgi-bin/stable_token"
PATH_GET_PHONE_NUMBER = "/wxa/business/getuserphonenumber"

ENDPOINTS = {
    "jscode2session": ("GET", PATH_JSCODE2SESSION),
    "stableToken": ("POST", PATH_STABLE_TOKEN),
    "getPhoneNumber": ("POST", PATH_GET_PHONE_NUMBER),
}


def resolved_paths(overrides: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """「清单默认路径」+「环境变量覆盖」合成实际路径表；未知键忽略，缺前导斜杠自动补。"""
    paths = {name: path for name, (_method, path) in ENDPOINTS.items()}
    for name, path in (overrides or {}).items():
        text = str(path or "").strip()
        if not text or name not in paths:
            continue
        paths[name] = text if text.startswith("/") else "/" + text
    return paths


class WechatError(RuntimeError):
    """微信接口调用失败。"""


@dataclass
class WechatConfig:
    app_id: str
    app_secret: str
    api_base_url: str = DEFAULT_WECHAT_API_BASE_URL
    timeout_ms: int = 10000
    # 接口路径覆盖：键名取 ENDPOINTS 的 name（jscode2session / stableToken / getPhoneNumber）
    paths: Optional[Dict[str, str]] = None


@dataclass
class WechatPhone:
    phone: str
    watermark_app_id: str = ""


@dataclass
class WechatSession:
    open_id: str
    union_id: str
    session_key: str = ""


class WechatClient:
    def __init__(self, config: WechatConfig, transport: Optional[Transport] = None):
        self.config = config
        self._transport = transport or urllib_transport
        # 实际使用的接口路径：ENDPOINTS 默认值 + 环境变量覆盖
        self._paths = resolved_paths(config.paths)
        self._token_lock = threading.Lock()
        self._access_token = ""
        self._token_expire_at = 0.0

    # ---------- 基础 ----------

    def _path(self, name: str) -> str:
        """按清单 name 取实际路径。"""
        return self._paths.get(name) or ENDPOINTS[name][1]

    def paths(self) -> Dict[str, str]:
        """当前生效的接口路径表（给 /health 之类的自检回显用）。"""
        return dict(self._paths)

    def _base(self) -> str:
        return (self.config.api_base_url or DEFAULT_WECHAT_API_BASE_URL).rstrip("/")

    def _post_json(self, path: str, payload: dict) -> dict:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        status, text = self._transport(
            self._base() + path, "POST", {"Content-Type": "application/json"}, body,
            max(self.config.timeout_ms, 1000) / 1000.0,
        )
        try:
            data = json.loads(text)
        except ValueError as error:
            raise WechatError("微信返回非 JSON（HTTP %s）：%s" % (status, text[:200])) from error
        return data

    def stable_access_token(self, force_refresh: bool = False) -> str:
        """小程序全局 access_token（stable_token），进程内缓存，提前 5 分钟过期。"""
        if not self.config.app_id or not self.config.app_secret:
            raise WechatError("缺少微信小程序凭证：WX_APP_ID / WX_APP_SECRET")
        with self._token_lock:
            if not force_refresh and self._access_token and time.time() < self._token_expire_at:
                return self._access_token

            data = self._post_json(
                self._path("stableToken"),
                {"grant_type": "client_credential", "appid": self.config.app_id, "secret": self.config.app_secret},
            )
            token = str(data.get("access_token") or "")
            if not token:
                raise WechatError("微信未返回 access_token：%s %s" % (data.get("errcode"), data.get("errmsg") or ""))
            expires_in = int(data.get("expires_in") or 7200)
            self._access_token = token
            self._token_expire_at = time.time() + max(expires_in - 300, 60)
            return token

    def get_phone_number(self, code: str) -> WechatPhone:
        """用 getPhoneNumber 的 code 换手机号（校验水印 appid 与当前小程序一致）。"""
        if not (code or "").strip():
            raise WechatError("缺少手机号授权 code")

        access_token = self.stable_access_token()
        data = self._post_json(
            self._path("getPhoneNumber") + "?access_token=" + urllib.parse.quote(access_token),
            {"code": code},
        )
        if int(data.get("errcode") or 0) != 0:
            raise WechatError("换手机号失败：%s %s" % (data.get("errcode"), data.get("errmsg") or ""))

        info = data.get("phone_info") or {}
        phone = str(info.get("purePhoneNumber") or info.get("phoneNumber") or "").strip()
        watermark = str((info.get("watermark") or {}).get("appid") or "")
        if not phone:
            raise WechatError("微信返回的手机号为空")
        if watermark and self.config.app_id and watermark != self.config.app_id:
            raise WechatError("手机号凭证所属小程序不匹配：%s" % watermark)
        return WechatPhone(phone=phone, watermark_app_id=watermark)

    def jscode2session(self, code: str) -> WechatSession:
        if not self.config.app_id or not self.config.app_secret:
            raise WechatError("缺少微信小程序凭证：WX_APP_ID / WX_APP_SECRET")
        if not (code or "").strip():
            raise WechatError("缺少微信登录 code")

        base = (self.config.api_base_url or DEFAULT_WECHAT_API_BASE_URL).rstrip("/")
        query = urllib.parse.urlencode(
            {
                "appid": self.config.app_id,
                "secret": self.config.app_secret,
                "js_code": code,
                "grant_type": "authorization_code",
            }
        )
        status, text = self._transport(
            self._base() + self._path("jscode2session") + "?" + query,
            "GET",
            {},
            None,
            max(self.config.timeout_ms, 1000) / 1000.0,
        )
        try:
            data: Dict[str, Any] = json.loads(text)
        except ValueError as error:
            raise WechatError("微信返回非 JSON（HTTP %s）：%s" % (status, text[:200])) from error

        errcode = int(data.get("errcode") or 0)
        if errcode != 0:
            raise WechatError("微信 code2session 失败：%s %s" % (errcode, data.get("errmsg") or ""))

        open_id = str(data.get("openid") or "")
        union_id = str(data.get("unionid") or "")
        if not open_id:
            raise WechatError("微信未返回 openid")
        return WechatSession(open_id=open_id, union_id=union_id, session_key=str(data.get("session_key") or ""))
