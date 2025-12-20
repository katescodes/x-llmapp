"""
模板抽取服务包
从招标书blocks自动抽取投标文件格式/样表/范本
"""
from app.services.template_extract.candidate_recall_service import TemplateCandidateRecallService
from app.services.template_extract.coverage_guard_service import TemplateCoverageGuard
from app.services.template_extract.llm_span_service import LlmTemplateSpanService
from app.services.template_extract.orchestrator_service import TemplateExtractOrchestrator
from app.services.template_extract.span_refiner_service import TemplateSpanRefiner

__all__ = [
    "TemplateCandidateRecallService",
    "TemplateCoverageGuard",
    "LlmTemplateSpanService",
    "TemplateExtractOrchestrator",
    "TemplateSpanRefiner",
]

