#!/bin/bash

# 测试 oss120b 配置
echo "======================================"
echo "测试 oss120b LLM 配置"
echo "======================================"
echo ""

echo "1. 当前配置信息："
echo "   - 模型名称: gpt-oss-20b"
echo "   - API Key: gptoss20b-yagoo"
echo "   - Base URL: https://ai.yglinker.com:6399"
echo "   - Endpoint: /122/v1/chat/completions"
echo ""

echo "2. 直接测试 API（使用正确的配置）："
curl --location --request POST 'https://ai.yglinker.com:6399/122/v1/chat/completions' \
--header 'Authorization: Bearer gptoss20b-yagoo' \
--header 'Content-Type: application/json' \
--data-raw '{
  "model": "gpt-oss-20b",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant."
    },
    {
      "role": "user",
      "content": "简单介绍一下量子科技"
    }
  ],
  "max_tokens": 100,
  "temperature": 0.5
}' 2>&1

echo ""
echo ""
echo "======================================"
echo "测试完成"
echo "======================================"




