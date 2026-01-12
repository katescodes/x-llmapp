"""
范文应用服务
将提取的格式范文插入到投标书节点中
"""
import re
import json
import logging
from typing import Dict, Any, List, Optional
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)


def identify_placeholders(text: str) -> List[Dict[str, Any]]:
    """
    识别文本中的占位符
    
    常见占位符格式：
    - 【xxx】
    - [xxx]
    - ___xxx___
    - {xxx}
    - ____（空白下划线）
    
    Returns:
        List[{
            "placeholder": "原始占位符",
            "key": "标准化的键名",
            "start": 起始位置,
            "end": 结束位置
        }]
    """
    placeholders = []
    
    # 模式1: 【xxx】
    pattern1 = r'【([^】]+)】'
    for match in re.finditer(pattern1, text):
        placeholders.append({
            "placeholder": match.group(0),
            "key": match.group(1).strip(),
            "start": match.start(),
            "end": match.end(),
            "pattern": "brackets"
        })
    
    # 模式2: [xxx] (但排除日期格式)
    pattern2 = r'\[([^\]]{2,30})\]'
    for match in re.finditer(pattern2, text):
        content = match.group(1).strip()
        # 排除日期格式如 [2024-01-01]
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', content):
            placeholders.append({
                "placeholder": match.group(0),
                "key": content,
                "start": match.start(),
                "end": match.end(),
                "pattern": "square"
            })
    
    # 模式3: ___xxx___ (3个以上下划线包围)
    pattern3 = r'_{3,}([^_]+)_{3,}'
    for match in re.finditer(pattern3, text):
        placeholders.append({
            "placeholder": match.group(0),
            "key": match.group(1).strip(),
            "start": match.start(),
            "end": match.end(),
            "pattern": "underline"
        })
    
    # 模式4: 单独的长下划线 (10个以上)
    pattern4 = r'_{10,}'
    for match in re.finditer(pattern4, text):
        placeholders.append({
            "placeholder": match.group(0),
            "key": f"blank_{len(placeholders)}",
            "start": match.start(),
            "end": match.end(),
            "pattern": "blank_line"
        })
    
    return placeholders


def auto_fill_placeholders(
    text: str,
    project_info: Optional[Dict[str, Any]] = None,
    custom_values: Optional[Dict[str, str]] = None
) -> str:
    """
    自动填充文本中的占位符
    
    Args:
        text: 包含占位符的文本
        project_info: 项目信息（从 tender_info_v3 或 tender_projects 获取）
        custom_values: 自定义填充值
    
    Returns:
        填充后的文本
    """
    if not text:
        return text
    
    # 识别所有占位符
    placeholders = identify_placeholders(text)
    
    if not placeholders:
        return text
    
    # 构建填充映射
    fill_map = {}
    
    # 从项目信息中提取常用字段
    if project_info:
        # 项目名称
        project_name = project_info.get("project_name") or project_info.get("name")
        if project_name:
            fill_map["项目名称"] = project_name
            fill_map["project_name"] = project_name
            fill_map["工程名称"] = project_name
        
        # 招标单位
        tender_unit = project_info.get("tender_unit") or project_info.get("buyer_name")
        if tender_unit:
            fill_map["招标单位"] = tender_unit
            fill_map["招标人"] = tender_unit
            fill_map["采购人"] = tender_unit
        
        # 预算金额
        budget = project_info.get("budget") or project_info.get("estimated_price")
        if budget:
            fill_map["预算金额"] = str(budget)
            fill_map["投标报价"] = str(budget)
        
        # 工期
        duration = project_info.get("duration") or project_info.get("construction_period")
        if duration:
            fill_map["工期"] = str(duration)
            fill_map["工程工期"] = str(duration)
    
    # 自定义值优先
    if custom_values:
        fill_map.update(custom_values)
    
    # 按位置从后向前替换（避免位置偏移）
    result = text
    for placeholder in sorted(placeholders, key=lambda x: x["start"], reverse=True):
        key = placeholder["key"]
        
        # 查找匹配的填充值
        fill_value = None
        
        # 精确匹配
        if key in fill_map:
            fill_value = fill_map[key]
        else:
            # 模糊匹配
            for map_key, map_value in fill_map.items():
                if map_key in key or key in map_key:
                    fill_value = map_value
                    break
        
        # 如果找到了填充值，进行替换
        if fill_value:
            start = placeholder["start"]
            end = placeholder["end"]
            result = result[:start] + str(fill_value) + result[end:]
            logger.debug(f"Filled placeholder '{placeholder['placeholder']}' with '{fill_value}'")
    
    return result


def apply_snippet_to_node(
    snippet_id: str,
    node_id: str,
    project_id: str,
    db_pool: ConnectionPool,
    mode: str = "replace",
    auto_fill: bool = True,
    custom_values: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    将范文应用到节点
    
    Args:
        snippet_id: 范文ID
        node_id: 节点ID
        project_id: 项目ID
        db_pool: 数据库连接池
        mode: 应用模式 (replace=替换, append=追加)
        auto_fill: 是否自动填充占位符
        custom_values: 自定义填充值
    
    Returns:
        {
            "success": bool,
            "node_id": str,
            "node_title": str,
            "snippet_title": str,
            "placeholders_found": int,
            "placeholders_filled": int,
            "message": str
        }
    """
    logger.info(f"Applying snippet {snippet_id} to node {node_id} (mode={mode}, auto_fill={auto_fill})")
    
    with db_pool.connection() as conn:
        with conn.cursor() as cur:
            # 1. 获取范文内容
            cur.execute("""
                SELECT id, title, blocks_json
                FROM tender_format_snippets
                WHERE id = %s AND project_id = %s
            """, (snippet_id, project_id))
            
            snippet_row = cur.fetchone()
            if not snippet_row:
                return {
                    "success": False,
                    "message": f"范文 {snippet_id} 不存在"
                }
            
            snippet_title = snippet_row['title']
            blocks_json = snippet_row['blocks_json']
            
            # PostgreSQL JSONB 直接返回为 Python 对象
            if not isinstance(blocks_json, list):
                if isinstance(blocks_json, str):
                    blocks_json = json.loads(blocks_json)
                else:
                    blocks_json = []
            
            # 2. 将blocks转换为文本
            snippet_text = _blocks_to_text(blocks_json)
            
            if not snippet_text.strip():
                return {
                    "success": False,
                    "message": "范文内容为空"
                }
            
            # 3. 获取节点信息
            cur.execute("""
                SELECT id, title, body_content
                FROM tender_directory_nodes
                WHERE id = %s AND project_id = %s
            """, (node_id, project_id))
            
            node_row = cur.fetchone()
            if not node_row:
                return {
                    "success": False,
                    "message": f"节点 {node_id} 不存在"
                }
            
            node_title = node_row['title']
            existing_content = node_row['body_content'] or ""
            
            # 4. 识别占位符
            placeholders = identify_placeholders(snippet_text)
            placeholders_found = len(placeholders)
            
            # 5. 自动填充占位符
            final_text = snippet_text
            placeholders_filled = 0
            
            if auto_fill and placeholders:
                # 获取项目信息
                cur.execute("""
                    SELECT name, meta_json
                    FROM tender_projects
                    WHERE project_id = %s
                """, (project_id,))
                
                project_row = cur.fetchone()
                project_info = {}
                if project_row:
                    project_info["name"] = project_row['name']
                    meta_json_data = project_row.get('meta_json')
                    if meta_json_data:
                        if isinstance(meta_json_data, dict):
                            project_info.update(meta_json_data)
                        elif isinstance(meta_json_data, str):
                            project_info.update(json.loads(meta_json_data))
                
                # 填充占位符
                filled_text = auto_fill_placeholders(snippet_text, project_info, custom_values)
                
                # 计算填充了多少个
                filled_placeholders = identify_placeholders(filled_text)
                placeholders_filled = placeholders_found - len(filled_placeholders)
                
                final_text = filled_text
            
            # 6. 根据模式更新节点内容
            if mode == "replace":
                new_content = final_text
            elif mode == "append":
                new_content = existing_content + "\n\n" + final_text if existing_content else final_text
            else:
                return {
                    "success": False,
                    "message": f"不支持的模式: {mode}"
                }
            
            # 7. 渲染blocks为HTML
            content_html = _render_blocks_to_html(blocks_json)
            
            # 8. 持久化到 project_section_body 表
            # 先检查是否已存在
            cur.execute("""
                SELECT id FROM project_section_body
                WHERE project_id = %s AND node_id = %s
            """, (project_id, node_id))
            
            existing = cur.fetchone()
            
            if existing:
                # 更新现有记录
                cur.execute("""
                    UPDATE project_section_body
                    SET 
                        content_html = %s,
                        source = 'SNIPPET',
                        updated_at = NOW()
                    WHERE project_id = %s AND node_id = %s
                """, (content_html, project_id, node_id))
            else:
                # 插入新记录
                from app.utils.id import _id
                body_id = _id("psb")
                cur.execute("""
                    INSERT INTO project_section_body (
                        id, project_id, node_id, source, content_html, 
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, 'SNIPPET', %s, NOW(), NOW())
                """, (body_id, project_id, node_id, content_html))
            
            # 9. 同时更新 meta_json（作为备份和标记）
            cur.execute("""
                SELECT meta_json FROM tender_directory_nodes
                WHERE id = %s AND project_id = %s
            """, (node_id, project_id))
            
            row = cur.fetchone()
            meta_json = row['meta_json'] if row and row['meta_json'] else {}
            if isinstance(meta_json, str):
                meta_json = json.loads(meta_json)
            
            # 将范文blocks存入meta_json
            meta_json['snippet_blocks'] = blocks_json
            meta_json['snippet_id'] = snippet_id
            
            cur.execute("""
                UPDATE tender_directory_nodes
                SET 
                    meta_json = %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s AND project_id = %s
            """, (json.dumps(meta_json, ensure_ascii=False), node_id, project_id))
            
            if cur.rowcount == 0:
                return {
                    "success": False,
                    "message": "更新节点失败"
                }
            
            conn.commit()
    
    logger.info(f"✅ Applied snippet '{snippet_title}' to node '{node_title}' "
               f"({placeholders_filled}/{placeholders_found} placeholders filled)")
    
    return {
        "success": True,
        "node_id": node_id,
        "node_title": node_title,
        "snippet_id": snippet_id,
        "snippet_title": snippet_title,
        "placeholders_found": placeholders_found,
        "placeholders_filled": placeholders_filled,
        "mode": mode,
        "message": f"成功应用范文到节点 '{node_title}'"
    }


def _blocks_to_text(blocks: List[Dict[str, Any]]) -> str:
    """
    将doc_blocks格式的blocks转换为纯文本
    
    Args:
        blocks: blocks_json数据
    
    Returns:
        文本内容
    """
    parts = []
    
    for block in blocks:
        block_type = block.get("type", "")
        
        # 段落类型：p, paragraph, heading等
        if block_type in ("p", "paragraph", "heading", "h1", "h2", "h3", "h4", "h5", "h6"):
            # 段落：提取text
            text = block.get("text", "").strip()
            if text:
                parts.append(text)
        
        elif block_type == "table":
            # 表格：提取为Markdown格式
            table_data = block.get("data", {})
            rows = table_data.get("rows", [])
            
            if rows:
                # 表头
                header = rows[0] if len(rows) > 0 else []
                if header:
                    parts.append(" | ".join(str(cell) for cell in header))
                    parts.append(" | ".join(["---"] * len(header)))
                
                # 表格内容
                for row in rows[1:]:
                    parts.append(" | ".join(str(cell) for cell in row))
                
                parts.append("")  # 空行分隔
    
    return "\n".join(parts)


def _render_blocks_to_html(blocks: List[Dict[str, Any]]) -> str:
    """
    将doc_blocks格式的blocks渲染为HTML
    
    Args:
        blocks: blocks_json数据
    
    Returns:
        HTML字符串
    """
    html_parts = []
    
    for block in blocks:
        block_type = block.get("type", "")
        
        # 段落
        if block_type == "p":
            text = block.get("text", "").strip()
            if text:
                # 简单处理换行
                text_html = text.replace("\n", "<br>")
                html_parts.append(f"<p>{text_html}</p>")
        
        # 表格
        elif block_type == "table":
            rows = block.get("rows", [])
            if not rows:
                continue
            
            # 使用更真实的表格样式
            html_parts.append('''<table style="
                border-collapse: collapse; 
                width: 100%; 
                margin: 16px 0;
                border: 1px solid #d0d0d0;
                font-size: 14px;
            ">''')
            
            # 表头
            if len(rows) > 0:
                html_parts.append("<thead><tr>")
                for cell in rows[0]:
                    cell_text = str(cell).replace("\n", "<br>")
                    html_parts.append(f'''<th style="
                        background-color: #f5f5f5; 
                        font-weight: 600; 
                        text-align: center; 
                        padding: 10px 8px;
                        border: 1px solid #d0d0d0;
                        color: #333;
                    ">{cell_text}</th>''')
                html_parts.append("</tr></thead>")
            
            # 表体
            if len(rows) > 1:
                html_parts.append("<tbody>")
                for row in rows[1:]:
                    html_parts.append("<tr>")
                    for cell in row:
                        cell_text = str(cell).replace("\n", "<br>")
                        html_parts.append(f'''<td style="
                            padding: 10px 8px;
                            border: 1px solid #d0d0d0;
                            vertical-align: top;
                        ">{cell_text}</td>''')
                    html_parts.append("</tr>")
                html_parts.append("</tbody>")
            
            html_parts.append("</table>")
    
    return "\n".join(html_parts)


def batch_apply_snippets(
    matches: List[Dict[str, Any]],
    project_id: str,
    db_pool: ConnectionPool,
    mode: str = "replace",
    auto_fill: bool = True
) -> Dict[str, Any]:
    """
    批量应用范文到节点
    
    Args:
        matches: 匹配结果列表 [{node_id, snippet_id, ...}]
        project_id: 项目ID
        db_pool: 数据库连接池
        mode: 应用模式
        auto_fill: 是否自动填充占位符
    
    Returns:
        {
            "success_count": int,
            "failed_count": int,
            "total": int,
            "results": List[Dict],
            "errors": List[str]
        }
    """
    logger.info(f"Batch applying {len(matches)} snippets to nodes")
    
    results = []
    errors = []
    success_count = 0
    failed_count = 0
    
    for match in matches:
        try:
            result = apply_snippet_to_node(
                snippet_id=match["snippet_id"],
                node_id=match["node_id"],
                project_id=project_id,
                db_pool=db_pool,
                mode=mode,
                auto_fill=auto_fill
            )
            
            if result["success"]:
                success_count += 1
            else:
                failed_count += 1
                errors.append(f"{match['node_id']}: {result['message']}")
            
            results.append(result)
            
        except Exception as e:
            failed_count += 1
            error_msg = f"{match.get('node_id', 'unknown')}: {str(e)}"
            errors.append(error_msg)
            logger.error(f"Error applying snippet: {e}", exc_info=True)
            results.append({
                "success": False,
                "node_id": match.get("node_id"),
                "message": str(e)
            })
    
    logger.info(f"Batch apply complete: {success_count} success, {failed_count} failed")
    
    return {
        "success_count": success_count,
        "failed_count": failed_count,
        "total": len(matches),
        "results": results,
        "errors": errors
    }
