"""
报价明细结构化抽取器

从投标书中提取报价表的结构化数据，用于"明细合计=总价"校验
"""
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


class PriceDetailExtractor:
    """报价明细结构化抽取器"""
    
    def __init__(self, llm_orchestrator, retriever):
        """
        初始化
        
        Args:
            llm_orchestrator: LLM编排器
            retriever: 检索器
        """
        self.llm = llm_orchestrator
        self.retriever = retriever
    
    async def extract_price_details(
        self,
        project_id: str,
        bidder_name: str,
        model_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """
        提取报价明细结构
        
        Args:
            project_id: 项目ID
            bidder_name: 投标人名称
            model_id: 模型ID
            
        Returns:
            {
                "total_price": 总价（元）,
                "total_price_text": "总价原文",
                "detail_items": [
                    {"item_name": "项目名", "unit_price": 单价, "quantity": 数量, "subtotal": 小计},
                    ...
                ],
                "detail_sum": 明细合计（元）,
                "difference": 差异（元）,
                "difference_ratio": 差异比例,
                "evidence_segment_ids": ["seg_xxx"],
                "extraction_method": "llm_structured|rule_based",
            }
            
            返回None表示未能提取到明细结构
        """
        logger.info(f"[报价明细] 开始提取 project_id={project_id}, bidder={bidder_name}")
        
        # 1. 检索报价相关内容
        try:
            price_chunks = await self.retriever.retrieve(
                query="报价表 报价明细 分项报价 价格清单 开标一览表 报价汇总 总价 单价 数量 合计",
                project_id=project_id,
                doc_types=["bid"],
                top_k=30,
            )
        except Exception as e:
            logger.error(f"[报价明细] 检索失败: {e}")
            return None
        
        if not price_chunks:
            logger.warning("[报价明细] 未检索到报价相关内容")
            return None
        
        logger.info(f"[报价明细] 检索到 {len(price_chunks)} 个价格相关片段")
        
        # 2. 尝试规则化提取（优先，不消耗LLM token）
        rule_result = self._rule_based_extraction(price_chunks)
        if rule_result:
            logger.info("[报价明细] 规则化提取成功")
            return rule_result
        
        # 3. 降级到LLM结构化提取
        logger.info("[报价明细] 规则化提取失败，使用LLM结构化提取...")
        llm_result = await self._llm_structured_extraction(
            price_chunks=price_chunks,
            model_id=model_id,
        )
        
        if llm_result:
            logger.info("[报价明细] LLM结构化提取成功")
            return llm_result
        
        logger.warning("[报价明细] 所有方法均未能提取到明细结构")
        return None
    
    def _rule_based_extraction(
        self,
        chunks: List[Any]
    ) -> Optional[Dict[str, Any]]:
        """
        规则化提取（基于正则表达式和模式匹配）
        
        适用场景：明细表格式规范、包含明确的数量/单价/小计列
        """
        # 查找包含表格特征的chunk
        for chunk in chunks:
            text = chunk.text if hasattr(chunk, 'text') else str(chunk)
            
            # 检测是否包含表格特征（多行、对齐、数字列）
            if self._is_likely_price_table(text):
                # 尝试解析表格
                parsed = self._parse_price_table(text)
                if parsed and len(parsed["detail_items"]) > 0:
                    # 计算明细合计
                    detail_sum = sum(
                        item.get("subtotal", 0) 
                        for item in parsed["detail_items"]
                    )
                    
                    # 提取总价
                    total_price = self._extract_total_price_from_text(text)
                    
                    if total_price and detail_sum > 0:
                        difference = abs(total_price - detail_sum)
                        diff_ratio = difference / total_price if total_price > 0 else 0
                        
                        return {
                            "total_price": total_price,
                            "total_price_text": parsed.get("total_price_text", ""),
                            "detail_items": parsed["detail_items"],
                            "detail_sum": detail_sum,
                            "difference": difference,
                            "difference_ratio": diff_ratio,
                            "evidence_segment_ids": [chunk.chunk_id] if hasattr(chunk, 'chunk_id') else [],
                            "extraction_method": "rule_based",
                        }
        
        return None
    
    def _is_likely_price_table(self, text: str) -> bool:
        """判断文本是否可能包含报价表格"""
        # 表格特征：包含"序号"/"项目"/"单价"/"数量"/"合计"等列标题
        table_indicators = [
            r'序号.*项目.*单价.*数量.*小计',
            r'序号.*项目.*单价.*数量.*金额',
            r'项目名称.*单价.*数量.*合计',
            r'报价明细表',
            r'分项报价表',
        ]
        
        for pattern in table_indicators:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        # 或者：包含多个价格行（每行都有数字 + 金额单位）
        price_lines = re.findall(r'.*\d+[,.]\d+.*元.*', text)
        if len(price_lines) >= 3:  # 至少3行价格数据
            return True
        
        return False
    
    def _parse_price_table(self, text: str) -> Optional[Dict[str, Any]]:
        """
        解析报价表格文本
        
        返回结构化的明细数据
        """
        detail_items = []
        total_price_text = ""
        
        # 按行分割
        lines = text.split('\n')
        
        for line in lines:
            # 跳过表头行
            if any(kw in line for kw in ['序号', '项目名称', '单价', '数量', '合计']):
                continue
            
            # 尝试匹配明细行模式：序号 项目名 单价 数量 小计
            # 示例：1. 设备采购 15000 10 150000
            match = re.search(
                r'(\d+)[\.、\s]+([^0-9]+?)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)',
                line
            )
            
            if match:
                try:
                    item = {
                        "seq": int(match.group(1)),
                        "item_name": match.group(2).strip(),
                        "unit_price": self._parse_number(match.group(3)),
                        "quantity": self._parse_number(match.group(4)),
                        "subtotal": self._parse_number(match.group(5)),
                    }
                    detail_items.append(item)
                except (ValueError, InvalidOperation):
                    continue
            
            # 提取总价行
            if any(kw in line for kw in ['总计', '合计', '投标总价']):
                total_price_text = line.strip()
        
        if detail_items:
            return {
                "detail_items": detail_items,
                "total_price_text": total_price_text,
            }
        
        return None
    
    def _parse_number(self, text: str) -> float:
        """解析数字（支持千分位逗号）"""
        text = text.replace(',', '').replace('，', '').strip()
        return float(text)
    
    def _extract_total_price_from_text(self, text: str) -> Optional[float]:
        """从文本中提取总价"""
        # 查找总价模式
        patterns = [
            r'总[计价][：:]\s*[\￥]?([\d,\.]+)\s*元',
            r'投标总价[：:]\s*[\￥]?([\d,\.]+)\s*元',
            r'合计[：:]\s*[\￥]?([\d,\.]+)\s*元',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return self._parse_number(match.group(1))
                except (ValueError, InvalidOperation):
                    continue
        
        return None
    
    async def _llm_structured_extraction(
        self,
        price_chunks: List[Any],
        model_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """
        使用LLM进行结构化提取（降级方案）
        
        当规则化提取失败时使用
        """
        if not self.llm:
            logger.warning("[报价明细] LLM未配置，无法使用LLM提取")
            return None
        
        # 构建上下文
        price_context = "\n\n".join([
            f"[SEG:{chunk.chunk_id if hasattr(chunk, 'chunk_id') else 'unknown'}] "
            f"{chunk.text if hasattr(chunk, 'text') else str(chunk)}"
            for chunk in price_chunks[:20]
        ])
        
        prompt = f"""# 报价明细结构化提取任务

## 投标文档内容（价格相关）
{price_context}

## 任务要求
从上述内容中提取报价明细表的结构化数据。

### 输出格式
返回JSON对象：

```json
{{
  "has_detail_table": true,
  "total_price": 总价（数值，单位：元）,
  "total_price_text": "总价原文（如：投标总价：1,560,000元）",
  "detail_items": [
    {{
      "seq": 序号,
      "item_name": "项目名称",
      "unit_price": 单价（数值）,
      "quantity": 数量（数值）,
      "subtotal": 小计（数值）
    }}
  ],
  "evidence_segment_ids": ["seg_xxx"]
}}
```

### 注意事项
- 如果文档中没有明细表格，has_detail_table=false，detail_items=[]
- 所有价格数值应转换为数字类型（去除逗号、货币符号）
- 单价×数量应该=小计（如果不等，说明是错误数据）
- 总价应该=所有小计之和（误差应在合理范围内）

请开始提取："""
        
        try:
            messages = [{"role": "user", "content": prompt}]
            llm_response = await self.llm.achat(
                messages=messages,
                model_id=model_id,
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=4096,
            )
            
            import json
            llm_output = llm_response.get("choices", [{}])[0].get("message", {}).get("content")
            if not llm_output:
                logger.warning("[报价明细] LLM返回空内容")
                return None
            
            result_data = json.loads(llm_output)
            
            if not result_data.get("has_detail_table"):
                logger.info("[报价明细] LLM判断：文档中无明细表格")
                return None
            
            detail_items = result_data.get("detail_items", [])
            if not detail_items:
                logger.warning("[报价明细] LLM返回空明细列表")
                return None
            
            # 计算明细合计
            detail_sum = sum(item.get("subtotal", 0) for item in detail_items)
            
            total_price = result_data.get("total_price")
            if not total_price or total_price <= 0:
                logger.warning("[报价明细] 未能提取到有效总价")
                return None
            
            # 计算差异
            difference = abs(total_price - detail_sum)
            diff_ratio = difference / total_price if total_price > 0 else 0
            
            return {
                "total_price": total_price,
                "total_price_text": result_data.get("total_price_text", ""),
                "detail_items": detail_items,
                "detail_sum": detail_sum,
                "difference": difference,
                "difference_ratio": diff_ratio,
                "evidence_segment_ids": result_data.get("evidence_segment_ids", []),
                "extraction_method": "llm_structured",
            }
            
        except Exception as e:
            logger.error(f"[报价明细] LLM结构化提取失败: {e}", exc_info=True)
            return None

