#!/bin/bash
# 方案D测试验证脚本

PROJECT_ID="tp_9160ce348db444e9b5a3fa4b66e8680a"

echo "=========================================="
echo "方案D测试验证"
echo "=========================================="
echo ""

echo "【测试1】查看提取结果的整体结构"
echo "---"
docker exec localgpt-postgres psql -U localgpt -d localgpt -c "
SELECT 
    project_id,
    jsonb_typeof(data_json) as data_type,
    jsonb_object_keys(data_json) as top_level_keys
FROM tender_project_info
WHERE project_id = '$PROJECT_ID'
LIMIT 1;
"
echo ""

echo "【测试2】查看base字段（检查自定义字段）"
echo "---"
docker exec localgpt-postgres psql -U localgpt -d localgpt -c "
SELECT 
    jsonb_pretty(data_json->'base') as base_info
FROM tender_project_info
WHERE project_id = '$PROJECT_ID';
"
echo ""

echo "【测试3】查看technical_parameters的第一条（检查新字段）"
echo "---"
docker exec localgpt-postgres psql -U localgpt -d localgpt -c "
SELECT 
    jsonb_pretty(data_json->'technical_parameters'->0) as first_tech_param
FROM tender_project_info
WHERE project_id = '$PROJECT_ID';
"
echo ""

echo "【测试4】统计technical_parameters的字段使用情况"
echo "---"
docker exec localgpt-postgres psql -U localgpt -d localgpt -c "
SELECT 
    COUNT(*) as total_count,
    COUNT(*) FILTER (WHERE tp ? 'description') as has_description,
    COUNT(*) FILTER (WHERE tp ? 'structured') as has_structured,
    COUNT(*) FILTER (WHERE tp ? 'requirement') as has_requirement,
    COUNT(*) FILTER (WHERE tp ? 'parameters') as has_parameters
FROM tender_project_info,
     jsonb_array_elements(data_json->'technical_parameters') as tp
WHERE project_id = '$PROJECT_ID';
"
echo ""

echo "【测试5】查看business_terms的第一条（检查新字段）"
echo "---"
docker exec localgpt-postgres psql -U localgpt -d localgpt -c "
SELECT 
    jsonb_pretty(data_json->'business_terms'->0) as first_business_term
FROM tender_project_info
WHERE project_id = '$PROJECT_ID';
"
echo ""

echo "【测试6】统计business_terms的字段使用情况"
echo "---"
docker exec localgpt-postgres psql -U localgpt -d localgpt -c "
SELECT 
    COUNT(*) as total_count,
    COUNT(*) FILTER (WHERE bt ? 'description') as has_description,
    COUNT(*) FILTER (WHERE bt ? 'structured') as has_structured,
    COUNT(*) FILTER (WHERE bt ? 'requirement') as has_requirement
FROM tender_project_info,
     jsonb_array_elements(data_json->'business_terms') as bt
WHERE project_id = '$PROJECT_ID';
"
echo ""

echo "【测试7】查看提取数量"
echo "---"
docker exec localgpt-postgres psql -U localgpt -d localgpt -c "
SELECT 
    jsonb_array_length(data_json->'technical_parameters') as tech_count,
    jsonb_array_length(data_json->'business_terms') as business_count
FROM tender_project_info
WHERE project_id = '$PROJECT_ID';
"
echo ""

echo "【测试8】查看开标时间和投标截止时间"
echo "---"
docker exec localgpt-postgres psql -U localgpt -d localgpt -c "
SELECT 
    data_json->'base'->>'bidOpeningTime' as opening_time,
    data_json->'base'->>'bidDeadline' as deadline
FROM tender_project_info
WHERE project_id = '$PROJECT_ID';
"
echo ""

echo "=========================================="
echo "测试完成！"
echo "=========================================="
echo ""
echo "预期结果："
echo "  ✅ base中可能有自定义字段（如'项目规模'、'建设单位'等）"
echo "  ✅ technical_parameters中有description或structured字段"
echo "  ✅ business_terms中有description或structured字段"
echo "  ✅ 技术参数数量 > 20条"
echo "  ✅ 商务条款数量 > 15条"
echo "  ✅ 开标时间 = 投标截止时间"
echo ""

