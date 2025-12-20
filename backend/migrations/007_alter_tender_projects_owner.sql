-- 007_alter_tender_projects_owner.sql
-- 为 tender_projects 增加 owner_id，支持多用户隔离

ALTER TABLE tender_projects
ADD COLUMN IF NOT EXISTS owner_id VARCHAR(36);

CREATE INDEX IF NOT EXISTS idx_tender_projects_owner ON tender_projects(owner_id);

COMMENT ON COLUMN tender_projects.owner_id IS '项目所有者ID，用于多用户隔离';
