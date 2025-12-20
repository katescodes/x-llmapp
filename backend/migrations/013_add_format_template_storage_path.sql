-- 013_add_format_template_storage_path.sql
-- 为 format_templates 表增加模板 docx 的磁盘存储路径（用于导出 KEEP_ALL/KEEP_RANGE 保留页眉页脚/页边距/底板）

ALTER TABLE format_templates
  ADD COLUMN IF NOT EXISTS template_storage_path TEXT;

COMMENT ON COLUMN format_templates.template_storage_path IS '格式模板对应的 docx 文件存储路径（用于导出时加载底板文档）';


