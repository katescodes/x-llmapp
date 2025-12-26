#!/bin/bash
# 测试项目自动填充功能
# 用法: ./test_autofill.sh

PROJECT_ID="tp_9160ce348db444e9b5a3fa4b66e8680a"

echo "=========================================="
echo "测试项目自动填充功能"
echo "=========================================="
echo ""
echo "项目ID: $PROJECT_ID"
echo ""

# 启动日志监控（后台）
echo "🔍 启动实时日志监控..."
docker-compose logs -f backend 2>&1 | grep -E "(auto_fill|OutlineSampleAttacher|LLMFragmentMatcher|generate_directory)" &
LOG_PID=$!

sleep 2

echo ""
echo "📞 调用 auto_fill_samples API..."
echo ""

# 调用API
RESPONSE=$(curl -s -X POST "http://localhost:9001/api/apps/tender/projects/$PROJECT_ID/directory/auto-fill-samples" \
  -H "Content-Type: application/json" \
  -d '{}')

echo "API响应:"
echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"

sleep 5

# 停止日志监控
kill $LOG_PID 2>/dev/null

echo ""
echo "=========================================="
echo "测试完成"
echo "=========================================="
echo ""
echo "💡 查看完整日志:"
echo "   docker-compose logs backend | grep -A 20 'auto_fill_samples' | tail -100"

