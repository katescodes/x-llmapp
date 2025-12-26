"""
文本增强服务
用于对ASR转写结果进行后处理，添加标点符号和段落划分
"""
import logging
from typing import Optional, Dict, Any
from app.services.llm.llm_model_store import LLMModelStore

logger = logging.getLogger(__name__)


PUNCTUATION_PROMPT = """你是一个专业的文本编辑助手。你的任务是为语音转写的文本添加标点符号和段落划分，使其更易读。

要求：
1. **添加标点符号**：句号、逗号、问号、感叹号、冒号、分号、引号等
2. **段落划分**：根据语义和主题切换合理分段，每段不超过200字
3. **保持原意**：不要改变原文的意思，只添加标点和分段
4. **不要删减**：保留所有内容，包括口语化表达
5. **不要添加**：不要添加原文没有的内容

原始文本：
{original_text}

请输出优化后的文本（只输出文本本身，不要任何解释）：
"""


PUNCTUATION_PROMPT_FORMAL = """你是一个专业的文本编辑助手。你的任务是将语音转写的口语文本转换为正式的书面语。

要求：
1. **添加标点符号**：句号、逗号、问号、感叹号、冒号、分号、引号等
2. **段落划分**：根据语义和主题切换合理分段，每段不超过200字
3. **口语转书面语**：
   - 去除语气词（嗯、啊、呃、那个等）
   - 修正重复表达
   - 统一时态和人称
   - 修正语病
4. **保持原意**：不要改变核心意思
5. **适当精简**：可以合并重复内容，但不要删除关键信息

原始文本：
{original_text}

请输出优化后的文本（只输出文本本身，不要任何解释）：
"""


MEETING_MINUTES_PROMPT = """你是一个会议记录专家。请将语音转写的会议内容整理为规范的会议纪要格式。

要求：
1. **识别发言人**：如果有多人发言，尝试区分（如"发言人A"、"发言人B"）
2. **结构化**：
   - 会议主题/讨论要点
   - 关键决策
   - 行动项（如果有）
3. **添加标点符号和段落**
4. **精简冗余**：去除无意义的口语填充词
5. **保留关键信息**：决策、数据、时间节点等

原始文本：
{original_text}

请输出整理后的会议纪要：
"""


async def enhance_transcription(
    text: str,
    enhancement_type: str = "punctuation",
    model_id: Optional[str] = None
) -> str:
    """
    增强转写文本
    
    Args:
        text: 原始转写文本
        enhancement_type: 增强类型
            - "punctuation": 只添加标点和段落（保持口语风格）
            - "formal": 转换为正式书面语
            - "meeting": 整理为会议纪要格式
        model_id: LLM模型ID（如果不指定则使用默认模型）
    
    Returns:
        增强后的文本
    """
    if not text or len(text.strip()) < 10:
        logger.warning("Text too short for enhancement, returning original")
        return text
    
    # 选择prompt模板
    if enhancement_type == "formal":
        prompt = PUNCTUATION_PROMPT_FORMAL.format(original_text=text)
    elif enhancement_type == "meeting":
        prompt = MEETING_MINUTES_PROMPT.format(original_text=text)
    else:  # "punctuation"
        prompt = PUNCTUATION_PROMPT.format(original_text=text)
    
    try:
        # 获取LLM服务
        store = LLMModelStore()
        
        # 如果没有指定model_id，使用默认模型
        if not model_id:
            models = store.list_models()
            if not models:
                logger.warning("No LLM models available, skipping enhancement")
                return text
            model_id = models[0]["model_id"]
            logger.info(f"Using default LLM model: {model_id}")
        
        llm = store.get_model(model_id)
        
        # 调用LLM
        logger.info(f"Enhancing transcription with LLM (type={enhancement_type}, length={len(text)}, model={model_id})")
        
        # 使用流式输出并收集完整结果
        enhanced_text = ""
        async for chunk in llm.chat_stream(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,  # 较低温度保证稳定性
            max_tokens=4000
        ):
            if chunk.get("type") == "content":
                enhanced_text += chunk.get("content", "")
        
        # 清理输出
        enhanced_text = enhanced_text.strip()
        
        # 验证输出长度（防止LLM输出过短）
        if len(enhanced_text) < len(text) * 0.5:
            logger.warning(f"Enhanced text too short ({len(enhanced_text)} vs {len(text)}), using original")
            return text
        
        logger.info(f"Enhancement completed: {len(text)} → {len(enhanced_text)} chars")
        return enhanced_text
    
    except Exception as e:
        logger.error(f"Enhancement failed: {e}", exc_info=True)
        # 失败时返回原文
        return text


async def enhance_transcription_with_segments(
    segments: list,
    enhancement_type: str = "punctuation",
    model_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    增强转写文本（保留segment信息）
    
    Args:
        segments: Whisper返回的segments列表
        enhancement_type: 增强类型
        model_id: LLM模型ID
    
    Returns:
        {
            "enhanced_text": str,  # 增强后的完整文本
            "original_text": str,  # 原始文本
            "original_segments": list,  # 原始segments
            "enhanced_paragraphs": list  # 增强后的段落列表
        }
    """
    # 提取原始文本
    original_text = ' '.join([seg.get('text', '').strip() for seg in segments])
    
    # 调用LLM增强
    enhanced_text = await enhance_transcription(
        text=original_text,
        enhancement_type=enhancement_type,
        model_id=model_id
    )
    
    # 分段（按换行符）
    paragraphs = [p.strip() for p in enhanced_text.split('\n\n') if p.strip()]
    if not paragraphs:
        # 如果没有双换行符，尝试单换行符
        paragraphs = [p.strip() for p in enhanced_text.split('\n') if p.strip()]
    
    return {
        "enhanced_text": enhanced_text,
        "original_text": original_text,
        "original_segments": segments,
        "enhanced_paragraphs": paragraphs
    }

