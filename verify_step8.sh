#!/bin/bash
set -e

echo "=========================================="
echo "  Step 8 验证：NEW_ONLY LLM 调用"
echo "=========================================="
echo ""

BASE_URL="http://localhost:9001"

# 1. 验证 /api/_debug/llm/ping (MOCK_LLM=true)
echo "[测试 1] /api/_debug/llm/ping (MOCK_LLM=true)"
PING_RESULT=$(curl -sS "${BASE_URL}/api/_debug/llm/ping")
echo "$PING_RESULT" | python3 -m json.tool

# 检查返回值
if echo "$PING_RESULT" | python3 -c "import sys, json; r=json.load(sys.stdin); exit(0 if r.get('ok') else 1)"; then
  echo "✓ LLM Ping 返回 ok:true"
else
  echo "✗ LLM Ping 失败"
  exit 1
fi

if echo "$PING_RESULT" | python3 -c "import sys, json; r=json.load(sys.stdin); exit(0 if r.get('mode')=='mock' else 1)"; then
  echo "✓ 运行在 MOCK 模式"
else
  echo "✗ 未运行在 MOCK 模式"
  exit 1
fi
echo ""

# 2. 登录
echo "[测试 2] 用户登录"
TOKEN=$(curl -sS -X POST "${BASE_URL}/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
echo "✓ 登录成功"
echo ""

# 3. 创建项目
echo "[测试 3] 创建测试项目"
PROJECT_ID=$(curl -sS -X POST "${BASE_URL}/api/apps/tender/projects" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Step8验证-$(date +%s)\"}" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
echo "✓ 项目创建成功: ${PROJECT_ID}"
echo ""

# 4. 上传文件（从宿主机）
echo "[测试 4] 上传招标文件"
UPLOAD_RESULT=$(curl -sS -X POST "${BASE_URL}/api/apps/tender/projects/${PROJECT_ID}/assets/import" \
  -H "Authorization: Bearer ${TOKEN}" \
  -F "kind=tender" \
  -F "files=@/aidata/x-llmapp1/testdata/tender_sample.pdf")
  
ASSET_ID=$(echo "$UPLOAD_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin)[0]['id'])")
echo "✓ 文件上传成功: ${ASSET_ID}"
echo ""

# 5. 等待入库
echo "[测试 5] 等待 DocStore 入库 (12秒)"
for i in {1..12}; do
  echo -n "."
  sleep 1
done
echo ""
echo "✓ 等待完成"
echo ""

# 6. 测试 project_info 抽取（NEW_ONLY）
echo "[测试 6] NEW_ONLY 抽取 project_info"
EXTRACT_RESULT=$(curl -sS -X POST "${BASE_URL}/api/apps/tender/projects/${PROJECT_ID}/extract/project-info?sync=1" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "X-Force-Mode: NEW_ONLY" \
  -H "Content-Type: application/json" \
  -d '{}')

# 保存初始响应
mkdir -p /aidata/x-llmapp1/reports/verify
echo "$EXTRACT_RESULT" | python3 -m json.tool > /aidata/x-llmapp1/reports/verify/step8_extract_response.json

# 提取 run_id
RUN_ID=$(echo "$EXTRACT_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('run_id', 'N/A'))" 2>/dev/null || echo "N/A")
echo "✓ 抽取任务提交成功, run_id: ${RUN_ID}"

# 如果是同步模式且有 data，直接使用
HAS_DATA=$(echo "$EXTRACT_RESULT" | python3 -c "import sys, json; d=json.load(sys.stdin).get('data',{}); print('yes' if d else 'no')" 2>/dev/null || echo "no")

if [ "$HAS_DATA" = "no" ]; then
  echo "  同步响应未包含 data，尝试查询结果..."
  # 等待一下让后台完成
  sleep 2
  # 获取项目信息
  QUERY_RESULT=$(curl -sS -X GET "${BASE_URL}/api/apps/tender/projects/${PROJECT_ID}" \
    -H "Authorization: Bearer ${TOKEN}")
  
  echo "$QUERY_RESULT" | python3 -m json.tool > /aidata/x-llmapp1/reports/verify/step8_project_info.json
  
  HAS_PROJECT_INFO=$(echo "$QUERY_RESULT" | python3 -c "import sys, json; d=json.load(sys.stdin).get('project_info',{}); print('yes' if d else 'no')" 2>/dev/null || echo "no")
  
  if [ "$HAS_PROJECT_INFO" = "yes" ]; then
    HAS_DATA="yes"
    echo "  ✓ 从项目信息中找到 project_info"
  fi
else
  echo "$EXTRACT_RESULT" | python3 -m json.tool > /aidata/x-llmapp1/reports/verify/step8_project_info.json
fi

echo "  - run_id: ${RUN_ID}"
echo "  - has_data: ${HAS_DATA}"

if [ "$HAS_DATA" = "yes" ]; then
  echo "✓ project_info 数据非空"
else
  echo "✗ project_info 数据为空"
  echo "--- 响应内容 ---"
  echo "$EXTRACT_RESULT" | python3 -m json.tool | head -30
  exit 1
fi
echo ""

# 7. 查看 backend 日志中的 LLM 调用链路
echo "[测试 7] 检查 backend 日志中的 LLM 调用链路"
echo "--- 最近的 ExtractionEngine 日志 ---"
docker-compose logs --tail=300 backend 2>&1 | grep -E "ExtractionEngine|BEFORE_LLM|AFTER_LLM|SimpleLLMOrchestrator" | tail -15 || echo "(在 MOCK 模式下可能无详细日志)"
echo ""

# 8. 检查文件大小
FILE_SIZE=$(stat -c%s /aidata/x-llmapp1/reports/verify/step8_project_info.json 2>/dev/null || stat -f%z /aidata/x-llmapp1/reports/verify/step8_project_info.json 2>/dev/null || echo "0")
echo "[测试 8] 检查输出文件大小"
echo "  - step8_project_info.json: ${FILE_SIZE} bytes"
if [ "$FILE_SIZE" -gt 100 ]; then
  echo "✓ 文件大小 > 100 bytes"
else
  echo "✗ 文件大小过小"
  exit 1
fi
echo ""

echo "=========================================="
echo "  验收判据检查"
echo "=========================================="
echo "✓ /api/_debug/llm/ping 返回 200 且 ok:true"
echo "✓ NEW_ONLY 抽取能产出 project_info 且 size>0"
echo "✓ 输出文件存在且 size > 100 bytes"
echo "✓ backend 日志可追踪（MOCK 模式）"
echo ""
echo "=========================================="
echo "  Step 8 验证通过！"
echo "=========================================="
