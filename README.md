# AiAssistant 智能客服助手

> 基于 **DeepSeek + LangChain + LangGraph** 的拼团营销平台智能客服，采用 DDD 分层架构（参考 Java 项目 `group-buy-market`）。
>
> 通过自然语言回答用户在拼团进度、成团状态、余额使用、活动规则等方面的问题；具备工具调用、多轮对话、流式输出能力（分阶段实现）。

---

## 当前状态

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| 阶段 0 | 项目骨架 + DDD 分层 + 配置 + 通用层 + 接口契约 | ✅ 已完成 |
| 阶段 1 | DeepSeek LLM 接入（domain + infrastructure） | ✅ 已完成 |
| 阶段 2 | LangGraph 工作流 + Redis 多轮会话 | ✅ 已完成 |
| 阶段 3 | MCP 工具（拼团/成团/余额查询） | ✅ 已完成 |
| 阶段 4 | SSE 流式 HTTP 接口 | ⬜ 待实现 |
| 阶段 5 | RAG 预留 + 部署文档 | ⬜ 待实现 |
>
> 📌 **阶段 3 状态**：工具调用链路已通（LLM 自主调工具 -> tool_node 执行 -> 综合），T-1/T-2 已接真实 group-buy-market 网关；T-3 余额无对应接口、降级提示；MCP Server 对外暴露（3.5）未做。

> ⚠️ **当前能力边界**：到阶段 2 为止只到**服务层**——能通过 `AssistantService` 完成**多轮** LLM 对话（Redis 记上下文，按 `session_id` 隔离），**尚未提供 HTTP 接口**（`/chat`、`/health` 等在阶段 4 / 后续补齐）。验证方式为直接调用服务层测试，无需启动 Web 服务。

---

## 技术栈

| 维度 | 选型 |
| --- | --- |
| 语言 | Python ≥ 3.12 |
| LLM | DeepSeek `deepseek-chat`（OpenAI 兼容接口） |
| LLM 编排 | LangChain / LangChain-OpenAI |
| 工作流 | LangGraph（阶段 2 起） |
| Web 框架 | FastAPI + Uvicorn（阶段 4 起） |
| 会话存储 | Redis（阶段 2 起） |
| 配置 | Pydantic Settings + `.env` |
| 架构 | DDD 分层（app / api / trigger / domain / infrastructure / common） |

---

## 目录结构

```
AiAssistant/
├── app/                            # 应用启动层
│   ├── config/settings.py          # ✅ Pydantic Settings（读 .env）
│   └── dependency.py               # ✅ 依赖注入装配（LLM 端口 + 仓储 + Graph + 服务）
├── api/                            # 接口契约层
│   ├── response.py                 # ✅ 统一 Response<T>
│   └── dto/chat.py                 # ✅ ChatRequest / ChatResponse / ChatMessageDTO
├── common/                         # 通用类型层（对应 Java types 模块）
│   ├── enums.py                    # ✅ ResponseCode
│   ├── exception.py                # ✅ AppException
│   ├── trace.py                    # ✅ TraceId 上下文（ContextVar）
│   └── event.py                    # ⬜ 事件层预留
├── domain/                         # 领域层
│   ├── assistant/
│       ├── adapter/
│       │   ├── port/illm_port.py                 # ✅ LLM 端口接口
│       │   └── repository/isession_repository.py # ✅ 会话仓储接口（阶段 2）
│       └── service/
│           ├── assistant_service.py              # ✅ IAssistantService 接口
│           ├── assistant_service_impl.py         # ✅ 多轮实现：load→graph→save（阶段 2）
│           └── graph/                            # ✅ LangGraph 工作流（阶段 2）
│               ├── state.py                      #   AssistantState
│               ├── assistant_graph.py            #   组装 intent/tool/response
│               └── nodes/{intent,tool,response}_node.py
│   └── mcp/                                      # ✅ MCP 工具领域（阶段 3）
│       ├── model/entity/groupbuy.py              #   值对象（拼团进度/成团/余额）
│       ├── adapter/repository/igroupbuy_repository.py  # 仓储接口
│       └── service/tools/                        #   3 个 @tool：拼团/成团/余额
├── infrastructure/                 # 基础设施层
│   ├── llm/deepseek_chat.py                      # ✅ ChatOpenAI(DeepSeek) 封装
│   ├── adapter/
│   │   ├── port/deepseek_llm_adapter.py          # ✅ ILLMPort 实现（chat / chat_stream）
│   │   └── repository/
│   │       ├── redis_session_repository.py       # ✅ 会话仓储 Redis 实现（阶段 2）
│   │       └── groupbuy_repository_impl.py       # ✅ 拼团仓储（真实 gateway，阶段 3）
│   ├── gateway/groupbuy_gateway.py               # ✅ group-buy-market HTTP 网关（阶段 3）
│   └── redis/redis_client.py                     # ✅ async Redis 客户端，按 loop 缓存（阶段 2）
├── trigger/                        # 触发器层（HTTP controller，阶段 4）
├── tests/test_llm.py               # ✅ 阶段 1 验证
├── tests/test_session.py           # ✅ 阶段 2 多轮验证
├── tests/test_tools.py             # ✅ 阶段 3 工具调用验证
├── tests/test_groupbuy_mapping.py  # ✅ 阶段 3 字段映射验证（mock）
├── conftest.py                     # ✅ pytest 根级 sys.path 配置
├── requirements.txt
├── pyproject.toml
└── .env.example                    # 环境变量模板（见下；注意被 .gitignore 忽略）
```

---

## 快速开始

### 1. 环境准备

```bash
# 要求 Python >= 3.12
python -m venv .venv

# 激活虚拟环境
# Windows (Git Bash):
source .venv/Scripts/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 `.env`

在项目根目录创建 `.env`（**该文件含密钥，已被 `.gitignore` 忽略，不会入库**），填入：

```ini
# ===================== DeepSeek =====================
DEEPSEEK_API_KEY=sk-你的真实key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# ===================== Redis（多轮会话存储，阶段 2 起）=====================
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# ===================== 业务数据网关（group-buy-market）=====================
GROUPBUY_API_BASE=http://localhost:8091

# ===================== 应用 =====================
APP_HOST=0.0.0.0
APP_PORT=8088
APP_DEBUG=true

# ===================== 会话 =====================
SESSION_MAX_TURNS=20
SESSION_TTL_SECONDS=86400

# ===================== RAG（预留，本期不启用）=====================
RAG_ENABLED=false
```

### 3. 运行阶段 1 验证

```bash
.venv/Scripts/python.exe tests/test_llm.py
```

预期输出：DeepSeek 返回中文客服回复，末尾打印 `阶段 1 验证通过 ✓`。

该脚本也可用 pytest 运行（安装 `pytest` 后）：

```bash
.venv/Scripts/python.exe -m pytest tests/test_llm.py -s
```

---

## 架构与依赖方向

```
trigger ──▶ api
   │
   ▼
domain ◀── infrastructure（实现 domain 的 port/repository 接口）
   │
   ▼
common（被所有层依赖）
```

- `domain` 不依赖 `infrastructure`，只定义 `port` 接口；
- `infrastructure` 实现 `domain` 接口；
- `app/dependency.py` 负责把 `infrastructure` 实现注入 `domain`；
- 严格遵守「依赖倒置」，便于替换 DeepSeek → 其他 LLM、Redis → 其他存储。

### 阶段 1 数据流

```
调用方
  └─ app.dependency.get_assistant_service()        # 装配
       └─ AssistantServiceImpl                       # domain：单轮服务
            └─ ILLMPort.chat(messages)               # domain：端口（接口）
                 └─ DeepSeekLLMAdapter                # infrastructure：实现
                      └─ ChatOpenAI.ainvoke           # infrastructure：LangChain 封装
                           └─ DeepSeek HTTP API
```

---

## 阶段 1 实现要点

| 文件 | 作用 |
| --- | --- |
| `domain/assistant/adapter/port/illm_port.py` | `ILLMPort` 抽象端口：`chat()` 非流式 + `chat_stream()` 流式 |
| `infrastructure/llm/deepseek_chat.py` | 用 `ChatOpenAI(model=deepseek-chat, base_url, api_key)` 封装 DeepSeek |
| `infrastructure/adapter/port/deepseek_llm_adapter.py` | `ILLMPort` 实现，内部持有 `ChatOpenAI`，异常归一为 `AppException` |
| `domain/assistant/service/assistant_service.py` | `IAssistantService` 接口 |
| `domain/assistant/service/assistant_service_impl.py` | `AssistantServiceImpl`：组装消息 → 调端口 → 返回 `ChatResponse` |
| `app/config/settings.py` | Pydantic Settings 自动读取 `.env` |
| `app/dependency.py` | 工厂函数 + `lru_cache` 单例装配 |
| `common/` | `ResponseCode` / `AppException` / `TraceId`（对齐 Java `types` 模块） |
| `api/` | `Response[T]` 与对话 DTO |

---

## 命名说明：`types/` → `common/`

PRD 中 DDD 的「通用类型层」写作顶层 `types/` 包，但 Python 标准库已占用 `types` 模块名（解释器启动即缓存，且 `enum` 依赖它），导致 `from types.enums import ...` 报 `'types' is not a package`。因此将该层重命名为 `common/`，子模块结构与 PRD 一致，其余分层包名不变。详见 `common/__init__.py` 顶部说明。

---

## 路线图

- **阶段 2**：LangGraph State + 意图/工具/回答三节点 + Redis 会话仓储（多轮上下文）
- **阶段 3**：MCP 工具（拼团进度 / 成团进度 / 余额使用）+ group-buy-market 网关
- **阶段 4**：FastAPI SSE 流式 `/chat` 接口 + 异常降级
- **阶段 5**：RAG 接口预留 + Docker 部署 + 联调文档

---

## 相关文档

- `PRD.md`：产品需求文档（本地，未入库）
- `IMPLEMENTATION.md`：分阶段实现步骤（本地，未入库）
