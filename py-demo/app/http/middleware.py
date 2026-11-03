"""中间件：trace_id / 访问日志 / 异常兜底。"""
from __future__ import annotations

import time
import uuid
from typing import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.http.response import TRACE_ID_FIELD, TRACE_ID_HEADER, envelope, trace_id_of
from app.providers import logger

RequestHandler = Callable[[Request], Awaitable[Response]]


def _is_valid_trace_id(value: str) -> bool:
    if not value or len(value) > 64:
        return False
    return all(ch.isalnum() or ch in "-_.:" for ch in value)


class TraceIDMiddleware(BaseHTTPMiddleware):
    """校验或生成 trace_id，写入 request.state / 响应头。"""

    async def dispatch(self, request: Request, call_next: RequestHandler) -> Response:
        incoming = request.headers.get(TRACE_ID_HEADER) or request.headers.get("X-Request-ID") or ""
        trace_id = incoming if _is_valid_trace_id(incoming) else uuid.uuid4().hex
        setattr(request.state, TRACE_ID_FIELD, trace_id)

        started = time.time()
        response = await call_next(request)
        response.headers[TRACE_ID_HEADER] = trace_id

        logger().info(
            "http_request\tmethod=%s\tpath=%s\tstatus=%s\tcost_ms=%s\ttrace_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            int((time.time() - started) * 1000),
            trace_id,
        )
        return response


class RecoveryMiddleware(BaseHTTPMiddleware):
    """兜住未处理异常，返回统一失败体。"""

    async def dispatch(self, request: Request, call_next: RequestHandler) -> Response:
        try:
            return await call_next(request)
        except Exception as error:  # noqa: BLE001 - 演示工程统一兜底
            logger().exception("panic_recovered\tpath=%s", request.url.path)
            body = envelope(-1, "服务器内部错误：%s" % error, None, trace_id_of(request))
            return JSONResponse(
                content=body,
                status_code=200,
                headers={TRACE_ID_HEADER: body[TRACE_ID_FIELD]},
            )
