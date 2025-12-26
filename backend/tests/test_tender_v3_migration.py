"""
Test Database Migration for Step 2

测试 028_add_tender_v3_tables.sql 迁移文件的语法和结构
"""
import pytest
from pathlib import Path


def test_migration_file_exists():
    """测试迁移文件存在"""
    migration_file = Path(__file__).parent.parent.parent / "backend" / "migrations" / "028_add_tender_v3_tables.sql"
    assert migration_file.exists(), f"Migration file not found: {migration_file}"


def test_migration_file_not_empty():
    """测试迁移文件不为空"""
    migration_file = Path(__file__).parent.parent.parent / "backend" / "migrations" / "028_add_tender_v3_tables.sql"
    content = migration_file.read_text(encoding="utf-8")
    assert len(content) > 100, "Migration file is too short"


def test_migration_file_has_required_tables():
    """测试迁移文件包含所需的表"""
    migration_file = Path(__file__).parent.parent.parent / "backend" / "migrations" / "028_add_tender_v3_tables.sql"
    content = migration_file.read_text(encoding="utf-8")
    
    # 检查四个新表
    assert "CREATE TABLE IF NOT EXISTS tender_requirements" in content
    assert "CREATE TABLE IF NOT EXISTS tender_rule_packs" in content
    assert "CREATE TABLE IF NOT EXISTS tender_rules" in content
    assert "CREATE TABLE IF NOT EXISTS tender_bid_response_items" in content


def test_migration_file_has_alter_statements():
    """测试迁移文件包含 ALTER 语句（扩展现有表）"""
    migration_file = Path(__file__).parent.parent.parent / "backend" / "migrations" / "028_add_tender_v3_tables.sql"
    content = migration_file.read_text(encoding="utf-8")
    
    # 检查扩展 tender_review_items 表
    assert "ALTER TABLE tender_review_items" in content
    assert "ADD COLUMN IF NOT EXISTS rule_id" in content
    assert "ADD COLUMN IF NOT EXISTS requirement_id" in content
    assert "ADD COLUMN IF NOT EXISTS severity" in content
    assert "ADD COLUMN IF NOT EXISTS evaluator" in content


def test_migration_file_has_indexes():
    """测试迁移文件包含必要的索引"""
    migration_file = Path(__file__).parent.parent.parent / "backend" / "migrations" / "028_add_tender_v3_tables.sql"
    content = migration_file.read_text(encoding="utf-8")
    
    # 检查关键索引
    assert "idx_tender_requirements_project" in content
    assert "idx_tender_requirements_dimension" in content
    assert "idx_tender_rule_packs_project" in content
    assert "idx_tender_rules_pack" in content
    assert "idx_tender_rules_key" in content
    assert "idx_tender_bid_response_project" in content
    assert "idx_tender_bid_response_bidder" in content
    assert "idx_tender_review_rule" in content
    assert "idx_tender_review_requirement" in content


def test_migration_file_uses_if_not_exists():
    """测试迁移文件使用 IF NOT EXISTS（幂等性）"""
    migration_file = Path(__file__).parent.parent.parent / "backend" / "migrations" / "028_add_tender_v3_tables.sql"
    content = migration_file.read_text(encoding="utf-8")
    
    # 检查幂等性
    assert "IF NOT EXISTS" in content
    assert content.count("IF NOT EXISTS") >= 8  # 至少8个地方使用


def test_migration_file_has_foreign_keys():
    """测试迁移文件包含外键约束"""
    migration_file = Path(__file__).parent.parent.parent / "backend" / "migrations" / "028_add_tender_v3_tables.sql"
    content = migration_file.read_text(encoding="utf-8")
    
    # 检查外键
    assert "REFERENCES tender_projects(id) ON DELETE CASCADE" in content
    assert "REFERENCES tender_rule_packs(id) ON DELETE CASCADE" in content


def test_migration_file_has_comments():
    """测试迁移文件包含注释（说明文档）"""
    migration_file = Path(__file__).parent.parent.parent / "backend" / "migrations" / "028_add_tender_v3_tables.sql"
    content = migration_file.read_text(encoding="utf-8")
    
    # 检查注释
    assert "COMMENT ON TABLE tender_requirements" in content
    assert "COMMENT ON TABLE tender_rule_packs" in content
    assert "COMMENT ON TABLE tender_rules" in content
    assert "COMMENT ON TABLE tender_bid_response_items" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

