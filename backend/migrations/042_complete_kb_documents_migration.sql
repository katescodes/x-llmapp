-- 完成最后2条kb_documents的迁移
-- 更新documents表的meta_json字段

UPDATE documents d
SET meta_json = jsonb_build_object(
    'kb_id', kd.kb_id,
    'kb_category', kd.kb_category,
    'kb_doc_id', kd.id,
    'source', kd.source
)
FROM kb_documents kd
WHERE d.id = kd.id
  AND kd.id IN ('doc_7595c4bac5b04994b6ce6a526d86255c', 'doc_8a8a00b9a00d442baa4fd2e40ffd0df6');

-- 验证迁移结果
SELECT 
    d.id,
    d.meta_json->>'kb_id' as kb_id,
    d.meta_json->>'kb_doc_id' as kb_doc_id,
    d.meta_json->>'kb_category' as kb_category
FROM documents d
WHERE d.id IN ('doc_7595c4bac5b04994b6ce6a526d86255c', 'doc_8a8a00b9a00d442baa4fd2e40ffd0df6');

