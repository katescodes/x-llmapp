-- 008_enhance_tender_directory.sql
-- 增强 tender_directory_nodes 表：添加索引以优化树形查询和排序

-- 确保 order_no, parent_id 已存在（migration 005 已创建）
-- 添加复合索引以优化按项目+顺序查询
CREATE INDEX IF NOT EXISTS idx_tender_directory_nodes_proj_order 
  ON tender_directory_nodes(project_id, order_no);

-- 添加 parent_id 索引（如果不存在）
CREATE INDEX IF NOT EXISTS idx_tender_dir_parent 
  ON tender_directory_nodes(parent_id);

-- 为 tender_project_info 添加 evidence_chunk_ids_json 字段（如果不存在）
DO $$ 
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'tender_project_info' 
    AND column_name = 'evidence_chunk_ids_json'
  ) THEN
    ALTER TABLE tender_project_info 
    ADD COLUMN evidence_chunk_ids_json JSONB DEFAULT '[]'::jsonb;
  END IF;
END $$;

-- 确保 tender_directory_nodes 的 created_at 字段存在
DO $$ 
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'tender_directory_nodes' 
    AND column_name = 'created_at'
  ) THEN
    ALTER TABLE tender_directory_nodes 
    ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT now();
  END IF;
END $$;

-- 为 tender_project_assets 添加缺失字段（如果不存在）
DO $$ 
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'tender_project_assets' 
    AND column_name = 'created_at'
  ) THEN
    ALTER TABLE tender_project_assets 
    ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT now();
  END IF;
END $$;
