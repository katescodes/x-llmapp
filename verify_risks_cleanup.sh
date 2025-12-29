#!/bin/bash
echo "=========================================="
echo "Risks模块清理验证脚本"
echo "=========================================="
echo ""

echo "1. 检查后端关键文件和方法"
echo "----------------------------------------"

echo "✅ extract_requirements_v1 存在："
grep -q "async def extract_requirements_v1" backend/app/works/tender/extract_v2_service.py && echo "   YES" || echo "   NO - 错误！"

echo "✅ extract_risks路由存在（调用requirements）："
grep -q "@router.post.*extract/risks" backend/app/routers/tender.py && echo "   YES" || echo "   NO - 错误！"

echo "✅ get_requirements接口存在："
grep -q "@router.get.*requirements" backend/app/routers/tender.py && echo "   YES" || echo "   NO - 错误！"

echo "✅ ReviewPipelineV3._load_requirements存在："
grep -q "def _load_requirements" backend/app/works/tender/review_pipeline_v3.py && echo "   YES" || echo "   NO - 错误！"

echo ""
echo "2. 检查已删除的risks模块"
echo "----------------------------------------"

echo "❌ risks_v2.py已删除："
[ ! -f backend/app/works/tender/extraction_specs/risks_v2.py ] && echo "   YES (已删除)" || echo "   NO - 应该删除！"

echo "❌ extract_risks_v2方法已删除："
grep -q "async def extract_risks_v2" backend/app/works/tender/extract_v2_service.py && echo "   NO - 应该删除！" || echo "   YES (已删除)"

echo "❌ TenderService.extract_risks已删除："
grep -q "def extract_risks" backend/app/services/tender_service.py && echo "   NO - 应该删除！" || echo "   YES (已删除)"

echo ""
echo "3. 检查contract文件"
echo "----------------------------------------"

echo "✅ requirements能力定义存在："
grep -q "^requirements:" backend/app/works/tender/contracts/tender_contract_v1.yaml && echo "   YES" || echo "   NO - 错误！"

echo "✅ requirements必需字段数量："
grep -A 10 "required_fields:" backend/app/works/tender/contracts/tender_contract_v1.yaml | grep -c "^        -" || echo "0"

echo ""
echo "4. 检查前端文件"
echo "----------------------------------------"

echo "✅ extractRequirements函数存在："
grep -q "const extractRequirements" frontend/src/components/TenderWorkspace.tsx && echo "   YES" || echo "   NO - 错误！"

echo "✅ loadRiskAnalysis函数存在："
grep -q "const loadRiskAnalysis" frontend/src/components/TenderWorkspace.tsx && echo "   YES" || echo "   NO - 错误！"

echo "✅ 招标要求提取UI存在："
grep -q "招标要求提取" frontend/src/components/TenderWorkspace.tsx && echo "   YES" || echo "   NO - 错误！"

echo ""
echo "5. 检查数据库"
echo "----------------------------------------"

echo "✅ tender_requirements表存在："
docker-compose exec -T postgres psql -U localgpt -d localgpt -c "\d tender_requirements" > /dev/null 2>&1 && echo "   YES" || echo "   NO - 错误！"

echo "✅ prompt_templates中risks模块已删除："
RISKS_COUNT=$(docker-compose exec -T postgres psql -U localgpt -d localgpt -t -c "SELECT COUNT(*) FROM prompt_templates WHERE module = 'risks';" | tr -d ' ')
[ "$RISKS_COUNT" = "0" ] && echo "   YES (已删除)" || echo "   NO - 还有 $RISKS_COUNT 条记录"

echo ""
echo "=========================================="
echo "验证完成"
echo "=========================================="
