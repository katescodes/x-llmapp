-- 清理risks模块的SQL脚本
-- 此脚本将删除所有risks相关的表和数据

-- 1. 删除prompt_templates中risks模块的记录
DELETE FROM prompt_templates WHERE module = 'risks';

-- 2. 删除tender_risks表中的所有数据
DELETE FROM tender_risks;

-- 3. 删除tender_risks表（可选，如果要彻底删除表）
-- DROP TABLE IF EXISTS tender_risks CASCADE;

-- 4. 检查是否还有其他引用risks的数据
SELECT 'tender_risks records deleted' AS status;
