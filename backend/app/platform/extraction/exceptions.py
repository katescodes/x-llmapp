"""
Platform Extraction Exceptions
抽取引擎的异常类型
"""


class ExtractionParseError(Exception):
    """JSON 解析失败异常"""
    def __init__(self, message: str, raw_output: str = ""):
        super().__init__(message)
        self.raw_output = raw_output
        self.error_type = "ExtractionParseError"


class ExtractionSchemaError(Exception):
    """Schema 验证失败异常"""
    def __init__(self, message: str, schema_errors: list = None, raw_data: dict = None):
        super().__init__(message)
        self.schema_errors = schema_errors or []
        self.raw_data = raw_data
        self.error_type = "ExtractionSchemaError"


class PromptNotFoundError(Exception):
    """Prompt未在数据库中找到的异常"""
    def __init__(self, module_name: str):
        self.module_name = module_name
        self.message = (
            f"未找到模块 '{module_name}' 的活跃Prompt模板。\n"
            f"请在【系统设置 → Prompts】中配置该模块的Prompt模板。"
        )
        super().__init__(self.message)
        self.error_type = "PromptNotFoundError"
