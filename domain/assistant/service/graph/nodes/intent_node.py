"""意图节点（对应 IMPL 2.2 / 3.4）。

调 LLM（绑定工具）处理本轮：
- 若 LLM 产生 ``tool_calls`` -> ``intent='need_tool'``，路由到 tool_node；
- 否则 ``intent='direct'``，AIMessage.content 即为回答，路由到 response_node（直通）。
"""
from __future__ import annotations

from langchain_core.messages import SystemMessage

from domain.assistant.adapter.port.illm_port import ILLMPort
from domain.assistant.service.graph.state import AssistantState


def build_intent_node(llm_port: ILLMPort, tools: list):
    """构造意图节点（闭包注入 LLM 端口 + 工具列表）。返回 langgraph 节点函数。"""

    async def intent_node(state: AssistantState) -> dict:
        # 组装 LLM 输入：系统提示 + 历史 + 本轮（state.messages 已含历史与本轮 user）
        messages = [SystemMessage(content=state["system_prompt"])] + list(state["messages"])
        ai = await llm_port.chat_with_tools(messages, tools)
        intent = "need_tool" if ai.tool_calls else "direct"
        return {"messages": [ai], "intent": intent}

    return intent_node
