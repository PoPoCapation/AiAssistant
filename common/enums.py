"""统一响应码枚举（对齐 Java group-buy-market 的 ResponseCode）。

Java 中 ``ResponseCode(code, info)`` 为双字段枚举；这里用 ``Enum`` + ``__new__``
让三者同时成立：
    ResponseCode.SUCCESS.code  == "0000"
    ResponseCode.SUCCESS.info  == "成功"
    ResponseCode.SUCCESS.value == "0000"   # 便于 ResponseCode("0000") 反查
"""
from __future__ import annotations

from enum import Enum


class ResponseCode(Enum):
    """系统级响应码。"""

    # ---- 通用（与 Java 版一致）----
    SUCCESS = ("0000", "成功")
    UN_ERROR = ("0001", "未知失败")
    ILLEGAL_PARAMETER = ("0002", "非法参数")
    INDEX_EXCEPTION = ("0003", "唯一索引冲突")
    UPDATE_ZERO = ("0004", "更新记录为0")
    HTTP_EXCEPTION = ("0005", "HTTP接口调用异常")
    RATE_LIMITER = ("0006", "接口限流")

    # ---- 智能助手相关 ----
    LLM_ERROR = ("A0001", "LLM 调用失败")
    LLM_STREAM_ERROR = ("A0002", "LLM 流式调用失败")
    LLM_CONFIG_ERROR = ("A0003", "LLM 配置缺失")
    LLM_TIMEOUT = ("A0004", "LLM 调用超时")

    def __new__(cls, code: str, info: str) -> "ResponseCode":
        obj = object.__new__(cls)
        obj._value_ = code  # value 即 code
        obj.code = code
        obj.info = info
        return obj

    def __str__(self) -> str:
        return f"{self.code} {self.info}"
