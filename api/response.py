"""统一响应 ``Response[T]``（对齐 Java group-buy-market 的 ``Response``）。

非流式接口统一返回 ``{"code","info","data"}``，对应 ``common/enums.py::ResponseCode``。
"""
from __future__ import annotations

from typing import Generic, Optional, TypeVar

from pydantic import BaseModel

from common.enums import ResponseCode

T = TypeVar("T")


class Response(BaseModel, Generic[T]):
    """统一响应体。"""

    code: str = ResponseCode.SUCCESS.code
    info: str = ResponseCode.SUCCESS.info
    data: Optional[T] = None    

    @classmethod
    def success(cls, data: Optional[T] = None, info: str = ResponseCode.SUCCESS.info) -> "Response[T]":
        return cls(code=ResponseCode.SUCCESS.code, info=info, data=data)

    @classmethod
    def failure(
        cls,
        code: ResponseCode = ResponseCode.UN_ERROR,
        info: Optional[str] = None,
        data: Optional[T] = None,
    ) -> "Response[T]":
        return cls(code=code.code, info=info if info is not None else code.info, data=data)
