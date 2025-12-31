"""
项目信息提取器 - 基于Checklist的框架驱动方法
"""
import logging
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any

from app.works.tender.project_info_prompt_builder import ProjectInfoPromptBuilder

logger = logging.getLogger(__name__)


class ProjectInfoExtractor:
    """
    项目信息提取器 - 基于Checklist + P0/P1两阶段提取
    
    流程：
    1. 加载checklist配置（从YAML）
    2. P0阶段：基于checklist的结构化提取
    3. P1阶段：补充扫描
    4. 验证和规范化
    5. 返回标准格式数据
    """
    
    def __init__(self, llm, checklist_path: Optional[str] = None):
        """
        初始化提取器
        
        Args:
            llm: LLM orchestrator实例
            checklist_path: checklist YAML文件路径（可选）
        """
        self.llm = llm
        
        # 加载checklist配置
        if checklist_path:
            self.checklist_path = Path(checklist_path)
        else:
            # 默认路径
            self.checklist_path = Path(__file__).parent / "checklists" / "project_info_v1.yaml"
        
        logger.info(f"项目信息提取器已初始化，checklist配置: {self.checklist_path}")
        
        # 加载配置
        self.config = self._load_checklist()
        
        # 提取stage配置
        self.stages_config = self._extract_stages_config()
    
    def _load_checklist(self) -> Dict[str, Any]:
        """加载checklist配置文件"""
        if not self.checklist_path.exists():
            raise FileNotFoundError(f"Checklist not found: {self.checklist_path}")
        
        try:
            with open(self.checklist_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            logger.info(
                f"已加载checklist: {config.get('template_name')}, "
                f"版本={config.get('version')}, "
                f"stage数量={config.get('metadata', {}).get('total_stages', 0)}"
            )
            
            return config
        
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse checklist YAML: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load checklist: {e}")
            raise
    
    def _extract_stages_config(self) -> Dict[int, Dict[str, Any]]:
        """提取各个stage的配置"""
        stages = {}
        
        for key, value in self.config.items():
            # 查找stage_X_xxx的key
            if key.startswith("stage_") and isinstance(value, dict):
                stage_num = value.get("stage")
                if stage_num:
                    stages[stage_num] = value
        
        logger.info(f"已提取{len(stages)}个stage配置")
        
        return stages
    
    async def extract_stage(
        self,
        stage: int,
        context_text: str,
        segment_id_map: Dict[str, Any],
        model_id: Optional[str] = None,
        context_info: Optional[Dict] = None,
        enable_p1: bool = True
    ) -> Dict[str, Any]:
        """
        提取单个stage的信息
        
        Args:
            stage: stage编号（1-6）
            context_text: 招标文档上下文文本（带segment ID标记）
            segment_id_map: segment_id到chunk对象的映射
            model_id: LLM模型ID
            context_info: 前序stage的结果（用于传递上下文）
            enable_p1: 是否启用P1补充扫描
        
        Returns:
            {
                "stage": stage编号,
                "stage_key": stage键名,
                "data": 提取的数据,
                "evidence_segment_ids": 证据segment IDs,
                "p1_supplements_count": P1补充项数量
            }
        """
        if stage not in self.stages_config:
            raise ValueError(f"Stage {stage} not found in checklist config")
        
        stage_config = self.stages_config[stage]
        stage_key = stage_config.get("stage_key")
        stage_name = stage_config.get("stage_name")
        
        logger.info(
            f"正在提取stage {stage} ({stage_name}), "
            f"启用P1={enable_p1}, 有前序上下文={context_info is not None}"
        )
        
        # 创建Prompt Builder
        prompt_builder = ProjectInfoPromptBuilder(stage, stage_config)
        
        # ===== P0阶段：基于Checklist的结构化提取 =====
        logger.info(f"Stage {stage} P0阶段: 构建prompt...")
        p0_prompt = prompt_builder.build_p0_prompt(context_text, context_info)
        
        logger.info(f"Stage {stage} P0阶段: 调用LLM... (prompt长度={len(p0_prompt)})")
        p0_llm_response = await self.llm.achat(
            messages=[{"role": "user", "content": p0_prompt}],
            model_id=model_id,
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=8000
        )
        
        p0_output = p0_llm_response.get("choices", [{}])[0].get("message", {}).get("content")
        if p0_output is None:
            p0_output = "{}"  # Fallback to empty object
            logger.warning(f"Stage {stage} P0阶段: LLM返回None，使用空对象")
        
        logger.info(f"Stage {stage} P0阶段: 解析响应... (长度={len(p0_output)})")
        p0_result = prompt_builder.parse_p0_response(p0_output)
        
        # ===== P1阶段：补充扫描 =====
        p1_result = {"supplements": {}, "evidence_map": {}, "reasons": {}}
        
        if enable_p1:
            logger.info(f"Stage {stage} P1阶段: 构建补充prompt...")
            p1_prompt = prompt_builder.build_p1_prompt(context_text, p0_result["data"], context_info)
            
            logger.info(f"Stage {stage} P1阶段: 调用LLM... (prompt长度={len(p1_prompt)})")
            p1_llm_response = await self.llm.achat(
                messages=[{"role": "user", "content": p1_prompt}],
                model_id=model_id,
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=4000
            )
            
            p1_output = p1_llm_response.get("choices", [{}])[0].get("message", {}).get("content")
            if p1_output is None:
                p1_output = "{}"
                logger.warning(f"Stage {stage} P1阶段: LLM返回None，使用空对象")
            
            if p1_output and p1_output.strip():
                logger.info(f"Stage {stage} P1阶段: 解析响应... (长度={len(p1_output)})")
                try:
                    p1_result = prompt_builder.parse_p1_response(p1_output)
                except Exception as e:
                    logger.warning(f"Stage {stage} P1阶段解析失败: {e}，跳过P1补充")
                    p1_result = {"supplements": {}, "evidence_map": {}, "reasons": {}, "metadata": {}}
            else:
                logger.warning(f"Stage {stage} P1阶段: LLM返回空响应，跳过")
                p1_result = {"supplements": {}, "evidence_map": {}, "reasons": {}, "metadata": {}}
        else:
            logger.info(f"Stage {stage} P1阶段: 已禁用，跳过")
        
        # ===== 合并P0和P1结果 =====
        logger.info(f"Stage {stage}: 合并P0和P1结果...")
        merged_result = prompt_builder.merge_p0_p1(p0_result, p1_result)
        
        # ===== 转换为Schema格式 =====
        logger.info(f"Stage {stage}: 转换为Schema格式...")
        schema_result = prompt_builder.convert_to_schema(merged_result)
        
        # 构建返回结果
        result = {
            "stage": stage,
            "stage_key": stage_key,
            "stage_name": stage_name,
            "data": schema_result[stage_key],
            "evidence_segment_ids": schema_result.get("evidence_chunk_ids", []),
            "p1_supplements_count": merged_result.get("p1_supplements_count", 0)
        }
        
        logger.info(
            f"Stage {stage} 提取完成: "
            f"字段数={len(result['data'])}, "
            f"证据片段数={len(result['evidence_segment_ids'])}, "
            f"P1补充数={result['p1_supplements_count']}"
        )
        
        return result
    
    async def extract_all_stages(
        self,
        context_text: str,
        segment_id_map: Dict[str, Any],
        model_id: Optional[str] = None,
        enable_p1: bool = True,
        sequential: bool = True
    ) -> Dict[str, Any]:
        """
        提取所有6个stage的信息
        
        Args:
            context_text: 招标文档上下文
            segment_id_map: segment ID映射
            model_id: LLM模型ID
            enable_p1: 是否启用P1补充扫描
            sequential: 是否顺序提取（传递context_info）
        
        Returns:
            {
                "schema_version": "tender_info_v3",
                "project_overview": {...},
                "bidder_qualification": {...},
                "evaluation_and_scoring": {...},
                "business_terms": {...},
                "technical_requirements": {...},
                "document_preparation": {...},
                "evidence_chunk_ids": [...],
                "stages_stats": {...}
            }
        """
        logger.info(
            f"Extracting all stages: sequential={sequential}, enable_p1={enable_p1}"
        )
        
        all_results = {}
        all_evidence_ids = set()
        stages_stats = {}
        
        # 用于传递context_info
        context_info = None
        
        for stage in range(1, 7):
            logger.info(f"=== Processing Stage {stage}/6 ===")
            
            try:
                result = await self.extract_stage(
                    stage=stage,
                    context_text=context_text,
                    segment_id_map=segment_id_map,
                    model_id=model_id,
                    context_info=context_info if sequential else None,
                    enable_p1=enable_p1
                )
                
                # 保存结果
                stage_key = result["stage_key"]
                all_results[stage_key] = result["data"]
                
                # 收集证据
                all_evidence_ids.update(result["evidence_segment_ids"])
                
                # 统计
                stages_stats[f"stage_{stage}"] = {
                    "stage_name": result["stage_name"],
                    "fields_count": len(result["data"]),
                    "evidence_segments": len(result["evidence_segment_ids"]),
                    "p1_supplements": result["p1_supplements_count"]
                }
                
                # 如果是顺序模式，传递结果给下一个stage
                if sequential:
                    if context_info is None:
                        context_info = {}
                    context_info[stage_key] = result["data"]
                
                logger.info(f"Stage {stage} completed successfully")
                
            except Exception as e:
                logger.error(f"Stage {stage} failed: {e}", exc_info=True)
                # 失败时保存空结果
                stage_config = self.stages_config[stage]
                stage_key = stage_config.get("stage_key")
                all_results[stage_key] = {}
                stages_stats[f"stage_{stage}"] = {
                    "stage_name": stage_config.get("stage_name"),
                    "error": str(e)
                }
        
        # 构建最终结果
        final_result = {
            "schema_version": "tender_info_v3",
            **all_results,
            "evidence_chunk_ids": sorted(list(all_evidence_ids)),
            "stages_stats": stages_stats
        }
        
        logger.info(
            f"All stages extraction complete: "
            f"total_evidence_segments={len(all_evidence_ids)}, "
            f"successful_stages={len([s for s in stages_stats.values() if 'error' not in s])}/6"
        )
        
        return final_result
    
    def validate_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证提取结果
        
        Args:
            result: 提取的结果
        
        Returns:
            验证报告
        """
        validation_report = {
            "is_valid": True,
            "errors": [],
            "warnings": []
        }
        
        # 检查schema_version
        if result.get("schema_version") != "tender_info_v3":
            validation_report["errors"].append(
                f"Invalid schema_version: {result.get('schema_version')}"
            )
            validation_report["is_valid"] = False
        
        # 检查6个stage是否存在
        required_stages = [
            "project_overview",
            "bidder_qualification",
            "evaluation_and_scoring",
            "business_terms",
            "technical_requirements",
            "document_preparation"
        ]
        
        for stage_key in required_stages:
            if stage_key not in result:
                validation_report["errors"].append(f"Missing stage: {stage_key}")
                validation_report["is_valid"] = False
            elif not isinstance(result[stage_key], dict):
                validation_report["errors"].append(
                    f"Invalid stage data type for {stage_key}: {type(result[stage_key])}"
                )
                validation_report["is_valid"] = False
        
        # 检查必填字段（示例：项目名称）
        project_overview = result.get("project_overview", {})
        if not project_overview.get("project_name"):
            validation_report["warnings"].append("Missing required field: project_name")
        
        # 检查证据
        evidence_ids = result.get("evidence_chunk_ids", [])
        if len(evidence_ids) == 0:
            validation_report["warnings"].append("No evidence segments recorded")
        
        logger.info(
            f"Validation complete: valid={validation_report['is_valid']}, "
            f"errors={len(validation_report['errors'])}, "
            f"warnings={len(validation_report['warnings'])}"
        )
        
        return validation_report

