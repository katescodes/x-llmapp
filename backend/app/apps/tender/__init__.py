"""
Apps Tender Shim - 向后兼容层
实际实现已迁移到 app.works.tender

从 Step 5 开始，tender 作为正式的 Work 实现，位于 works/tender
此目录仅为向后兼容保留
"""
# Re-export from works.tender
from app.works.tender.extract_v2_service import ExtractV2Service
from app.works.tender.review_v2_service import ReviewV2Service  
from app.works.tender.extract_diff import compare_project_info, compare_risks
from app.works.tender.review_diff import compare_review_results

__all__ = [
    "ExtractV2Service",
    "ReviewV2Service",
    "compare_project_info",
    "compare_risks",
    "compare_review_results",
]
