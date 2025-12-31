from typing import Literal


# Unified kb document categories so ORM/routers/frontend share the same literal type.
# 知识库文档分类：
# - general_doc: 普通文档
# - history_case: 历史案例
# - reference_rule: 规章制度
# - web_snapshot: 网页快照
# - tender_app: 招投标文档（旧，保留兼容）
# - tender_notice: 招标文件
# - bid_document: 投标文件
# - format_template: 格式模板
# - standard_spec: 标准规范
# - technical_material: 技术资料
# - qualification_doc: 资质资料
KbCategory = Literal[
    "general_doc",
    "history_case", 
    "reference_rule", 
    "web_snapshot", 
    "tender_app",
    "tender_notice",
    "tender_doc",      # 招标文档（新）
    "bid_document",
    "bid_doc",         # 投标文档（新）
    "custom_rule",     # 自定义规则（新）
    "template_doc",    # 模板文档（新）
    "format_template",
    "standard_spec",
    "technical_material",
    "qualification_doc"
]



