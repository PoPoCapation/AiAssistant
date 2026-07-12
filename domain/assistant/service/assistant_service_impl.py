"""智能助手服务实现（领域层）。

对应 IMPL 阶段 2/4 + 上下文管理（预算 + 滚动摘要 + Redis v2）：
- ``chat`` 非流式 / ``chat_stream`` 流式（astream_events）；
- 每轮：load SessionContext -> compact（超预算滚动摘要）-> 组装（系统提示含摘要）-> graph -> 追加本轮 -> save；
- ``session_id`` 缺省新建；异常降级。
接口定义见 ``assistant_service.py``。
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import AsyncIterator, List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from api.dto.chat import ChatRequest, ChatResponse
from common.enums import ResponseCode
from common.exception import AppException
from domain.assistant.adapter.port.illm_port import ILLMPort
from domain.assistant.adapter.repository.isession_repository import ISessionRepository
from domain.assistant.model.valobj.session_context import SessionContext
from domain.assistant.service.assistant_service import IAssistantService
from domain.assistant.service.context_budget_service import ContextBudgetService

_DEFAULT_SYSTEM_PROMPT = (
    "你是「拼团营销平台」的智能客服助手。请用简洁、专业的中文回答用户关于拼团进度、"
    "成团状态、账户余额、活动规则、退款等问题。涉及用户真实业务数据时，仅依据工具返回"
    "结果作答，不要编造。无法确认意图时，先追问一个最小必要信息。"
)

_ROLE_TO_MSG = {"user": HumanMessage, "assistant": AIMessage}


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _to_messages(req: ChatRequest, system_prompt: str) -> List[BaseMessage]:
    """把 ChatRequest 转成 LangChain 消息列表（system + history + 本轮），供流式测试用。"""
    from langchain_core.messages import SystemMessage

    messages: List[BaseMessage] = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    for m in req.history:
        cls = _ROLE_TO_MSG.get(m.role.lower())
        if cls is not None:
            messages.append(cls(content=m.content))
    messages.append(HumanMessage(content=req.message))
    return messages


def _last_ai_text(messages: List[BaseMessage]) -> str:
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            content = m.content
            return content if isinstance(content, str) else str(content)
    return ""


def _build_system_prompt(base: str, user_id: str, session_id: str, summary: str = "") -> str:
    prompt = (
        f"{base}\n\n[当前上下文] 用户ID：{user_id}；会话ID：{session_id}。"
        "查询用户数据时请使用此 user_id。"
    )
    if summary:
        prompt += f"\n\n[之前对话摘要] {summary}"
    return prompt


class AssistantServiceImpl(IAssistantService):
    def __init__(
        self,
        llm_port: ILLMPort,
        session_repo: ISessionRepository,
        graph,
        budget_service: ContextBudgetService,
        summary_enabled: bool = True,
        system_prompt: str = _DEFAULT_SYSTEM_PROMPT,
    ) -> None:
        self._llm_port = llm_port
        self._session_repo = session_repo
        self._graph = graph
        self._budget = budget_service
        self._summary_enabled = summary_enabled
        self._system_prompt = system_prompt

    async def _prepare(self, req: ChatRequest):
        """load 上下文 -> compact -> 组装初始 state。返回 (session_id, state, ctx)。"""
        if not req.message or not req.message.strip():
            raise AppException(ResponseCode.ILLEGAL_PARAMETER, "消息内容不能为空")
        session_id = req.session_id or str(uuid.uuid4())
        ctx = await self._session_repo.load(session_id)
        current = HumanMessage(content=req.message)
        if self._summary_enabled:
            ctx = await self._budget.compact(ctx, current)
        system_prompt = _build_system_prompt(
            self._system_prompt, req.user_id, session_id, ctx.summary
        )
        state = {
            "messages": ctx.messages + [current],
            "user_id": req.user_id,
            "session_id": session_id,
            "system_prompt": system_prompt,
            "intent": None,
            "tool_results": [],
        }
        return session_id, state, ctx

    async def chat(self, req: ChatRequest) -> ChatResponse:
        session_id, state, ctx = await self._prepare(req)
        try:
            result = await self._graph.ainvoke(state)
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                ResponseCode.LLM_ERROR, str(e) or ResponseCode.LLM_ERROR.info, cause=e
            ) from e

        messages = result.get("messages", [])
        reply = _last_ai_text(messages)
        new_ctx = SessionContext(
            summary=ctx.summary, messages=messages, source_message_count=ctx.source_message_count
        )
        await self._session_repo.save(session_id, new_ctx)
        # 回答完成后：持久化超 compact_trigger 则异步压缩（为下一轮预压缩）
        self._maybe_compact_async(session_id, new_ctx, HumanMessage(content=req.message))
        return ChatResponse(
            session_id=session_id, user_id=req.user_id, reply=reply, intent=result.get("intent")
        )

    async def chat_stream(self, req: ChatRequest) -> AsyncIterator[str]:
        try:
            session_id, state, ctx = await self._prepare(req)
        except AppException as ex:
            yield _sse({"error": ex.info or ex.code})
            return

        final_state = None
        try:
            async for ev in self._graph.astream_events(state, version="v2"):
                etype = ev.get("event")
                if etype == "on_chat_model_stream":
                    chunk = ev.get("data", {}).get("chunk")
                    text = chunk.content if chunk is not None and isinstance(chunk.content, str) else ""
                    if text:
                        yield _sse({"token": text})
                elif etype == "on_tool_start":
                    yield _sse({"tool": ev.get("name"), "args": ev.get("data", {}).get("input", {})})
                elif etype == "on_chain_end" and ev.get("name") == "LangGraph":
                    out = ev.get("data", {}).get("output")
                    if isinstance(out, dict) and "messages" in out:
                        final_state = out
        except AppException as ex:
            yield _sse({"error": ex.info or ex.code})
            return
        except Exception as ex:
            yield _sse({"error": str(ex) or ResponseCode.LLM_ERROR.info})
            return

        if final_state:
            try:
                new_ctx = SessionContext(
                    summary=ctx.summary,
                    messages=final_state.get("messages", []),
                    source_message_count=ctx.source_message_count,
                )
                await self._session_repo.save(session_id, new_ctx)
                self._maybe_compact_async(session_id, new_ctx, HumanMessage(content=req.message))
            except Exception:
                pass

        yield "data: [DONE]\n\n"

    def _maybe_compact_async(self, session_id: str, ctx: SessionContext, current: BaseMessage) -> None:
        """回答完成后：持久化超 compact_trigger 则异步压缩（为下一轮预压缩），不阻塞当前响应。"""
        if self._summary_enabled and self._budget.should_compact_post(ctx):
            asyncio.create_task(self._compact_and_save(session_id, ctx, current))

    async def _compact_and_save(self, session_id: str, ctx: SessionContext, current: BaseMessage) -> None:
        try:
            compacted = await self._budget.compact(ctx, current)
            await self._session_repo.save(session_id, compacted)
        except Exception:
            pass  # 后台压缩失败不影响主流程
