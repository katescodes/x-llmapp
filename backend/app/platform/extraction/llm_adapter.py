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
        raise RuntimeError("LLM orchestrator not available")
    
    # 尝试常见的方法名
    for method_name in ("chat", "complete", "generate", "run", "ask"):
        fn = getattr(llm_orchestrator, method_name, None)
        if not fn:
            continue
        
        try:
            # 尝试 (messages, model_id, temperature) 签名
            res = fn(messages=messages, model_id=model_id, temperature=temperature, **kwargs)
            
            # 处理返回值
            if isinstance(res, str):
                return res
            if isinstance(res, dict):
                # 尝试常见的键
                for k in ("content", "text", "output"):
                    if k in res and isinstance(res[k], str):
                        return res[k]
                # OpenAI-like 格式
                if "choices" in res and res["choices"]:
                    ch = res["choices"][0]
                    if isinstance(ch, dict):
                        msg = ch.get("message")
                        if msg and isinstance(msg, dict):
                            cnt = msg.get("content")
                            if isinstance(cnt, str):
                                return cnt
            
            raise ValueError(f"LLM returned unexpected format: {type(res)}")
            
        except Exception as e:
            logger.debug(f"LLM method {method_name} failed: {e}")
            continue
    
    raise RuntimeError(f"No compatible LLM method found in orchestrator")

