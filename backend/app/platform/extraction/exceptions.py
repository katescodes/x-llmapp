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
