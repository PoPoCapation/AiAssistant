"""会话上下文值对象（Redis Session v2，对应 PRD 第九章）。

- ``summary``：较早轮次的滚动摘要；
- ``messages``：最近若干轮**完整**消息（无损，含 tool_calls/tool_call_id）；
- ``revision``：保存版本号（每次写入递增）；
- ``updated_at``：最后更新时间（ISO）；
- ``source_message_count``：已被摘要进 summary 的消息条数。
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage


class SessionContext(BaseModel):
    summary: str = Field(default="", description="较早轮次的滚动摘要")
    messages: list[BaseMessage] = Field(default_factory=list, description="最近若干轮完整消息（无损）")
    revision: int = Field(default=0, description="保存版本号")
    updated_at: str = Field(default="", description="最后更新时间（ISO）")
    source_message_count: int = Field(default=0, description="已被摘要的消息条数")

    model_config = {"arbitrary_types_allowed": True}
