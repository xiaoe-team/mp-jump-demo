"""健康检查：/health。"""
from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Request

from app.config import Settings
from app.http.response import ok
from app.http.schemas import HealthResponse
from app.providers import settings
from app.services.client_service import wechat_client, xiaoe_client
from app.services.login_service import LoginService

router = APIRouter(tags=["运维"])


def _upstreams(config: Settings) -> Dict[str, object]:
    """当前实际使用的上游接口清单（默认路径 + 环境变量覆盖），用来确认配置是否生效。"""
    xiaoe = xiaoe_client.resolved_paths(config.xiaoe_paths)
    wechat = wechat_client.resolved_paths(config.wechat_paths)
    overridden: List[str] = ["xiaoe." + name for name in sorted(config.xiaoe_paths or {})]
    overridden += ["wechat." + name for name in sorted(config.wechat_paths or {})]
    return {
        "xiaoe": {
            name: "%s %s" % (xiaoe_client.ENDPOINTS[name][0], path) for name, path in xiaoe.items()
        },
        "wechat": {
            name: "%s %s" % (wechat_client.ENDPOINTS[name][0], path) for name, path in wechat.items()
        },
        # 被环境变量覆盖过的项（空数组表示全部走代码里的默认路径）
        "overridden": overridden,
    }


def _health(request: Request):
    config = settings()
    info = {
        "name": "jump-xiaoe-live-demo",
        "model": "py-demo",
        "mode": "real",
        "apiBaseUrl": config.api_base_url,
        "wechatApiBaseUrl": config.wechat_api_base_url,
        "credentials": config.credential_status(),
        "upstreams": _upstreams(config),
        "env": config.env_name,
        "configFile": config.config_file,
    }
    return ok(request, info)


_HEALTH_DOC = dict(
    summary="健康检查",
    description="回显环境、配置文件来源、凭证是否配齐（只给布尔），以及当前生效的上游接口清单。",
    responses={200: {"model": HealthResponse}},
)


@router.get("/health", operation_id="healthGet", **_HEALTH_DOC)
def health_get(request: Request):
    return _health(request)


@router.post("/health", operation_id="healthPost", **_HEALTH_DOC)
def health_post(request: Request):
    return _health(request)
