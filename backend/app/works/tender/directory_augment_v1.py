"""
目录增强服务 (v1) - 从招标书"格式章节"精确提取目录

✅ 重要变更（2026-01）：
- 不再使用固定的"商务标/技术标/价格标"划分
- 完全依赖招标书中"投标文件格式/响应文件格式"章节的实际要求
- 如果招标书要求划分卷册，则按招标书的划分方式和名称
- 如果招标书没有要求划分，则不进行划分

策略：
1. 定位"投标文件格式/响应文件格式/磋商响应文件格式"章节
2. 用规则方法提取目录结构（编号+标题+层级）
3. 保持原样，不需要LLM理解和发挥
4. 支持的编号格式：第X册、一/二/三、(一)(二)、1./2.、1.1/1.2等
"""
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def augment_directory_from_tender_info_v3(
    project_id: str,
    pool: Any,
    tender_info: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    从招标书"格式章节"精确提取目录结构
    
    完整流程：
    1. 加载招标书文档
    2. 定位"投标文件格式"章节（组合匹配）
    3. 提取章节内的目录结构（规则优先）
    4. 入库（保留编号、标题、层级）
    
    Args:
        project_id: 项目ID
        pool: 数据库连接池
        tender_info: tender_info_v3 数据（兼容旧调用，可选）
    
    Returns:
        增强统计信息
    """
    logger.info(f"[目录增强] 开始从格式章节提取目录: project_id={project_id}")
    
    # 🔍 DEBUG: 写入调试日志
    import sys
    debug_log = open("/tmp/augment_debug.log", "a")
    debug_log.write(f"\n=== augment_directory_from_tender_info_v3 START ===\n")
    debug_log.write(f"project_id: {project_id}\n")
    debug_log.flush()
    
    print(f"[目录增强-DEBUG] 开始提取: project_id={project_id}", file=sys.stderr)
    
    # 1. 读取现有目录节点
    existing_nodes = _get_existing_directory_nodes(pool, project_id)
    existing_titles = {node["title"] for node in existing_nodes}
    
    logger.info(f"[目录增强] 现有目录节点数: {len(existing_nodes)}")
    debug_log.write(f"现有节点数: {len(existing_nodes)}, 标题: {list(existing_titles)[:5]}\n")
    debug_log.flush()
    print(f"[目录增强-DEBUG] 现有节点数: {len(existing_nodes)}, 标题: {list(existing_titles)[:5]}", file=sys.stderr)
    
    # 2. 加载招标书文档
    try:
        doc_path = _get_tender_document_path(pool, project_id)
        if not doc_path:
            logger.warning(f"[目录增强] 未找到招标书文档，跳过增强")
            return _empty_result(len(existing_nodes))
    except Exception as e:
        import traceback
        logger.warning(f"[目录增强] 获取招标书文档失败: {e}")
        logger.warning(f"[目录增强] 错误堆栈: {traceback.format_exc()}")
        return _empty_result(len(existing_nodes))
    
    # 3. 提取文档blocks
    try:
        from app.works.tender.snippet.doc_blocks import extract_blocks
        blocks = extract_blocks(doc_path)
        logger.info(f"[目录增强] 文档blocks提取完成: {len(blocks)} 个")
    except Exception as e:
        logger.error(f"[目录增强] 文档blocks提取失败: {e}")
        return _empty_result(len(existing_nodes))
    
    if not blocks:
        logger.warning(f"[目录增强] 文档为空，跳过增强")
        return _empty_result(len(existing_nodes))
    
    # 4. 定位"格式章节"
    try:
        from app.works.tender.snippet.snippet_locator import locate_format_chapter
        format_blocks = locate_format_chapter(blocks)
        logger.info(f"[目录增强] 格式章节定位完成: {len(format_blocks)} 个blocks")
        debug_log.write(f"格式章节blocks数: {len(format_blocks)}\n")
        debug_log.flush()
        
        print(f"[目录增强-DEBUG] 格式章节blocks数: {len(format_blocks)}", file=sys.stderr)
        if format_blocks:
            debug_log.write(f"前5个format_blocks:\n")
            for i, b in enumerate(format_blocks[:5]):
                if b['type'] == 'p':
                    text = b.get('text', '')[:80]
                    debug_log.write(f"  {i}: {text}\n")
            debug_log.flush()
        
        # 🔥 4.1 预处理：将目录表格转换为文本块
        format_blocks = _preprocess_tables_to_text(format_blocks)
        logger.info(f"[目录增强] 表格预处理完成，当前blocks数: {len(format_blocks)}")
        debug_log.write(f"表格预处理后blocks数: {len(format_blocks)}\n")
        debug_log.flush()
        
    except Exception as e:
        logger.error(f"[目录增强] 格式章节定位失败: {e}")
        debug_log.write(f"格式章节定位失败: {e}\n")
        debug_log.close()
        return _empty_result(len(existing_nodes))
    
    if not format_blocks:
        logger.warning(f"[目录增强] 未定位到格式章节，跳过增强")
        return _empty_result(len(existing_nodes))
    
    # 5. 提取目录结构（规则方法）
    try:
        directory_nodes = _extract_directory_from_blocks(format_blocks, existing_titles)
        logger.info(f"[目录增强] 提取到 {len(directory_nodes)} 个目录节点")
        debug_log.write(f"提取到 {len(directory_nodes)} 个目录节点\n")
        debug_log.flush()
        
        # 🔍 DEBUG: 输出提取到的节点详情
        if directory_nodes:
            logger.info(f"[目录增强-DEBUG] 提取节点详情:")
            debug_log.write(f"提取节点详情（前10个）:\n")
            for i, node in enumerate(directory_nodes[:10]):
                info = f"  节点{i+1}: block_index={node.get('block_index')}, {node.get('numbering')} {node['title']}"
                logger.info(info)
                debug_log.write(info + "\n")
            debug_log.flush()
        
        # 如果规则方法提取不到节点，尝试用LLM提取
        if len(directory_nodes) == 0:
            logger.info(f"[目录增强] 规则提取无结果，尝试LLM提取...")
            debug_log.write(f"规则提取无结果，尝试LLM提取...\n")
            debug_log.flush()
            directory_nodes = _extract_directory_with_llm(format_blocks, existing_titles, project_id, pool)
            logger.info(f"[目录增强] LLM提取到 {len(directory_nodes)} 个目录节点")
            debug_log.write(f"LLM提取到 {len(directory_nodes)} 个目录节点\n")
            debug_log.flush()
            
    except Exception as e:
        logger.error(f"[目录增强] 目录提取失败: {e}")
        return _empty_result(len(existing_nodes))
    
    # 6. 入库
    added_count = 0
    if directory_nodes:
        logger.info(f"[目录增强] 准备插入 {len(directory_nodes)} 个节点 (按提取顺序):")
        debug_log.write(f"准备插入 {len(directory_nodes)} 个节点:\n")
        for i, node in enumerate(directory_nodes):
            info = f"  节点{i+1}: block_idx={node.get('block_index')} {node.get('numbering', '')} {node['title']} (level={node['level']}, source={node.get('source', 'N/A')})"
            logger.info(info)
            debug_log.write(info + "\n")
        debug_log.flush()
        
        try:
            added_count = _insert_directory_nodes(pool, project_id, directory_nodes)
            logger.info(f"[目录增强] 成功插入 {added_count} 个目录节点")
            debug_log.write(f"成功插入 {added_count} 个目录节点\n")
            debug_log.close()
        except Exception as e:
            import traceback
            logger.error(f"[目录增强] 目录节点入库失败: {e}")
            logger.error(f"[目录增强] 错误堆栈:\n{traceback.format_exc()}")
            debug_log.write(f"入库失败: {e}\n")
            debug_log.write(f"错误堆栈:\n{traceback.format_exc()}\n")
            debug_log.close()
            return {
                "existing_nodes_count": len(existing_nodes),
                "identified_required_count": len(directory_nodes),
                "added_count": 0,
                "enhanced_titles": [],
                "error": str(e)
            }
    else:
        debug_log.write(f"没有节点需要插入\n")
        debug_log.close()
    
    return {
        "existing_nodes_count": len(existing_nodes),
        "identified_required_count": len(directory_nodes),
        "added_count": added_count,
        "enhanced_titles": [n["title"] for n in directory_nodes[:20]]  # 最多显示20个
    }


def _empty_result(existing_count: int) -> Dict[str, Any]:
    """返回空结果"""
    return {
        "existing_nodes_count": existing_count,
        "identified_required_count": 0,
        "added_count": 0,
        "enhanced_titles": []
    }


def _get_tender_document_path(pool: Any, project_id: str) -> Optional[str]:
    """
    获取招标书文档路径
    
    从tender_project_assets表中查找招标书文档
    """
    from psycopg.rows import dict_row
    
    with pool.connection() as conn:
        conn.row_factory = dict_row
        with conn.cursor() as cur:
            # 从assets表查找招标书（优先docx，因为更容易解析）
            cur.execute("""
                SELECT storage_path, filename
                FROM tender_project_assets
                WHERE project_id = %s 
                AND kind = 'tender'
                AND storage_path IS NOT NULL
                ORDER BY 
                    CASE 
                        WHEN filename LIKE %s THEN 1
                        WHEN filename LIKE %s THEN 2
                        WHEN filename LIKE %s THEN 3
                        ELSE 4
                    END,
                    created_at DESC
                LIMIT 1
            """, (project_id, '%.docx', '%.doc', '%.pdf'))
            row = cur.fetchone()
            
            if row and row['storage_path']:
                # storage_path是相对路径，需要加上/app/前缀
                storage_path = row['storage_path']
                if not storage_path.startswith('/'):
                    storage_path = f"/app/{storage_path}"
                return storage_path
            
            logger.warning(f"[目录增强] 项目无招标书文档: {project_id}")
            return None


def _preprocess_tables_to_text(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    预处理：将目录表格转换为文本块
    
    策略：表格已经被extract_blocks解析为结构化的rows数组，
    我们只需要判断哪些表格是投标文件目录，然后转换为文本格式。
    同时，在表格前查找L1标题（如"技术资信标"、"（2）商务标"）。
    
    Args:
        blocks: 包含表格和文本的blocks列表
        
    Returns:
        处理后的blocks列表（表格转换为文本，可能插入L1标题）
    """
    import sys
    processed_blocks = []
    table_converted_count = 0
    
    print(f"[表格预处理] 开始处理 {len(blocks)} 个blocks", file=sys.stderr)
    
    for i, block in enumerate(blocks):
        if block['type'] == 'table':
            rows = block.get('rows', [])
            print(f"[表格预处理] 发现表格 at block {i}, rows数: {len(rows)}", file=sys.stderr)
            
            # 判断是否是投标文件目录表格
            if _is_directory_table(rows):
                print(f"[表格预处理] ✓ 是目录表格，开始转换", file=sys.stderr)
                logger.info(f"[表格预处理] 发现目录表格 at block {i}, 转换为文本")
                
                # 🔥 查找表格前的L1标题
                l1_title_text = _find_l1_title_before_table(blocks, i)
                l1_title_pure = None  # 提取纯标题（去除编号）
                
                if l1_title_text:
                    print(f"[表格预处理] 找到L1标题: {l1_title_text}", file=sys.stderr)
                    # 提取纯标题：去除"（1）"、"（2）"等编号
                    import re
                    match = re.match(r'^[（\(]\d+[）\)]\s*(.+)$', l1_title_text)
                    if match:
                        l1_title_pure = match.group(1).strip()
                    else:
                        l1_title_pure = l1_title_text.strip()
                    
                    processed_blocks.append({
                        "type": "p",
                        "text": l1_title_text,
                        "blockId": f"table{i}_l1_title",
                        "from_table": True,  # 标记为from_table
                        "suggested_level": 1  # 🔥 明确标记为L1
                    })
                
                # 🔥 转换为文本块，并传入L1纯标题用于建立父子关系
                text_blocks = _convert_table_rows_to_text_blocks(rows, i, l1_title_pure)
                print(f"[表格预处理] 转换得到 {len(text_blocks)} 个文本块", file=sys.stderr)
                processed_blocks.extend(text_blocks)
                table_converted_count += 1
            else:
                print(f"[表格预处理] ✗ 不是目录表格", file=sys.stderr)
                processed_blocks.append(block)
        else:
            processed_blocks.append(block)
    
    print(f"[表格预处理] 完成，共转换 {table_converted_count} 个表格", file=sys.stderr)
    if table_converted_count > 0:
        logger.info(f"[表格预处理] 共转换 {table_converted_count} 个目录表格")
    
    return processed_blocks


def _find_l1_title_before_table(blocks: List[Dict[str, Any]], table_index: int) -> str:
    """
    在表格前查找L1标题
    
    向前搜索最近5个blocks，查找：
    - 包含关键词："技术资信标"、"商务标"、"价格标"等
    - 文本较短（<20字符）
    - 如果已有"（1）"、"（2）"等编号，直接使用
    - 否则，根据表格顺序推断编号
    
    Returns:
        L1标题文本，如"（1）技术资信标"，如果未找到则返回None
    """
    keywords = ["技术资信标", "商务标", "资信标", "价格标", "报价标"]
    table_count = 0  # 当前是第几个表格
    
    # 统计table_index之前有多少个目录表格
    for j in range(table_index):
        if blocks[j]['type'] == 'table':
            rows = blocks[j].get('rows', [])
            if _is_directory_table(rows):
                table_count += 1
    
    # 向前搜索
    for j in range(max(0, table_index - 5), table_index):
        if blocks[j]['type'] != 'p':
            continue
        text = blocks[j].get('text', '').strip()
        if not text or len(text) > 30:  # 标题通常较短
            continue
        
        # 检查是否包含关键词
        for kw in keywords:
            if kw in text:
                # 如果已经有"（1）"、"（2）"等编号，直接返回
                if re.match(r'^[（\(]\d+[）\)]', text):
                    return text
                # 如果是纯标题（如"技术资信标"、"商务标"），添加编号
                if text in keywords:
                    return f"（{table_count + 1}）{text}"
                # 其他情况（如"3）商务标"），提取关键词并添加编号
                return f"（{table_count + 1}）{kw}"
    
    return None


def _is_directory_table(rows: List[List]) -> bool:
    """
    判断表格是否是投标文件目录表格
    
    特征：
    - 表头同时包含"序号"和"内容/名称"等关键词
    - 排除技术规格表（包含"规格"、"参数"、"型号"、"单位"、"数量"等）
    - 至少有2行（表头+内容）
    """
    if not rows or len(rows) < 2:
        return False
    
    # 检查表头
    header = [str(cell).lower().strip() for cell in rows[0]]
    header_text = ''.join(header)
    
    # 目录表格的特征关键词
    content_keywords = ['内容', '名称', '文件', '材料', '资料']
    number_keywords = ['序号', '编号', 'no']
    
    # 技术规格表的排除关键词
    spec_keywords = ['规格', '参数', '型号', '单位', '数量', '价格', '金额', '单价', '总价', '品牌', '厂家', '制造商']
    
    has_content = any(kw in header_text for kw in content_keywords)
    has_number = any(kw in header_text for kw in number_keywords)
    has_spec = any(kw in header_text for kw in spec_keywords)
    
    # 必须同时有"序号"和"内容/名称"，且不是技术规格表
    return has_content and has_number and not has_spec


def _convert_table_rows_to_text_blocks(rows: List[List], table_index: int, l1_title: str = None) -> List[Dict[str, Any]]:
    """
    将表格行转换为文本块，并建立层级关系
    
    策略：
    - 使用栈维护当前每个层级的父节点标题
    - 为每个节点设置parent_title，后续可直接使用
    
    Args:
        rows: 表格行数据
        table_index: 表格索引
        l1_title: L1标题（如"技术资信标"），用于设置L2节点的父节点
        
    Returns:
        包含parent_title的文本块列表
    """
    import sys
    if len(rows) < 2:
        return []
    
    # 找到"内容"列的索引
    header = [str(cell).strip() for cell in rows[0]]
    content_col_idx = _find_content_column_index(header)
    number_col_idx = 0  # 序号通常在第一列
    
    print(f"[表格转换] 表头: {header}, 内容列: {content_col_idx}", file=sys.stderr)
    
    # 🔥 维护层级栈：{level: title}
    parent_stack = {1: l1_title} if l1_title else {}
    
    text_blocks = []
    for row_idx, row in enumerate(rows[1:], 1):  # 跳过表头
        if not row or len(row) <= content_col_idx:
            continue
        
        # 提取编号和内容
        numbering = str(row[number_col_idx]).strip() if len(row) > number_col_idx else ""
        content = str(row[content_col_idx]).strip() if len(row) > content_col_idx else ""
        
        # 去除特殊字符（如▲表示重要性）
        numbering = numbering.replace('▲', '').strip()
        content = content.replace('▲', '').strip()
        
        if not content:
            continue
        
        # 组合成文本
        if numbering:
            text = f"{numbering} {content}"
        else:
            text = content
        
        # 🔥 根据编号格式推断层级
        suggested_level = _infer_level_from_numbering(numbering)
        
        # 🔥 确定父节点：查找栈中上一层的标题
        parent_title = None
        if suggested_level > 1:
            # 向上查找父层级
            for parent_level in range(suggested_level - 1, 0, -1):
                if parent_level in parent_stack:
                    parent_title = parent_stack[parent_level]
                    break
        
        # 🔥 更新栈：当前层级的标题
        parent_stack[suggested_level] = content
        # 清除比当前层级更深的层级
        for lv in list(parent_stack.keys()):
            if lv > suggested_level:
                del parent_stack[lv]
        
        print(f"[表格转换] 第{row_idx}行: {text} [L{suggested_level}, 父:{parent_title or 'ROOT'}]", file=sys.stderr)
        
        text_blocks.append({
            "type": "p",
            "text": text,
            "blockId": f"table{table_index}_row{row_idx}",
            "from_table": True,
            "suggested_level": suggested_level,
            "parent_title": parent_title  # 🔥 记录父节点标题
        })
    
    logger.info(f"[表格转换] 从表格提取 {len(text_blocks)} 个文本项")
    print(f"[表格转换] 完成，共 {len(text_blocks)} 个文本项", file=sys.stderr)
    return text_blocks


def _infer_level_from_numbering(numbering: str) -> int:
    """
    根据编号格式推断层级
    
    规则：
    - 空或无编号 → L2（默认）
    - 数字编号（1、2、3、1）、2）） → L2
    - 字母编号（a、b、A）、B）） → L3
    - 罗马数字（i、ii、iii） → L3
    """
    if not numbering:
        return 2
    
    # 提取编号主体（去除括号和标点）
    core = re.sub(r'[\)）\.\、\s]', '', numbering)
    
    # 字母编号
    if re.match(r'^[a-zA-Z]$', core):
        return 3
    
    # 罗马数字（小写）
    if re.match(r'^[ivxlcdm]+$', core.lower()) and len(core) <= 4:
        return 3
    
    # 数字编号
    if re.match(r'^\d+$', core):
        return 2
    
    # 默认L2
    return 2


def _find_content_column_index(header: List[str]) -> int:
    """
    找到"内容"列的索引
    
    优先级：内容 > 项目 > 名称 > 文件 > 默认第二列
    """
    keywords = ['内容', '项目', '名称', '文件', '材料']
    
    for i, col in enumerate(header):
        col_lower = col.lower()
        if any(kw in col_lower for kw in keywords):
            return i
    
    # 默认第二列（第一列通常是序号）
    return 1 if len(header) > 1 else 0


def _extract_directory_from_blocks(
    blocks: List[Dict[str, Any]], 
    existing_titles: set
) -> List[Dict[str, Any]]:
    """
    从blocks中提取目录结构（规则方法）
    
    策略：
    1. 优先提取表格转换的目录项（标记为from_table=True的块）
    2. 如果没有表格转换的项，则提取所有编号的文本
    3. 推断层级关系
    4. 过滤已存在的节点
    
    Args:
        blocks: 格式章节的blocks（可能包含表格转换后的文本块）
        existing_titles: 已存在的标题集合
        
    Returns:
        目录节点列表
    """
    # 1. 检查是否有表格转换的目录项
    has_table_items = any(b.get('from_table', False) for b in blocks if b.get('type') == 'p')
    
    if has_table_items:
        logger.info("[目录提取] 发现表格转换的目录项，提取表格项及其前后的L1标题")
    else:
        logger.info("[目录提取] 未发现表格目录，提取所有编号的文本项")
    
    # 2. 识别标题行
    title_candidates = []
    seen_titles = set()  # 用于去重
    first_l1_titles = set()  # 记录第一轮出现的L1标题
    
    for i, block in enumerate(blocks):
        if block["type"] != "p":
            continue
        
        text = block.get("text", "").strip()
        if not text:
            continue
        
        # 检查是否是标题（编号模式）
        numbering, title, level = _parse_title_line(text)
        
        if not numbering or not title:
            continue
        
        # 🔥 如果block有suggested_level（来自表格转换），优先使用
        if block.get('suggested_level'):
            level = block['suggested_level']
            logger.debug(f"[目录提取] 使用表格建议层级: {title} → L{level}")
        
        # 🔥 强制保留所有from_table的块（表格转换的目录项）
        is_from_table = block.get('from_table', False)
        
        # 🔥 如果有表格转换的项，**只**提取from_table=True的块
        if has_table_items:
            if not is_from_table:
                continue
        
        # 过滤：跳过太长的文本
        if len(text) > 100:
            continue
        
        # 过滤：跳过已存在的标题
        if title in existing_titles:
            continue
        
        # L1节点去重检查
        if level == 1:
            if title in first_l1_titles:
                logger.info(f"[目录提取] 遇到重复L1标题「{title}」，停止提取")
                break
            first_l1_titles.add(title)
        
        # 全局去重
        if title in seen_titles:
            continue
        
        seen_titles.add(title)
        
        title_candidates.append({
            "block_index": i,
            "numbering": numbering,
            "title": title,
            "level": level,
            "original_text": text,
            "block_id": block.get("blockId", f"b{i}"),
            "parent_title": block.get("parent_title")  # 🔥 传递parent_title
        })
        logger.debug(f"[目录提取] 添加候选: L{level} {numbering} {title[:30]}, 父:{block.get('parent_title', 'ROOT')}")
    
    logger.info(f"[目录提取] 识别到 {len(title_candidates)} 个标题候选")
    
    # 🔥 调试：打印候选节点的numbering
    import sys
    if title_candidates:
        print(f"[目录提取-DEBUG] 前5个候选节点的numbering:", file=sys.stderr)
        for i, cand in enumerate(title_candidates[:5]):
            print(f"  {i+1}. L{cand['level']} {cand['numbering']} - {cand['title'][:30]}", file=sys.stderr)
    
    # 2. 推断父子关系
    directory_nodes = _infer_parent_child_relations(title_candidates)
    
    # 🔥 调试：打印推断后的numbering
    if directory_nodes:
        print(f"[目录提取-DEBUG] 推断后前5个节点的numbering:", file=sys.stderr)
        for i, node in enumerate(directory_nodes[:5]):
            print(f"  {i+1}. L{node['level']} {node['numbering']} - {node['title'][:30]}", file=sys.stderr)
    
    return directory_nodes


def _parse_title_line(text: str) -> tuple:
    """
    解析标题行，提取编号、标题、层级
    
    支持的编号格式：
    - 一级：第一册、第二册、一、二、(一)、(二)
    - 二级：1.、2.、(1)、(2)、①、②
    - 三级：1.1、1.2、a)、b)
    
    Args:
        text: 标题文本
        
    Returns:
        (编号, 标题, 层级) 或 (None, None, 0)
    """
    text = text.strip()
    
    # 过滤1：太长的不是标题（超过60字符）
    if len(text) > 60:
        return None, None, 0
    
    # 过滤2：包含句号的通常是正文
    if '。' in text:
        return None, None, 0
    
    # 过滤3：包含冒号+长文本的通常是正文（如"项目名称：XXX"）
    # 但如果文本以编号开头（如"2）XXX："），则不过滤
    if ('：' in text or ':' in text) and len(text) > 20:
        # 检查是否以编号开头
        if not re.match(r'^([一二三四五六七八九十]+|[0-9]{1,2}|[a-zA-Z])[\)）\.\、]', text):
            return None, None, 0
    
    # 过滤4：标点密集的是正文
    punct_count = text.count('，') + text.count('。') + text.count('；') + text.count('、')
    if punct_count > 2:
        return None, None, 0
    
    # 过滤5：以动词开头的可能是正文（在、我、按、本等）
    if text.startswith(('在收到', '在签订', '在合同', '在投标', '按照', '我单位', '本协议', '联合体各', '联合体牵头')):
        return None, None, 0
    
    # 过滤6：包含"须"、"应"、"必须"等要求性词汇且较长的是正文
    if any(word in text for word in ['必须', '应当', '须']) and len(text) > 30:
        return None, None, 0
    
    # 模式1: "第X册/第X部分/第X章" - 1级
    match = re.match(r'^(第[一二三四五六七八九十百千万]+(?:册|部分|章|节))\s+(.+)$', text)
    if match:
        return match.group(1), match.group(2).strip(), 1
    
    # 模式2: "一、二、三、" - 1级（必须有顿号或空格）
    match = re.match(r'^([一二三四五六七八九十]+)[、\s](.+)$', text)
    if match and len(match.group(1)) <= 3:
        return match.group(1), match.group(2).strip(), 1
    
    # 模式3: "(一)(二)(三)" - 1级
    match = re.match(r'^[\(（]([一二三四五六七八九十]+)[\)）][、\s：:]*(.+)$', text)
    if match:
        return f"({match.group(1)})", match.group(2).strip(), 1
    
    # 模式4: "1.1 1.2" - 3级（必须先匹配，优先级高）
    match = re.match(r'^(\d{1,2}\.\d{1,2})\s+(.+)$', text)
    if match:
        return match.group(1), match.group(2).strip(), 3
    
    # 模式5: "1. 2. 3." - 2级（后面必须有点号或顿号）
    match = re.match(r'^(\d{1,2})[\.\、]\s*(.+)$', text)
    if match:
        return match.group(1), match.group(2).strip(), 2
    
    # 模式5b: "1）2）3）" - 2级（常见于表格导出的目录）
    match = re.match(r'^(\d{1,2})[\)）]\s*(.+)$', text)
    if match:
        return match.group(1) + ")", match.group(2).strip(), 2
    
    # 模式6: "(1)(2)(3)" - 2级（半角括号）
    match = re.match(r'^[\(](\d{1,2})[\)][、\s：:]*(.+)$', text)
    if match:
        return f"({match.group(1)})", match.group(2).strip(), 2
    
    # 模式7: "（1）（2）（3）" - 1级（全角括号，常见于大标题）
    match = re.match(r'^[（](\d{1,2})[）]\s*(.+)$', text)
    if match:
        return f"（{match.group(1)}）", match.group(2).strip(), 1
    
    # 模式8: "①②③" - 2级
    match = re.match(r'^([①②③④⑤⑥⑦⑧⑨⑩])\s*(.+)$', text)
    if match:
        return match.group(1), match.group(2).strip(), 2
    
    # 模式9: "a) b) c)" 或 "A) B) C)" - 3级（支持大小写）
    match = re.match(r'^([a-zA-Z])[\)）\.][\s：:]*(.+)$', text)
    if match:
        return match.group(1) + ")", match.group(2).strip(), 3
    
    # 未匹配到编号模式
    return None, None, 0


def _infer_parent_child_relations(
    title_candidates: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    推断父子关系，构建层级结构，并按照树的深度优先遍历顺序返回
    
    优先使用parent_title（表格转换时已建立的关系），
    否则使用栈来跟踪父节点
    """
    if not title_candidates:
        return []
    
    title_to_node = {}  # title -> node_dict
    title_to_children = {}  # title -> [child_nodes]
    stack = []  # [(level, node_dict)]
    roots = []  # 根节点列表
    
    for candidate in title_candidates:
        level = candidate["level"]
        title = candidate["title"]
        parent_title = candidate.get("parent_title")
        
        # 创建节点
        node = {
            "numbering": candidate["numbering"],
            "title": title,
            "level": level,
            "parent_id": None,
            "parent_ref": None,
            "is_required": True,
            "source": "format_chapter_extracted",
            "evidence_chunk_ids": [candidate["block_id"]],
            "meta_json": {
                "original_text": candidate["original_text"],
                "block_index": candidate["block_index"]
            }
        }
        
        # 🔥 使用parent_title建立关系
        if parent_title and parent_title in title_to_node:
            node["parent_ref"] = parent_title
            # 将当前节点添加到父节点的children列表
            title_to_children.setdefault(parent_title, []).append(node)
        else:
            # fallback：使用栈推断
            while stack and stack[-1][0] >= level:
                stack.pop()
            if stack:
                parent_node = stack[-1][1]
                node["parent_ref"] = parent_node["title"]
                title_to_children.setdefault(parent_node["title"], []).append(node)
            else:
                # 无父节点，是根节点
                roots.append(node)
        
        title_to_node[title] = node
        stack.append((level, node))
    
    # 🔥 按照深度优先遍历顺序返回
    result = []
    def dfs(node):
        result.append(node)
        children = title_to_children.get(node["title"], [])
        for child in children:
            dfs(child)
    
    for root in roots:
        dfs(root)
    
    return result


def _insert_directory_nodes(
    pool: Any, 
    project_id: str, 
    nodes: List[Dict[str, Any]]
) -> int:
    """
    插入目录节点到数据库
    
    Returns:
        成功插入的节点数
    """
    if not nodes:
        return 0
    
    # 🔥 步骤1：先为所有节点生成id
    for node in nodes:
        if "id" not in node:
            node["id"] = str(uuid.uuid4())
    
    # 🔥 步骤2：创建title -> node的映射
    title_to_node = {n["title"]: n for n in nodes}
    
    # 🔥 步骤3：为每个节点设置parent_id
    import sys
    parent_set_count = 0
    for node in nodes:
        parent_ref = node.get("parent_ref")
        print(f"[目录保存] 节点: {node['title'][:30]}, parent_ref={parent_ref[:20] if parent_ref else 'None'}", file=sys.stderr)
        if parent_ref and parent_ref in title_to_node:
            parent_node = title_to_node[parent_ref]
            node["parent_id"] = parent_node["id"]
            parent_set_count += 1
            print(f"[目录保存] ✓ 设置父节点: {node['title'][:20]} -> {parent_ref[:20]}", file=sys.stderr)
        elif parent_ref:
            print(f"[目录保存] ✗ 父节点'{parent_ref}'未找到，节点: {node['title'][:30]}", file=sys.stderr)
    
    print(f"[目录保存] 成功设置{parent_set_count}/{len(nodes)}个节点的parent_id", file=sys.stderr)
    
    added_count = 0
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            # 获取最大 order_no（不使用dict_row，直接取tuple）
            cur.execute(
                "SELECT COALESCE(MAX(order_no), 0) FROM tender_directory_nodes WHERE project_id = %s",
                (project_id,)
            )
            result = cur.fetchone()
            # result可能是tuple或dict，需要判断
            logger.info(f"[目录增强-DEBUG] fetchone result: {result}, type={type(result)}")
            
            if isinstance(result, dict):
                # 如果是dict，取字典的第一个值
                max_order = list(result.values())[0] if result else 0
            elif isinstance(result, (tuple, list)):
                # 如果是tuple或list，取第一个元素
                max_order = result[0] if result and len(result) > 0 else 0
            else:
                # 其他情况，默认0
                max_order = 0
            
            for i, node in enumerate(nodes):
                # 🔥 使用node已有的id，如果没有才生成（但前面已经确保有了）
                node_id = node.get("id") or str(uuid.uuid4())
                order_no = max_order + i + 1
                
                try:
                    import json
                    cur.execute("""
                        INSERT INTO tender_directory_nodes (
                            id, project_id, parent_id, order_no, level,
                            numbering, title, is_required, source,
                            evidence_chunk_ids, meta_json
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        node_id,
                        project_id,
                        node.get("parent_id"),  # 🔥 使用已设置的parent_id
                        order_no,
                        node.get("level", 2),
                        node.get("numbering", ""),
                        node["title"],
                        node.get("is_required", True),
                        node.get("source", "format_chapter_extracted"),
                        node.get("evidence_chunk_ids", []),  # 直接传list，PostgreSQL会转为array
                        json.dumps(node.get("meta_json", {}))  # jsonb用json.dumps
                    ))
                    added_count += 1
                except Exception as e:
                    import traceback
                    logger.error(f"[目录增强] 插入节点失败: {node['title']}, 错误: {e}")
                    logger.error(f"[目录增强] 错误堆栈: {traceback.format_exc()}")
                    continue
        
        conn.commit()
    
    return added_count


def _extract_directory_with_llm(
    blocks: List[Dict[str, Any]],
    existing_titles: set,
    project_id: str,
    pool: Any
) -> List[Dict[str, Any]]:
    """
    用LLM从格式章节提取目录（兜底方案）
    
    当规则方法无法提取时，使用LLM理解文本内容
    """
    # 将blocks转换为文本
    text_content = []
    for block in blocks[:50]:  # 限制前50个blocks
        if block["type"] == "p":
            text = block.get("text", "").strip()
            if text:
                text_content.append(text)
    
    if not text_content:
        return []
    
    full_text = "\n".join(text_content)
    
    # 构建LLM提示
    prompt = f"""请从以下招标文件内容中提取投标文件目录结构。

要求：
1. 只提取目录项，不要提取说明性文字
2. 保持原始编号和标题
3. 识别层级关系（1级、2级、3级）
4. 输出JSON格式

内容：
{full_text[:2000]}

请输出JSON数组，格式如下：
[
  {{"numbering": "一", "title": "资格证明文件", "level": 1}},
  {{"numbering": "1", "title": "营业执照", "level": 2}},
  ...
]
"""
    
    try:
        # 调用LLM（注意：这里需要传入LLM实例，暂时跳过）
        # TODO: 需要从外层传入llm实例
        logger.info(f"[目录增强] LLM提取功能需要LLM实例支持，暂时跳过")
        return []
        
        # 以下代码待启用
        # from app.llm.orchestrator import LLMOrchestrator
        # llm = LLMOrchestrator()
        # 
        # response = llm.complete(
        #     prompt=prompt,
        #     model_id="gpt-4",
        #     temperature=0.1
        # )
        
        # 解析JSON
        import json
        import re
        
        # 提取JSON部分
        json_match = re.search(r'\[[\s\S]*\]', response)
        if json_match:
            nodes_data = json.loads(json_match.group(0))
            
            # 转换为标准格式
            result = []
            for node in nodes_data:
                if node.get("title") and node["title"] not in existing_titles:
                    result.append({
                        "numbering": node.get("numbering", ""),
                        "title": node["title"],
                        "level": node.get("level", 2),
                        "is_required": True,
                        "source": "format_chapter_llm_extracted",
                        "evidence_chunk_ids": [],
                        "meta_json": {"extraction_method": "llm"}
                    })
            
            return result
        
    except Exception as e:
        logger.warning(f"[目录增强] LLM提取失败: {e}")
    
    return []


def _get_existing_directory_nodes(pool: Any, project_id: str) -> List[Dict[str, Any]]:
    """获取现有目录节点"""
    from psycopg.rows import dict_row
    
    with pool.connection() as conn:
        conn.row_factory = dict_row
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

