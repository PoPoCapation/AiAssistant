"""TraceId 上下文变量（对应 Java TraceIdFilter 的 ``MDC.put("trace-id", ...)``）。

在请求入口生成 traceId 写入上下文，日志/调用链统一读取；
基于 ``contextvars.ContextVar``，协程与异步任务间隔离安全。
对应 PRD types/common.py。
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Optional

# HTTP 头名，与 Java TraceIdFilter 的 "trace-id" 对齐
TRACE_ID_HEADER: str = "trace-id"

_TRACE_ID: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


def get_trace_id() -> Optional[str]:
    """获取当前上下文的 traceId，未设置返回 None。"""
    return _TRACE_ID.get()


def set_trace_id(trace_id: Optional[str]) -> None:
    """设置当前上下文的 traceId。"""
    _TRACE_ID.set(trace_id)


def new_trace_id() -> str:
    """生成并设置一个新的 traceId（UUID，带连字符，与 Java 一致），返回该值。"""
    trace_id = str(uuid.uuid4())
    _TRACE_ID.set(trace_id)
    return trace_id


def clear_trace_id() -> None:
    """清除当前上下文的 traceId（对应 Java ``finally { MDC.clear(); }``）。"""
    _TRACE_ID.set(None)
