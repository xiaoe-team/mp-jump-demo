"""登录态接口：login / session/check / profile / login-url。"""
from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.http.response import fail, ok
from app.providers import settings
from app.services.client_service.wechat_client import WechatError
from app.services.client_service.xiaoe_client import XiaoeError
from app.services.login_service import LoginService

router = APIRouter()


class LoginRequest(BaseModel):
    """登录入参：小程序 appid 统一叫 wx_app_id，放请求体，不用请求头。"""

    wx_app_id: str = ""
    code: str = ""
    # 内嵌环境标识：由前端作为参数传入（不再走请求头）
    app_env_type: str = ""


class TokenRequest(BaseModel):
    token: str = ""
    # 内嵌环境标识：由前端作为参数传入（不再走请求头）
    app_env_type: str = ""


class PhoneBindRequest(BaseModel):
    token: str = ""
    code: str = ""
    bind_token: str = ""
    confirm_merge: bool = False
    app_env_type: str = ""


class LoginUrlRequest(BaseModel):
    """内嵌 H5 登录态中转入参：小程序 appid 统一叫 wx_app_id。"""

    wx_app_id: str = ""
    code: str = ""
    redirect_uri: str = ""
    app_env_type: str = ""


@router.post("/login")
def user_login(request: Request, body: LoginRequest):
    service = LoginService(settings())
    try:
        return ok(request, service.login(body.code, body.wx_app_id))
    except (ValueError, XiaoeError, WechatError) as error:
        return fail(request, str(error))


@router.post("/session/check")
def check_login(request: Request, body: TokenRequest):
    service = LoginService(settings())
    try:
        return ok(request, service.check_login(body.token))
    except (ValueError, XiaoeError, WechatError) as error:
        return fail(request, str(error))


@router.post("/check-bind-phone")
def check_bind_phone(request: Request, body: TokenRequest):
    service = LoginService(settings())
    try:
        return ok(request, service.check_bind_phone(body.token))
    except (ValueError, XiaoeError, WechatError) as error:
        return fail(request, str(error))


@router.post("/bind-or-merge-phone")
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


@router.post("/login-url")
def login_url(request: Request, body: LoginUrlRequest):
    """内嵌 H5 登录态中转：换一次性登录地址。"""
    service = LoginService(settings())
    try:
        return ok(request, service.login_url(body.code, body.redirect_uri, body.wx_app_id))
    except (ValueError, XiaoeError, WechatError) as error:
        return fail(request, str(error))


@router.post("/profile")
def get_profile(request: Request, body: TokenRequest):
    service = LoginService(settings())
    try:
        return ok(request, service.profile(body.token))
    except (ValueError, XiaoeError, WechatError) as error:
        return fail(request, str(error))
