#!/usr/bin/env python3
"""
kb_documents 数据迁移脚本

功能：
1. 将 kb_documents 的数据映射补充到 documents 表
2. 验证迁移结果
3. 可选：删除旧表

使用方法：
python backend/scripts/migrate_kb_documents.py --mode=analyze  # 分析模式
python backend/scripts/migrate_kb_documents.py --mode=migrate  # 执行迁移
python backend/scripts/migrate_kb_documents.py --mode=verify   # 验证迁移
python backend/scripts/migrate_kb_documents.py --mode=cleanup  # 清理旧表（谨慎！）
"""

import argparse
import json
import sys
from datetime import datetime
from typing import Dict, List, Any

# 添加项目路径
sys.path.insert(0, '/aidata/x-llmapp1/backend')

from app.services.db.postgres import _get_pool


class KBDocumentsMigration:
    """kb_documents 迁移工具"""
    
    def __init__(self):
        self.pool = _get_pool()
        self.stats = {
            "kb_documents_count": 0,
            "documents_to_update": 0,
            "documents_updated": 0,
            "errors": [],
        }
    
    def analyze(self) -> Dict[str, Any]:
        """分析现有数据"""
        print("\n" + "=" * 60)
        print("步骤 1: 数据分析")
        print("=" * 60)
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                # 统计 kb_documents
                cur.execute("SELECT COUNT(*) FROM kb_documents")
                self.stats["kb_documents_count"] = cur.fetchone()[0]
                
                # 分析 kb_documents 的 doc_version_id
                cur.execute("""
                    SELECT 
                        kd.id as kb_doc_id,
                        kd.kb_id,
                        kd.filename,
                        kd.meta_json->>'doc_version_id' as doc_version_id,
                        dv.id as actual_version_id,
                        dv.document_id
                    FROM kb_documents kd
                    LEFT JOIN document_versions dv ON (kd.meta_json->>'doc_version_id')::text = dv.id
                    ORDER BY kd.created_at DESC
                """)
                rows = cur.fetchall()
                
                print(f"\n✅ kb_documents 记录数：{self.stats['kb_documents_count']}")
                print(f"\n详细信息：")
                
                valid_count = 0
                invalid_count = 0
                
                for row in rows:
                    kb_doc_id, kb_id, filename, doc_version_id, actual_version_id, document_id = row
                    
                    if document_id:
                        valid_count += 1
                        print(f"  ✅ {filename[:40]:40s} | kb_id: {kb_id[:8]} | doc_version: {doc_version_id[:8]} → document: {document_id[:8]}")
                    else:
                        invalid_count += 1
                        print(f"  ❌ {filename[:40]:40s} | kb_id: {kb_id[:8]} | doc_version: {doc_version_id} (NOT FOUND)")
                
                self.stats["documents_to_update"] = valid_count
                
                print(f"\n统计：")
                print(f"  有效记录（可迁移）：{valid_count}")
                print(f"  无效记录（需修复）：{invalid_count}")
                
                # 检查 documents 表当前状态
                cur.execute("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(meta_json->>'kb_id') as with_kb_id
                    FROM documents
                    WHERE namespace = 'tender'
                """)
                doc_row = cur.fetchone()
                
                print(f"\n📊 documents 表状态：")
                print(f"  总文档数：{doc_row[0]}")
                print(f"  已有 kb_id：{doc_row[1]}")
                print(f"  需要补充：{doc_row[0] - doc_row[1]}")
        
        return self.stats
    
    def migrate(self) -> Dict[str, Any]:
        """执行迁移"""
        print("\n" + "=" * 60)
        print("步骤 2: 执行数据迁移")
        print("=" * 60)
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                # 获取所有需要迁移的记录
                cur.execute("""
                    SELECT 
                        kd.id as kb_doc_id,
                        kd.kb_id,
                        kd.kb_category,
                        kd.meta_json,
                        dv.document_id
                    FROM kb_documents kd
                    JOIN document_versions dv ON (kd.meta_json->>'doc_version_id')::text = dv.id
                    WHERE dv.document_id IS NOT NULL
                """)
                rows = cur.fetchall()
                
                print(f"\n开始迁移 {len(rows)} 条记录...")
                
                updated_count = 0
                for row in rows:
                    kb_doc_id, kb_id, kb_category, meta_json, document_id = row
                    
                    try:
                        # 解析 meta_json
                        if isinstance(meta_json, str):
                            meta_json = json.loads(meta_json)
                        
                        # 补充 kb_id 和 kb_category 到 documents.meta_json
                        cur.execute("""
                            UPDATE documents
                            SET meta_json = meta_json || jsonb_build_object(
                                'kb_id', %s::text,
                                'kb_category', %s::text,
                                'kb_doc_id', %s::text,
                                'migrated_from_kb_documents', true,
                                'migration_time', %s::text
                            )
                            WHERE id = %s
                        """, (kb_id, kb_category or 'tender_doc', kb_doc_id, datetime.now().isoformat(), document_id))
                        
                        if cur.rowcount > 0:
                            updated_count += 1
                            print(f"  ✅ 更新 document {document_id[:12]} (kb_id: {kb_id[:8]})")
                        else:
                            self.stats["errors"].append(f"Failed to update document {document_id}")
                            print(f"  ❌ 更新失败：document {document_id}")
                    
                    except Exception as e:
                        self.stats["errors"].append(f"Error migrating {kb_doc_id}: {str(e)}")
                        print(f"  ❌ 错误：{e}")
                
                conn.commit()
                
                self.stats["documents_updated"] = updated_count
                
                print(f"\n✅ 迁移完成！")
                print(f"  成功更新：{updated_count}/{len(rows)}")
                print(f"  失败：{len(rows) - updated_count}")
        
        return self.stats
    
    def verify(self) -> Dict[str, Any]:
        """验证迁移结果"""
        print("\n" + "=" * 60)
        print("步骤 3: 验证迁移结果")
        print("=" * 60)
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                # 检查迁移结果
                cur.execute("""
                    SELECT 
                        d.id,
                        d.namespace,
                        d.doc_type,
                        d.meta_json->>'kb_id' as kb_id,
                        d.meta_json->>'kb_category' as kb_category,
                        d.meta_json->>'migrated_from_kb_documents' as migrated
                    FROM documents d
                    WHERE d.meta_json->>'migrated_from_kb_documents' = 'true'
                    ORDER BY d.created_at DESC
                """)
                rows = cur.fetchall()
                
                print(f"\n✅ 已迁移的文档：{len(rows)}")
                
                for row in rows:
                    doc_id, namespace, doc_type, kb_id, kb_category, migrated = row
                    print(f"  📄 {doc_id[:12]} | ns: {namespace:10s} | type: {doc_type:10s} | kb: {kb_id[:8] if kb_id else 'N/A':8s} | cat: {kb_category or 'N/A'}")
                
                # 检查是否还有未迁移的
                cur.execute("""
                    SELECT 
                        kd.id,
                        kd.filename,
                        dv.document_id
                    FROM kb_documents kd
                    JOIN document_versions dv ON (kd.meta_json->>'doc_version_id')::text = dv.id
                    JOIN documents d ON dv.document_id = d.id
                    WHERE d.meta_json->>'kb_id' IS NULL
                       OR d.meta_json->>'migrated_from_kb_documents' IS NULL
                """)
                unmigrated = cur.fetchall()
                
                if unmigrated:
                    print(f"\n⚠️  警告：还有 {len(unmigrated)} 条记录未迁移：")
                    for row in unmigrated[:5]:  # 只显示前5条
                        print(f"  ❌ {row[1][:40]} (doc_id: {row[2][:12]})")
                    if len(unmigrated) > 5:
                        print(f"  ... 还有 {len(unmigrated) - 5} 条")
                else:
                    print(f"\n✅ 所有记录已成功迁移！")
                
                # 验证检索功能
                print(f"\n验证检索功能...")
                
                # 测试：通过 kb_id 查询 documents
                cur.execute("""
                    SELECT 
                        d.id,
                        d.meta_json->>'kb_id' as kb_id,
                        dv.id as version_id
                    FROM documents d
                    JOIN document_versions dv ON d.id = dv.document_id
                    WHERE d.meta_json->>'kb_id' IS NOT NULL
                    LIMIT 3
                """)
                test_rows = cur.fetchall()
                
                if test_rows:
                    print(f"  ✅ 检索测试通过（找到 {len(test_rows)} 条记录）")
                    for row in test_rows:
                        print(f"     doc: {row[0][:12]} | kb: {row[1][:8]} | version: {row[2][:12]}")
                else:
                    print(f"  ❌ 检索测试失败：未找到记录")
        
        return {"status": "verified", "migrated_count": len(rows), "unmigrated_count": len(unmigrated)}
    
    def cleanup(self, confirm: bool = False) -> Dict[str, Any]:
        """清理旧表（谨慎操作！）"""
        print("\n" + "=" * 60)
        print("步骤 4: 清理旧表（DANGER ZONE ⚠️）")
        print("=" * 60)
        
        if not confirm:
            print("\n⚠️  警告：此操作将删除 kb_documents 和 kb_chunks 表！")
            print("请先运行 --mode=verify 确认迁移成功")
            print("如果确定要删除，请使用 --confirm 参数")
            return {"status": "cancelled"}
        
        print("\n⚠️  开始清理旧表...")
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                try:
                    # 统计数据
                    cur.execute("SELECT COUNT(*) FROM kb_documents")
                    kb_docs_count = cur.fetchone()[0]
                    
                    cur.execute("SELECT COUNT(*) FROM kb_chunks")
                    kb_chunks_count = cur.fetchone()[0]
                    
                    print(f"\n准备删除：")
                    print(f"  kb_documents: {kb_docs_count} 条")
                    print(f"  kb_chunks: {kb_chunks_count} 条")
                    
                    # 删除表
                    cur.execute("DROP TABLE IF EXISTS kb_chunks CASCADE")
                    print(f"  ✅ 已删除 kb_chunks 表")
                    
                    cur.execute("DROP TABLE IF EXISTS kb_documents CASCADE")
                    print(f"  ✅ 已删除 kb_documents 表")
                    
                    conn.commit()
                    
                    print(f"\n✅ 清理完成！")
                    
                    return {"status": "success", "deleted_tables": ["kb_documents", "kb_chunks"]}
                
                except Exception as e:
                    conn.rollback()
                    print(f"\n❌ 清理失败：{e}")
                    return {"status": "error", "message": str(e)}


def main():
    parser = argparse.ArgumentParser(description='kb_documents 数据迁移工具')
    parser.add_argument('--mode', choices=['analyze', 'migrate', 'verify', 'cleanup', 'all'], 
                       default='analyze', help='运行模式')
    parser.add_argument('--confirm', action='store_true', help='确认清理操作')
    
    args = parser.parse_args()
    
    migration = KBDocumentsMigration()
    
    print(f"\n{'='*60}")
    print(f"kb_documents 数据迁移工具")
    print(f"模式：{args.mode}")
    print(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    try:
        if args.mode == 'analyze' or args.mode == 'all':
            migration.analyze()
        
        if args.mode == 'migrate' or args.mode == 'all':
            migration.migrate()
        
        if args.mode == 'verify' or args.mode == 'all':
            migration.verify()
        
        if args.mode == 'cleanup':
            migration.cleanup(confirm=args.confirm)
        
        print(f"\n{'='*60}")
        print(f"执行完成！")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n❌ 执行失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

