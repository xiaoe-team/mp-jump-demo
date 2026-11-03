"""未匹配路径统一返回 JSON 信封。"""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.http.response import fail

router = APIRouter()


@router.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def api_not_found(request: Request, rest: str):
    return fail(request, "没有这个接口：/api/" + rest)


@router.api_route("/{rest:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def not_found(request: Request, rest: str):
    return fail(request, "没有这个路径：/" + rest + "（后端只提供 /api/* 与 /health）")
