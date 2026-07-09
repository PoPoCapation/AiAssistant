"""FastAPI 应用入口（对应 PRD ``app/main.py`` + 阶段 0.6）。

注册 ``trigger/http/*_controller`` 路由，加 TraceId 中间件（参考 Java ``TraceIdFilter``）。

启动：``uvicorn app.main:app --host 0.0.0.0 --port 8088 --reload``
"""
from __future__ import annotations

from fastapi import FastAPI
from starlette.types import ASGIApp

from common.trace import TRACE_ID_HEADER, clear_trace_id, new_trace_id
from trigger.http.assistant_controller import router as assistant_router
from trigger.http.chat_controller import router as chat_router
from trigger.http.health_controller import router as health_router


class TraceIdMiddleware:
    """生成/透传 trace-id（纯 ASGI 中间件，不缓冲流式响应）。

    参考 Java ``TraceIdFilter``：无 ``trace-id`` 请求头则生成 UUID，
    写入 contextvar（同 task，endpoint 可见）+ ``scope.state``，
    响应头回写 ``trace-id``，结束清理上下文。
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        trace_id = None
        for key, value in scope.get("headers", []):
            if key.decode().lower() == TRACE_ID_HEADER:
                trace_id = value.decode()
                break
        if not trace_id:
            trace_id = new_trace_id()  # 顺带写入 contextvar

        scope.setdefault("state", {})["trace_id"] = trace_id

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((TRACE_ID_HEADER.encode(), trace_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            clear_trace_id()


def create_app() -> FastAPI:
    app = FastAPI(title="AiAssistant", description="拼团营销平台智能客服", version="1.0.0")
    app.add_middleware(TraceIdMiddleware)  # type: ignore[arg-type]
    app.include_router(health_router)
    app.include_router(assistant_router)
    app.include_router(chat_router)
    return app


app = create_app()
