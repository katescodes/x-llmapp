#!/usr/bin/env python3
"""
数据库Schema验证脚本 - Step 2

验证 028_add_tender_v3_tables.sql 迁移是否正确执行
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.db.postgres import get_conn


def check_table_exists(cursor, table_name: str) -> bool:
    """检查表是否存在"""
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = %s
        );
    """, (table_name,))
    return cursor.fetchone()[0]


def check_column_exists(cursor, table_name: str, column_name: str) -> bool:
    """检查列是否存在"""
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = %s 
            AND column_name = %s
        );
    """, (table_name, column_name))
    return cursor.fetchone()[0]


def check_index_exists(cursor, index_name: str) -> bool:
    """检查索引是否存在"""
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND indexname = %s
        );
    """, (index_name,))
    return cursor.fetchone()[0]


def verify_schema():
    """验证数据库Schema"""
    print("=" * 60)
    print("Step 2: 数据库Schema验证")
    print("=" * 60)
    
    all_passed = True
    
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 检查新表
            print("\n[1] 检查新增表...")
            tables = [
                "tender_requirements",
                "tender_rule_packs",
                "tender_rules",
                "tender_bid_response_items",
            ]
            
            for table in tables:
                exists = check_table_exists(cur, table)
                status = "✅" if exists else "❌"
                print(f"  {status} {table}")
                if not exists:
                    all_passed = False
            
            # 检查 tender_requirements 的字段
            print("\n[2] 检查 tender_requirements 表字段...")
            requirement_columns = [
                "id", "project_id", "requirement_id", "dimension", "req_type",
                "requirement_text", "is_hard", "allow_deviation", "value_schema_json",
                "evidence_chunk_ids", "created_at"
            ]
            
            for col in requirement_columns:
                exists = check_column_exists(cur, "tender_requirements", col)
                status = "✅" if exists else "❌"
                print(f"  {status} {col}")
                if not exists:
                    all_passed = False
            
            # 检查 tender_rule_packs 的字段
            print("\n[3] 检查 tender_rule_packs 表字段...")
            rule_pack_columns = [
                "id", "pack_name", "pack_type", "project_id", "priority",
                "is_active", "created_at", "updated_at"
            ]
            
            for col in rule_pack_columns:
                exists = check_column_exists(cur, "tender_rule_packs", col)
                status = "✅" if exists else "❌"
                print(f"  {status} {col}")
                if not exists:
                    all_passed = False
            
            # 检查 tender_rules 的字段
            print("\n[4] 检查 tender_rules 表字段...")
            rule_columns = [
                "id", "rule_pack_id", "rule_key", "rule_name", "dimension",
                "evaluator", "condition_json", "severity", "is_hard", "created_at"
            ]
            
            for col in rule_columns:
                exists = check_column_exists(cur, "tender_rules", col)
                status = "✅" if exists else "❌"
                print(f"  {status} {col}")
                if not exists:
                    all_passed = False
            
            # 检查 tender_bid_response_items 的字段
            print("\n[5] 检查 tender_bid_response_items 表字段...")
            response_columns = [
                "id", "project_id", "bidder_name", "dimension", "response_type",
                "response_text", "extracted_value_json", "evidence_chunk_ids", "created_at"
            ]
            
            for col in response_columns:
                exists = check_column_exists(cur, "tender_bid_response_items", col)
                status = "✅" if exists else "❌"
                print(f"  {status} {col}")
                if not exists:
                    all_passed = False
            
            # 检查 tender_review_items 新增字段
            print("\n[6] 检查 tender_review_items 新增字段...")
            review_new_columns = [
                "rule_id", "requirement_id", "severity", "evaluator"
            ]
            
            for col in review_new_columns:
                exists = check_column_exists(cur, "tender_review_items", col)
                status = "✅" if exists else "❌"
                print(f"  {status} {col}")
                if not exists:
                    all_passed = False
            
            # 检查关键索引
            print("\n[7] 检查关键索引...")
            indexes = [
                "idx_tender_requirements_project",
                "idx_tender_requirements_dimension",
                "idx_tender_requirements_project_dimension",
                "idx_tender_rule_packs_project",
                "idx_tender_rules_pack",
                "idx_tender_rules_key",
                "idx_tender_bid_response_project",
                "idx_tender_bid_response_bidder",
                "idx_tender_review_rule",
                "idx_tender_review_requirement",
            ]
            
            for idx in indexes:
                exists = check_index_exists(cur, idx)
                status = "✅" if exists else "❌"
                print(f"  {status} {idx}")
                if not exists:
                    all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ 所有Schema验证通过！")
        return 0
    else:
        print("❌ Schema验证失败！请检查上述错误。")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(verify_schema())
    except Exception as e:
        print(f"\n❌ 验证过程出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

