-- ==========================================
-- 系统清理脚本：删除废弃的表和代码
-- ==========================================
-- 
-- 注意：执行前请确保已备份数据库！
--
-- 清理内容：
-- 1. kb_documents (17条，已全部迁移到documents表)
-- 2. kb_chunks (0条，空表)
-- 3. tender_custom_rule_sets (0条，空表但功能在用，保留)
-- 
-- ==========================================

-- 1. 验证kb_documents迁移完成
DO $$
DECLARE
    kb_doc_count INT;
    migrated_count INT;
BEGIN
    SELECT COUNT(*) INTO kb_doc_count FROM kb_documents;
    
    SELECT COUNT(*) INTO migrated_count
    FROM kb_documents kd
    INNER JOIN documents d ON d.meta_json->>'kb_doc_id' = kd.id;
    
    RAISE NOTICE 'kb_documents总数: %, 已迁移: %', kb_doc_count, migrated_count;
    
    IF kb_doc_count != migrated_count THEN
        RAISE EXCEPTION '还有未迁移的kb_documents记录！';
    END IF;
    
    RAISE NOTICE '✅ 所有kb_documents已迁移';
END $$;

-- 2. 验证kb_chunks为空
DO $$
DECLARE
    chunk_count INT;
BEGIN
    SELECT COUNT(*) INTO chunk_count FROM kb_chunks;
    
    RAISE NOTICE 'kb_chunks总数: %', chunk_count;
    
    IF chunk_count > 0 THEN
        RAISE EXCEPTION 'kb_chunks表不为空！';
    END IF;
    
    RAISE NOTICE '✅ kb_chunks为空表';
END $$;

-- 3. 删除kb_chunks表（空表，安全删除）
DROP TABLE IF EXISTS kb_chunks CASCADE;
RAISE NOTICE '✅ 已删除 kb_chunks 表';

-- 4. 删除kb_documents表（已迁移，安全删除）
DROP TABLE IF EXISTS kb_documents CASCADE;
RAISE NOTICE '✅ 已删除 kb_documents 表';

-- 5. 验证删除结果
DO $$
BEGIN
    -- 检查表是否存在
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'kb_documents') THEN
        RAISE EXCEPTION 'kb_documents表仍然存在！';
    END IF;
    
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'kb_chunks') THEN
        RAISE EXCEPTION 'kb_chunks表仍然存在！';
    END IF;
    
    RAISE NOTICE '✅ 所有废弃表已成功删除';
END $$;

-- 6. 显示当前tender相关表
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public' 
  AND (tablename LIKE 'tender_%' OR tablename LIKE 'kb_%' OR tablename LIKE 'doc%')
ORDER BY tablename;

