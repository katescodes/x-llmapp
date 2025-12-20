#!/bin/bash
# 测试项目删除功能

set -e

API_BASE="http://localhost:9001/api"
TOKEN=""

echo "=== 测试项目删除功能 ==="
echo ""

# 1. 登录获取token（如果需要）
echo "1. 准备测试环境..."
# 这里假设已经有登录token，或者系统不需要认证

# 2. 创建测试项目
echo "2. 创建测试项目..."
PROJECT_RESPONSE=$(curl -s -X POST "$API_BASE/apps/tender/projects" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "删除测试项目_'$(date +%s)'",
    "description": "这是一个用于测试删除功能的项目"
  }')

PROJECT_ID=$(echo $PROJECT_RESPONSE | jq -r '.id')
PROJECT_NAME=$(echo $PROJECT_RESPONSE | jq -r '.name')

if [ "$PROJECT_ID" == "null" ] || [ -z "$PROJECT_ID" ]; then
  echo "❌ 创建项目失败"
  echo "$PROJECT_RESPONSE"
  exit 1
fi

echo "✅ 项目创建成功: $PROJECT_ID ($PROJECT_NAME)"
echo ""

# 3. 获取删除计划
echo "3. 获取删除计划..."
PLAN_RESPONSE=$(curl -s -X GET "$API_BASE/apps/tender/projects/$PROJECT_ID/delete-plan")

CONFIRM_TOKEN=$(echo $PLAN_RESPONSE | jq -r '.confirm_token')

if [ "$CONFIRM_TOKEN" == "null" ] || [ -z "$CONFIRM_TOKEN" ]; then
  echo "❌ 获取删除计划失败"
  echo "$PLAN_RESPONSE"
  exit 1
fi

echo "✅ 删除计划获取成功"
echo "确认令牌: $CONFIRM_TOKEN"
echo "删除计划:"
echo "$PLAN_RESPONSE" | jq '.items'
echo ""

# 4. 执行删除
echo "4. 执行删除操作..."
DELETE_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X DELETE "$API_BASE/apps/tender/projects/$PROJECT_ID" \
  -H "Content-Type: application/json" \
  -d "{
    \"confirm_text\": \"$PROJECT_NAME\",
    \"confirm_token\": \"$CONFIRM_TOKEN\"
  }")

HTTP_CODE=$(echo "$DELETE_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
RESPONSE_BODY=$(echo "$DELETE_RESPONSE" | grep -v "HTTP_CODE:")

if [ "$HTTP_CODE" == "204" ]; then
  echo "✅ 项目删除成功 (HTTP 204)"
else
  echo "❌ 项目删除失败 (HTTP $HTTP_CODE)"
  echo "$RESPONSE_BODY"
  exit 1
fi

echo ""

# 5. 验证项目已删除
echo "5. 验证项目已删除..."
VERIFY_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X GET "$API_BASE/apps/tender/projects/$PROJECT_ID")
VERIFY_HTTP_CODE=$(echo "$VERIFY_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)

if [ "$VERIFY_HTTP_CODE" == "404" ] || [ "$VERIFY_HTTP_CODE" == "500" ]; then
  echo "✅ 验证成功：项目已不存在"
else
  echo "⚠️  项目仍然存在 (HTTP $VERIFY_HTTP_CODE)"
fi

echo ""
echo "=== 测试完成 ==="




