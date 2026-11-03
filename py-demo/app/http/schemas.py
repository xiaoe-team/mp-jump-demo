"""OpenAPI 响应模型：统一信封 + 各接口的 data。

路由实际返回的是 JSONResponse（{code,msg,data,trace_id} 信封，HTTP 恒为 200），
这里用 Pydantic 模型把这些结构声明出来，只为了生成可读的接口文档 / 契约，
不参与运行时校验。
"""
from __future__ import annotations

from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    """统一响应信封：code=0 成功、code=-1 失败，HTTP 状态码恒为 200。"""

    code: int = Field(0, description="0 成功；-1 失败（HTTP 恒为 200，失败原因看 msg）")
    msg: str = Field("ok", description="成功为 ok，失败时为可读原因")
    data: Optional[T] = Field(None, description="业务数据；失败时为 null")
    trace_id: str = Field(..., description="请求追踪 ID，响应头 X-Trace-ID 同值")


# ---------------------------------------------------------------- 各接口 data


class LoginData(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {"koToken": "ko_xxx", "userId": "u_xxx", "expiresIn": 7200}
    })

    koToken: str = Field(..., description="店铺级登录态 ko_token，跳转时按需携带")
    userId: str = Field(..., description="小鹅通用户 ID")
    expiresIn: int = Field(..., description="ko_token 有效期（秒）")


class SessionCheckData(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {"valid": True, "userId": "u_xxx", "msg": ""}
    })

    valid: bool = Field(..., description="登录态是否有效（查后端进程内会话表）")
    userId: str = Field("", description="有效时返回用户 ID")
    msg: str = Field("", description="无效时的原因")


class ProfileData(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "userId": "u_xxx",
            "isBindPhone": True,
            "maskedPhone": "138****1234",
            "nickname": "小明",
            "avatar": "https://...",
        }
    })

    userId: str = Field(..., description="用户 ID")
    isBindPhone: bool = Field(..., description="是否已绑定手机号")
    maskedPhone: str = Field("", description="脱敏手机号")
    nickname: str = Field("", description="昵称")
    avatar: str = Field("", description="头像地址")


class BindPhoneCheckData(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {"isBindPhone": False, "maskedPhone": ""}
    })

    isBindPhone: bool = Field(..., description="是否已绑定手机号")
    maskedPhone: str = Field("", description="脱敏手机号（未绑定为空）")


class BindPhoneData(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": False,
            "needMergeConfirm": True,
            "maskedPhone": "138****1234",
            "bindToken": "bt_xxx",
            "expiresIn": 600,
            "conflictUserId": "u_other",
        }
    })

    success: bool = Field(..., description="是否已直接完成绑定")
    needMergeConfirm: bool = Field(..., description="手机号属于其它账号，需要二次确认合并")
    maskedPhone: str = Field("", description="脱敏手机号")
    bindToken: Optional[str] = Field(None, description="需要合并时的一次性凭证（10 分钟有效）")
    expiresIn: Optional[int] = Field(None, description="bindToken 有效期（秒）")
    conflictUserId: Optional[str] = Field(None, description="手机号已归属的用户 ID")
    merged: Optional[bool] = Field(None, description="本次是否为合并操作")


class LoginUrlData(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "loginUrl": "https://xiaoe.example.com/p/course/ecourse/preview/course_xxx"
            "?app_env_type=mini_program_wechat_sdk&app_id=app_xxx&state=xxx",
            "userId": "u_xxx",
        }
    })

    loginUrl: str = Field(..., description="内嵌 H5 一次性登录地址（有效期 1 分钟，state 一次性）")
    userId: str = Field(..., description="登录后的小鹅通用户 ID")


class HealthData(BaseModel):
    name: str = Field(..., description="服务名")
    model: str = Field(..., description="实现分支标识，当前固定 py-demo")
    mode: str = Field(..., description="是否真实调用上游，当前固定 real")
    apiBaseUrl: str = Field(..., description="小鹅云开放平台地址")
    wechatApiBaseUrl: str = Field(..., description="微信接口地址")
    credentials: Dict[str, bool] = Field(..., description="各凭证是否配齐（只回显布尔）")
    upstreams: Dict[str, Any] = Field(..., description="当前生效的上游接口路径与被覆盖项")
    env: str = Field(..., description="环境名（development / test / production）")
    configFile: str = Field(..., description="实际读取的配置文件")


# ---------------------------------------------------------------- 响应类型别名

LoginResponse = Envelope[LoginData]
SessionCheckResponse = Envelope[SessionCheckData]
ProfileResponse = Envelope[ProfileData]
BindPhoneCheckResponse = Envelope[BindPhoneCheckData]
BindPhoneResponse = Envelope[BindPhoneData]
LoginUrlResponse = Envelope[LoginUrlData]
HealthResponse = Envelope[HealthData]

__all__: List[str] = [
    "Envelope",
    "LoginData",
    "LoginResponse",
    "SessionCheckData",
    "SessionCheckResponse",
    "ProfileData",
    "ProfileResponse",
    "BindPhoneCheckData",
    "BindPhoneCheckResponse",
    "BindPhoneData",
    "BindPhoneResponse",
    "LoginUrlData",
    "LoginUrlResponse",
    "HealthData",
    "HealthResponse",
]
