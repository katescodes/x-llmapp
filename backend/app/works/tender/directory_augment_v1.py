"""
目录增强服务 (v1)

利用 tender_info_v3 自动补充必填目录节点
"""
import logging
import uuid
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def augment_directory_from_tender_info_v3(
    project_id: str,
    pool: Any,
    tender_info: Dict[str, Any],
) -> Dict[str, Any]:
    """
    从 tender_info_v3 增强目录节点
    
    自动补充以下必填节点：
    1. document_preparation.required_forms - 必填表单
    2. bidder_qualification.must_provide_documents - 资格证明文件
    3. document_preparation.bid_documents_structure - 文档结构要求
    
    Args:
        project_id: 项目ID
        pool: 数据库连接池
        tender_info: tender_info_v3 数据
    
    Returns:
        增强统计信息
    """
    logger.info(f"开始从 tender_info_v3 增强目录: project_id={project_id}")
    
    # 1. 读取现有目录节点
    existing_nodes = _get_existing_directory_nodes(pool, project_id)
    existing_titles = {node["title"] for node in existing_nodes}
    
    logger.info(f"现有目录节点数: {len(existing_nodes)}")
    
    # 2. 提取必填节点
    required_nodes = []
    seen_titles = set()  # 用于去重
    
    # 2.1 从 document_preparation 提取
    if "document_preparation" in tender_info:
        doc_prep = tender_info["document_preparation"]
        
        # 必填表单
        if doc_prep.get("required_forms"):
            for form in doc_prep["required_forms"]:
                form_name = form.get("form_name")
                if form_name and form.get("is_mandatory", True):
                    if form_name not in existing_titles and form_name not in seen_titles:
                        required_nodes.append({
                            "title": form_name,
                            "level": 2,  # 假设为二级目录
                            "is_required": True,
                            "source": "tender_info_v3_document_preparation",
                            "evidence_chunk_ids": form.get("evidence_chunk_ids", [])
                        })
                        seen_titles.add(form_name)
    
    # 2.2 从 bidder_qualification 提取
    if "bidder_qualification" in tender_info:
        qual = tender_info["bidder_qualification"]
        
        # 必须提供的文件
        if qual.get("must_provide_documents"):
            for doc_name in qual["must_provide_documents"]:
                if doc_name and doc_name not in existing_titles and doc_name not in seen_titles:
                    required_nodes.append({
                        "title": doc_name,
                        "level": 2,
                        "is_required": True,
                        "source": "tender_info_v3_bidder_qualification",
                        "evidence_chunk_ids": qual.get("evidence_chunk_ids", [])
                    })
                    seen_titles.add(doc_name)
    
    logger.info(f"识别到 {len(required_nodes)} 个必填节点需要补充")
    
    # 3. 插入新节点到数据库
    added_count = 0
    if required_nodes:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # 获取最大 order_no
                cur.execute(
                    "SELECT COALESCE(MAX(order_no), 0) FROM tender_directory_nodes WHERE project_id = %s",
                    (project_id,)
                )
                max_order = list(cur.fetchone().values())[0]
                
                for i, node in enumerate(required_nodes):
                    node_id = str(uuid.uuid4())
                    order_no = max_order + i + 1
                    
                    cur.execute("""
                        INSERT INTO tender_directory_nodes (
                            id, project_id, parent_id, order_no, level,
                            numbering, title, is_required, source,
                            evidence_chunk_ids, meta_json
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        node_id,
                        project_id,
                        None,  # 暂不关联父节点
                        order_no,
                        node.get("level", 2),
                        "",  # 编号由后续处理生成
                        node["title"],
                        node.get("is_required", True),
                        node.get("source", "tender_info_v3"),
                        node.get("evidence_chunk_ids", []),
                        {"source_hint": node.get("source", "tender_info_v3")}
                    ))
                    added_count += 1
            
            conn.commit()
    
    logger.info(f"成功补充 {added_count} 个必填目录节点")
    
    return {
        "existing_nodes_count": len(existing_nodes),
        "identified_required_count": len(required_nodes),
        "added_count": added_count,
        "enhanced_titles": [n["title"] for n in required_nodes]
    }


def _get_existing_directory_nodes(pool: Any, project_id: str) -> List[Dict[str, Any]]:
    """获取现有目录节点"""
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, level, order_no, is_required, source
                FROM tender_directory_nodes
                WHERE project_id = %s
                ORDER BY order_no
            """, (project_id,))
            
            rows = cur.fetchall()
            return [
                {
                    "id": row['id'],
                    "title": row['title'],
                    "level": row['level'],
                    "order_no": row['order_no'],
                    "is_required": row['is_required'],
                    "source": row['source']
                }
                for row in rows
            ]

