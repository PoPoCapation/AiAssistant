"""应用异常（对齐 Java group-buy-market 的 AppException）。

携带 ``code``/``info``，由 trigger 层捕获后转成统一 ``Response``。
构造方式：
    AppException(ResponseCode.UN_ERROR)
    AppException(ResponseCode.LLM_ERROR, "超时")
    AppException("A0001", "LLM 调用失败")
    AppException(ResponseCode.LLM_ERROR, cause=exc)
"""
from __future__ import annotations

from typing import Optional, Union

from common.enums import ResponseCode


class AppException(RuntimeError):
    """携带 code/info 的业务/系统异常。"""

    code: str
    info: str

    def __init__(
        self,
        code: Union[ResponseCode, str],
        info: Optional[str] = None,
        *,
        cause: Optional[BaseException] = None,
    ) -> None:
        if isinstance(code, ResponseCode):
            self.code = code.code
            self.info = info if info is not None else code.info
        else:
            self.code = str(code)
            self.info = info if info is not None else ""
        super().__init__(self.info or self.code, cause)

    def __str__(self) -> str:
        return f"AppException(code={self.code!r}, info={self.info!r})"
