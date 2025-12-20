#!/bin/bash
# Smoke 测试验证脚本

echo "======================================"
echo "  Smoke 测试环境验证"
echo "======================================"
echo ""

# 检查文件存在性
echo "📁 检查文件..."
files=(
    "testdata/tender_sample.pdf"
    "testdata/bid_sample.docx"
    "testdata/rules.yaml"
    "scripts/smoke/tender_e2e.py"
    "scripts/smoke/README.md"
    "backend/pytest.ini"
    "backend/tests/smoke/test_tender_e2e.py"
    "SMOKE_TEST.md"
)

missing=0
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✓ $file"
    else
        echo "  ✗ $file (缺失)"
        missing=$((missing + 1))
    fi
done

echo ""

if [ $missing -eq 0 ]; then
    echo "✅ 所有文件都存在！"
else
    echo "❌ 缺失 $missing 个文件"
    exit 1
fi

echo ""
echo "📋 测试数据统计:"
echo "  招标文件: $(du -h testdata/tender_sample.pdf | cut -f1)"
echo "  投标文件: $(du -h testdata/bid_sample.docx | cut -f1)"
echo "  测试脚本: $(du -h scripts/smoke/tender_e2e.py | cut -f1)"

echo ""
echo "🔍 Python 语法检查..."
if python -m py_compile scripts/smoke/tender_e2e.py 2>/dev/null; then
    echo "  ✓ tender_e2e.py 语法正确"
else
    echo "  ✗ tender_e2e.py 语法错误"
    exit 1
fi

if python -m py_compile backend/tests/smoke/test_tender_e2e.py 2>/dev/null; then
    echo "  ✓ test_tender_e2e.py 语法正确"
else
    echo "  ✗ test_tender_e2e.py 语法错误"
    exit 1
fi

echo ""
echo "======================================"
echo "✅ 验证完成！环境就绪。"
echo "======================================"
echo ""
echo "下一步："
echo "  1. 启动服务: docker compose up -d --build"
echo "  2. 运行测试: python scripts/smoke/tender_e2e.py"
echo ""
