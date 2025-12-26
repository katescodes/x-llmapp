"""
测试前端类型定义和迁移指南
"""
import pytest
from pathlib import Path


def test_frontend_types_file_exists():
    """测试前端类型定义文件存在"""
    file_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "types" / "tenderInfoV3.ts"
    assert file_path.exists(), f"tenderInfoV3.ts 不存在: {file_path}"


def test_frontend_migration_guide_exists():
    """测试前端迁移指南文件存在"""
    file_path = Path(__file__).parent.parent.parent / "frontend" / "TENDER_INFO_V3_MIGRATION.md"
    assert file_path.exists(), f"TENDER_INFO_V3_MIGRATION.md 不存在: {file_path}"


def test_tender_info_v3_type_definition():
    """测试 TenderInfoV3 类型定义包含九大类"""
    file_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "types" / "tenderInfoV3.ts"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证九大类接口定义
    assert "interface ProjectOverview" in content
    assert "interface ScopeAndLots" in content
    assert "interface ScheduleAndSubmission" in content
    assert "interface BidderQualification" in content
    assert "interface EvaluationAndScoring" in content
    assert "interface BusinessTerms" in content
    assert "interface TechnicalRequirements" in content
    assert "interface DocumentPreparation" in content
    assert "interface BidSecurity" in content
    
    # 验证顶层接口
    assert "interface TenderInfoV3" in content
    assert "schema_version" in content


def test_tender_info_v3_categories_constant():
    """测试类别常量定义"""
    file_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "types" / "tenderInfoV3.ts"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证类别常量
    assert "TENDER_INFO_V3_CATEGORIES" in content
    
    # 验证包含所有九个类别
    assert "project_overview" in content
    assert "scope_and_lots" in content
    assert "schedule_and_submission" in content
    assert "bidder_qualification" in content
    assert "evaluation_and_scoring" in content
    assert "business_terms" in content
    assert "technical_requirements" in content
    assert "document_preparation" in content
    assert "bid_security" in content


def test_tender_info_v3_category_labels():
    """测试类别标签映射"""
    file_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "types" / "tenderInfoV3.ts"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证类别标签
    assert "TENDER_INFO_V3_CATEGORY_LABELS" in content
    
    # 验证中文标签
    assert "项目概况" in content
    assert "范围与标段" in content
    assert "进度与提交" in content
    assert "投标人资格" in content
    assert "评审与评分" in content
    assert "商务条款" in content
    assert "技术要求" in content
    assert "文件编制" in content
    assert "投标保证金" in content


def test_type_guard_function():
    """测试类型守卫函数"""
    file_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "types" / "tenderInfoV3.ts"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证类型守卫函数
    assert "isTenderInfoV3" in content
    assert "is TenderInfoV3" in content
    assert "tender_info_v3" in content


def test_evidence_chunk_ids_in_types():
    """测试所有类别都包含 evidence_chunk_ids"""
    file_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "types" / "tenderInfoV3.ts"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证 evidence_chunk_ids 字段
    assert "evidence_chunk_ids" in content
    # 应该出现多次（每个类别一次）
    assert content.count("evidence_chunk_ids") >= 9


def test_migration_guide_content():
    """测试迁移指南包含关键内容"""
    file_path = Path(__file__).parent.parent.parent / "frontend" / "TENDER_INFO_V3_MIGRATION.md"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证包含迁移步骤
    assert "迁移步骤" in content or "Migration" in content
    
    # 验证包含代码示例
    assert "```typescript" in content or "```ts" in content
    
    # 验证包含九大类说明
    assert "项目概况" in content
    assert "九大类" in content or "9" in content
    
    # 验证包含向后兼容性说明
    assert "向后兼容" in content or "兼容性" in content


def test_migration_guide_api_examples():
    """测试迁移指南包含 API 示例"""
    file_path = Path(__file__).parent.parent.parent / "frontend" / "TENDER_INFO_V3_MIGRATION.md"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证包含 API 路由
    assert "/api/projects" in content or "project-info" in content
    
    # 验证包含 schema_version
    assert "schema_version" in content
    assert "tender_info_v3" in content


def test_migration_guide_component_examples():
    """测试迁移指南包含组件示例"""
    file_path = Path(__file__).parent.parent.parent / "frontend" / "TENDER_INFO_V3_MIGRATION.md"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证包含组件名称
    assert "Component" in content or "组件" in content
    
    # 验证包含 useState 或类似的 React hooks
    assert "useState" in content or "state" in content


def test_typescript_export_statements():
    """测试 TypeScript 导出语句"""
    file_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "types" / "tenderInfoV3.ts"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证导出语句
    assert "export interface" in content or "export type" in content
    assert "export function" in content or "export const" in content


def test_optional_fields_in_types():
    """测试类型定义中的可选字段"""
    file_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "types" / "tenderInfoV3.ts"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证使用了可选标记 ?
    assert "?" in content
    # 应该有大量可选字段
    assert content.count("?:") > 50


def test_migration_guide_search_keywords():
    """测试迁移指南包含搜索关键字"""
    file_path = Path(__file__).parent.parent.parent / "frontend" / "TENDER_INFO_V3_MIGRATION.md"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证包含旧字段名（用于搜索）
    assert "base" in content or "technical_parameters" in content or "business_terms" in content


def test_api_response_type():
    """测试 API 响应类型定义"""
    file_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "types" / "tenderInfoV3.ts"
    content = file_path.read_text(encoding="utf-8")
    
    # 验证 API 响应类型
    assert "TenderProjectInfoResponse" in content or "Response" in content
    assert "data_json" in content
    assert "project_id" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

