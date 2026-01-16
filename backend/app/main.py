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
    declare,
    permissions,
    custom_rules,
    user_documents,
    organizations,  # 新增企业管理路由
)
from .services.db.postgres import init_db, _get_pool
from .services.llm_client import get_default_llm_model
import httpx
import json
import logging
import asyncio

logger = logging.getLogger(__name__)

init_db()
app = FastAPI(title="亿林亿问 Backend", version="0.2.0")


# ========== 应用生命周期管理 ==========

@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    logger.info("🚀 应用启动中...")
    
    # 启动任务监控器（自动清理卡死的任务）
    try:
        import os
        import psycopg
        from psycopg.rows import dict_row
        from app.services.task_monitor import TaskMonitor
        
        # 创建独立的数据库连接（不使用连接池）
        monitor_conn = psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "postgres"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            dbname=os.getenv("POSTGRES_DB", "localgpt"),
            user=os.getenv("POSTGRES_USER", "localgpt"),
            password=os.getenv("POSTGRES_PASSWORD", "localgpt"),
            row_factory=dict_row,
            autocommit=False
        )
        
        # 创建并启动监控器
        # 超时阈值：10分钟，检查间隔：60秒
        monitor = TaskMonitor(monitor_conn, timeout_minutes=20, check_interval_seconds=60)
        
        # 保存到app.state以便后续访问
        app.state.task_monitor = monitor
        app.state.task_monitor_conn = monitor_conn
        
        # 启动监控循环
        monitor.start()
        
        logger.info("✅ 任务监控器已启动（超时阈值：10分钟，检查间隔：60秒）")
    except Exception as e:
        logger.error(f"❌ 任务监控器启动失败: {e}", exc_info=True)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理"""
    logger.info("🛑 应用关闭中...")
    
    # 停止任务监控器
    if hasattr(app.state, "task_monitor"):
        try:
            await app.state.task_monitor.stop()
            logger.info("✅ 任务监控器已停止")
        except Exception as e:
            logger.error(f"❌ 任务监控器停止失败: {e}")
    
    # 关闭数据库连接
    if hasattr(app.state, "task_monitor_conn"):
        try:
            app.state.task_monitor_conn.close()
            logger.info("✅ 任务监控器数据库连接已关闭")
        except Exception as e:
            logger.error(f"❌ 任务监控器数据库连接关闭失败: {e}")


# LLM Orchestrator 包装器 - 用于 TenderService
class SimpleLLMOrchestrator:
    """
    简单的 LLM orchestrator 包装器，兼容 TenderService 的 duck typing 接口
    
    支持两种模式：
    1. MOCK 模式（MOCK_LLM=true + DEBUG=true）：返回模拟数据，不访问外部服务
    2. REAL 模式：调用真实 LLM（通过 llm_models 表配置）
    
    初始化策略（可降级）：
    - MOCK 模式：无需任何外部依赖，直接返回 mock 数据
    - REAL 模式：依赖 llm_models 表配置，如果配置缺失，在调用时抛出明确错误
    """
    
    def chat(self, messages: list, model_id: str = None, **kwargs) -> dict:
        """
        调用 LLM 生成回答（同步版本）
        
        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            model_id: 可选的模型 ID
            **kwargs: 其他参数（temperature, max_tokens, top_p 等）
        
        Returns:
            OpenAI 格式的响应: {"choices": [{"message": {"content": "..."}}]}
        
        Raises:
            RuntimeError: 当 LLM 调用失败时
        """
        # 检查 MOCK_LLM 模式
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
        
        # MOCK 模式：返回模拟数据（不访问任何外部服务，不查询 DB）
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
            return {"choices": [{"message": {"content": json.dumps(mock_response, ensure_ascii=False)}}]}
        
        # REAL 模式：调用真实 LLM
        try:
            # 获取模型配置（依赖 llm_models 表）
            if model_id:
                from app.services.llm_client import get_llm_model_by_id
                model = get_llm_model_by_id(model_id)
            else:
                model = get_default_llm_model()
            
            if not model:
                error_msg = (
                    "No LLM model configured. "
                    "Please ensure llm_models table has at least one active model. "
                    "Alternatively, set MOCK_LLM=true and DEBUG=true for testing."
                )
                logger.error(f"[SimpleLLMOrchestrator] {error_msg}")
                raise RuntimeError(error_msg)
            
            # 构建请求 URL
            base_url = model.base_url.rstrip("/")
            endpoint_path = model.endpoint_path or "/v1/chat/completions"
            
            # 单点兜底：确保 max_tokens 有合理默认值
            # 如果调用方没传 max_tokens，默认给 4096
            if "max_tokens" not in kwargs:
                kwargs["max_tokens"] = 4096
                logger.debug(f"[SimpleLLMOrchestrator] max_tokens not provided, defaulting to 4096")
            
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
            
            # 发送同步请求（增加超时时间到600秒，用于处理大文本和16K tokens输出）
            # 注意：verify=False 用于跳过SSL证书验证（自签名证书）
            actual_max_tokens = kwargs.get('max_tokens', 'default')
            
            # 详细的调用信息
            logger.info("=" * 80)
            logger.info("[LLM调用] 开始")
            logger.info(f"  端点: {endpoint}")
            logger.info(f"  模型: {model.model}")
            logger.info(f"  max_tokens: {payload.get('max_tokens', 'not set')}")
            logger.info(f"  temperature: {payload.get('temperature', 'not set')}")
            logger.info(f"  top_p: {payload.get('top_p', 'not set')}")
            logger.info(f"  消息数量: {len(messages)}")
            if messages:
                first_msg = messages[0]
                content_preview = first_msg.get('content', '')[:200]
                logger.info(f"  第一条消息预览: {content_preview}...")
            logger.info(f"  请求头: Authorization={'已设置' if model.api_key else '未设置'}")
            logger.info("=" * 80)
            
            with httpx.Client(timeout=600.0, verify=False) as client:
                response = client.post(endpoint, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
            
            logger.info("=" * 80)
            logger.info("[LLM响应] 完成")
            logger.info(f"  状态码: {response.status_code}")
            logger.info(f"  响应长度: {len(response.text)} 字符")
            logger.info("=" * 80)
            
            # 检查返回的 usage 和 finish_reason
            if "usage" in result:
                print(f"[DEBUG] LLM usage: {json.dumps(result['usage'], ensure_ascii=False)}")
            
            if "choices" in result and result["choices"]:
                first_choice = result["choices"][0]
                finish_reason = first_choice.get("finish_reason", "unknown")
                print(f"[DEBUG] LLM finish_reason: {finish_reason}")
                
                if finish_reason == "length":
                    print(f"[WARNING] LLM stopped due to LENGTH limit!")
                elif finish_reason == "stop":
                    print(f"[INFO] LLM stopped naturally (stop sequence)")
                    
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
                
        except httpx.ConnectTimeout as e:
            logger.error("=" * 80)
            logger.error("[LLM调用失败] 连接超时")
            logger.error(f"  错误: {e}")
            logger.error(f"  端点: {endpoint if 'endpoint' in locals() else 'unknown'}")
            logger.error("  可能原因:")
            logger.error("    1. LLM服务器不可达")
            logger.error("    2. 网络连接问题")
            logger.error("    3. 防火墙阻止连接")
            logger.error("=" * 80)
            raise RuntimeError(f"LLM 请求超时，无法连接到服务器") from e
        except httpx.HTTPStatusError as e:
            logger.error("=" * 80)
            logger.error("[LLM调用失败] HTTP错误")
            logger.error(f"  状态码: {e.response.status_code}")
            logger.error(f"  响应: {e.response.text[:500]}")
            logger.error("=" * 80)
            raise RuntimeError(f"LLM 请求失败: HTTP {e.response.status_code}") from e
        except Exception as e:
            logger.error("=" * 80)
            logger.error("[LLM调用失败] 未知错误")
            logger.error(f"  错误类型: {type(e).__name__}")
            logger.error(f"  错误信息: {str(e)}")
            logger.error("=" * 80)
            logger.error("详细堆栈:", exc_info=True)
            raise RuntimeError(f"LLM 请求失败，请检查模型服务") from e
    
    async def achat(self, messages: list, model_id: str = None, **kwargs) -> dict:
        """
        异步版本的 chat 方法
        
        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            model_id: 可选的模型 ID
            **kwargs: 其他参数（temperature, max_tokens, top_p, response_format 等）
        
        Returns:
            OpenAI 格式的响应: {"choices": [{"message": {"content": "..."}}]}
        
        Raises:
            RuntimeError: 当 LLM 调用失败时
        """
        import asyncio
        
        # 在线程池中运行同步的chat方法
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.chat(messages, model_id, **kwargs))
    
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
app.include_router(declare.router)
app.include_router(export.router)
app.include_router(template_analysis.router)

# Prompt管理
from app.routers import prompts
app.include_router(prompts.router)

# 权限管理
app.include_router(permissions.router)

# 自定义规则管理
app.include_router(custom_rules.router)

# 用户文档管理
app.include_router(user_documents.router)

# 企业管理
app.include_router(organizations.router)

# Legacy tender APIs 已删除
# if os.getenv("LEGACY_TENDER_APIS_ENABLED", "false").lower() in ("true", "1", "yes"):
#     ... (legacy APIs removed)


@app.get("/")
async def root():
    return {"message": "亿林亿问 Backend is running"}
