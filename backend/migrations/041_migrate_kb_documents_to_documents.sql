-- 041_migrate_kb_documents_to_documents.sql
-- 迁移 kb_documents 数据到 documents 表
-- 日期：2025-12-31

-- ====================
-- 步骤 1: 分析现有数据
-- ====================

DO $$
DECLARE
    kb_docs_count INTEGER;
    valid_mappings INTEGER;
    documents_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO kb_docs_count FROM kb_documents;
    
    SELECT COUNT(*) INTO valid_mappings
    FROM kb_documents kd
    JOIN document_versions dv ON (kd.meta_json->>'doc_version_id')::text = dv.id;
    
    SELECT COUNT(*) INTO documents_count FROM documents WHERE namespace = 'tender';
    
    RAISE NOTICE '==========================================================';
    RAISE NOTICE '数据分析';
    RAISE NOTICE '==========================================================';
    RAISE NOTICE 'kb_documents 记录数: %', kb_docs_count;
    RAISE NOTICE '有效映射数（可迁移）: %', valid_mappings;
    RAISE NOTICE 'documents 总数（tender命名空间）: %', documents_count;
    RAISE NOTICE '==========================================================';
END $$;

-- ====================
-- 步骤 2: 执行数据迁移
-- ====================

DO $$
DECLARE
    updated_count INTEGER := 0;
    doc_rec RECORD;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '开始迁移数据...';
    RAISE NOTICE '';
    
    -- 遍历所有 kb_documents 记录
    FOR doc_rec IN
        SELECT 
            kd.id as kb_doc_id,
            kd.kb_id,
            kd.kb_category,
            kd.meta_json,
            dv.document_id
        FROM kb_documents kd
        JOIN document_versions dv ON (kd.meta_json->>'doc_version_id')::text = dv.id
        WHERE dv.document_id IS NOT NULL
    LOOP
        -- 更新 documents 表，添加 kb_id 等信息
        UPDATE documents
        SET meta_json = meta_json || jsonb_build_object(
            'kb_id', doc_rec.kb_id,
            'kb_category', COALESCE(doc_rec.kb_category, 'tender_doc'),
            'kb_doc_id', doc_rec.kb_doc_id,
            'migrated_from_kb_documents', true,
            'migration_time', NOW()::text
        )
        WHERE id = doc_rec.document_id;
        
        IF FOUND THEN
            updated_count := updated_count + 1;
            RAISE NOTICE '  ✓ 更新 document % (kb_id: %)', 
                substring(doc_rec.document_id, 1, 12), 
                substring(doc_rec.kb_id, 1, 8);
        END IF;
    END LOOP;
    
    RAISE NOTICE '';
    RAISE NOTICE '✓ 迁移完成！已更新 % 条记录', updated_count;
END $$;

-- ====================
-- 步骤 3: 验证迁移结果
-- ====================

DO $$
DECLARE
    migrated_count INTEGER;
    unmigrated_count INTEGER;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '==========================================================';
    RAISE NOTICE '验证迁移结果';
    RAISE NOTICE '==========================================================';
    
    -- 统计已迁移的文档
    SELECT COUNT(*) INTO migrated_count
    FROM documents
    WHERE meta_json->>'migrated_from_kb_documents' = 'true';
    
    RAISE NOTICE '已迁移的文档数：%', migrated_count;
    
    -- 检查未迁移的记录
    SELECT COUNT(*) INTO unmigrated_count
    FROM kb_documents kd
    JOIN document_versions dv ON (kd.meta_json->>'doc_version_id')::text = dv.id
    JOIN documents d ON dv.document_id = d.id
    WHERE d.meta_json->>'kb_id' IS NULL
       OR d.meta_json->>'migrated_from_kb_documents' IS NULL;
    
    IF unmigrated_count > 0 THEN
        RAISE WARNING '警告：还有 % 条记录未迁移！', unmigrated_count;
    ELSE
        RAISE NOTICE '✓ 所有记录已成功迁移！';
    END IF;
    
    RAISE NOTICE '==========================================================';
END $$;

-- ====================
-- 步骤 4: 创建便捷查询视图（可选）
-- ====================

-- 创建视图，方便查询通过 kb_id 检索文档
CREATE OR REPLACE VIEW v_kb_documents_new AS
SELECT 
    d.id as document_id,
    d.meta_json->>'kb_id' as kb_id,
    d.meta_json->>'kb_category' as kb_category,
    d.doc_type,
    dv.id as version_id,
    dv.filename,
    dv.sha256,
    dv.storage_path,
    d.created_at
FROM documents d
JOIN document_versions dv ON d.id = dv.document_id
WHERE d.meta_json->>'kb_id' IS NOT NULL
ORDER BY d.created_at DESC;

-- 添加注释
COMMENT ON VIEW v_kb_documents_new IS '新的知识库文档视图（替代 kb_documents 表）';

-- 显示迁移后的数据示例
SELECT 
    '=== 迁移后的数据示例（前5条）===' as info,
    NULL::text as document_id,
    NULL::text as kb_id,
    NULL::text as kb_category,
    NULL::text as doc_type,
    NULL::text as filename
UNION ALL
SELECT 
    '',
    substring(document_id, 1, 12),
    substring(kb_id, 1, 8),
    kb_category,
    doc_type,
    substring(filename, 1, 40)
FROM v_kb_documents_new
LIMIT 5;

-- 完成
SELECT '✓ kb_documents 数据迁移完成！' as status;

