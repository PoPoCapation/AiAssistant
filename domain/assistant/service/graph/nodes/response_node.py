"""回答节点（对应 IMPL 2.2）。

- ``direct`` 路径（Phase 2 全部）：intent_node 已直接给出回答，本节点**直通**，不重复调 LLM；
- ``need_tool`` 路径（Phase 3）：基于 messages + tool_results 综合生成最终回答。
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, SystemMessage

from domain.assistant.adapter.port.illm_port import ILLMPort
from domain.assistant.service.graph.state import AssistantState


def build_response_node(llm_port: ILLMPort):
    """构造回答节点。"""

    async def response_node(state: AssistantState) -> dict:
        # direct：intent_node 产生的 AIMessage 已是最终回答，无需再调 LLM
        if not state.get("tool_results"):
            return {}
        # need_tool：带工具结果再生成最终回答（Phase 3 激活）
        messages = [SystemMessage(content=state["system_prompt"])] + list(state["messages"])
        reply = await llm_port.chat(messages)
        return {"messages": [AIMessage(content=reply)]}

    return response_node
