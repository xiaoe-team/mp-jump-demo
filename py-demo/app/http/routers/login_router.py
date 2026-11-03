"""登录态接口：login / session/check / profile / login-url。"""
from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.http.response import fail, ok
from app.http.schemas import (
    BindPhoneCheckResponse,
    BindPhoneResponse,
    LoginResponse,
    LoginUrlResponse,
    ProfileResponse,
    SessionCheckResponse,
)
from app.providers import settings
from app.services.client_service.wechat_client import WechatError
from app.services.client_service.xiaoe_client import XiaoeError
from app.services.login_service import LoginService

router = APIRouter(tags=["登录与登录态"])


class LoginRequest(BaseModel):
    """登录入参：小程序 appid 统一叫 wx_app_id，放请求体，不用请求头。"""

    wx_app_id: str = ""
    code: str = ""


class TokenRequest(BaseModel):
    token: str = ""


class PhoneBindRequest(BaseModel):
    token: str = ""
    code: str = ""
    bind_token: str = ""
    confirm_merge: bool = False


class LoginUrlRequest(BaseModel):
    """内嵌 H5 登录态中转入参：小程序 appid 统一叫 wx_app_id。"""

    wx_app_id: str = ""
    code: str = ""
    redirect_uri: str = ""


@router.post(
    "/login",
    operation_id="login",
    summary="小程序登录",
    description="微信 code → union_id → 小鹅云注册（幂等）→ SDK 登录，返回 ko_token。\n\n"
    "上游报错原样透出（如 40029 invalid code、40125 invalid appsecret）。",
    responses={200: {"model": LoginResponse, "description": "登录结果（code=-1 表示失败）"}},
)
def user_login(request: Request, body: LoginRequest):
    service = LoginService(settings())
    try:
        return ok(request, service.login(body.code, body.wx_app_id))
    except (ValueError, XiaoeError, WechatError) as error:
        return fail(request, str(error))


@router.post(
    "/session/check",
    operation_id="sessionCheck",
    summary="校验登录态",
    description="查后端进程内会话表（ko_token → user_id）。后端重启后会话即清空。",
    responses={200: {"model": SessionCheckResponse}},
)
def check_login(request: Request, body: TokenRequest):
    service = LoginService(settings())
    try:
        return ok(request, service.check_login(body.token))
    except (ValueError, XiaoeError, WechatError) as error:
        return fail(request, str(error))


@router.post(
    "/check-bind-phone",
    operation_id="checkBindPhone",
    summary="查询手机号绑定状态",
    description="只有 phone_resource 为 phone 才算真正绑定（信息采集来的不算）。",
    responses={200: {"model": BindPhoneCheckResponse}},
)
def check_bind_phone(request: Request, body: TokenRequest):
    service = LoginService(settings())
    try:
        return ok(request, service.check_bind_phone(body.token))
    except (ValueError, XiaoeError, WechatError) as error:
        return fail(request, str(error))


@router.post(
    "/bind-or-merge-phone",
    operation_id="bindOrMergePhone",
    summary="绑定 / 合并手机号",
    description="两阶段：\n\n"
    "1. 只传 code → 换手机号，若该号属于其他账号则返回 needMergeConfirm + bindToken；\n"
    "2. 传 bindToken + confirm_merge=true → 执行绑定/合并。",
    responses={200: {"model": BindPhoneResponse}},
)
def bind_or_merge_phone(request: Request, body: PhoneBindRequest):
    service = LoginService(settings())
    try:
        return ok(
            request,
            service.bind_or_merge_phone(
                token=body.token,
                code=body.code,
                bind_token=body.bind_token,
                confirm_merge=body.confirm_merge,
            ),
        )
    except (ValueError, XiaoeError, WechatError) as error:
        return fail(request, str(error))


@router.post(
    "/login-url",
    operation_id="loginUrl",
    summary="换取内嵌 H5 登录地址",
    description="登录取 user_id 后调小鹅云 xe.login.url（login_type=4）换一次性地址，"
    "落地点会种下 H5 的登录 cookie。redirect_uri 上的 app_env_type / app_id 会先被剥掉（平台会自己补）。",
    responses={200: {"model": LoginUrlResponse}},
)
def login_url(request: Request, body: LoginUrlRequest):
    """内嵌 H5 登录态中转：换一次性登录地址。"""
    service = LoginService(settings())
    try:
        return ok(request, service.login_url(body.code, body.redirect_uri, body.wx_app_id))
    except (ValueError, XiaoeError, WechatError) as error:
        return fail(request, str(error))


@router.post(
    "/profile",
    operation_id="profile",
    summary="查询用户资料",
    description="按会话表里的 user_id 调 xe.user.info.get；手机号已脱敏。",
    responses={200: {"model": ProfileResponse}},
)
def get_profile(request: Request, body: TokenRequest):
    service = LoginService(settings())
    try:
        return ok(request, service.profile(body.token))
    except (ValueError, XiaoeError, WechatError) as error:
        return fail(request, str(error))
