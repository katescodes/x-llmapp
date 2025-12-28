-- 032_add_new_kb_categories.sql
-- 为知识库添加新的文档分类类型
-- 支持：招标文件、投标文件、格式模板、标准规范、技术资料、资质资料

-- 说明：
-- kb_documents.kb_category 和 kb_chunks.kb_category 字段已存在，类型为 TEXT
-- 新增的分类值会自动支持，无需修改表结构
-- 此迁移主要用于文档记录和说明

-- ============================================
-- 新增的知识库文档分类
-- ============================================

-- 原有分类：
-- - general_doc: 普通文档
-- - history_case: 历史案例
-- - reference_rule: 规章制度
-- - web_snapshot: 网页快照
-- - tender_app: 招投标文档（旧，保留兼容）

-- 新增分类：
-- - tender_notice: 招标文件
-- - bid_document: 投标文件
-- - format_template: 格式模板
-- - standard_spec: 标准规范
-- - technical_material: 技术资料
-- - qualification_doc: 资质资料

-- 这些新分类值可以直接使用，因为 kb_category 字段是 TEXT 类型
-- 应用层（Python/TypeScript）的 Literal 类型定义已更新

-- ============================================
-- 更新说明文档
-- ============================================

COMMENT ON COLUMN kb_documents.kb_category IS '文档分类：general_doc(普通文档), history_case(历史案例), reference_rule(规章制度), web_snapshot(网页快照), tender_app(招投标文档-旧), tender_notice(招标文件), bid_document(投标文件), format_template(格式模板), standard_spec(标准规范), technical_material(技术资料), qualification_doc(资质资料)';

COMMENT ON COLUMN kb_chunks.kb_category IS '文档分类：general_doc(普通文档), history_case(历史案例), reference_rule(规章制度), web_snapshot(网页快照), tender_app(招投标文档-旧), tender_notice(招标文件), bid_document(投标文件), format_template(格式模板), standard_spec(标准规范), technical_material(技术资料), qualification_doc(资质资料)';

-- ============================================
-- 创建文档类型映射说明表（可选）
-- ============================================

CREATE TABLE IF NOT EXISTS kb_category_mappings (
  app_doc_type TEXT PRIMARY KEY,
  kb_category TEXT NOT NULL,
  description TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 插入映射关系（供参考和文档用途）
INSERT INTO kb_category_mappings (app_doc_type, kb_category, description)
VALUES
  -- 招投标应用
  ('tender', 'tender_notice', '招投标应用-招标文件'),
  ('bid', 'bid_document', '招投标应用-投标文件'),
  ('template', 'format_template', '招投标应用-格式模板'),
  ('custom_rule', 'reference_rule', '招投标应用-自定义规则'),
  
  -- 用户文档
  ('tender_user_doc', 'technical_material', '用户文档-默认为技术资料'),
  ('technical', 'technical_material', '用户文档-技术资料'),
  ('qualification', 'qualification_doc', '用户文档-资质资料'),
  ('standard', 'standard_spec', '用户文档-标准规范'),
  
  -- 申报应用
  ('declare_notice', 'tender_notice', '申报应用-申报通知'),
  ('declare_company', 'qualification_doc', '申报应用-企业信息'),
  ('declare_tech', 'technical_material', '申报应用-技术资料'),
  ('declare_other', 'general_doc', '申报应用-其他文档')
ON CONFLICT (app_doc_type) DO UPDATE SET
  kb_category = EXCLUDED.kb_category,
  description = EXCLUDED.description;

COMMENT ON TABLE kb_category_mappings IS '应用文档类型到知识库分类的映射关系表（用于文档和参考）';

