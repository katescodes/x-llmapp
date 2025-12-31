"""
目录快速构建器 (Fast Builder)

利用已提取的项目信息快速构建目录骨架，无需LLM
"""
import logging
import uuid
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def build_directory_from_project_info(
    project_id: str,
    pool: Any,
    tender_info: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    从项目信息快速构建目录骨架
    
    构建规则：
    1. 商务标部分
       - 投标函及投标函附录
       - 法定代表人身份证明/授权委托书
       - 项目管理机构
       - 资格审查资料
       - 其他材料（从必填表单提取）
    
    2. 技术标部分
       - 技术方案
       - 项目实施方案
       - 服务承诺
       - 其他技术资料
    
    Args:
        project_id: 项目ID
        pool: 数据库连接池
        tender_info: tender_info_v3 数据
    
    Returns:
        (nodes, stats): 目录节点列表和统计信息
    """
    logger.info(f"[FastBuilder] 开始快速构建目录: project_id={project_id}")
    
    nodes = []
    order_no = 1
    
    # 1. 商务标部分
    nodes.append({
        "title": "商务标",
        "level": 1,
        "order_no": order_no,
        "parent_ref": None,
        "required": True,
        "volume": "第一卷",
        "notes": "商务文件",
        "evidence_chunk_ids": [],
        "source": "fast_builder"
    })
    order_no += 1
    
    # 1.1 投标函
    nodes.append({
        "title": "投标函及投标函附录",
        "level": 2,
        "order_no": order_no,
        "parent_ref": "商务标",
        "required": True,
        "volume": "第一卷",
        "notes": "",
        "evidence_chunk_ids": [],
        "source": "fast_builder"
    })
    order_no += 1
    
    # 1.2 法定代表人身份证明
    nodes.append({
        "title": "法定代表人身份证明或授权委托书",
        "level": 2,
        "order_no": order_no,
        "parent_ref": "商务标",
        "required": True,
        "volume": "第一卷",
        "notes": "",
        "evidence_chunk_ids": [],
        "source": "fast_builder"
    })
    order_no += 1
    
    # 1.3 从 document_preparation 提取必填表单
    if "document_preparation" in tender_info:
        doc_prep = tender_info["document_preparation"]
        if doc_prep.get("required_forms"):
            for form in doc_prep["required_forms"]:
                form_name = form.get("form_name")
                if form_name and form.get("is_mandatory", True):
                    nodes.append({
                        "title": form_name,
                        "level": 2,
                        "order_no": order_no,
                        "parent_ref": "商务标",
                        "required": True,
                        "volume": "第一卷",
                        "notes": form.get("purpose", ""),
                        "evidence_chunk_ids": form.get("evidence_chunk_ids", []),
                        "source": "project_info"
                    })
                    order_no += 1
    
    # 1.4 从 bidder_qualification 提取资格证明文件
    if "bidder_qualification" in tender_info:
        qual = tender_info["bidder_qualification"]
        
        # 添加"资格审查资料"父节点
        nodes.append({
            "title": "资格审查资料",
            "level": 2,
            "order_no": order_no,
            "parent_ref": "商务标",
            "required": True,
            "volume": "第一卷",
            "notes": "",
            "evidence_chunk_ids": [],
            "source": "fast_builder"
        })
        order_no += 1
        
        if qual.get("must_provide_documents"):
            for doc_name in qual["must_provide_documents"]:
                if doc_name:
                    nodes.append({
                        "title": doc_name,
                        "level": 3,
                        "order_no": order_no,
                        "parent_ref": "资格审查资料",
                        "required": True,
                        "volume": "第一卷",
                        "notes": "",
                        "evidence_chunk_ids": qual.get("evidence_chunk_ids", []),
                        "source": "project_info"
                    })
                    order_no += 1
    
    # 2. 技术标部分
    nodes.append({
        "title": "技术标",
        "level": 1,
        "order_no": order_no,
        "parent_ref": None,
        "required": True,
        "volume": "第二卷",
        "notes": "技术文件",
        "evidence_chunk_ids": [],
        "source": "fast_builder"
    })
    order_no += 1
    
    # 2.1 从 technical_requirements 提取技术要求
    if "technical_requirements" in tender_info:
        tech = tender_info["technical_requirements"]
        
        # 技术方案
        if tech.get("mandatory_specs") or tech.get("technical_specs"):
            nodes.append({
                "title": "技术方案",
                "level": 2,
                "order_no": order_no,
                "parent_ref": "技术标",
                "required": True,
                "volume": "第二卷",
                "notes": "",
                "evidence_chunk_ids": tech.get("evidence_chunk_ids", []),
                "source": "project_info"
            })
            order_no += 1
        
        # 项目实施方案
        nodes.append({
            "title": "项目实施方案",
            "level": 2,
            "order_no": order_no,
            "parent_ref": "技术标",
            "required": True,
            "volume": "第二卷",
            "notes": "",
            "evidence_chunk_ids": [],
            "source": "fast_builder"
        })
        order_no += 1
    
    # 2.2 服务承诺
    if "business_terms" in tender_info:
        biz = tender_info["business_terms"]
        if biz.get("warranty_requirements") or biz.get("service_requirements"):
            nodes.append({
                "title": "服务承诺",
                "level": 2,
                "order_no": order_no,
                "parent_ref": "技术标",
                "required": True,
                "volume": "第二卷",
                "notes": "",
                "evidence_chunk_ids": biz.get("evidence_chunk_ids", []),
                "source": "project_info"
            })
            order_no += 1
    
    # 3. 价格标部分（如果有价格相关信息）
    if "business_terms" in tender_info:
        biz = tender_info["business_terms"]
        if biz.get("pricing_basis") or biz.get("payment_terms"):
            nodes.append({
                "title": "价格标",
                "level": 1,
                "order_no": order_no,
                "parent_ref": None,
                "required": True,
                "volume": "第三卷",
                "notes": "价格文件",
                "evidence_chunk_ids": [],
                "source": "fast_builder"
            })
            order_no += 1
            
            nodes.append({
                "title": "投标报价表",
                "level": 2,
                "order_no": order_no,
                "parent_ref": "价格标",
                "required": True,
                "volume": "第三卷",
                "notes": "",
                "evidence_chunk_ids": biz.get("evidence_chunk_ids", []),
                "source": "project_info"
            })
            order_no += 1
    
    stats = {
        "total_nodes": len(nodes),
        "from_project_info": sum(1 for n in nodes if n["source"] == "project_info"),
        "from_fast_builder": sum(1 for n in nodes if n["source"] == "fast_builder"),
        "level_1": sum(1 for n in nodes if n["level"] == 1),
        "level_2": sum(1 for n in nodes if n["level"] == 2),
        "level_3": sum(1 for n in nodes if n["level"] == 3),
    }
    
    logger.info(
        f"[FastBuilder] 完成快速构建: total={stats['total_nodes']}, "
        f"from_info={stats['from_project_info']}, "
        f"L1={stats['level_1']}, L2={stats['level_2']}, L3={stats['level_3']}"
    )
    
    return nodes, stats

