#!/usr/bin/env python3
"""测试LLM调用并输出详细参数"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.llm_model_store import get_llm_store
from app.main import app

# 获取所有LLM模型
store = get_llm_store()
models = store.list_models()

if not models:
    print("❌ 没有配置LLM模型")
    sys.exit(1)

# 使用第一个模型
model = models[0]
model_tuple = store.get_model_with_token(model.id)
if not model_tuple:
    print("❌ 无法获取模型token")
    sys.exit(1)

model, token = model_tuple

print("=" * 80)
print("LLM模型配置")
print("=" * 80)
print(f"模型ID: {model.id}")
print(f"模型名称: {model.name}")
print(f"Base URL: {model.base_url}")
print(f"Endpoint: {model.endpoint_path}")
print(f"Model: {model.model}")
print(f"Max Tokens: {model.max_tokens}")
print(f"Temperature: {model.temperature}")
print(f"API Key: {'已配置' if token else '未配置'}")
print("=" * 80)

# 获取LLM orchestrator
llm = app.state.llm_orchestrator

print("\n测试LLM调用...")
print("=" * 80)

try:
    messages = [
        {"role": "user", "content": "你好，请回复'测试成功'"}
    ]
    
    print(f"发送消息: {messages}")
    print()
    
    result = llm.chat(messages, model_id=model.id, max_tokens=50)
    
    print("\n✅ LLM调用成功!")
    print("=" * 80)
    if "choices" in result and result["choices"]:
        content = result["choices"][0].get("message", {}).get("content", "")
        print(f"响应内容: {content}")
    else:
        print(f"响应格式: {result}")
    print("=" * 80)
    
except Exception as e:
    print(f"\n❌ LLM调用失败: {e}")
    print("=" * 80)
    print("\n请检查后端日志获取详细的调用参数:")
    print("  docker logs localgpt-backend --tail 100")

