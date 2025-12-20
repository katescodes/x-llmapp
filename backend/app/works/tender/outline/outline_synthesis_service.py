"""
目录合成服务 - 阶段B
使用要求项合成多级目录结构
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from app.schemas.semantic_outline import (
    OutlineNodeLLMOutput,
    RequirementItem,
    SemanticOutlineNode,
)

logger = logging.getLogger(__name__)


class OutlineSynthesisService:
    """目录合成服务"""
    
    def __init__(self, llm_orchestrator: Any = None):
        """
        初始化服务
        
        Args:
            llm_orchestrator: LLM编排器（duck typing接口）
        """
        self.llm = llm_orchestrator
    
    def synthesize_outline(
        self,
        requirements: List[RequirementItem],
        mode: str = "FAST",
        max_depth: int = 5,
    ) -> List[SemanticOutlineNode]:
        """
        从要求项合成多级目录
        
        Args:
            requirements: 要求项列表
            mode: 合成模式 FAST/FULL
            max_depth: 最大层级
            
        Returns:
            目录树（根节点列表）
        """
        logger.info(f"开始合成目录，mode={mode}, max_depth={max_depth}, requirements数量={len(requirements)}")
        
        if not requirements:
            logger.warning("要求项列表为空")
            return []
        
        # 1. 使用LLM合成目录
        outline_nodes = self._synthesize_with_llm(requirements, mode, max_depth)
        logger.info(f"LLM合成目录节点数={len(outline_nodes)}")
        
        # 2. 后处理：生成编号、汇总证据链
        self._post_process_outline(outline_nodes, requirements)
        
        return outline_nodes
    
    def _synthesize_with_llm(
        self,
        requirements: List[RequirementItem],
        mode: str,
        max_depth: int,
    ) -> List[SemanticOutlineNode]:
        """
        使用LLM合成目录
        
        Args:
            requirements: 要求项列表
            mode: FAST/FULL
            max_depth: 最大层级
            
        Returns:
            目录树
        """
        if not self.llm:
            logger.warning("LLM未配置，返回空列表")
            return []
        
        # 构建prompt
        prompt = self._build_synthesis_prompt(requirements, mode, max_depth)
        
        # 调用LLM
        try:
            messages = [
                {
                    "role": "system",
                    "content": "你是一个专业的技术方案编写专家，擅长从评分点和要求项中生成完整的多级技术方案目录。",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ]
            
            response = self.llm.chat(messages=messages, model_id=None)
            
            # 解析响应
            content = self._extract_content_from_response(response)
            outline = self._parse_llm_output(content, requirements)
            
            return outline
            
        except Exception as e:
            logger.error(f"LLM调用失败: {e}", exc_info=True)
            return []
    
    def _build_synthesis_prompt(
        self,
        requirements: List[RequirementItem],
        mode: str,
        max_depth: int,
    ) -> str:
        """构建合成prompt"""
        # 按类型分组
        req_by_type: Dict[str, List[RequirementItem]] = {}
        for req in requirements:
            req_type = req.req_type.value
            if req_type not in req_by_type:
                req_by_type[req_type] = []
            req_by_type[req_type].append(req)
        
        # 构建要求项文本
        requirements_text = ""
        for req_type, reqs in req_by_type.items():
            requirements_text += f"\n### {req_type} ({len(reqs)}项)\n"
            for i, req in enumerate(reqs[:20]):  # 每类最多显示20项
                requirements_text += f"{i+1}. [{req.req_id}] {req.title}: {req.content[:100]}\n"
            if len(reqs) > 20:
                requirements_text += f"... 还有{len(reqs)-20}项\n"
        
        min_l1_nodes = 8 if mode == "FULL" else 6
        min_total_nodes = 60 if mode == "FULL" else 40
        
        prompt = f"""请根据以下招标要求项，生成一个完整的技术方案目录结构。

要求项列表（共{len(requirements)}项）：
{requirements_text}

目录生成要求：
1. **覆盖度**：目录必须覆盖所有重要的要求项（TECH_SCORE、TECH_SPEC、DELIVERY_ACCEPTANCE、SERVICE_WARRANTY、BIZ_SCORE、QUALIFICATION）
2. **结构要求**：
   - 一级章节（L1）至少 {min_l1_nodes} 个
   - 总节点数至少 {min_total_nodes} 个
   - 最大层级不超过 {max_depth}
3. **章节示例**（参考标准技术方案结构）：
   - 第1章 项目概述
   - 第2章 项目理解
   - 第3章 总体方案设计
   - 第4章 技术方案
   - 第5章 产品/功能规格
   - 第6章 实施方案
   - 第7章 交付与验收
   - 第8章 售后服务与保障
   - 第9章 项目团队与业绩
   - 第10章 商务方案
4. **功能点拆分**：如果要求项中有"N项功能/N个评分点"，必须拆成对应的子节点（如5.1.1~5.1.N）
5. **每个节点必须**：
   - 有合理的标题（10字以内）
   - 有一句话说明（summary，40字以内）
   - 关联到具体的要求项ID（covered_req_ids）
   - 适当的标签（tags）

输出格式（JSON数组，每个节点包含children子节点）：
```json
[
  {{
    "level": 1,
    "title": "项目概述",
    "summary": "介绍项目背景、目标和整体情况",
    "tags": ["总体", "背景"],
    "covered_req_ids": ["req_xxx", "req_yyy"],
    "children": [
      {{
        "level": 2,
        "title": "项目背景",
        "summary": "描述项目的背景和需求来源",
        "tags": ["背景"],
        "covered_req_ids": ["req_xxx"],
        "children": []
      }},
      {{
        "level": 2,
        "title": "项目目标",
        "summary": "阐述项目要达成的目标和预期效果",
        "tags": ["目标"],
        "covered_req_ids": ["req_yyy"],
        "children": []
      }}
    ]
  }},
  {{
    "level": 1,
    "title": "技术方案",
    "summary": "详细描述技术架构和实现方案",
    "tags": ["技术", "对应评分项"],
    "covered_req_ids": ["req_zzz"],
    "children": [...]
  }}
]
```

注意：
1. 只输出JSON数组，不要有其他文字
2. 每个节点的covered_req_ids必须引用实际存在的要求项ID
3. 如果一个章节没有直接对应的要求项，covered_req_ids可以为空数组
4. 目录要完整、合理、符合技术方案的标准结构
5. 确保一级节点数量 >= {min_l1_nodes}，总节点数 >= {min_total_nodes}

请开始生成目录："""
        
        return prompt
    
    def _extract_content_from_response(self, response: Any) -> str:
        """从LLM响应中提取内容"""
        if isinstance(response, str):
            return response
        
        if isinstance(response, dict):
            for key in ("content", "text", "output"):
                if key in response and isinstance(response[key], str):
                    return response[key]
            
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
        requirements: List[RequirementItem],
    ) -> List[SemanticOutlineNode]:
        """
        解析LLM输出
        
        Args:
            content: LLM输出的文本
            requirements: 要求项列表（用于验证req_ids）
            
        Returns:
            目录树
        """
        # 提取JSON部分
        json_str = self._extract_json_from_text(content)
        if not json_str:
            logger.warning("未找到有效的JSON输出")
            return []
        
        try:
            nodes_raw = json.loads(json_str)
            if not isinstance(nodes_raw, list):
                logger.warning("JSON输出不是数组")
                return []
            
            # 构建req ID集合（用于验证）
            valid_req_ids = {req.req_id for req in requirements}
            
            # 递归解析节点
            outline = self._parse_nodes_recursive(nodes_raw, valid_req_ids)
            
            return outline
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            return []
    
    def _parse_nodes_recursive(
        self,
        nodes_data: List[Dict[str, Any]],
        valid_req_ids: set,
        parent_level: int = 0,
    ) -> List[SemanticOutlineNode]:
        """递归解析节点"""
        nodes = []
        
        for node_data in nodes_data:
            try:
                level = node_data.get("level", parent_level + 1)
                
                # 验证并过滤req IDs
                covered_req_ids = node_data.get("covered_req_ids", [])
                valid_covered = [rid for rid in covered_req_ids if rid in valid_req_ids]
                
                # 递归解析子节点
                children_data = node_data.get("children", [])
                children = self._parse_nodes_recursive(
                    children_data,
                    valid_req_ids,
                    parent_level=level,
                )
                
                # 构建节点
                node = SemanticOutlineNode(
                    node_id=f"node_{uuid.uuid4().hex[:12]}",
                    level=level,
                    numbering=None,  # 后处理生成
                    title=node_data.get("title", "未命名")[:100],
                    summary=node_data.get("summary", "")[:200],
                    tags=node_data.get("tags", [])[:10],
                    evidence_chunk_ids=[],  # 后处理汇总
                    covered_req_ids=valid_covered,
                    children=children,
                )
                
                nodes.append(node)
                
            except Exception as e:
                logger.warning(f"解析节点失败: {e}")
                continue
        
        return nodes
    
    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """从文本中提取JSON部分"""
        # 尝试提取```json ... ```包裹的内容
        match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text, re.DOTALL)
        if match:
            return match.group(1)
        
        # 尝试直接查找JSON数组
        match = re.search(r"(\[[\s\S]*\])", text, re.DOTALL)
        if match:
            return match.group(1)
        
        return None
    
    def _post_process_outline(
        self,
        nodes: List[SemanticOutlineNode],
        requirements: List[RequirementItem],
    ) -> None:
        """
        后处理目录：生成编号、汇总证据链
        
        Args:
            nodes: 目录树（会被就地修改）
            requirements: 要求项列表
        """
        # 构建req_id -> requirement映射
        req_map = {req.req_id: req for req in requirements}
        
        # 递归处理
        self._post_process_recursive(nodes, req_map, numbering_prefix="")
    
    def _post_process_recursive(
        self,
        nodes: List[SemanticOutlineNode],
        req_map: Dict[str, RequirementItem],
        numbering_prefix: str,
    ) -> None:
        """递归后处理节点"""
        for i, node in enumerate(nodes, start=1):
            # 生成编号
            if numbering_prefix:
                node.numbering = f"{numbering_prefix}.{i}"
            else:
                node.numbering = str(i)
            
            # 汇总证据链（从covered_req_ids）
            evidence_chunks = set()
            for req_id in node.covered_req_ids:
                req = req_map.get(req_id)
                if req:
                    evidence_chunks.update(req.source_chunk_ids)
            node.evidence_chunk_ids = list(evidence_chunks)
            
            # 递归处理子节点
            if node.children:
                self._post_process_recursive(
                    node.children,
                    req_map,
                    numbering_prefix=node.numbering,
                )
                
                # 如果父节点没有自己的证据，汇总子节点的证据
                if not node.evidence_chunk_ids:
                    child_evidence = set()
                    for child in node.children:
                        child_evidence.update(child.evidence_chunk_ids)
                    node.evidence_chunk_ids = list(child_evidence)

