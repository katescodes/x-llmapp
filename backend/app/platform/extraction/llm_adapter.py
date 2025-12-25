"""
LLM Adapter
LLM 调用适配器，支持 duck-typing
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def call_llm(
    messages: List[Dict[str, str]],
    llm_orchestrator: Any,
    model_id: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
    **kwargs
) -> str:
    """
    调用 LLM（duck-typing 适配器）
    
    尝试调用常见的 LLM 方法名：chat, complete, generate, run, ask
    
    Args:
        messages: 消息列表，格式为 [{"role": "...", "content": "..."}, ...]
        llm_orchestrator: LLM 编排器对象
        model_id: 模型 ID
        temperature: 温度参数
        max_tokens: 最大 token 数（如果未提供，默认 4096）
        **kwargs: 其他参数
        
    Returns:
        LLM 返回的文本内容
        
    Raises:
        RuntimeError: 如果找不到兼容的 LLM 方法或调用失败
    """
    import time
    import traceback
    
    # 如果没有orchestrator但有model_id，尝试直接调用LLM
    if not llm_orchestrator:
        if model_id:
            logger.info(f"[call_llm] No orchestrator, using direct LLM client with model_id={model_id}")
            from app.services.llm_client import llm_chat
            # 转换messages格式并调用
            result = llm_chat(messages, model_id=model_id, temperature=temperature, max_tokens=max_tokens or 4096)
            return result
        else:
            logger.error("[call_llm] LLM orchestrator is None and no model_id provided!")
            raise RuntimeError("LLM orchestrator not available")
    
    # 单点兜底：确保 max_tokens 有合理默认值
    if max_tokens is None:
        max_tokens = 4096
        logger.debug(f"[call_llm] max_tokens not provided, defaulting to {max_tokens}")
    
    logger.info(
        f"[call_llm] START orchestrator_type={type(llm_orchestrator).__name__} "
        f"model_id={model_id} temperature={temperature} max_tokens={max_tokens}"
    )
    
    start_time = time.time()
    
    # 尝试常见的方法名
    for method_name in ("chat", "complete", "generate", "run", "ask"):
        fn = getattr(llm_orchestrator, method_name, None)
        if not fn:
            continue
        
        logger.info(f"[call_llm] Trying method: {method_name}")
        
        try:
            # 尝试 (messages, model_id, temperature, max_tokens) 签名
            res = fn(
                messages=messages,
                model_id=model_id,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            logger.info(
                f"[call_llm] Method {method_name} returned: "
                f"type={type(res).__name__} latency_ms={latency_ms}"
            )
            
            # 处理返回值
            if isinstance(res, str):
                logger.info(f"[call_llm] SUCCESS: Returning string of length {len(res)}")
                return res
            
            if isinstance(res, dict):
                # 尝试常见的键
                for k in ("content", "text", "output"):
                    if k in res and isinstance(res[k], str):
                        logger.info(f"[call_llm] SUCCESS: Found key '{k}' with length {len(res[k])}")
                        return res[k]
                
                # OpenAI-like 格式
                if "choices" in res and res["choices"]:
                    ch = res["choices"][0]
                    if isinstance(ch, dict):
                        msg = ch.get("message")
                        if msg and isinstance(msg, dict):
                            cnt = msg.get("content")
                            if isinstance(cnt, str):
                                logger.info(f"[call_llm] SUCCESS: Found OpenAI format content with length {len(cnt)}")
                                return cnt
            
            error_msg = f"LLM returned unexpected format: type={type(res)} keys={list(res.keys()) if isinstance(res, dict) else 'N/A'}"
            logger.warning(f"[call_llm] {error_msg}")
            
            # 记录详细错误信息
            logger.error(
                f"[call_llm] FAILED: Unexpected response format\n"
                f"  orchestrator_type={type(llm_orchestrator).__name__}\n"
                f"  method={method_name}\n"
                f"  model_id={model_id}\n"
                f"  response_type={type(res).__name__}\n"
                f"  response_preview={str(res)[:500]}"
            )
            
            raise ValueError(error_msg)
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            error_type = type(e).__name__
            error_msg = str(e)
            stack_trace = traceback.format_exc()
            
            logger.warning(
                f"[call_llm] Method {method_name} failed: {error_type}: {error_msg}"
            )
            
            # 如果是最后一个方法，记录完整错误信息
            if method_name == "ask":
                logger.error(
                    f"[call_llm] FAILED: All methods exhausted\n"
                    f"  orchestrator_type={type(llm_orchestrator).__name__}\n"
                    f"  model_id={model_id}\n"
                    f"  temperature={temperature}\n"
                    f"  max_tokens={max_tokens}\n"
                    f"  latency_ms={latency_ms}\n"
                    f"  last_error={error_type}: {error_msg}\n"
                    f"  stack_trace:\n{stack_trace}"
                )
            
            continue
    
    # 所有方法都失败了
    available_methods = [m for m in dir(llm_orchestrator) if not m.startswith('_')]
    error_msg = (
        f"No compatible LLM method found in orchestrator. "
        f"Available methods: {available_methods}"
    )
    
    logger.error(
        f"[call_llm] FATAL: {error_msg}\n"
        f"  orchestrator_type={type(llm_orchestrator).__name__}\n"
        f"  model_id={model_id}\n"
        f"  temperature={temperature}\n"
        f"  max_tokens={max_tokens}"
    )
    
    raise RuntimeError(error_msg)

