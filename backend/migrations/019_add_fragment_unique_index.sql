-- 添加 doc_fragment 表的唯一索引以强制去重
-- 去重键: (owner_type, owner_id, fragment_type, source_file_key, start_body_index)

CREATE UNIQUE INDEX IF NOT EXISTS uniq_doc_fragment_dedup
ON doc_fragment(owner_type, owner_id, fragment_type, source_file_key, start_body_index);

COMMENT ON INDEX uniq_doc_fragment_dedup IS '确保同一所有者、同一文件、同一类型、同一起始位置的片段唯一';

