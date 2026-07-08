r"""LangGraph 工作流定义（对应 IMPL 2.3）。

```
START -> intent --(direct)-----> response -> END
              \--(need_tool)--> tool -> response -> END
```

Phase 2 无工具，恒走 ``intent -> response``；Phase 3 注入工具后 ``need_tool`` 分支激活。
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from domain.assistant.adapter.port.illm_port import ILLMPort
from domain.assistant.service.graph.nodes.intent_node import build_intent_node
from domain.assistant.service.graph.nodes.response_node import build_response_node
from domain.assistant.service.graph.nodes.tool_node import build_tool_node
from domain.assistant.service.graph.state import AssistantState


def build_assistant_graph(llm_port: ILLMPort, tools: list | None = None):
    """组装并编译助手工作流，返回可 ``ainvoke`` 的已编译图。"""
    tools = tools or []

    graph = StateGraph(AssistantState)
    graph.add_node("intent", build_intent_node(llm_port, tools))
    graph.add_node("tool", build_tool_node(tools))
    graph.add_node("response", build_response_node(llm_port))

    graph.add_edge(START, "intent")
    graph.add_conditional_edges(
        "intent",
        lambda state: state.get("intent"),  # 'direct' | 'need_tool'
        {"need_tool": "tool", "direct": "response"},
    )
    graph.add_edge("tool", "response")
    graph.add_edge("response", END)
    return graph.compile()
