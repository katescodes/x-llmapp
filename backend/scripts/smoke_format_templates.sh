#!/bin/bash
#
# 格式模板功能 Smoke Test
# 验证：上传模板 -> 预览 -> 套用 -> 下载
#

set -e

# ==================== 配置 ====================

# API 基础 URL
API_BASE="${API_BASE:-http://localhost:8000}"
API_PREFIX="${API_PREFIX:-/api/apps/tender}"

# 认证 Token（从环境变量获取，或使用测试token）
AUTH_TOKEN="${AUTH_TOKEN:-test_token_123}"

# 测试用模板文件（需要提前准备一个 .docx 文件）
TEMPLATE_FILE="${TEMPLATE_FILE:-./test_template.docx}"

# 输出目录
OUTPUT_DIR="/tmp/format_templates_smoke_test"
mkdir -p "$OUTPUT_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ==================== 辅助函数 ====================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_response() {
    local response="$1"
    local expected_status="$2"
    local description="$3"
    
    if echo "$response" | grep -q "\"ok\".*true\|\"success\".*true\|\"id\".*:"; then
        log_info "✅ $description - 成功"
        return 0
    else
        log_error "❌ $description - 失败"
        echo "$response"
        return 1
    fi
}

# ==================== 测试步骤 ====================

log_info "========================================"
log_info "格式模板功能 Smoke Test"
log_info "========================================"
log_info "API Base: $API_BASE"
log_info "Output Dir: $OUTPUT_DIR"
log_info ""

# Step 0: 检查模板文件
log_info "Step 0: 检查测试模板文件..."
if [ ! -f "$TEMPLATE_FILE" ]; then
    log_error "测试模板文件不存在: $TEMPLATE_FILE"
    log_warn "请提供一个包含 Logo/页眉的 .docx 文件"
    log_warn "使用方式: TEMPLATE_FILE=/path/to/template.docx $0"
    exit 1
fi
log_info "✅ 模板文件存在: $TEMPLATE_FILE"

# Step 1: 创建或获取项目
log_info ""
log_info "Step 1: 创建测试项目..."
PROJECT_RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"name":"格式模板测试项目","description":"Smoke Test"}' \
    "${API_BASE}${API_PREFIX}/projects" || echo '{"error":"创建失败"}')

if echo "$PROJECT_RESPONSE" | grep -q "\"id\""; then
    PROJECT_ID=$(echo "$PROJECT_RESPONSE" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    log_info "✅ 项目创建成功: $PROJECT_ID"
else
    log_warn "项目创建失败，尝试使用现有项目..."
    # 获取第一个项目
    LIST_RESPONSE=$(curl -s -X GET \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        "${API_BASE}${API_PREFIX}/projects" || echo '[]')
    PROJECT_ID=$(echo "$LIST_RESPONSE" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    
    if [ -z "$PROJECT_ID" ]; then
        log_error "无法获取项目ID，请检查 API 和认证"
        exit 1
    fi
    log_info "使用现有项目: $PROJECT_ID"
fi

# Step 2: 上传格式模板
log_info ""
log_info "Step 2: 上传格式模板..."
UPLOAD_RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    -F "file=@${TEMPLATE_FILE}" \
    -F "name=Smoke Test 模板" \
    -F "description=用于自动化测试" \
    -F "is_public=false" \
    "${API_BASE}${API_PREFIX}/format-templates" || echo '{"error":"上传失败"}')

if echo "$UPLOAD_RESPONSE" | grep -q "\"template_id\""; then
    TEMPLATE_ID=$(echo "$UPLOAD_RESPONSE" | grep -o '"template_id":"[^"]*"' | cut -d'"' -f4)
    log_info "✅ 模板上传成功: $TEMPLATE_ID"
else
    log_error "❌ 模板上传失败"
    echo "$UPLOAD_RESPONSE"
    exit 1
fi

# Step 3: 获取模板预览 (PDF)
log_info ""
log_info "Step 3: 获取模板预览 (PDF)..."
PREVIEW_PDF="${OUTPUT_DIR}/template_preview.pdf"
HTTP_CODE=$(curl -s -w "%{http_code}" -o "$PREVIEW_PDF" \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    "${API_BASE}${API_PREFIX}/format-templates/${TEMPLATE_ID}/preview?format=pdf")

if [ "$HTTP_CODE" = "200" ] && [ -f "$PREVIEW_PDF" ] && [ -s "$PREVIEW_PDF" ]; then
    log_info "✅ 模板预览 PDF 下载成功: $PREVIEW_PDF"
    log_warn "请手动打开此文件确认 Logo/页眉是否存在"
else
    log_warn "⚠️  模板预览 PDF 下载失败 (HTTP $HTTP_CODE)，可能未实现PDF转换"
fi

# Step 4: 套用格式模板到项目 (return_type=json)
log_info ""
log_info "Step 4: 套用格式模板到项目 (JSON)..."
APPLY_RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"format_template_id\":\"${TEMPLATE_ID}\"}" \
    "${API_BASE}${API_PREFIX}/projects/${PROJECT_ID}/directory/apply-format-template?return_type=json" \
    || echo '{"ok":false,"detail":"请求失败"}')

echo "$APPLY_RESPONSE" > "${OUTPUT_DIR}/apply_response.json"

if echo "$APPLY_RESPONSE" | grep -q "\"ok\".*true"; then
    log_info "✅ 格式模板套用成功"
    
    # 提取 URL
    PREVIEW_PDF_URL=$(echo "$APPLY_RESPONSE" | grep -o '"preview_pdf_url":"[^"]*"' | cut -d'"' -f4)
    DOWNLOAD_DOCX_URL=$(echo "$APPLY_RESPONSE" | grep -o '"download_docx_url":"[^"]*"' | cut -d'"' -f4)
    
    if [ -n "$PREVIEW_PDF_URL" ]; then
        log_info "✅ 返回了 preview_pdf_url: $PREVIEW_PDF_URL"
    else
        log_error "❌ 未返回 preview_pdf_url"
    fi
    
    if [ -n "$DOWNLOAD_DOCX_URL" ]; then
        log_info "✅ 返回了 download_docx_url: $DOWNLOAD_DOCX_URL"
    else
        log_error "❌ 未返回 download_docx_url"
    fi
else
    log_error "❌ 格式模板套用失败"
    echo "$APPLY_RESPONSE"
    exit 1
fi

# Step 5: 下载预览 PDF
log_info ""
log_info "Step 5: 下载预览 PDF..."
if [ -n "$PREVIEW_PDF_URL" ]; then
    PREVIEW_OUTPUT="${OUTPUT_DIR}/project_preview.pdf"
    HTTP_CODE=$(curl -s -w "%{http_code}" -o "$PREVIEW_OUTPUT" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        "${API_BASE}${PREVIEW_PDF_URL}")
    
    if [ "$HTTP_CODE" = "200" ] && [ -f "$PREVIEW_OUTPUT" ] && [ -s "$PREVIEW_OUTPUT" ]; then
        log_info "✅ 预览 PDF 下载成功: $PREVIEW_OUTPUT"
        log_warn "请手动打开此文件确认：页眉、Logo、内容完整性"
    else
        log_error "❌ 预览 PDF 下载失败 (HTTP $HTTP_CODE)"
    fi
else
    log_warn "⚠️  跳过预览 PDF 下载（未返回URL）"
fi

# Step 6: 下载 DOCX
log_info ""
log_info "Step 6: 下载 DOCX..."
if [ -n "$DOWNLOAD_DOCX_URL" ]; then
    DOCX_OUTPUT="${OUTPUT_DIR}/project_export.docx"
    HTTP_CODE=$(curl -s -w "%{http_code}" -o "$DOCX_OUTPUT" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        "${API_BASE}${DOWNLOAD_DOCX_URL}")
    
    if [ "$HTTP_CODE" = "200" ] && [ -f "$DOCX_OUTPUT" ] && [ -s "$DOCX_OUTPUT" ]; then
        log_info "✅ DOCX 下载成功: $DOCX_OUTPUT"
        log_warn "请手动打开此文件确认：页眉 Logo 存在、内容完整"
        
        # 尝试用 unzip 检查 DOCX 结构
        if command -v unzip &> /dev/null; then
            log_info "检查 DOCX 内部结构..."
            if unzip -l "$DOCX_OUTPUT" | grep -q "word/header"; then
                log_info "✅ 包含页眉部分 (word/header)"
            else
                log_warn "⚠️  未检测到页眉部分"
            fi
            
            if unzip -l "$DOCX_OUTPUT" | grep -q "word/media/"; then
                log_info "✅ 包含媒体文件 (word/media/)"
            else
                log_warn "⚠️  未检测到媒体文件（Logo可能丢失）"
            fi
        fi
    else
        log_error "❌ DOCX 下载失败 (HTTP $HTTP_CODE)"
    fi
else
    log_error "❌ 跳过 DOCX 下载（未返回URL）"
    exit 1
fi

# ==================== 总结 ====================

log_info ""
log_info "========================================"
log_info "Smoke Test 完成！"
log_info "========================================"
log_info "输出文件位于: $OUTPUT_DIR"
log_info ""
log_info "请手动验证以下文件："
log_info "1. $OUTPUT_DIR/template_preview.pdf - 模板原始预览"
log_info "2. $OUTPUT_DIR/project_preview.pdf - 项目套用后预览"
log_info "3. $OUTPUT_DIR/project_export.docx - 项目导出 DOCX"
log_info ""
log_warn "验收标准："
log_warn "✅ 所有文件均可打开"
log_warn "✅ DOCX 中包含模板的页眉 Logo"
log_warn "✅ PDF 预览正常显示（如果 LibreOffice 已安装）"
log_info ""
log_info "如需清理，执行: rm -rf $OUTPUT_DIR"

# 清理测试项目（可选，默认不清理）
if [ "${CLEANUP:-no}" = "yes" ]; then
    log_info ""
    log_info "清理测试数据..."
    curl -s -X DELETE \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        "${API_BASE}${API_PREFIX}/format-templates/${TEMPLATE_ID}" > /dev/null
    curl -s -X DELETE \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        "${API_BASE}${API_PREFIX}/projects/${PROJECT_ID}" > /dev/null
    log_info "✅ 测试数据已清理"
fi

exit 0

