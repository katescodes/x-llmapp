#!/bin/bash
# 范本提取诊断工具
# 用法: ./diagnose_fragments.sh [project_id]

echo "=========================================="
echo "范本提取诊断工具"
echo "=========================================="
echo ""

PROJECT_ID="$1"

if [ -z "$PROJECT_ID" ]; then
    echo "⚠️  未提供项目ID，将显示最近的提取记录"
    echo ""
fi

echo "📊 1. 检查范本提取日志"
echo "----------------------------------------"
if [ -n "$PROJECT_ID" ]; then
    docker-compose logs backend | grep -E "samples.*$PROJECT_ID" | tail -30
else
    docker-compose logs backend | grep -E "auto_fill_samples|extractor" | tail -50
fi
echo ""

echo "📊 2. 查看提取统计"
echo "----------------------------------------"
docker-compose logs backend | grep -E "(upserted_fragments|fragments_detected|llm_used)" | tail -20
echo ""

echo "📊 3. 检查LLM定位"
echo "----------------------------------------"
docker-compose logs backend | grep -E "llm spans" | tail -10
echo ""

echo "📊 4. 查看警告信息"
echo "----------------------------------------"
docker-compose logs backend | grep -E "未能抽取|使用内置范本库|needs_reupload" | tail -10
echo ""

echo "📊 5. 检查错误"
echo "----------------------------------------"
docker-compose logs backend | grep -E "ERROR.*fragment" | tail -10
echo ""

echo "=========================================="
echo "诊断完成"
echo "=========================================="
echo ""
echo "💡 解读提示:"
echo "  - upserted_fragments: X  →  实际入库的范本数（应 > 0）"
echo "  - llm_used: true/false  →  是否使用了LLM定位"
echo "  - warnings: [...]       →  查看具体警告信息"
echo ""
echo "📖 详细文档: FRAGMENT_EXTRACTION_TROUBLESHOOTING.md"

