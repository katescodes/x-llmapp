"""
投标响应审核兜底抽取器

无论招标要求如何，都确保提取到审核必需的基线字段：
- 项目识别信息（项目名称、项目编号）
- 投标人主体信息（公司名称、统一社会信用代码）
- 报价信息（总价、大小写）
- 关键承诺（工期、质保）
"""
import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BidBaselineExtractor:
    """投标响应审核兜底抽取器"""
    
    def __init__(self, llm_orchestrator, retriever, dao):
        """
        初始化
        
        Args:
            llm_orchestrator: LLM编排器
            retriever: 检索器
            dao: 数据访问对象
        """
        self.llm = llm_orchestrator
        self.retriever = retriever
        self.dao = dao
    
    async def extract_baseline_fields(
        self,
        project_id: str,
        bidder_name: str,
        model_id: Optional[str],
        existing_responses: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        提取审核兜底字段
        
        策略：检查已提取响应中是否包含关键字段，缺失则专项抽取
        
        Args:
            project_id: 项目ID
            bidder_name: 投标人名称
            model_id: 模型ID
            existing_responses: 已提取的响应列表
            
        Returns:
            新提取的兜底响应列表
        """
        logger.info(f"[兜底抽取] 开始检查审核必需字段...")
        
        # 1. 分析已提取响应，识别缺失的关键字段
        missing_fields = self._identify_missing_baseline_fields(existing_responses)
        
        if not missing_fields:
            logger.info("[兜底抽取] 所有关键字段已覆盖，无需补充")
            return []
        
        logger.info(f"[兜底抽取] 发现缺失关键字段: {missing_fields}")
        
        # 2. 针对缺失字段进行专项检索和抽取
        baseline_responses = await self._extract_missing_fields(
            project_id=project_id,
            bidder_name=bidder_name,
            model_id=model_id,
            missing_fields=missing_fields,
        )
        
        logger.info(f"[兜底抽取] 完成，补充了 {len(baseline_responses)} 条兜底响应")
        
        return baseline_responses
    
    def _identify_missing_baseline_fields(
        self,
        existing_responses: List[Dict[str, Any]]
    ) -> List[str]:
        """
        识别缺失的兜底字段
        
        返回缺失字段的标识列表
        """
        # 定义兜底字段及其识别规则
        baseline_fields = {
            "project_name": {
                "keywords": ["项目名称", "工程名称", "采购项目"],
                "norm_key": "project_name",
            },
            "project_code": {
                "keywords": ["项目编号", "招标编号", "项目号"],
                "norm_key": "project_code",
            },
            "company_name": {
                "keywords": ["投标人", "公司名称", "企业名称"],
                "norm_key": "company_name",
            },
            "total_price": {
                "keywords": ["投标总价", "投标报价", "总价"],
                "norm_key": "total_price_cny",
            },
            "duration": {
                "keywords": ["工期", "交付期"],
                "norm_key": "duration_days",
            },
            "warranty": {
                "keywords": ["质保期", "保修期"],
                "norm_key": "warranty_months",
            },
        }
        
        # 检查每个兜底字段是否已存在
        missing = []
        for field_id, field_info in baseline_fields.items():
            found = False
            
            # 检查normalized_fields_json中是否有对应的norm_key
            for resp in existing_responses:
                norm_fields = resp.get("normalized_fields_json", {})
                if isinstance(norm_fields, dict):
                    norm_key = field_info["norm_key"]
                    if norm_key in norm_fields and norm_fields[norm_key]:
                        found = True
                        break
                
                # 或检查response_text中是否包含关键词
                response_text = resp.get("response_text", "").lower()
                if any(kw.lower() in response_text for kw in field_info["keywords"][:2]):
                    found = True
                    break
            
            if not found:
                missing.append(field_id)
                logger.info(f"[兜底抽取] 缺失字段: {field_id} ({field_info['keywords'][0]})")
        
        return missing
    
    async def _extract_missing_fields(
        self,
        project_id: str,
        bidder_name: str,
        model_id: Optional[str],
        missing_fields: List[str],
    ) -> List[Dict[str, Any]]:
        """针对缺失字段进行专项抽取"""
        
        # 构建针对性查询
        field_queries = {
            "project_name": "项目名称 工程名称 采购项目",
            "project_code": "项目编号 招标编号 采购编号",
            "company_name": "投标人 公司名称 企业名称",
            "total_price": "投标总价 投标报价 报价汇总 开标一览表",
            "duration": "工期承诺 交付期 施工周期",
            "warranty": "质保期 保修期 质量保证期",
        }
        
        # 合并查询
        combined_query = " ".join([field_queries[f] for f in missing_fields if f in field_queries])
        
        logger.info(f"[兜底抽取] 检索投标文档，查询: {combined_query[:100]}...")
        
        # 检索投标文档
        try:
            bid_chunks = await self.retriever.retrieve(
                query=combined_query,
                project_id=project_id,
                doc_types=["bid"],
                top_k=50,
            )
        except Exception as e:
            logger.error(f"[兜底抽取] 检索失败: {e}")
            return []
        
        if not bid_chunks:
            logger.warning("[兜底抽取] 未检索到投标文档内容")
            return []
        
        logger.info(f"[兜底抽取] 检索到 {len(bid_chunks)} 个投标文档片段")
        
        # 构建抽取prompt
        bid_context = "\n\n".join([
            f"[SEG:{chunk.chunk_id}] {chunk.text}"
            for chunk in bid_chunks[:30]
        ])
        
        fields_desc = {
            "project_name": "项目名称（如：XX工程、XX采购项目）",
            "project_code": "项目编号/招标编号（如：XXTB-2024-001）",
            "company_name": "投标人名称/公司名称",
            "total_price": "投标总价（含大小写金额）",
            "duration": "工期承诺（天数）",
            "warranty": "质保期承诺（月数）",
        }
        
        missing_desc = "\n".join([
            f"- {fields_desc.get(f, f)}"
            for f in missing_fields
        ])
        
        prompt = f"""# 投标响应兜底抽取任务

## 背景
已完成需求驱动的响应抽取，但以下**审核必需的关键字段**仍缺失：

{missing_desc}

## 投标文档内容
{bid_context}

## 任务要求
请从投标文档中提取上述缺失的关键字段，**只提取明确存在的字段**。

### 输出格式
返回JSON数组：

```json
{{
  "baseline_responses": [
    {{
      "field_id": "project_name|project_code|company_name|total_price|duration|warranty",
      "dimension": "other",
      "response_type": "direct_answer",
      "response_text": "提取的内容（保留原文）",
      "normalized_fields_json": {{
        "_norm_key": "对应的norm_key",
        "对应的norm_key": "标准化的值"
      }},
      "evidence_segment_ids": ["seg_xxx"]
    }}
  ]
}}
```

### 注意事项
- **只提取明确存在的字段**，找不到的不要编造
- 项目名称、公司名称应保留完整原文
- 报价、工期、质保期需同时提取数值和单位
- 每个字段提供evidence_segment_ids

请开始提取："""
        
        # 调用LLM
        try:
            messages = [{"role": "user", "content": prompt}]
            llm_response = await self.llm.achat(
                messages=messages,
                model_id=model_id,
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=2048,
            )
            
            import json
            llm_output = llm_response.get("choices", [{}])[0].get("message", {}).get("content")
            if not llm_output:
                logger.warning("[兜底抽取] LLM返回空内容")
                return []
            
            result_data = json.loads(llm_output)
            baseline_items = result_data.get("baseline_responses", [])
            
            if not baseline_items:
                logger.info("[兜底抽取] LLM未找到缺失字段")
                return []
            
            logger.info(f"[兜底抽取] LLM返回 {len(baseline_items)} 条兜底响应")
            
            # 保存到数据库
            saved_responses = []
            for item in baseline_items:
                db_id = str(uuid.uuid4())
                
                norm_fields = item.get("normalized_fields_json", {})
                if not isinstance(norm_fields, dict):
                    norm_fields = {"_norm_key": None, "source": "audit_baseline"}
                else:
                    norm_fields["source"] = "audit_baseline"
                
                evidence_segment_ids = item.get("evidence_segment_ids", [])
                
                try:
                    self.dao._execute("""
                        INSERT INTO tender_bid_response_items (
                            id, project_id, bidder_name, dimension, response_type,
                            response_text, extracted_value_json, evidence_chunk_ids,
                            normalized_fields_json, evidence_json
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::text[], %s::jsonb, NULL)
                    """, (
                        db_id,
                        project_id,
                        bidder_name,
                        item.get("dimension", "other"),
                        item.get("response_type", "direct_answer"),
                        item.get("response_text", ""),
                        json.dumps({}),
                        evidence_segment_ids,
                        json.dumps(norm_fields),
                    ))
                    saved_responses.append(item)
                except Exception as e:
                    logger.error(f"[兜底抽取] 保存失败: {e}")
            
            logger.info(f"[兜底抽取] 成功保存 {len(saved_responses)} 条兜底响应")
            return saved_responses
            
        except Exception as e:
            logger.error(f"[兜底抽取] LLM调用失败: {e}", exc_info=True)
            return []

