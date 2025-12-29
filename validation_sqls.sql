-- ====================================================================
-- 【投标响应抽取改进 - 验收SQL】
-- ====================================================================
-- 使用说明：
-- 1. 替换 'YOUR_PROJECT_ID' 为实际的 project_id
-- 2. 重新抽取投标响应后执行这些SQL
-- 3. 所有查询结果应符合"期望值"
-- ====================================================================

-- 替换为实际的 project_id
\set project_id 'YOUR_PROJECT_ID'

\echo '======================================================================'
\echo '【验收1】price 维度不应包含业绩金额'
\echo '期望：0 行（bad_price_rows=0）'
\echo '======================================================================'

SELECT COUNT(*) AS bad_price_rows
FROM tender_bid_response_items
WHERE project_id = :'project_id'
  AND dimension = 'price'
  AND response_text ~ '(合同金额|业绩|类似项目|项目业绩|中标金额|合同价|历史业绩|业绩合同|已完成项目|完工项目金额|近\S*年\S*完成)';

\echo ''
\echo '======================================================================'
\echo '【验收2】qualification 维度应包含业绩金额（不是price）'
\echo '期望：> 0 行（有业绩证明）'
\echo '======================================================================'

SELECT COUNT(*) AS perf_in_qual
FROM tender_bid_response_items
WHERE project_id = :'project_id'
  AND dimension = 'qualification'
  AND response_text ~ '(合同金额|项目业绩|中标金额|业绩证明|完成项目)';

\echo ''
\echo '======================================================================'
\echo '【验收3】doc_structure 不应包含证书类文件'
\echo '期望：0 或极少（bad_doc_structure=0）'
\echo '======================================================================'

SELECT COUNT(*) AS bad_doc_structure
FROM tender_bid_response_items
WHERE project_id = :'project_id'
  AND dimension = 'doc_structure'
  AND response_text ~ '(营业执照|授权书|授权委托书|资质证书|安全生产许可证|保证金回执|基本存款账户|银行开户许可证)';

\echo ''
\echo '======================================================================'
\echo '【验收4】关键维度的核心字段至少各有一条'
\echo '期望：price_core > 0, duration_core > 0, warranty_core > 0'
\echo '======================================================================'

SELECT
  SUM(CASE WHEN dimension='price' AND response_text ~ '(投标总价|投标报价|报价表|开标一览表|投标函总价|报价一览)' THEN 1 ELSE 0 END) AS price_core,
  SUM(CASE WHEN dimension='schedule_quality' AND response_text ~ '(工期|90天|天|自然日|完成|交付)' THEN 1 ELSE 0 END) AS duration_core,
  SUM(CASE WHEN dimension='business' AND response_text ~ '(质保|保修|售后|服务期|月|年)' THEN 1 ELSE 0 END) AS warranty_core
FROM tender_bid_response_items
WHERE project_id=:'project_id';

\echo ''
\echo '======================================================================'
\echo '【验收5】normalized_fields_json 是否有数据'
\echo '期望：has_total_price > 0, has_duration > 0, has_warranty > 0'
\echo '======================================================================'

SELECT
  SUM(CASE WHEN normalized_fields_json->>'total_price_cny' IS NOT NULL THEN 1 ELSE 0 END) AS has_total_price,
  SUM(CASE WHEN normalized_fields_json->>'duration_days' IS NOT NULL THEN 1 ELSE 0 END) AS has_duration,
  SUM(CASE WHEN normalized_fields_json->>'warranty_months' IS NOT NULL THEN 1 ELSE 0 END) AS has_warranty
FROM tender_bid_response_items
WHERE project_id=:'project_id';

\echo ''
\echo '======================================================================'
\echo '【验收6】维度分布统计（确认数据合理性）'
\echo '期望：各维度都有合理数量的数据'
\echo '======================================================================'

SELECT 
  dimension,
  COUNT(*) AS count,
  COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS percentage
FROM tender_bid_response_items
WHERE project_id=:'project_id'
GROUP BY dimension
ORDER BY count DESC;

\echo ''
\echo '======================================================================'
\echo '【验收7】矫正器生效验证 - 查看是否有标记为 past_performance 的条目'
\echo '期望：> 0（说明矫正器捕获了业绩金额）'
\echo '======================================================================'

SELECT COUNT(*) AS corrected_performance
FROM tender_bid_response_items
WHERE project_id=:'project_id'
  AND dimension='qualification'
  AND extracted_value_json->>'type' = 'past_performance';

\echo ''
\echo '======================================================================'
\echo '【验收8】evidence_json 是否正确组装'
\echo '期望：大部分条目都有 evidence_json'
\echo '======================================================================'

SELECT
  COUNT(*) AS total,
  SUM(CASE WHEN evidence_json IS NOT NULL AND jsonb_array_length(evidence_json) > 0 THEN 1 ELSE 0 END) AS has_evidence,
  ROUND(100.0 * SUM(CASE WHEN evidence_json IS NOT NULL AND jsonb_array_length(evidence_json) > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS evidence_percentage
FROM tender_bid_response_items
WHERE project_id=:'project_id';

\echo ''
\echo '======================================================================'
\echo '【验收完成】'
\echo '如果所有验收都通过，说明三步改进都已生效！'
\echo '======================================================================'
