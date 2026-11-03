"""统一响应信封 {code, msg, data, trace_id}。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

from app.providers import logger

CODE_OK = 0
CODE_FAILED = -1

TRACE_ID_HEADER = "X-Trace-ID"
TRACE_ID_FIELD = "trace_id"


def trace_id_of(request: Request) -> str:
    """取当前请求的 trace_id（中间件写入 request.state）。"""
    return getattr(request.state, TRACE_ID_FIELD, "") or "unknown"


def envelope(code: int, msg: str, data: Any = None, trace_id: str = "") -> Dict[str, Any]:
    return {"code": code, "msg": msg, "data": data, "trace_id": trace_id}


def _json(request: Request, body: Dict[str, Any]) -> JSONResponse:
    return JSONResponse(
        content=body,
        status_code=200,
        headers={TRACE_ID_HEADER: body.get(TRACE_ID_FIELD, "")},
    )


def ok(request: Request, data: Optional[Any] = None) -> JSONResponse:
    """成功响应。"""
    return _json(request, envelope(CODE_OK, "ok", {} if data is None else data, trace_id_of(request)))


def fail(request: Request, msg: str, code: int = CODE_FAILED) -> JSONResponse:
    """失败响应（HTTP 仍为 200，业务码表示失败）。

    失败原因必须落日志：信封是 200，网关/访问日志里看不出业务失败，
    排查线上问题（例如 H5 登录态交接失败）时只能靠这一行。
    """
    logger().warning(
        "biz_failed\tmethod=%s\tpath=%s\tcode=%s\ttrace_id=%s\tmsg=%s",
        request.method,
        request.url.path,
        code,
        trace_id_of(request),
        msg,
    )
    return _json(request, envelope(code, msg, None, trace_id_of(request)))
