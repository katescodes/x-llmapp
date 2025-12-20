"""
LLM分析服务 - 只负责三件事
1. isTemplate 二分类
2. kind 归一到固定枚举
3. startBlockId/endBlockId 边界
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.config.template_extract_config import TemplateExtractConfig, get_template_extract_config
from app.schemas.template_extract import DocumentBlock, LlmWindowResult, TemplateKind

logger = logging.getLogger(__name__)


class LlmTemplateSpanService:
    """LLM范围分析服务"""
    
    def __init__(
        self,
        llm_orchestrator: Any = None,
        config: TemplateExtractConfig | None = None,
    ):
        """
        初始化服务
        
        Args:
            llm_orchestrator: LLM编排器（duck typing）
            config: 配置
        """
        self.llm = llm_orchestrator
        self.config = config or get_template_extract_config()
    
    def analyze_window(
        self,
        window_blocks: List[DocumentBlock],
    ) -> Optional[LlmWindowResult]:
        """
        分析窗口，判断是否是范本并确定边界
        
        Args:
            window_blocks: 窗口内的块列表
            
        Returns:
            分析结果，如果LLM调用失败则返回None
        """
        if not self.llm:
            logger.warning("LLM未配置，无法分析窗口")
            return None
        
        if not window_blocks:
            return None
        
        # 构建prompt
        prompt = self._build_prompt(window_blocks)
        
        # 调用LLM
        try:
            messages = [
                {
                    "role": "system",
                    "content": "你是一个专业的招投标文档分析专家，擅长从招标书中识别投标文件格式/样表/范本。",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ]
            
            response = self.llm.chat(messages=messages, model_id=None)
            
            # 解析响应
            content = self._extract_content_from_response(response)
            result = self._parse_llm_output(content, window_blocks)
            
            return result
            
        except Exception as e:
            logger.error(f"LLM调用失败: {e}", exc_info=True)
            return None
    
    def _build_prompt(self, window_blocks: List[DocumentBlock]) -> str:
        """构建LLM prompt"""
        # 准备blocks文本（截断避免token爆炸）
        blocks_text = ""
        total_chars = 0
        max_chars_per_block = 500  # 每个block最多500字
        max_total_chars = 8000     # 总共最多8000字
        
        for i, block in enumerate(window_blocks):
            text = (block.text or "")[:max_chars_per_block]
            block_info = f"\n[Block {i+1}]\n" \
                        f"  block_id: {block.block_id}\n" \
                        f"  order_no: {block.order_no}\n" \
                        f"  type: {block.block_type}\n" \
                        f"  text: {text}\n"
            
            if total_chars + len(block_info) > max_total_chars:
                blocks_text += f"\n... (剩余{len(window_blocks)-i}个块已省略)\n"
                break
            
            blocks_text += block_info
            total_chars += len(block_info)
        
        prompt = f"""请分析以下招标书文档片段，判断是否包含"投标文件格式/样表/范本"。

文档片段（共{len(window_blocks)}个块）：
{blocks_text}

范本类型定义：
- BID_LETTER: 投标函
- LEGAL_AUTHORIZATION: 法人授权委托书
- PRICE_SCHEDULE: 报价表/报价文件
- DEVIATION_TABLE: 偏离表（技术/商务）
- COMMITMENT_LETTER: 承诺书/响应承诺
- PERFORMANCE_TABLE: 业绩表
- STAFF_TABLE: 人员表/社保
- CREDENTIALS_LIST: 证书清单
- OTHER: 其他范本

判断标准：
1. 是否包含"填写模板"、"按以下格式"、"样表"等指示
2. 是否有明确的表格框架或签章占位
3. 是否有"投标人"、"日期"、"盖章"等待填写字段

请以JSON格式输出（**只能引用输入中实际存在的block_id**）：

如果是范本：
```json
{{
  "isTemplate": true,
  "kind": "LEGAL_AUTHORIZATION",
  "displayTitle": "法人授权委托书",
  "startBlockId": "b_xxx",
  "endBlockId": "b_yyy",
  "confidence": 0.86,
  "evidenceBlockIds": ["b_xxx", "b_yyy"],
  "reason": "命中授权委托书且包含被授权人/权限范围/签章占位"
}}
```

如果不是范本：
```json
{{
  "isTemplate": false,
  "confidence": 0.2,
  "reason": "仅为描述性文字，无模板特征"
}}
```

注意事项：
1. **只能输出输入中存在的block_id**
2. startBlockId和endBlockId必须是输入blocks中的ID
3. 如果不确定是否是范本，confidence设为0.5以下
4. 只输出JSON，不要有其他文字

请开始分析："""
        
        return prompt
    
    def _extract_content_from_response(self, response: Any) -> str:
        """从LLM响应中提取内容"""
        if isinstance(response, str):
            return response
        
        if isinstance(response, dict):
            for key in ("content", "text", "output"):
                if key in response and isinstance(response[key], str):
                    return response[key]
            
            # OpenAI-like格式
            if "choices" in response and response["choices"]:
                choice = response["choices"][0]
                if isinstance(choice, dict):
                    message = choice.get("message", {})
                    if isinstance(message, dict) and "content" in message:
                        return message["content"]
        
        return str(response)
    
    def _parse_llm_output(
        self,
        content: str,
        window_blocks: List[DocumentBlock],
    ) -> Optional[LlmWindowResult]:
        """
        解析LLM输出
        
        Args:
            content: LLM输出的文本
            window_blocks: 窗口块列表（用于验证block_id）
            
        Returns:
            解析结果，如果解析失败返回None
        """
        # 提取JSON
        json_str = self._extract_json_from_text(content)
        if not json_str:
            logger.warning("未找到有效的JSON输出")
            return None
        
        try:
            data = json.loads(json_str)
            
            # 验证必要字段
            is_template = data.get("isTemplate", False)
            confidence = float(data.get("confidence", 0.0))
            
            # 如果不是范本
            if not is_template:
                return LlmWindowResult(
                    is_template=False,
                    confidence=confidence,
                    reason=data.get("reason", "非范本区域"),
                )
            
            # 是范本，验证更多字段
            kind_str = data.get("kind")
            if not kind_str:
                logger.warning("缺少kind字段")
                return None
            
            # 验证kind是否有效
            try:
                kind = TemplateKind(kind_str)
            except ValueError:
                logger.warning(f"无效的kind: {kind_str}")
                kind = TemplateKind.OTHER
            
            start_block_id = data.get("startBlockId")
            end_block_id = data.get("endBlockId")
            
            # 验证block IDs
            valid_block_ids = {b.block_id for b in window_blocks}
            
            if start_block_id and start_block_id not in valid_block_ids:
                logger.warning(f"startBlockId {start_block_id} 不在窗口中")
                return None
            
            if end_block_id and end_block_id not in valid_block_ids:
                logger.warning(f"endBlockId {end_block_id} 不在窗口中")
                return None
            
            # 验证evidence block IDs
            evidence_block_ids = data.get("evidenceBlockIds", [])
            valid_evidence_ids = [
                bid for bid in evidence_block_ids
                if bid in valid_block_ids
            ]
            
            return LlmWindowResult(
                is_template=True,
                kind=kind,
                display_title=data.get("displayTitle", kind.value),
                start_block_id=start_block_id,
                end_block_id=end_block_id,
                confidence=confidence,
                evidence_block_ids=valid_evidence_ids,
                reason=data.get("reason", ""),
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            return None
        except Exception as e:
            logger.error(f"解析LLM输出失败: {e}", exc_info=True)
            return None
    
    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """从文本中提取JSON部分"""
        # 尝试提取```json ... ```包裹的内容
        match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.DOTALL)
        if match:
            return match.group(1)
        
        # 尝试直接查找JSON对象
        match = re.search(r"(\{[\s\S]*\})", text, re.DOTALL)
        if match:
            return match.group(1)
        
        return None

