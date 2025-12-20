"""
语义目录生成服务包 - SHIM
真实实现已迁移到 app.works.tender.outline
此文件仅保留向后兼容
"""
from app.works.tender.outline.requirement_extraction_service import RequirementExtractionService
from app.works.tender.outline.outline_synthesis_service import OutlineSynthesisService

__all__ = ["RequirementExtractionService", "OutlineSynthesisService"]
