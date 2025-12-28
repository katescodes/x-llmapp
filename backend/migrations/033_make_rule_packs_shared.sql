-- 033_make_rule_packs_shared.sql
-- 支持规则包共享模式：project_id为NULL表示全局共享规则包

-- 1. 删除外键约束（如果存在）
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'tender_rule_packs_project_id_fkey') THEN
        ALTER TABLE tender_rule_packs DROP CONSTRAINT tender_rule_packs_project_id_fkey;
    END IF;
END
$$;

-- 2. 为 NULL 的 project_id 添加索引，以便快速查询共享规则包
CREATE INDEX IF NOT EXISTS idx_rule_packs_null_project
  ON tender_rule_packs(id) WHERE project_id IS NULL;

-- 3. 添加注释说明
COMMENT ON COLUMN tender_rule_packs.project_id IS '所属项目ID（可选，NULL表示全局共享规则包）';

