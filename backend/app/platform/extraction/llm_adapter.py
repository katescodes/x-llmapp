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
        **kwargs: 其他参数
        
    Returns:
        LLM 返回的文本内容
        
    Raises:
        RuntimeError: 如果找不到兼容的 LLM 方法
    """
    if not llm_orchestrator:
        logger.error("[call_llm] LLM orchestrator is None!")
        raise RuntimeError("LLM orchestrator not available")
    
    logger.info(f"[call_llm] Attempting to call LLM: orchestrator_type={type(llm_orchestrator).__name__} model_id={model_id}")
    
    # 尝试常见的方法名
    for method_name in ("chat", "complete", "generate", "run", "ask"):
        fn = getattr(llm_orchestrator, method_name, None)
        if not fn:
            continue
        
        logger.info(f"[call_llm] Trying method: {method_name}")
        
        try:
            # 尝试 (messages, model_id, temperature) 签名
            res = fn(messages=messages, model_id=model_id, temperature=temperature, **kwargs)
            
            logger.info(f"[call_llm] Method {method_name} returned: type={type(res).__name__} len={len(str(res)) if res else 0}")
            
            # 处理返回值
            if isinstance(res, str):
                logger.info(f"[call_llm] Returning string of length {len(res)}")
                return res
            if isinstance(res, dict):
                # 尝试常见的键
                for k in ("content", "text", "output"):
                    if k in res and isinstance(res[k], str):
                        logger.info(f"[call_llm] Found key '{k}' with length {len(res[k])}")
                        return res[k]
                # OpenAI-like 格式
                if "choices" in res and res["choices"]:
                    ch = res["choices"][0]
                    if isinstance(ch, dict):
                        msg = ch.get("message")
                        if msg and isinstance(msg, dict):
                            cnt = msg.get("content")
                            if isinstance(cnt, str):
                                logger.info(f"[call_llm] Found OpenAI format content with length {len(cnt)}")
                                return cnt
            
            logger.warning(f"[call_llm] LLM returned unexpected format: {type(res)} keys={list(res.keys()) if isinstance(res, dict) else 'N/A'}")
            raise ValueError(f"LLM returned unexpected format: {type(res)}")
            
        except Exception as e:
            logger.warning(f"[call_llm] LLM method {method_name} failed: {e}")
            continue
    
    logger.error(f"[call_llm] No compatible LLM method found! Available methods: {[m for m in dir(llm_orchestrator) if not m.startswith('_')]}")
    raise RuntimeError(f"No compatible LLM method found in orchestrator")

