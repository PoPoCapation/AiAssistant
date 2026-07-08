"""LangGraph 工作流状态（对应 IMPL 2.1）。

``AssistantState`` 在节点间流转：
- ``messages`` 用 ``add_messages`` 累加器：节点返回的消息会**追加**而非覆盖；
- 其余字段为普通替换语义（节点返回哪个就更新哪个）。
"""
from __future__ import annotations

from typing import Annotated, List, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AssistantState(TypedDict):
    """助手工作流状态。"""

    # 历史 + 本轮消息；节点返回的消息经 add_messages 自动追加
    messages: Annotated[List[BaseMessage], add_messages]
    user_id: str
    session_id: str
    system_prompt: str
    # 意图：'need_tool' | 'direct' | None；Phase 2 恒 'direct'，Phase 3 由 tool_calls 决定
    intent: Optional[str]
    # 工具执行结果（Phase 3 填充）
    tool_results: List
