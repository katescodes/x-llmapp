"""
范本章节定位器
在招标文件中定位"格式范本"章节，减少LLM处理范围
"""
from __future__ import annotations
import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# 组合匹配方案：文件类型词 + 格式词
FILE_TYPE_KEYWORDS = [
    "投标", "响应", "应答", "磋商", "竞谈",
    "投标文件", "响应文件", "应答文件", "磋商文件", "竞谈文件"
]

FORMAT_KEYWORDS = [
    "格式", "样式", "范本", "模板", "编制", "组成"
]

# 备用精确匹配关键词（降级策略）
FALLBACK_KEYWORDS = [
    "第六章",
    "投标文件的编制",  # 新增：测试4的格式
    "投标文件编制",
    "投标文件的组成",
    "附件",
    "格式附件"
]

# 范本结束标志
FORMAT_CHAPTER_END_KEYWORDS = [
    "第七章",
    "第八章",
    "评分标准",
    "评审办法",
    "合同条款"
]


def _is_format_chapter_title(text: str) -> bool:
    """
    判断文本是否为格式章节标题（组合匹配）
    
    策略：同时包含"文件类型词"和"格式词"
    例如：投标文件格式、磋商响应文件编制要求、报价文件组成
    
    Args:
        text: 待检查的文本
        
    Returns:
        是否为格式章节标题
    """
    # 组合匹配：文件类型 + 格式
    has_file_type = any(keyword in text for keyword in FILE_TYPE_KEYWORDS)
    has_format = any(keyword in text for keyword in FORMAT_KEYWORDS)
    
    if has_file_type and has_format:
        return True
    
    # 降级：备用关键词
    for keyword in FALLBACK_KEYWORDS:
        if keyword in text:
            return True
    
    return False


def locate_format_chapter(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    在 blocks 中定位"格式范本"章节
    
    策略：
    1. 使用组合匹配查找所有候选标题：文件类型词 + 格式词
    2. 对每个候选，检查后续30个块中：
       - 文本段落中的编号目录项（一、二、三...或1)、2)...）
       - 表格中的目录项（判断表格是否是投标文件目录表格）
    3. 选择"目录得分最高"的候选（内容最丰富）
    4. 从该块开始，直到遇到结束标志或文档结尾
    5. 返回范围内的所有 blocks
    
    Args:
        blocks: 完整的文档 blocks
        
    Returns:
        格式章节内的 blocks
    """
    if not blocks:
        logger.warning("blocks 为空，返回空列表")
        return []
    
    logger.info(f"开始定位格式章节（组合匹配+表格检测），总块数: {len(blocks)}")
    
    # 1. 查找所有候选起始位置
    candidates = []
    for i, block in enumerate(blocks):
        if block["type"] != "p":
            continue
        
        text = block.get("text", "").strip()
        if not text:
            continue
        
        # 检查是否是格式章节标题（标题通常较短）
        if len(text) < 100 and _is_format_chapter_title(text):
            page_no = block.get("pageNo", 0)
            
            # 检查后续30个块中的目录内容
            dir_score = _calculate_directory_score(blocks, i)
            
            candidates.append((i, text, page_no, dir_score))
            logger.info(f"候选章节: block[{i}] (页{page_no}) 目录得分={dir_score} = '{text[:50]}'")
    
    # 如果没找到，返回全部（降级策略）
    if not candidates:
        logger.warning("⚠️ 未找到格式章节标题，返回全部 blocks")
        return blocks
    
    # 2. 选择最佳候选
    # 策略：
    # - 优先选择明确的格式章节标题（"投标文件的编制"、"第六章"等）
    # - 如果得分差距不大（<10分），选择标题更明确的
    candidates.sort(key=lambda x: (x[3], x[2]), reverse=True)
    
    # 检查是否有明确标题的候选
    explicit_titles = ["投标文件的编制", "投标文件编制", "第六章", "第三部分   附件"]
    best_explicit = None
    for i, text, page, score in candidates:
        if any(title in text for title in explicit_titles):
            best_explicit = (i, text, page, score)
            break
    
    # 如果最高分候选和明确标题候选得分差距<30分，选明确标题的
    start_idx, start_text, start_page, dir_score = candidates[0]
    if best_explicit and best_explicit[3] >= 15 and (dir_score - best_explicit[3]) < 30:
        start_idx, start_text, start_page, dir_score = best_explicit
        logger.info(f"🎯 选择明确标题的候选（得分虽低但标题明确）")
    
    logger.info(f"✅ 选择格式章节起始: block[{start_idx}] (页{start_page}) 目录得分={dir_score} = '{start_text[:50]}'")
    
    # 3. 查找结束位置
    end_idx = len(blocks)
    for i in range(start_idx + 1, len(blocks)):
        block = blocks[i]
        if block["type"] != "p":
            continue
        
        text = block.get("text", "").strip()
        if not text:
            continue
        
        # 检查是否是结束标志
        for keyword in FORMAT_CHAPTER_END_KEYWORDS:
            if text.startswith(keyword) or keyword in text[:20]:
                end_idx = i
                logger.info(f"找到格式章节结束: block[{i}] = '{text[:50]}'")
                break
        
        if end_idx < len(blocks):
            break
    
    # 4. 返回范围内的 blocks
    chapter_blocks = blocks[start_idx:end_idx]
    logger.info(f"格式章节定位完成: block[{start_idx}:{end_idx}]，共 {len(chapter_blocks)} 个块")
    
    return chapter_blocks


def _calculate_directory_score(blocks: List[Dict[str, Any]], start_idx: int) -> int:
    """
    计算从 start_idx 开始的章节中的目录内容得分
    
    策略：
    - 文本段落中的编号目录项：+1分
    - 投标文件目录表格：+20分（表格通常包含很多目录项）
    
    Args:
        blocks: 完整的文档 blocks
        start_idx: 候选章节的起始索引
        
    Returns:
        目录得分
    """
    score = 0
    check_range = min(start_idx + 30, len(blocks))
    
    for j in range(start_idx + 1, check_range):
        block = blocks[j]
        
        if block["type"] == "p":
            # 文本段落：检查是否是编号目录项
            text = block.get("text", "").strip()
            # 匹配：一、二、三...或 1)、2)、3)...或 1.、2.、3.
            if re.match(r'^([一二三四五六七八九十]+|[0-9]{1,2})[\)、．\.]', text):
                score += 1
        
        elif block["type"] == "table":
            # 表格：检查是否是投标文件目录表格
            rows = block.get("rows", [])
            if _is_directory_table(rows):
                # 目录表格给高分（一个表格通常包含10+个目录项）
                score += 20
                logger.info(f"  发现目录表格 at block[{j}]，得分+20")
    
    return score


def _is_directory_table(rows: List[List]) -> bool:
    """
    判断表格是否是投标文件目录表格
    
    特征：
    - 表头包含"内容"、"项目"、"名称"、"序号"等关键词
    - 至少有5行（表头+足够的内容行）
    - 排除：表头包含"业绩"、"产品"、"合同"、"金额"等业务表格关键词
    """
    if not rows or len(rows) < 5:
        return False
    
    # 检查表头
    header = [str(cell).lower().strip() for cell in rows[0]]
    header_text = ''.join(header)
    
    # 目录表格的特征关键词
    content_keywords = ['内容', '材料', '资料']  # 移除'项目'和'名称'以避免误判
    number_keywords = ['序号', '编号']
    
    has_content = any(kw in header_text for kw in content_keywords)
    has_number = any(kw in header_text for kw in number_keywords)
    
    # 排除业务表格
    exclude_keywords = ['业绩', '产品', '合同', '金额', '单价', '服务内容', '用户单位', '参数', '规格', '品牌']
    if any(kw in header_text for kw in exclude_keywords):
        return False
    
    return has_content and has_number  # 必须同时有"内容"和"序号"


def is_heading_block(block: Dict[str, Any]) -> bool:
    """
    判断一个 block 是否可能是标题
    
    Args:
        block: block 字典
        
    Returns:
        是否是标题
    """
    if block["type"] != "p":
        return False
    
    text = block.get("text", "").strip()
    if not text:
        return False
    
    # 标题特征
    # 1. 较短（<100字符）
    if len(text) > 100:
        return False
    
    # 2. 样式名包含"标题"或"Heading"
    style_name = block.get("styleName", "")
    if style_name and ("标题" in style_name or "Heading" in style_name.lower()):
        return True
    
    # 3. 包含章节编号
    if re.match(r'^[\d一二三四五六七八九十]+[、\.)：]', text):
        return True
    
    # 4. 全是数字或简短标题
    if re.match(r'^\d+\.?\d*$', text):  # 纯数字
        return True
    
    return False


def extract_heading_hierarchy(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    提取文档的标题层级结构（用于辅助定位）
    
    Args:
        blocks: 文档 blocks
        
    Returns:
        标题 blocks 列表（包含索引信息）
    """
    headings = []
    
    for i, block in enumerate(blocks):
        if is_heading_block(block):
            headings.append({
                "index": i,
                "blockId": block["blockId"],
                "text": block.get("text", "").strip(),
                "styleName": block.get("styleName")
            })
    
    logger.debug(f"提取标题层级: {len(headings)} 个标题")
    return headings

