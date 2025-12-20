from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import (
    health,
    chat,
    llm,
    export,
    template_analysis,
    llm_config,
    app_settings,
    history,
    kb,
    kb_category,
    embedding_providers,
    auth,
    asr_ws,
    recordings,
    asr_configs,
    attachments,
    tender,
    tender_snippets,
    debug,
)
from .services.db.postgres import init_db
from .services.llm_client import get_default_llm_model
import httpx
import json
import logging

logger = logging.getLogger(__name__)

init_db()
app = FastAPI(title="亿林亿问 Backend", version="0.2.0")


# LLM Orchestrator 包装器 - 用于 TenderService
class SimpleLLMOrchestrator:
    """简单的 LLM orchestrator 包装器，兼容 TenderService 的 duck typing 接口"""
    
    def chat(self, messages: list, model_id: str = None, **kwargs) -> dict:
        """调用 LLM 生成回答（同步版本）"""
        try:
            # 获取模型配置
            if model_id:
                from .services.llm_client import get_llm_model_by_id
                model = get_llm_model_by_id(model_id)
            else:
                model = get_default_llm_model()
            
            if not model:
                logger.error("No LLM model available")
                return {"choices": [{"message": {"content": "Error: No LLM model configured"}}]}
            
            # 构建请求 URL
            base_url = model.base_url.rstrip("/")
            endpoint_path = model.endpoint_path or "/v1/chat/completions"
            
            # 判断请求类型
            if "ollama" in base_url.lower():
                # Ollama 格式
                endpoint = f"{base_url}/api/chat"
                payload = {
                    "model": model.model,
                    "messages": messages,
                    "stream": False,
                }
                # 应用覆盖参数
                if kwargs:
                    options = {}
                    if "temperature" in kwargs:
                        options["temperature"] = kwargs["temperature"]
                    if "max_tokens" in kwargs:
                        options["num_predict"] = kwargs["max_tokens"]
                    if options:
                        payload["options"] = options
            else:
                # OpenAI 兼容格式
                endpoint = f"{base_url}{endpoint_path}"
                payload = {
                    "model": model.model,
                    "messages": messages,
                    "stream": False,
                }
                # 应用覆盖参数
                if kwargs:
                    if "temperature" in kwargs:
                        payload["temperature"] = kwargs["temperature"]
                    if "max_tokens" in kwargs:
                        payload["max_tokens"] = kwargs["max_tokens"]
                    if "top_p" in kwargs:
                        payload["top_p"] = kwargs["top_p"]
            
            # 准备请求头
            headers = {"Content-Type": "application/json"}
            if model.api_key:
                headers["Authorization"] = f"Bearer {model.api_key}"
            
            # 发送同步请求（增加超时时间到300秒，用于处理大文本）
            with httpx.Client(timeout=300.0) as client:
                response = client.post(endpoint, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
            
            # 返回统一格式
            if "choices" in result:
                return result
            elif "message" in result:  # Ollama 格式
                return {
                    "choices": [{
                        "message": {
                            "content": result["message"].get("content", "")
                        }
                    }]
                }
            else:
                logger.warning(f"Unexpected LLM response format: {result}")
                return {"choices": [{"message": {"content": str(result)}}]}
                
        except Exception as e:
            logger.error(f"LLM call failed: {e}", exc_info=True)
            # 抛出异常而不是返回错误消息，让上层捕获
            raise RuntimeError(f"LLM call failed: {str(e)}") from e
    
    # 为兼容性提供别名
    complete = chat
    generate = chat
    run = chat


# 初始化并注入到 app.state
app.state.llm_orchestrator = SimpleLLMOrchestrator()

# CORS：开发阶段先放开，生产可按域名收紧
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Force mode middleware (dev-only)
from .middleware.force_mode import ForceModeMiddleware
app.add_middleware(ForceModeMiddleware)

app.include_router(health.router)
app.include_router(debug.router)
app.include_router(auth.router)
app.include_router(asr_ws.router)
app.include_router(asr_configs.router)
app.include_router(recordings.router)
app.include_router(attachments.router)
app.include_router(chat.router)
app.include_router(llm.router)
app.include_router(llm_config.router)
app.include_router(app_settings.router)
app.include_router(embedding_providers.router)
app.include_router(history.router)
app.include_router(kb.router)
app.include_router(kb_category.router)
app.include_router(tender.router)
app.include_router(tender_snippets.router)
app.include_router(export.router)
app.include_router(template_analysis.router)


@app.get("/")
async def root():
    return {"message": "亿林亿问 Backend is running"}
