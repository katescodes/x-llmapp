#!/bin/bash
# 投标响应抽取 V2 完整测试脚本

PROJECT_ID="tp_3f49f66ead6d46e1bac3f0bd16a3efe9"
BIDDER="123"

echo "======================================"
echo "投标响应抽取 V2 - 完整测试"
echo "======================================"
echo ""

echo "===== Step 1: 清理旧数据 ====="
docker-compose exec -T postgres psql -U localgpt -d localgpt << EOF
DELETE FROM tender_bid_response_items WHERE project_id='${PROJECT_ID}' AND bidder_name='${BIDDER}';
DELETE FROM tender_review_items WHERE project_id='${PROJECT_ID}' AND bidder_name='${BIDDER}';
SELECT 'Cleanup done' as status;
EOF
echo ""

echo "===== Step 2: 验收 - normalized_fields_json 写入 ====="
echo "检查数据库中的响应数据..."
docker-compose exec -T postgres psql -U localgpt -d localgpt << EOF
SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN normalized_fields_json IS NOT NULL AND normalized_fields_json != '{}' THEN 1 ELSE 0 END) as has_nf,
  SUM(CASE WHEN evidence_json IS NOT NULL THEN 1 ELSE 0 END) as has_ev,
  SUM(CASE WHEN jsonb_typeof(evidence_json) = 'array' THEN 1 ELSE 0 END) as ev_is_array
FROM tender_bid_response_items
WHERE project_id='${PROJECT_ID}' AND bidder_name='${BIDDER}';
EOF
echo ""

echo "===== Step 3: 查看各维度 normalized_fields ====="
docker-compose exec -T postgres psql -U localgpt -d localgpt << EOF
SELECT 
  dimension,
  COUNT(*) as count,
  SUM(CASE WHEN normalized_fields_json != '{}' THEN 1 ELSE 0 END) as has_fields
FROM tender_bid_response_items
WHERE project_id='${PROJECT_ID}' AND bidder_name='${BIDDER}'
GROUP BY dimension
ORDER BY dimension;
EOF
echo ""

echo "===== Step 4: 查看商务维度 normalized_fields 详情 ====="
docker-compose exec -T postgres psql -U localgpt -d localgpt << EOF
SELECT 
  dimension,
  normalized_fields_json->'total_price_cny' as price_cny,
  normalized_fields_json->'warranty_months' as warranty,
  normalized_fields_json->'duration_days' as duration,
  SUBSTRING(response_text, 1, 80) as response_text_preview
FROM tender_bid_response_items
WHERE project_id='${PROJECT_ID}' AND bidder_name='${BIDDER}'
AND dimension IN ('business', 'price')
LIMIT 5;
EOF
echo ""

echo "===== Step 5: 查看 evidence_json 结构 ====="
docker-compose exec -T postgres psql -U localgpt -d localgpt << EOF
SELECT 
  dimension,
  jsonb_array_length(evidence_json) as ev_count,
  evidence_json->0->'page_start' as first_page,
  evidence_json->0->'source' as first_source,
  LENGTH(evidence_json->0->>'quote') as first_quote_len
FROM tender_bid_response_items
WHERE project_id='${PROJECT_ID}' AND bidder_name='${BIDDER}'
AND evidence_json IS NOT NULL
LIMIT 5;
EOF
echo ""

echo "===== Step 6: 验收审核结果 ====="
docker-compose exec -T postgres psql -U localgpt -d localgpt << EOF
SELECT 
  dimension,
  status,
  COUNT(*) as count
FROM tender_review_items
WHERE project_id='${PROJECT_ID}' AND bidder_name='${BIDDER}'
GROUP BY dimension, status
ORDER BY dimension, status;
EOF
echo ""

echo "===== Step 7: 查看 consistency 维度详情 ====="
docker-compose exec -T postgres psql -U localgpt -d localgpt << EOF
SELECT 
  requirement_id,
  status,
  remark,
  jsonb_typeof(evidence_json) as ev_type
FROM tender_review_items
WHERE project_id='${PROJECT_ID}' AND bidder_name='${BIDDER}'
AND dimension='consistency';
EOF
echo ""

echo "======================================"
echo "测试完成！"
echo "======================================"
echo ""
echo "验收指标:"
echo "  ✅ has_nf >= 70% (至少70%响应有normalized_fields)"
echo "  ✅ has_ev >= 70% (至少70%响应有evidence_json)"
echo "  ✅ 商务维度有 total_price_cny/warranty_months/duration_days"
echo "  ✅ evidence_json 包含 page_start/source/quote"
echo "  ✅ consistency 维度不再全是 PENDING"

