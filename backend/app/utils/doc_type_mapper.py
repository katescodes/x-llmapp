"""
文档类型映射工具
用于将应用内的文档类型映射到知识库的标准分类
"""
from app.schemas.types import KbCategory


def map_doc_type_to_kb_category(doc_type: str, context: str = "") -> KbCategory:
    """
    将文档类型映射到知识库分类
    
    Args:
        doc_type: 文档类型（应用内定义）
        context: 上下文信息（可选，用于更精确的映射）
    
    Returns:
        知识库分类
    """
    # 招投标应用映射
    tender_mapping = {
        "tender": "tender_notice",      # 招标文件
        "bid": "bid_document",           # 投标文件
        "template": "format_template",   # 格式模板
        "custom_rule": "reference_rule", # 自定义规则 -> 规章制度
    }
    
    # 用户文档映射
    user_doc_mapping = {
        "tender_user_doc": "technical_material",  # 默认为技术资料
        "technical": "technical_material",         # 技术资料
        "qualification": "qualification_doc",      # 资质资料
        "standard": "standard_spec",               # 标准规范
    }
    
    # 申报应用映射
    declare_mapping = {
        "declare_notice": "tender_notice",         # 申报通知 -> 招标文件（复用）
        "declare_company": "qualification_doc",    # 企业信息 -> 资质资料
        "declare_tech": "technical_material",      # 技术资料
        "declare_other": "general_doc",            # 其他
    }
    
    # 合并所有映射
    all_mappings = {
        **tender_mapping,
        **user_doc_mapping,
        **declare_mapping,
    }
    
    # 查找映射
    if doc_type in all_mappings:
        return all_mappings[doc_type]
    
    # 特殊处理：根据上下文推断
    if context:
        context_lower = context.lower()
        if "qualification" in context_lower or "资质" in context_lower:
            return "qualification_doc"
        elif "technical" in context_lower or "技术" in context_lower:
            return "technical_material"
        elif "standard" in context_lower or "标准" in context_lower or "规范" in context_lower:
            return "standard_spec"
        elif "template" in context_lower or "模板" in context_lower:
            return "format_template"
    
    # 默认返回普通文档
    return "general_doc"


def get_kb_category_display_name(category: KbCategory) -> str:
    """
    获取知识库分类的显示名称
    
    Args:
        category: 知识库分类
    
    Returns:
        显示名称
    """
    display_names = {
        "general_doc": "普通文档",
        "history_case": "历史案例",
        "reference_rule": "规章制度",
        "web_snapshot": "网页快照",
        "tender_app": "招投标文档",
        "tender_notice": "招标文件",
        "bid_document": "投标文件",
        "format_template": "格式模板",
        "standard_spec": "标准规范",
        "technical_material": "技术资料",
        "qualification_doc": "资质资料",
    }
    return display_names.get(category, "未知分类")

