#!/bin/bash

# 测试录音导入导出功能
# 使用方法: ./test_recording_import_export.sh <API_BASE_URL> <AUTH_TOKEN>

API_BASE_URL=${1:-"http://localhost:8000"}
AUTH_TOKEN=${2:-""}

if [ -z "$AUTH_TOKEN" ]; then
    echo "❌ 请提供认证令牌"
    echo "使用方法: $0 <API_BASE_URL> <AUTH_TOKEN>"
    exit 1
fi

echo "🧪 开始测试录音导入导出功能"
echo "API地址: $API_BASE_URL"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试结果统计
PASS=0
FAIL=0

# 测试函数
test_case() {
    local test_name=$1
    echo -e "${YELLOW}📋 测试: $test_name${NC}"
}

pass_test() {
    echo -e "${GREEN}✅ 通过${NC}"
    ((PASS++))
    echo ""
}

fail_test() {
    local reason=$1
    echo -e "${RED}❌ 失败: $reason${NC}"
    ((FAIL++))
    echo ""
}

# ============================================
# 测试1: 获取录音列表
# ============================================
test_case "获取录音列表"
RESPONSE=$(curl -s -w "\n%{http_code}" -X GET \
    "$API_BASE_URL/api/recordings?page=1&page_size=20" \
    -H "Authorization: Bearer $AUTH_TOKEN")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    TOTAL=$(echo "$BODY" | grep -o '"total":[0-9]*' | cut -d':' -f2)
    echo "找到 $TOTAL 条录音"
    pass_test
else
    fail_test "HTTP $HTTP_CODE"
fi

# ============================================
# 测试2: 创建测试音频文件并上传
# ============================================
test_case "上传音频文件"

# 创建一个小的测试音频文件 (使用ffmpeg生成1秒的静音)
TEST_AUDIO="/tmp/test_audio_$(date +%s).mp3"

if command -v ffmpeg &> /dev/null; then
    # 生成1秒的静音音频
    ffmpeg -f lavfi -i anullsrc=r=16000:cl=mono -t 1 -q:a 9 -acodec libmp3lame "$TEST_AUDIO" -y &>/dev/null
    
    if [ -f "$TEST_AUDIO" ]; then
        echo "生成测试音频文件: $TEST_AUDIO"
        
        # 上传文件
        UPLOAD_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
            "$API_BASE_URL/api/recordings/upload" \
            -H "Authorization: Bearer $AUTH_TOKEN" \
            -F "file=@$TEST_AUDIO" \
            -F "title=测试导入音频")
        
        HTTP_CODE=$(echo "$UPLOAD_RESPONSE" | tail -n1)
        BODY=$(echo "$UPLOAD_RESPONSE" | sed '$d')
        
        if [ "$HTTP_CODE" = "200" ]; then
            RECORDING_ID=$(echo "$BODY" | grep -o '"recording_id":"[^"]*"' | cut -d'"' -f4)
            echo "上传成功! Recording ID: $RECORDING_ID"
            pass_test
            
            # ============================================
            # 测试3: 下载录音文件
            # ============================================
            test_case "下载录音文件"
            
            DOWNLOAD_FILE="/tmp/downloaded_$(date +%s).mp3"
            HTTP_CODE=$(curl -s -w "%{http_code}" -X GET \
                "$API_BASE_URL/api/recordings/$RECORDING_ID/download" \
                -H "Authorization: Bearer $AUTH_TOKEN" \
                -o "$DOWNLOAD_FILE")
            
            if [ "$HTTP_CODE" = "200" ] && [ -f "$DOWNLOAD_FILE" ]; then
                FILE_SIZE=$(stat -f%z "$DOWNLOAD_FILE" 2>/dev/null || stat -c%s "$DOWNLOAD_FILE" 2>/dev/null)
                echo "下载成功! 文件大小: $FILE_SIZE 字节"
                
                # 验证文件是否可读
                if [ "$FILE_SIZE" -gt 0 ]; then
                    pass_test
                else
                    fail_test "下载的文件为空"
                fi
                
                # 清理下载的文件
                rm -f "$DOWNLOAD_FILE"
            else
                fail_test "HTTP $HTTP_CODE 或文件未创建"
            fi
            
            # ============================================
            # 测试4: 播放音频URL（检查是否可访问）
            # ============================================
            test_case "获取音频流URL"
            
            HTTP_CODE=$(curl -s -w "%{http_code}" -o /dev/null -X GET \
                "$API_BASE_URL/api/recordings/$RECORDING_ID/audio?token=$AUTH_TOKEN")
            
            if [ "$HTTP_CODE" = "200" ]; then
                echo "音频流可访问"
                pass_test
            else
                fail_test "HTTP $HTTP_CODE"
            fi
            
            # ============================================
            # 测试5: 转写音频（如果ASR服务可用）
            # ============================================
            test_case "转写音频（可选）"
            
            TRANSCRIBE_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
                "$API_BASE_URL/api/recordings/$RECORDING_ID/transcribe" \
                -H "Authorization: Bearer $AUTH_TOKEN" \
                -H "Content-Type: application/json" \
                -d '{"enhance": false, "enhancement_type": "punctuation"}')
            
            HTTP_CODE=$(echo "$TRANSCRIBE_RESPONSE" | tail -n1)
            BODY=$(echo "$TRANSCRIBE_RESPONSE" | sed '$d')
            
            if [ "$HTTP_CODE" = "200" ]; then
                WORD_COUNT=$(echo "$BODY" | grep -o '"word_count":[0-9]*' | cut -d':' -f2)
                echo "转写成功! 字数: $WORD_COUNT"
                pass_test
            else
                echo "转写失败（可能ASR服务未配置）: HTTP $HTTP_CODE"
                echo "这是可选测试，不计入失败"
            fi
            
            # ============================================
            # 测试6: 删除测试录音
            # ============================================
            test_case "删除测试录音"
            
            HTTP_CODE=$(curl -s -w "%{http_code}" -o /dev/null -X DELETE \
                "$API_BASE_URL/api/recordings/$RECORDING_ID" \
                -H "Authorization: Bearer $AUTH_TOKEN")
            
            if [ "$HTTP_CODE" = "200" ]; then
                echo "删除成功"
                pass_test
            else
                fail_test "HTTP $HTTP_CODE"
            fi
            
        else
            fail_test "HTTP $HTTP_CODE - $BODY"
        fi
        
        # 清理测试文件
        rm -f "$TEST_AUDIO"
    else
        fail_test "无法生成测试音频文件"
    fi
else
    echo "⚠️ 未找到ffmpeg，跳过上传测试"
    echo "提示: 您可以手动测试上传功能"
fi

# ============================================
# 测试7: 上传不支持的文件格式
# ============================================
test_case "上传不支持的文件格式（预期失败）"

TEST_TXT="/tmp/test.txt"
echo "This is a text file" > "$TEST_TXT"

UPLOAD_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
    "$API_BASE_URL/api/recordings/upload" \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    -F "file=@$TEST_TXT")

HTTP_CODE=$(echo "$UPLOAD_RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "400" ]; then
    echo "正确拒绝了不支持的文件格式"
    pass_test
else
    fail_test "应该返回400，实际返回 HTTP $HTTP_CODE"
fi

rm -f "$TEST_TXT"

# ============================================
# 输出测试结果
# ============================================
echo "================================"
echo "📊 测试结果统计"
echo "================================"
echo -e "${GREEN}✅ 通过: $PASS${NC}"
echo -e "${RED}❌ 失败: $FAIL${NC}"
echo "总计: $((PASS + FAIL))"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}🎉 所有测试通过！${NC}"
    exit 0
else
    echo -e "${RED}⚠️ 有 $FAIL 个测试失败${NC}"
    exit 1
fi

