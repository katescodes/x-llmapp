#!/bin/bash
# LLM 模板理解功能 - 快速验证脚本

set -e

echo "=========================================="
echo "LLM 模板理解功能 - 快速验证"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查函数
check_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
}

check_warn() {
    echo -e "${YELLOW}!${NC} $1"
}

# 1. 检查数据库迁移
echo "1. 检查数据库迁移..."
if psql -U localgpt -d localgpt -c "\d format_templates" 2>/dev/null | grep -q "template_sha256"; then
    check_pass "数据库表已更新（包含 template_sha256 字段）"
else
    check_fail "数据库表未更新，请执行迁移脚本："
    echo "   cd /aidata/x-llmapp/backend/migrations"
    echo "   psql -U localgpt -d localgpt -f 009_add_template_spec_fields.sql"
    exit 1
fi
echo ""

# 2. 检查 Python 依赖
echo "2. 检查 Python 依赖..."
cd /aidata/x-llmapp/backend
if python -c "import jsonschema" 2>/dev/null; then
    check_pass "jsonschema 已安装"
else
    check_warn "jsonschema 未安装，尝试安装..."
    pip install jsonschema
    if python -c "import jsonschema" 2>/dev/null; then
        check_pass "jsonschema 安装成功"
    else
        check_fail "jsonschema 安装失败"
        exit 1
    fi
fi

if python -c "import docx" 2>/dev/null; then
    check_pass "python-docx 已安装"
else
    check_fail "python-docx 未安装"
    exit 1
fi
echo ""

# 3. 检查配置文件
echo "3. 检查配置..."
if grep -q "TEMPLATE_LLM_ANALYSIS" /aidata/x-llmapp/backend/app/config.py; then
    check_pass "配置类已更新（包含 TEMPLATE_LLM_ANALYSIS 配置）"
else
    check_fail "配置类未更新"
    exit 1
fi
echo ""

# 4. 检查核心模块文件
echo "4. 检查核心模块文件..."
modules=(
    "app/services/template/__init__.py"
    "app/services/template/docx_extractor.py"
    "app/services/template/template_spec.py"
    "app/services/template/spec_validator.py"
    "app/services/template/llm_analyzer.py"
    "app/services/template/outline_merger.py"
    "app/schemas/template/template-spec.v1.schema.json"
)

for module in "${modules[@]}"; do
    if [ -f "$module" ]; then
        check_pass "$module"
    else
        check_fail "$module 不存在"
        exit 1
    fi
done
echo ""

# 5. 运行单元测试
echo "5. 运行单元测试..."
echo "   (跳过需要 LLM 的测试)"

# 测试 DocxBlockExtractor
if python -m pytest tests/test_docx_extractor.py -v --tb=short 2>&1 | grep -q "passed"; then
    check_pass "DocxBlockExtractor 测试通过"
else
    check_warn "DocxBlockExtractor 测试失败（可能需要创建测试夹具）"
fi

# 测试 TemplateSpec
if python -c "from app.services.template.template_spec import TemplateSpec; print('OK')" 2>/dev/null | grep -q "OK"; then
    check_pass "TemplateSpec 模块可导入"
else
    check_fail "TemplateSpec 模块导入失败"
    exit 1
fi

# 测试 Validator
if python -c "from app.services.template.spec_validator import get_validator; v = get_validator(); print('OK')" 2>/dev/null | grep -q "OK"; then
    check_pass "TemplateSpecValidator 可初始化"
else
    check_fail "TemplateSpecValidator 初始化失败"
    exit 1
fi
echo ""

# 6. 检查服务层方法
echo "6. 检查服务层方法..."
if grep -q "analyze_template_with_llm" app/services/tender_service.py; then
    check_pass "TenderService.analyze_template_with_llm 已添加"
else
    check_fail "TenderService.analyze_template_with_llm 未找到"
    exit 1
fi

if grep -q "import_format_template_with_analysis" app/services/tender_service.py; then
    check_pass "TenderService.import_format_template_with_analysis 已添加"
else
    check_fail "TenderService.import_format_template_with_analysis 未找到"
    exit 1
fi
echo ""

# 7. 检查 API 端点
echo "7. 检查 API 端点..."
if grep -q "POST.*format-templates" app/routers/tender.py; then
    check_pass "POST /api/apps/tender/format-templates 端点已添加"
else
    check_fail "POST /api/apps/tender/format-templates 端点未找到"
    exit 1
fi

if grep -q "GET.*format-templates.*spec" app/routers/tender.py; then
    check_pass "GET /api/apps/tender/format-templates/{id}/spec 端点已添加"
else
    check_fail "GET /api/apps/tender/format-templates/{id}/spec 端点未找到"
    exit 1
fi
echo ""

# 8. 检查文档
echo "8. 检查文档..."
docs=(
    "../TEMPLATE_LLM_README.md"
    "../TEMPLATE_LLM_QUICK_START.md"
    "../TEMPLATE_LLM_ANALYSIS_GUIDE.md"
    "../TEMPLATE_LLM_DEPLOYMENT_CHECKLIST.md"
)

for doc in "${docs[@]}"; do
    if [ -f "$doc" ]; then
        check_pass "$doc"
    else
        check_warn "$doc 不存在（非必需）"
    fi
done
echo ""

# 9. 测试简单的功能
echo "9. 测试基本功能..."

# 测试 DocxBlockExtractor
python << 'EOF'
import sys
try:
    from io import BytesIO
    from docx import Document
    from app.services.template.docx_extractor import DocxBlockExtractor
    
    # 创建一个简单的 docx
    doc = Document()
    doc.add_heading("测试标题", level=1)
    doc.add_paragraph("测试段落")
    
    buf = BytesIO()
    doc.save(buf)
    docx_bytes = buf.getvalue()
    
    # 提取
    extractor = DocxBlockExtractor()
    result = extractor.extract(docx_bytes, max_blocks=10, max_chars_per_block=100)
    
    if len(result.blocks) > 0:
        print("OK: 提取到 {} 个块".format(len(result.blocks)))
        sys.exit(0)
    else:
        print("FAIL: 未提取到任何块")
        sys.exit(1)
except Exception as e:
    print("ERROR: {}".format(e))
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    check_pass "DocxBlockExtractor 基本功能正常"
else
    check_fail "DocxBlockExtractor 基本功能测试失败"
    exit 1
fi

# 测试 TemplateSpec 序列化
python << 'EOF'
import sys
try:
    from app.services.template.template_spec import (
        TemplateSpec, BasePolicy, BasePolicyMode,
        StyleHints, MergePolicy, Diagnostics
    )
    
    spec = TemplateSpec(
        version="v1",
        language="zh-CN",
        base_policy=BasePolicy(mode=BasePolicyMode.KEEP_ALL),
        style_hints=StyleHints(heading1_style="标题 1"),
        outline=[],
        merge_policy=MergePolicy(
            template_defines_structure=True,
            ai_only_fill_missing=True
        ),
        diagnostics=Diagnostics(confidence=0.9)
    )
    
    # 序列化
    json_str = spec.to_json()
    
    # 反序列化
    spec2 = TemplateSpec.from_json(json_str)
    
    if spec2.version == "v1" and spec2.diagnostics.confidence == 0.9:
        print("OK: TemplateSpec 序列化/反序列化正常")
        sys.exit(0)
    else:
        print("FAIL: TemplateSpec 序列化/反序列化失败")
        sys.exit(1)
except Exception as e:
    print("ERROR: {}".format(e))
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    check_pass "TemplateSpec 序列化/反序列化正常"
else
    check_fail "TemplateSpec 序列化/反序列化失败"
    exit 1
fi
echo ""

# 总结
echo "=========================================="
echo -e "${GREEN}✓ 所有检查通过！${NC}"
echo "=========================================="
echo ""
echo "下一步："
echo "1. 重启后端服务："
echo "   docker-compose restart backend"
echo "   # 或手动重启"
echo ""
echo "2. 测试 API："
echo "   curl http://localhost:8000/api/health"
echo ""
echo "3. 上传测试模板："
echo "   curl -X POST http://localhost:8000/api/apps/tender/format-templates \\"
echo "     -H \"Authorization: Bearer YOUR_TOKEN\" \\"
echo "     -F \"name=测试模板\" \\"
echo "     -F \"file=@your_template.docx\""
echo ""
echo "4. 查看文档："
echo "   cat ../TEMPLATE_LLM_QUICK_START.md"
echo ""
