# LLM 集成架构体检报告

**生成时间**: 2025-12-17  
**分析范围**: /aidata/x-llmapp1 全仓库  
**分析方法**: ripgrep 关键词搜索 + 代码结构分析

---

## 执行摘要

### 架构判定

✅ **后端中转架构**（Frontend → Backend → LLM Model）

- **前端**: React + TypeScript (Vite)，通过 fetch 调用后端 API
- **后端**: Python FastAPI，作为中转层统一调用 LLM
- **部署**: Docker Compose，前端 6173 端口，后端 9001 端口

### API 形态

✅ **OpenAI 兼容 + Ollama 双协议支持**

- 主流使用 OpenAI 兼容格式：`/v1/chat/completions`
- 同时支持 Ollama 格式：`/api/chat`
- 动态识别：根据 `base_url` 中是否包含 "ollama" 自动切换

### 流式支持

✅ **SSE (Server-Sent Events) + 回退机制**

- 主流式方式：`text/event-stream` + ReadableStream
- 前端优先尝试流式，失败自动回退到普通请求
- 后端支持 `/api/chat` (非流式) 和 `/api/chat/stream` (流式SSE)

---

## 第1部分：关键词搜索结果

### 1.1 LLM API 端点搜索

**搜索词**: `chat/completions`, `/v1/chat`, `completions`

**命中位置**（核心）:

```
backend/app/main.py:55
    endpoint_path = model.endpoint_path or "/v1/chat/completions"

backend/app/services/llm_client.py:30
    endpoint_path: str = "/v1/chat/completions"

backend/app/config.py:57
    LOCAL_LLM_ENDPOINT_PATH: str = os.getenv("LOCAL_LLM_ENDPOINT_PATH", "/v1/chat/completions")

frontend/src/components/SystemSettings.tsx:179, 540, 667, 1955
    endpoint_path: "/v1/chat/completions"
```

### 1.2 OpenAI 相关搜索

**搜索词**: `openai`, `OpenAI` (忽略大小写)

**命中位置**（核心）:

```
backend/app/services/llm_client.py:334
    payload = _build_openai_payload(model, messages)

backend/app/services/llm_client.py:458
    if request_kind == "openai_chat":

backend/app/services/llm_client.py:634
    return "openai_chat"

backend/app/services/llm_client.py:649
    def _build_openai_payload(model: LLMModelStored, messages: List[dict]) -> dict:
```

### 1.3 消息格式搜索

**搜索词**: `messages.*role.*content`, `role.*content.*messages`

**命中位置**（核心）:

```
backend/app/services/llm_client.py:134
    messages = [{"role": "user", "content": prompt}]

backend/app/services/llm_client.py:642
    messages.append({"role": "system", "content": system_prompt})

backend/app/services/llm_client.py:644
    messages.append({"role": msg.role, "content": msg.content})
```

### 1.4 流式传输搜索

**搜索词**: `stream` (关键命中)

```
backend/app/services/llm_client.py:438
    async def stream_answer_with_model(

backend/app/services/llm_client.py:459
    payload["stream"] = True

backend/app/services/llm_client.py:460
    headers.setdefault("Accept", "text/event-stream")

backend/app/services/llm_client.py:473
    async with client.stream("POST", url, json=payload, headers=headers) as resp:
```

### 1.5 HTTP 客户端搜索

**搜索词**: `fetch(`, `axios`, `EventSource`, `ReadableStream`

**命中位置**:

```
frontend/src/components/ChatLayout.tsx:264
    const resp = await fetch(`${apiBaseUrl}/api/chat`, {

frontend/src/components/ChatLayout.tsx:278
    const resp = await fetch(`${apiBaseUrl}/api/chat/stream`, {

frontend/src/components/ChatLayout.tsx:288
    const reader = resp.body.getReader();
```

### 1.6 框架搜索

**搜索词**: `ollama`, `fastapi`, `express`

**命中位置**:

```
backend/requirements.txt:1
    fastapi==0.115.0

backend/app/main.py:1, 2
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

backend/app/main.py:58
    if "ollama" in base_url.lower():

backend/app/services/llm_client.py:220, 329-333
    if request_kind and request_kind.startswith("ollama"):
        # Ollama uses num_predict for token limit
    if request_kind == "ollama_chat":
        payload = _build_ollama_chat_payload(model, messages)
```

### 1.7 路由和服务搜索

**搜索词**: `/api/chat`, `controller`, `service`

**命中位置**（核心）:

```
backend/app/routers/chat.py:64
    router = APIRouter(prefix="/api", tags=["chat"])

backend/app/routers/chat.py:1017
    @router.post("/chat", response_model=ChatResponse)

backend/app/routers/chat.py:1023
    @router.post("/chat/stream")

backend/app/services/llm_client.py (service 层)
backend/app/services/llm_orchestrator.py
backend/app/services/prompt_templates.py
```

---

## 第2部分：当前调用链路图

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户浏览器                                │
│                    (localhost:6173)                              │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ HTTP fetch()
                            │ POST /api/chat (非流式)
                            │ POST /api/chat/stream (流式SSE)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              FastAPI Backend (Python)                            │
│                 (localhost:9001)                                 │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ backend/app/routers/chat.py                              │   │
│  │  - /api/chat → chat_endpoint()                          │   │
│  │  - /api/chat/stream → chat_stream_endpoint()           │   │
│  └──────────────────────────┬──────────────────────────────┘   │
│                             │                                    │
│                             ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ backend/app/services/llm_client.py                       │   │
│  │  - generate_answer_with_model() (非流式)                │   │
│  │  - stream_answer_with_model() (流式)                    │   │
│  │  - _build_openai_payload() / _build_ollama_*_payload() │   │
│  └──────────────────────────┬──────────────────────────────┘   │
│                             │                                    │
│                             │ httpx POST                         │
│                             │                                    │
└─────────────────────────────┼────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LLM Model API                               │
│                  (用户配置的 base_url)                            │
│                                                                   │
│  • OpenAI 兼容: {base_url}/v1/chat/completions                  │
│     - payload: {"model": "...", "messages": [...], "stream": ...}│
│     - Authorization: Bearer {api_key}                            │
│                                                                   │
│  • Ollama: {base_url}/api/chat                                  │
│     - payload: {"model": "...", "messages": [...], "options": ...}│
│     - 无 Authorization header (可选)                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 第3部分：API 详细规格

### 3.1 前端 → 后端

#### 请求端点

- **非流式**: `POST http://localhost:9001/api/chat`
- **流式**: `POST http://localhost:9001/api/chat/stream`

#### 请求体 (ChatRequest)

```json
{
  "message": "用户问题",
  "session_id": "uuid-string (可选)",
  "llm_key": "模型ID (可选)",
  "mode": "chat | decision | history_decision",
  "enable_web": false,
  "selected_kb_ids": ["kb1", "kb2"],
  "attachment_ids": ["att1", "att2"],
  "search_mode": "off | force"
}
```

#### 响应体 (ChatResponse) - 非流式

```json
{
  "answer": "LLM生成的答案",
  "sources": [...],
  "llm_key": "model-id",
  "llm_name": "Model Display Name",
  "session_id": "uuid-string",
  "search_mode": "off",
  "used_search": false,
  "search_queries": [],
  "used_model": {
    "id": "model-id",
    "name": "Model Name"
  }
}
```

#### 响应体 (SSE) - 流式

```
event: delta
data: {"text": "答案片段"}

event: delta
data: {"text": "下一个片段"}

event: result
data: {"answer": "完整答案", "sources": [...], ...}
```

### 3.2 后端 → LLM Model

#### OpenAI 兼容格式

**Endpoint**: `{base_url}/v1/chat/completions`

**请求头**:
```http
Content-Type: application/json
Authorization: Bearer {api_key}
Accept: text/event-stream (流式时)
```

**请求体**:
```json
{
  "model": "gpt-4o-mini",
  "messages": [
    {"role": "system", "content": "系统提示词"},
    {"role": "user", "content": "用户消息"},
    {"role": "assistant", "content": "助手回复"},
    {"role": "user", "content": "新用户消息"}
  ],
  "stream": false,
  "temperature": 0.7,
  "max_tokens": 4096,
  "top_p": 0.9
}
```

**响应体** (非流式):
```json
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "生成的答案"
      }
    }
  ]
}
```

**响应体** (流式):
```
data: {"choices": [{"delta": {"content": "片段"}}]}

data: [DONE]
```

#### Ollama 格式

**Endpoint**: `{base_url}/api/chat`

**请求头**:
```http
Content-Type: application/json
```

**请求体**:
```json
{
  "model": "llama3.1",
  "messages": [
    {"role": "user", "content": "用户消息"}
  ],
  "stream": false,
  "options": {
    "temperature": 0.7,
    "num_predict": 4096
  }
}
```

**响应体**:
```json
{
  "message": {
    "role": "assistant",
    "content": "生成的答案"
  }
}
```

---

## 第4部分：System Prompt 与历史消息处理

### 4.1 已有 System Prompt 概念

✅ **是**，系统已有完善的 system prompt 管理

**位置**: `backend/app/services/prompt_templates.py`

**现有 Prompts**:

1. **BASE_SYSTEM_PROMPT**: 通用 AI 助手提示词
   ```python
   你是一个严谨的中文 AI 助手。
   要求：
   - 回答时尽量使用清晰的小标题和有编号的列表结构（1. 2. 3.），避免使用无序列表 - 或 •。
   - 如果不确定，请明确说明"不确定"或指出需要补充的信息。
   ```

2. **DECISION_SYSTEM_PROMPT**: 决策分析专用提示词
   - 结构化输出：决策结论、背景目标、方案对比、风险提示、参考依据

3. **HISTORY_DECISION_SYSTEM_PROMPT**: 历史案例决策提示词
   - 导师角色定位
   - 问题分析、经验总结、行动方案、风险预警、学习建议

### 4.2 历史消息拼接方式

**核心逻辑**: `backend/app/routers/chat.py:381-432`

**策略**:

1. **智能摘要触发**:
   - 当消息数超过 20 条且无摘要时，自动生成历史摘要
   - 使用 `summarize_history()` 压缩早期对话

2. **上下文构建**:
   - **有摘要时**: `[摘要消息] + [最近10轮对话]`
   - **无摘要时**: `[最近10轮对话]`

3. **Token 限制**:
   - 最大上下文: 128,000 tokens
   - 超限时自动裁剪，从最新消息开始保留

4. **消息格式**:
   ```python
   messages = [
       {"role": "system", "content": system_prompt},
       {"role": "user", "content": "历史消息1"},
       {"role": "assistant", "content": "历史回复1"},
       ...
       {"role": "user", "content": "当前问题"}
   ]
   ```

### 4.3 Prompt 注入点

**位置**: `backend/app/services/llm_client.py:641-645`

```python
def _build_conversation_messages(
    system_prompt: str, history: List[Message], user_message: str
) -> List[dict]:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})
    return messages
```

---

## 第5部分：鉴权方式

### 5.1 后端 API 鉴权

**当前状态**: ✅ 已实现 JWT Token 鉴权

**路由**: `backend/app/routers/auth.py`

**机制**:
- 用户登录后获得 JWT token
- 前端在请求头中携带 `Authorization: Bearer {token}`
- 后端通过 `Depends` 依赖注入验证 token

### 5.2 LLM API 鉴权

**当前状态**: ✅ 支持 Bearer Token

**配置位置**: 
- 数据库: `data/llm_models.json`
- 字段: `api_key` (可选)

**注入逻辑**: `backend/app/services/llm_client.py:94-95`

```python
headers = {"Content-Type": "application/json"}
if model.api_key:
    headers["Authorization"] = f"Bearer {model.api_key}"
```

---

## 第6部分：现有 LLM 编排能力评估

### 6.1 已有能力 ✅

1. **多模型管理**:
   - 支持多个 LLM 配置（OpenAI、Ollama、自定义）
   - 可设置默认模型
   - 可按需切换模型

2. **历史对话管理**:
   - 会话持久化（PostgreSQL）
   - 智能摘要（超过20轮自动触发）
   - 上下文裁剪（防止超过 token 限制）

3. **流式输出**:
   - SSE 流式传输
   - 前端实时渲染
   - 自动回退到非流式

4. **RAG 集成**:
   - 知识库检索（Milvus Lite）
   - 网络搜索（Google CSE）
   - 附件上下文注入

5. **多模式支持**:
   - `chat`: 通用对话
   - `decision`: 决策分析
   - `history_decision`: 历史案例决策

6. **System Prompt 管理**:
   - 预定义 prompt 模板
   - 可按模式动态选择

### 6.2 缺失能力 ❌（本次改造目标）

1. **❌ 需求理解（需求抽取）**:
   - 当前仅有简单的 `intent_parser`（识别是否需要联网）
   - 缺乏对用户意图、约束、偏好的结构化提取

2. **❌ 模块化蓝图（Blueprint）**:
   - 当前回答是单一文本流
   - 没有按"对齐摘要、核心答案、时间线、例子、风险、下一步"等模块组织

3. **❌ 详尽度控制（Detail Level）**:
   - 没有 `brief/normal/detailed` 开关
   - 用户无法控制回答的详细程度

4. **❌ 少追问（智能假设 + 分支覆盖）**:
   - 当前遇到信息不足时，倾向于让用户补充
   - 缺乏"先合理假设给答案，再给可选澄清问题"的机制

5. **❌ 兜底修复（Repair Call）**:
   - 没有结构修复环节
   - 如果 LLM 输出混乱，无法自动重排

6. **❌ 分段渲染（Structured Sections）**:
   - 前端只渲染单一 `answer` 字段
   - 没有可折叠的模块化 UI

---

## 第7部分：改造建议

### 7.1 落点判定

✅ **在现有后端增强**，无需新建 BFF

**理由**:
- 后端已是 FastAPI，性能优秀
- 已有完善的会话管理、RAG、流式输出基础
- 只需在 `/api/chat` 路由中增加两段式编排逻辑

### 7.2 架构改造方案

**改造点**: `backend/app/routers/chat.py` + 新增 `backend/app/services/orchestrator/`

**新流程**:

```
用户请求
   ↓
[现有] intent_parser (是否需要联网)
   ↓
[新增] Extractor Call (非流式)
   ↓ 输出: RequirementJSON (intent, detail_level, blueprint_modules, clarifications)
   ↓
[现有] RAG 检索 + 网络搜索
   ↓
[新增] Answer Call (流式)
   ↓ 按 blueprint_modules 生成结构化答案
   ↓
[新增] Repair Call (可选)
   ↓ 如果结构混乱，重排为 sections
   ↓
返回: { sections: [...], followups: [...] }
```

### 7.3 最小改动清单

1. **新增类型定义**:
   - `backend/app/schemas/orchestrator.py`
   - `RequirementJSON`, `ChatSection`, `OrchestratedResponse`

2. **新增 Prompt 模板**:
   - `backend/app/services/orchestrator/prompts.py`
   - `EXTRACTOR_PROMPT`, `MODULAR_SYSTEM_PROMPT`, `REPAIR_PROMPT`

3. **新增编排服务**:
   - `backend/app/services/orchestrator/orchestrator_service.py`
   - `extract_requirements()`, `generate_modular_answer()`, `repair_structure()`

4. **修改聊天路由**:
   - `backend/app/routers/chat.py`
   - 在 `_chat_endpoint_impl()` 中插入两段式调用

5. **前端 Schema 更新**:
   - `frontend/src/types/chat.ts`
   - 新增 `sections` 字段

6. **前端 UI 组件**:
   - `frontend/src/components/ModularAnswer.tsx`
   - 渲染可折叠的 sections

---

## 第8部分：风险评估

### 8.1 兼容性风险

⚠️ **低风险**

- 改造为可选特性（通过参数控制）
- 不破坏现有 `/api/chat` 接口
- 可通过 `enable_orchestrator: true` 开关启用

### 8.2 性能风险

⚠️ **中等风险**

- 两段式调用增加延迟（Extractor + Answer）
- 建议：
  - Extractor 使用低延迟模型（如 gpt-4o-mini）
  - Extractor 设置 `temperature=0`, `max_tokens=512`
  - 并行执行 Extractor 和 RAG 检索

### 8.3 成本风险

⚠️ **低风险**

- Extractor 调用成本低（512 tokens）
- Repair 仅在必要时触发
- 详尽度开关可控制 Answer 长度

---

## 第9部分：下一步行动

### 立即可执行

1. ✅ 本报告已完成
2. ⏭️ 定义 JSON 协议（第2步）
3. ⏭️ 新增 Prompt 模板（第3步）
4. ⏭️ 实现编排器（第1步）

### 需用户确认

- [ ] 是否启用两段式编排（有延迟成本）
- [ ] 详尽度默认值：`brief` / `normal` / `detailed`
- [ ] Extractor 使用哪个模型（建议 gpt-4o-mini 或 gemini-1.5-flash）

---

## 附录：关键文件清单

### 后端核心文件

```
backend/
├── app/
│   ├── main.py                          # FastAPI 入口，包含 SimpleLLMOrchestrator
│   ├── routers/
│   │   └── chat.py                      # /api/chat 和 /api/chat/stream 路由
│   ├── services/
│   │   ├── llm_client.py                # LLM 调用封装（OpenAI/Ollama）
│   │   ├── llm_orchestrator.py          # 已有编排器（摘要流水线）
│   │   ├── prompt_templates.py          # 现有 system prompts
│   │   ├── intent/
│   │   │   └── intent_parser.py         # 意图识别（是否联网）
│   │   └── llm_model_store.py           # 模型配置管理
│   └── schemas/
│       └── chat.py                      # ChatRequest、ChatResponse 定义
├── requirements.txt                     # fastapi==0.115.0, httpx, ...
└── Dockerfile
```

### 前端核心文件

```
frontend/
├── src/
│   ├── components/
│   │   ├── ChatLayout.tsx               # 聊天界面主组件
│   │   └── SystemSettings.tsx           # LLM 模型配置界面
│   └── config/
│       └── api.ts                       # API 基础配置
└── Dockerfile
```

### 配置文件

```
/aidata/x-llmapp1/
├── docker-compose.yml                   # 服务编排
├── data/
│   ├── llm_models.json                  # LLM 模型配置
│   └── app_settings.json                # 应用设置
└── .env (如果有)
```

---

## 元数据

- **仓库路径**: `/aidata/x-llmapp1`
- **后端技术栈**: Python 3.11+ / FastAPI 0.115.0 / httpx / Pydantic
- **前端技术栈**: TypeScript / React 18 / Vite
- **数据库**: PostgreSQL 15 (会话、消息、知识库)
- **向量库**: Milvus Lite (本地嵌入式)
- **搜索**: Google CSE (可选)

---

**报告完成**。可基于此进行第1-6步改造。

