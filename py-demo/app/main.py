"""应用装配入口：create_app() 建应用，main() 起 uvicorn。"""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.http.docs_page import render_docs_html

from app.config import Settings, load_settings
from app.http.middleware import RecoveryMiddleware, TraceIDMiddleware
from app.http.routers import health_router, login_router, notfound_router
from app.providers import init_providers, logger

APP_NAME = "jump-xiaoe-live-demo"


def create_app(settings: Optional[Settings] = None, print_banner: bool = True) -> FastAPI:
    """创建 FastAPI 应用。"""
    config = init_providers(settings or load_settings())

    app = FastAPI(
        title=APP_NAME,
        description=(
            "跳转小鹅通鹅直播（直播 / 录播）的演示后端。\n\n"
            "**响应约定**：统一信封 `{code, msg, data, trace_id}`，`code=0` 成功、`code=-1` 失败，"
            "**HTTP 状态码恒为 200**，失败原因看 `msg`；`trace_id` 同时出现在响应头 `X-Trace-ID`。\n\n"
            "**请求约定**：不使用任何自定义请求头，业务参数（`wx_app_id` / `code` / `token` / "
            "`redirect_uri` / `app_env_type`）一律走请求体。"
        ),
        version="1.0.0",
        docs_url=None,   # 用自己的中文文档页（见 app/http/docs_page.py）
        openapi_url="/api/openapi.json",
        openapi_tags=[
            {"name": "登录与登录态", "description": "登录、登录态校验、用户资料、手机号绑定、内嵌 H5 交接"},
            {"name": "运维", "description": "健康检查与配置自检"},
        ],
    )

    # 注意顺序：后添加的在更外层。CORS 最外层，其次是 trace_id，最后是兜底。
    app.add_middleware(RecoveryMiddleware)
    app.add_middleware(TraceIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Trace-ID"],
    )

    app.include_router(health_router.router)

    api_prefix = "/api"
    app.include_router(login_router.router, prefix=api_prefix)

    # 中文版接口文档页（Swagger UI + 文案本地化），数据来自 /api/openapi.json
    @app.get("/api/docs", include_in_schema=False, summary="接口文档")
    def api_docs() -> HTMLResponse:
        return HTMLResponse(
            render_docs_html(title=app.title, openapi_url=app.openapi_url or "/api/openapi.json")
        )

    # 未匹配的路径统一返回 JSON 信封（后端只提供 API，不托管任何静态产物）
    app.include_router(notfound_router.router)

    if print_banner:
        _print_banner(config)
    return app


def _print_banner(config: Settings) -> None:
    log = logger()
    missing = [name for name, ok in config.credential_status().items() if not ok]
    log.info(
        "server_started\tenv=%s\tapi=%s\tstore_app_id=%s\tconfig=%s\tmissing=%s",
        config.env_name,
        config.api_base_url,
        config.store_app_id or "未配置",
        config.config_file,
        ", ".join(missing) if missing else "无",
    )


def main(env_name: Optional[str] = None, config_file: Optional[str] = None) -> None:
    """本地启动：python3 run.py [--env test] [--config path]。"""
    import uvicorn

    config = load_settings(env_file=config_file, env_name=env_name)
    app = create_app(config)
    uvicorn.run(app, host=config.host, port=config.port, log_level="info")


# uvicorn app.main:app 也能直接跑（模块级创建不重复打启动横幅，横幅由 main() 打）
app = create_app(print_banner=False)

if __name__ == "__main__":
    main()
