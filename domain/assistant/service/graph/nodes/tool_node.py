"""工具节点（对应 IMPL 2.2 / 3.4）。

执行 intent_node 选中的工具：取最后一条 AIMessage 的 ``tool_calls``，逐个执行，
结果转 ``ToolMessage`` 追加进 ``messages``，并写回 ``tool_results``。
单个工具失败不影响其它工具，错误信息作为该工具的返回内容（降级，对应 PRD 8.5）。
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, ToolMessage

from domain.assistant.service.graph.state import AssistantState


def build_tool_node(tools: list):
    """构造工具节点。``tools`` 为 LangChain ``@tool`` 列表。"""

    tool_map = {t.name: t for t in tools}

    async def tool_node(state: AssistantState) -> dict:
        if not tools:
            return {"tool_results": []}

        # 取最后一条 AIMessage 的 tool_calls
        last_ai = next((m for m in reversed(state["messages"]) if isinstance(m, AIMessage)), None)
        tool_calls = getattr(last_ai, "tool_calls", None) or []

        tool_messages: list[ToolMessage] = []
        results: list[dict] = []
        for tc in tool_calls:
            name = tc.get("name")
            args = tc.get("args", {}) or {}
            call_id = tc.get("id", "")
            tool = tool_map.get(name)
            if tool is None:
                content = f"工具 {name} 不存在"
            else:
                try:
                    content = await tool.ainvoke(args)
                except Exception as e:  # 单工具失败降级，不中断整体
                    content = f"工具 {name} 执行失败: {e}"
            content = str(content)
            tool_messages.append(ToolMessage(content=content, tool_call_id=call_id))
            results.append({"name": name, "args": args, "content": content})

        return {"messages": tool_messages, "tool_results": results}

    return tool_node
