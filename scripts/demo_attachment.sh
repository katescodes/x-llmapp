#!/bin/bash

# 附件功能演示脚本
# 此脚本演示如何使用附件上传和聊天 API

set -e

API_BASE="http://localhost:9001"

echo "========================================"
echo "附件功能演示"
echo "========================================"
echo ""

# 1. 创建测试文件
echo "1. 创建测试文件..."
cat > /tmp/test_attachment.txt << 'EOF'
这是一个测试文档。

关键信息：
- 项目名称：LocalGPT Search
- 版本：v2.0
- 主要功能：文档附件上传、RAG、联网搜索

技术栈：
1. 前端：React + TypeScript
2. 后端：FastAPI + Python
3. 数据库：PostgreSQL + Milvus

重要说明：
系统支持上传多种文档格式，包括 PDF、DOCX、PPTX 等。
EOF

echo "✓ 测试文件已创建: /tmp/test_attachment.txt"
echo ""

# 2. 上传附件
echo "2. 上传附件..."
UPLOAD_RESPONSE=$(curl -s -X POST "${API_BASE}/api/attachments/upload" \
  -F "file=@/tmp/test_attachment.txt" \
  -F "conversation_id=test-demo")

echo "上传响应："
echo "$UPLOAD_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$UPLOAD_RESPONSE"
echo ""

# 提取附件 ID
ATTACHMENT_ID=$(echo "$UPLOAD_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")

if [ -z "$ATTACHMENT_ID" ]; then
  echo "❌ 上传失败，无法获取附件 ID"
  exit 1
fi

echo "✓ 附件上传成功，ID: $ATTACHMENT_ID"
echo ""

# 3. 获取附件信息
echo "3. 获取附件信息..."
curl -s "${API_BASE}/api/attachments/${ATTACHMENT_ID}" | python3 -m json.tool
echo ""

# 4. 发送带附件的消息
echo "4. 发送带附件的聊天消息..."
CHAT_PAYLOAD=$(cat <<EOF
{
  "message": "这个文档中提到的主要技术栈有哪些？",
  "attachment_ids": ["${ATTACHMENT_ID}"],
  "history": []
}
EOF
)

echo "发送消息："
echo "$CHAT_PAYLOAD" | python3 -m json.tool
echo ""

CHAT_RESPONSE=$(curl -s -X POST "${API_BASE}/api/chat" \
  -H "Content-Type: application/json" \
  -d "$CHAT_PAYLOAD")

echo "回答："
echo "$CHAT_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('answer', data))" 2>/dev/null || echo "$CHAT_RESPONSE"
echo ""

# 5. 删除附件（可选）
echo "5. 清理：删除附件..."
DELETE_RESPONSE=$(curl -s -X DELETE "${API_BASE}/api/attachments/${ATTACHMENT_ID}")
echo "$DELETE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$DELETE_RESPONSE"
echo ""

echo "========================================"
echo "演示完成！"
echo "========================================"
echo ""
echo "测试要点："
echo "✓ 附件上传"
echo "✓ 附件信息查询"
echo "✓ 带附件的聊天"
echo "✓ 附件删除"
echo ""
echo "如需测试 PDF/DOCX 等格式，请替换测试文件。"
