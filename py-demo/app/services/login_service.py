"""登录核心：微信 code → union_id → 小鹅云注册/登录 → ko_token。"""
from __future__ import annotations

import urllib.parse
from typing import Any, Dict, Optional

from app.config import Settings
from app.providers import logger
from app.providers import settings as get_settings
from app.services.client_service.wechat_client import WechatClient, WechatConfig, WechatError
from app.services.session_store import (
    MemorySessionStore,
    PhoneIntentStore,
    default_phone_intents,
    default_store,
)
from app.services.client_service.xiaoe_client import (
    AccessTokenExpired,
    XiaoeClient,
    XiaoeConfig,
    XiaoeError,
)


def build_xiaoe_client(config: Settings, transport=None) -> XiaoeClient:
    """按配置创建小鹅云客户端（测试可替换本函数或注入 transport）。"""
    return XiaoeClient(
        XiaoeConfig(
            api_base_url=config.api_base_url,
            app_id=config.store_app_id,
            client_id=config.client_id,
            client_secret=config.client_secret,
            sdk_app_id=config.sdk_app_id,
            timeout_ms=config.request_timeout_ms,
            # 接口路径可被环境变量覆盖（API_PATH_*），未配就用 client 里的默认清单
            paths=config.xiaoe_paths,
        ),
        transport=transport,
    )


def build_wechat_client(config: Settings, transport=None) -> WechatClient:
    """按配置创建微信客户端。"""
    return WechatClient(
        WechatConfig(
            app_id=config.wx_app_id,
            app_secret=config.wx_app_secret,
            api_base_url=config.wechat_api_base_url,
            timeout_ms=config.request_timeout_ms,
            # 接口路径可被环境变量覆盖（WX_PATH_*）
            paths=config.wechat_paths,
        ),
        transport=transport,
    )


# 交给上游前要从 redirect_uri 上摘掉的参数：平台换地址时会自己补，我们带过去就重复
_REDIRECT_STRIP_KEYS = ("app_env_type", "app_id")


def strip_redirect_params(url: str) -> str:
    """去掉 redirect_uri 上的 app_env_type / app_id。

    实测：小鹅云 xe.login.url 换地址时会自己补 app_env_type 和 app_id，
    我们传的 redirect_uri 再带一遍就成了 `?app_env_type=..&app_id=..&app_id=..`；
    只传纯路径（保留其它业务参数，如 `?type=2`）换回来的地址参数最干净。
    """
    parts = urllib.parse.urlsplit(url)
    if not parts.query:
        return url
    pairs = [
        (k, v)
        for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        if k not in _REDIRECT_STRIP_KEYS
    ]
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(pairs), parts.fragment)
    )


def mask_phone(phone: str) -> str:
    text = str(phone or "").strip()
    if len(text) < 7:
        return text
    return text[:3] + "****" + text[-4:]


class LoginService:
    """登录相关接口的唯一实现。"""

    def __init__(
        self,
        config: Optional[Settings] = None,
        xiaoe: Optional[XiaoeClient] = None,
        wechat: Optional[WechatClient] = None,
        sessions: Optional[MemorySessionStore] = None,
        phone_intents: Optional[PhoneIntentStore] = None,
    ):
        self.config = config or get_settings()
        self.xiaoe = xiaoe or build_xiaoe_client(self.config)
        self.wechat = wechat or build_wechat_client(self.config)
        # 小鹅云的 xe.user.info.get 不校验 ko_token，所以登录态只能自己记：进程内 token → user_id
        self.sessions = sessions or default_store
        # 手机号绑定/合并的二次确认凭证（bind_token），同样只放内存
        self.phone_intents = phone_intents or default_phone_intents

    # ---------- 内部 ----------

    def _check_wx_app_id(self, wx_app_id: str) -> None:
        """前端传的 wx_app_id 必须与后端配置一致，避免环境写错时静默失败。"""
        incoming = (wx_app_id or "").strip()
        configured = (self.config.wx_app_id or "").strip()
        if incoming and configured and incoming != configured:
            raise ValueError("wx_app_id 与后端配置不一致：请求 %s，配置 %s" % (incoming, configured))

    def _exchange_union_id(self, code: str) -> str:
        session = self.wechat.jscode2session(code)
        if not session.union_id:
            raise ValueError("微信未返回 union_id：请确认小程序已关联正确的微信开放平台")
        return session.union_id

    def _with_token_retry(self, action):
        """access_token 过期（2008）时刷新一次并重试。"""
        token = self.xiaoe.get_access_token()
        try:
            return action(token)
        except AccessTokenExpired:
            token = self.xiaoe.get_access_token(force_refresh=True)
            return action(token)

    # ---------- 对外 ----------

    def login(self, code: str, wx_app_id: str = "") -> Dict[str, Any]:
        """微信 code → ko_token。"""
        if not (code or "").strip():
            raise ValueError("缺少微信登录 code")
        self._check_wx_app_id(wx_app_id)

        union_id = self._exchange_union_id(code)

        # 注册（幂等）+ SDK 登录；两次调用共用「过期则刷新一次」的重试
        self._with_token_retry(lambda token: self.xiaoe.register_user(token, union_id, union_id))
        data = self._with_token_retry(lambda token: self.xiaoe.sdk_account_login(token, union_id, union_id))

        ko_token = str(data.get("token_value") or "")
        user_id = str(data.get("user_id") or "")
        expires_in = int(data.get("expires") or 0)
        self.sessions.save(ko_token, user_id, expires_in)

        return {"koToken": ko_token, "userId": user_id, "expiresIn": expires_in}

    def check_login(self, token: str) -> Dict[str, Any]:
        """校验登录态：查进程内会话（小鹅云 info 接口不校验 ko_token）。"""
        if not (token or "").strip():
            return {"valid": False, "userId": "", "msg": "缺少 ko_token"}

        user_id = self.sessions.get_user_id(token)
        if not user_id:
            return {"valid": False, "userId": "", "msg": "登录态不存在或已过期，请重新登录"}
        return {"valid": True, "userId": user_id, "msg": ""}

    def profile(self, token: str) -> Dict[str, Any]:
        """当前用户资料（手机号脱敏）。"""
        if not (token or "").strip():
            raise ValueError("缺少 ko_token")

        user_id = self.sessions.get_user_id(token)
        if not user_id:
            raise ValueError("登录态不存在或已过期，请重新登录")

        access_token = self.xiaoe.get_access_token()
        info = self.xiaoe.get_user_info(access_token, ko_token=token, user_id=user_id)
        return {
            "userId": info.user_id,
            "isBindPhone": bool(info.phone),
            "maskedPhone": mask_phone(info.phone),
            "nickname": info.nickname,
            "avatar": info.avatar,
        }

    def login_url(self, code: str, redirect_uri: str, wx_app_id: str = "") -> Dict[str, Any]:
        """H5 登录态中转：先按正常链路登录拿 user_id，再换一次性登录地址。"""
        if not (redirect_uri or "").strip():
            raise ValueError("缺少 redirect_uri")

        result = self.login(code, wx_app_id)
        access_token = self.xiaoe.get_access_token()
        # app_env_type / app_id 不传给上游：平台换地址时会自己补，传过去就重复
        clean_redirect = strip_redirect_params(redirect_uri)
        login_url = self.xiaoe.get_login_url(
            access_token=access_token,
            user_id=result["userId"],
            redirect_uri=clean_redirect,
            wx_app_id=self.config.wx_app_id,
        )
        # 交接结果的形态必须可查：只记 origin + path + 参数名，不记 ticket 值
        parsed = urllib.parse.urlparse(login_url)
        logger().info(
            "h5_login_url_built	host=%s	path=%s	query_keys=%s	redirect_host=%s",
            parsed.netloc,
            parsed.path,
            ",".join(sorted(k for k, _v in urllib.parse.parse_qsl(parsed.query))),
            urllib.parse.urlparse(clean_redirect).netloc,
        )
        return {"loginUrl": login_url, "userId": result["userId"]}

    # ---------- 手机号：绑定 / 冲突检测 / 合并 ----------

    def check_bind_phone(self, token: str) -> Dict[str, Any]:
        """当前用户是否已绑定手机号。"""
        user_id = self.sessions.get_user_id(token)
        if not user_id:
            raise ValueError("登录态不存在或已过期，请重新登录")

        access_token = self.xiaoe.get_access_token()
        info = self.xiaoe.get_user_info(access_token, ko_token=token, user_id=user_id, fields=["phone"])
        # 与 psy 一致：只有 phone_resource == "phone" 才算真正绑定（信息采集来的不算）
        bound = bool(info.phone) and info.phone_resource in ("", "phone")
        return {"isBindPhone": bound, "maskedPhone": mask_phone(info.phone) if bound else ""}

    def bind_or_merge_phone(
        self,
        token: str,
        code: str = "",
        bind_token: str = "",
        confirm_merge: bool = False,
    ) -> Dict[str, Any]:
        """手机号绑定/合并（两阶段）。

        阶段一（只传 code）：换手机号 → 查该号是否属于其他账号；
            属于他人 → 返回 need_merge_confirm + bind_token（10 分钟一次性），不合并；
            不属于任何人 → 直接绑定，返回 success。
        阶段二（传 bind_token + confirm_merge=True）：按阶段一缓存的手机号执行绑定/合并。
        """
        user_id = self.sessions.get_user_id(token)
        if not user_id:
            raise ValueError("登录态不存在或已过期，请重新登录")

        access_token = self.xiaoe.get_access_token()

        if bind_token:
            consumed = self.phone_intents.consume(bind_token)
            if not consumed:
                raise ValueError("合并确认凭证已失效，请重新授权手机号")
            intent_user_id, phone = consumed
            if intent_user_id != user_id:
                raise ValueError("合并确认凭证与当前登录用户不一致")
            if not confirm_merge:
                raise ValueError("需要显式确认合并（confirm_merge=true）")
            self.xiaoe.bind_or_merge_phone(access_token, user_id, phone, ko_token=token)
            return {"success": True, "needMergeConfirm": False, "maskedPhone": mask_phone(phone), "merged": True}

        if not (code or "").strip():
            raise ValueError("缺少手机号授权 code")

        wechat_phone = self.wechat.get_phone_number(code)
        phone = wechat_phone.phone

        # 冲突检测：该手机号是否已属于另一个账号
        existing_user_id = self.xiaoe.find_user_by_phone(access_token, phone)
        if existing_user_id and existing_user_id != user_id:
            new_token = self.phone_intents.create(user_id, phone)
            return {
                "success": False,
                "needMergeConfirm": True,
                "maskedPhone": mask_phone(phone),
                "bindToken": new_token,
                "expiresIn": 600,
                "conflictUserId": existing_user_id,
            }

        self.xiaoe.bind_or_merge_phone(access_token, user_id, phone, ko_token=token)
        return {"success": True, "needMergeConfirm": False, "maskedPhone": mask_phone(phone), "merged": False}
