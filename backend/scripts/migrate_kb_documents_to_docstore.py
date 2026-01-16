"""
知识库文档迁移脚本

功能：
1. 从旧的 kb_documents 表读取文档
2. 迁移到新的 documents/document_versions/doc_segments 表
3. 保留原有的向量数据（Milvus）
4. 迁移完成后可选择清理旧数据

使用方法：
    python backend/scripts/migrate_kb_documents_to_docstore.py [--delete-old]
    
参数：
    --delete-old: 迁移完成后删除旧的 kb_documents 表中的数据
    --dry-run: 只模拟运行，不实际修改数据库
    --kb-id: 只迁移指定知识库的文档
"""
import sys
import os
import asyncio
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.db.postgres import _get_pool, init_db
from psycopg.types.json import Json


class KBDocumentMigrator:
    """知识库文档迁移器"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.pool = _get_pool()
        self.stats = {
            'total': 0,
            'migrated': 0,
            'skipped': 0,
            'failed': 0,
            'errors': []
        }
    
    def get_legacy_documents(self, kb_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取旧表中的文档"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                if kb_id:
                    query = """
                        SELECT id, kb_id, filename, source, status, created_at, updated_at, 
                               meta_json, kb_category
                        FROM kb_documents
                        WHERE kb_id = %s
                        ORDER BY created_at
                    """
                    cur.execute(query, (kb_id,))
                else:
                    query = """
                        SELECT id, kb_id, filename, source, status, created_at, updated_at, 
                               meta_json, kb_category
                        FROM kb_documents
                        ORDER BY created_at
                    """
                    cur.execute(query)
                
                return [dict(row) for row in cur.fetchall()]
    
    def get_doc_segments_by_doc_id(self, old_doc_id: str) -> List[Dict[str, Any]]:
        """获取文档对应的segments（从doc_segments表，通过chunk映射）"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                # 通过 kb_chunks 表找到对应的 chunk_id
                cur.execute("""
                    SELECT chunk_id, content, position
                    FROM kb_chunks
                    WHERE doc_id = %s
                    ORDER BY position
                """, (old_doc_id,))
                
                chunks = cur.fetchall()
                return [dict(chunk) for chunk in chunks]
    
    def calculate_file_hash(self, content: str) -> str:
        """计算文件内容的SHA256哈希"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def migrate_document(self, legacy_doc: Dict[str, Any]) -> bool:
        """迁移单个文档"""
        old_doc_id = legacy_doc['id']
        kb_id = legacy_doc['kb_id']
        filename = legacy_doc['filename']
        kb_category = legacy_doc.get('kb_category', 'general_doc')
        
        print(f"\n📄 迁移文档: {filename} (id={old_doc_id}, kb_id={kb_id})")
        
        try:
            # 1. 获取文档的所有chunks（用于计算content hash）
            chunks = self.get_doc_segments_by_doc_id(old_doc_id)
            
            if not chunks:
                print(f"  ⚠️  文档没有chunks，可能已经被删除或从未入库，跳过")
                self.stats['skipped'] += 1
                return False
            
            # 2. 合并所有chunk内容作为文档内容（用于计算hash）
            full_content = "\n".join([chunk['content'] for chunk in chunks])
            content_hash = self.calculate_file_hash(full_content)
            
            if self.dry_run:
                print(f"  [DRY RUN] 将创建 document + {len(chunks)} segments")
                self.stats['migrated'] += 1
                return True
            
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    # 3. 创建 document 记录
                    doc_id = old_doc_id  # 保持相同的ID，避免外键引用问题
                    
                    # 检查是否已存在
                    cur.execute("SELECT id FROM documents WHERE id = %s", (doc_id,))
                    if cur.fetchone():
                        print(f"  ⏭️  文档已存在于新表，跳过")
                        self.stats['skipped'] += 1
                        return False
                    
                    # 创建 document
                    cur.execute("""
                        INSERT INTO documents (id, namespace, doc_type, owner_id, created_at, meta_json)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        doc_id,
                        'kb',  # namespace
                        kb_category,  # doc_type
                        None,  # owner_id (知识库文档没有owner)
                        legacy_doc['created_at'],
                        Json({
                            'kb_id': kb_id,
                            'kb_category': kb_category,
                            'source': legacy_doc.get('source', 'upload'),
                            'legacy_migration': True,
                            'migrated_at': datetime.now().isoformat()
                        })
                    ))
                    print(f"  ✅ 创建 document: {doc_id}")
                    
                    # 4. 创建 document_version 记录
                    doc_version_id = f"{doc_id}_v1"
                    cur.execute("""
                        INSERT INTO document_versions (id, document_id, sha256, filename, storage_path, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        doc_version_id,
                        doc_id,
                        content_hash,
                        filename,
                        None,  # storage_path (旧数据没有存储路径)
                        legacy_doc['created_at']
                    ))
                    print(f"  ✅ 创建 document_version: {doc_version_id}")
                    
                    # 5. 创建 doc_segments 记录
                    for idx, chunk in enumerate(chunks):
                        segment_id = f"{doc_version_id}_seg{idx}"
                        cur.execute("""
                            INSERT INTO doc_segments (id, doc_version_id, segment_no, content_text, 
                                                     meta_json, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (
                            segment_id,
                            doc_version_id,
                            idx,
                            chunk['content'],
                            Json({
                                'chunk_id': chunk['chunk_id'],  # 保留原chunk_id以便追溯
                                'position': chunk['position']
                            }),
                            legacy_doc['created_at']
                        ))
                    
                    print(f"  ✅ 创建 {len(chunks)} 个 doc_segments")
                    
                    conn.commit()
                    self.stats['migrated'] += 1
                    return True
        
        except Exception as e:
            error_msg = f"迁移失败 {filename}: {str(e)}"
            print(f"  ❌ {error_msg}")
            self.stats['failed'] += 1
            self.stats['errors'].append(error_msg)
            return False
    
    def delete_legacy_document(self, doc_id: str):
        """删除旧表中的文档记录"""
        if self.dry_run:
            print(f"  [DRY RUN] 将删除旧表记录: {doc_id}")
            return
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                # kb_documents 表的外键会级联删除 kb_chunks
                cur.execute("DELETE FROM kb_documents WHERE id = %s", (doc_id,))
                conn.commit()
                print(f"  🗑️  已删除旧表记录: {doc_id}")
    
    def run(self, kb_id: Optional[str] = None, delete_old: bool = False):
        """运行迁移"""
        print("╔══════════════════════════════════════════════════════════════════════════════════════╗")
        print("║  📦 知识库文档迁移工具                                                              ║")
        print("╚══════════════════════════════════════════════════════════════════════════════════════╝")
        
        if self.dry_run:
            print("\n⚠️  DRY RUN 模式：只模拟运行，不实际修改数据库\n")
        
        # 1. 获取待迁移的文档
        print("\n📋 正在扫描旧表...")
        legacy_docs = self.get_legacy_documents(kb_id)
        self.stats['total'] = len(legacy_docs)
        
        if not legacy_docs:
            print("✅ 没有需要迁移的文档")
            return
        
        print(f"📊 找到 {len(legacy_docs)} 个待迁移文档")
        
        if kb_id:
            print(f"🎯 只迁移知识库: {kb_id}")
        
        # 2. 逐个迁移
        print("\n🚀 开始迁移...\n")
        for doc in legacy_docs:
            success = self.migrate_document(doc)
            
            # 如果迁移成功且需要删除旧数据
            if success and delete_old:
                self.delete_legacy_document(doc['id'])
        
        # 3. 输出统计
        print("\n╔══════════════════════════════════════════════════════════════════════════════════════╗")
        print("║  📊 迁移统计                                                                         ║")
        print("╚══════════════════════════════════════════════════════════════════════════════════════╝")
        print(f"总计:   {self.stats['total']}")
        print(f"成功:   {self.stats['migrated']} ✅")
        print(f"跳过:   {self.stats['skipped']} ⏭️")
        print(f"失败:   {self.stats['failed']} ❌")
        
        if self.stats['errors']:
            print("\n❌ 错误列表:")
            for error in self.stats['errors'][:10]:  # 只显示前10个错误
                print(f"  - {error}")
            if len(self.stats['errors']) > 10:
                print(f"  ... 还有 {len(self.stats['errors']) - 10} 个错误")
        
        if delete_old and not self.dry_run:
            print(f"\n🗑️  已删除 {self.stats['migrated']} 个旧表记录")
        
        print("\n✅ 迁移完成！")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='知识库文档迁移工具')
    parser.add_argument('--delete-old', action='store_true', 
                       help='迁移完成后删除旧的 kb_documents 表中的数据')
    parser.add_argument('--dry-run', action='store_true',
                       help='只模拟运行，不实际修改数据库')
    parser.add_argument('--kb-id', type=str,
                       help='只迁移指定知识库的文档')
    
    args = parser.parse_args()
    
    # 初始化数据库
    init_db()
    
    # 创建迁移器并运行
    migrator = KBDocumentMigrator(dry_run=args.dry_run)
    migrator.run(kb_id=args.kb_id, delete_old=args.delete_old)


if __name__ == '__main__':
    main()

