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
        # 开发环境：如果 MOCK_LLM=true，返回模拟数据
        # 安全检查：MOCK_LLM 只在 DEBUG=true 时允许生效
        import os
        mock_llm_enabled = os.getenv("MOCK_LLM", "false").lower() in ("true", "1", "yes")
        debug_enabled = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
        
        if mock_llm_enabled:
            if not debug_enabled:
                logger.warning("[SimpleLLMOrchestrator] MOCK_LLM=true but DEBUG=false, MOCK ignored for safety")
                mock_llm_enabled = False
            else:
                logger.info("[SimpleLLMOrchestrator] MOCK_LLM enabled, returning mock response")
        
        if mock_llm_enabled:
            # 返回一个符合 prompt 要求的四板块 JSON
            mock_response = {
                "data": {
                    "base": {
                        "projectName": "测试项目",
                        "ownerName": "测试招标人",
                        "agencyName": "测试代理机构",
                        "bidDeadline": "2024-12-31",
                        "bidOpeningTime": "2024-12-31 10:00",
                        "budget": "100万元",
                        "maxPrice": "",
                        "bidBond": "2万元",
                        "schedule": "60个工作日",
                        "quality": "合格",
                        "location": "测试地点",
                        "contact": "张三 13800138000"
                    },
                    "technical_parameters": [
                        {
                            "category": "技术参数",
                            "item": "测试项",
                            "requirement": "测试要求",
                            "parameters": [],
                            "evidence_chunk_ids": ["CHUNK_001"]
                        }
                    ],
                    "business_terms": [
                        {
                            "term": "付款方式",
                            "requirement": "合同签订后支付30%",
                            "evidence_chunk_ids": ["CHUNK_002"]
                        }
                    ],
                    "scoring_criteria": {
                        "evaluationMethod": "综合评分法",
                        "items": [
                            {
                                "category": "价格",
                                "item": "投标报价",
                                "score": "30",
                                "rule": "最低价得满分",
                                "evidence_chunk_ids": ["CHUNK_003"]
                            }
                        ]
                    }
                },
                "evidence_chunk_ids": ["CHUNK_001", "CHUNK_002", "CHUNK_003"]
            }
            import json
            return {"choices": [{"message": {"content": json.dumps(mock_response, ensure_ascii=False)}}]}
        
        try:
            # 获取模型配置
            if model_id:
                from app.services.llm_client import get_llm_model_by_id
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
                # 应用覆盖参数（设置合理的默认值）
                if kwargs:
                    if "temperature" in kwargs:
                        payload["temperature"] = kwargs["temperature"]
                    if "max_tokens" in kwargs:
                        payload["max_tokens"] = kwargs["max_tokens"]
                    else:
                        # 默认 4096 以支持长输出
                        payload["max_tokens"] = 4096
                    if "top_p" in kwargs:
                        payload["top_p"] = kwargs["top_p"]
                else:
                    # 没有 kwargs 时也设置默认值
                    payload["max_tokens"] = 4096
            
            # 准备请求头
            headers = {"Content-Type": "application/json"}
            if model.api_key:
                headers["Authorization"] = f"Bearer {model.api_key}"
            
            # 发送同步请求（增加超时时间到300秒，用于处理大文本）
            # 注意：verify=False 用于跳过SSL证书验证（自签名证书）
            logger.info(f"[SimpleLLMOrchestrator] Calling REAL LLM: endpoint={endpoint} model={model.model}")
            with httpx.Client(timeout=300.0, verify=False) as client:
                response = client.post(endpoint, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
            logger.info(f"[SimpleLLMOrchestrator] REAL LLM returned: status={response.status_code} content_length={len(response.text)}")
            
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
