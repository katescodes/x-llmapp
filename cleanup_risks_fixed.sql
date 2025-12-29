-- 清理risks模块的SQL脚本（修复版）

-- 1. 先删除prompt_history中risks相关的历史记录
DELETE FROM prompt_history WHERE prompt_id IN (SELECT id FROM prompt_templates WHERE module = 'risks');

-- 2. 删除prompt_templates中risks模块的记录
DELETE FROM prompt_templates WHERE module = 'risks';

-- 3. 删除tender_risks表中的所有数据
DELETE FROM tender_risks;

-- 4. 显示清理结果
SELECT 'risks module cleaned up successfully' AS status;
