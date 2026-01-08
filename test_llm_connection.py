#!/usr/bin/env python3
"""测试LLM连接"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import httpx
import time

# LLM配置
llm_url = "https://xai.yglinker.com:50443/611/v1/chat/completions"
llm_model = "gpt-oss-120b"

print("=" * 80)
print("测试LLM连接")
print("=" * 80)
print(f"URL: {llm_url}")
print(f"Model: {llm_model}")
print()

# 测试1: DNS解析
print("1. DNS解析测试...")
import socket
try:
    ip = socket.gethostbyname("xai.yglinker.com")
    print(f"✅ DNS解析成功: xai.yglinker.com -> {ip}")
except Exception as e:
    print(f"❌ DNS解析失败: {e}")
    sys.exit(1)

# 测试2: TCP连接
print("\n2. TCP连接测试...")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex((ip, 50443))
    sock.close()
    if result == 0:
        print(f"✅ TCP连接成功: {ip}:50443")
    else:
        print(f"❌ TCP连接失败: 错误码 {result}")
        sys.exit(1)
except Exception as e:
    print(f"❌ TCP连接失败: {e}")
    sys.exit(1)

# 测试3: HTTPS请求
print("\n3. HTTPS请求测试...")
try:
    start = time.time()
    
    payload = {
        "model": llm_model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 8,
        "temperature": 0.0
    }
    
    print(f"发送请求到: {llm_url}")
    print(f"Payload: {payload}")
    
    response = httpx.post(
        llm_url,
        json=payload,
        timeout=30.0,
        verify=False  # 跳过SSL验证
    )
    
    elapsed = time.time() - start
    
    print(f"\n状态码: {response.status_code}")
    print(f"耗时: {elapsed:.2f}秒")
    print(f"响应头: {dict(response.headers)}")
    print(f"响应体: {response.text[:500]}")
    
    if response.status_code == 200:
        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            content = data["choices"][0].get("message", {}).get("content", "")
            print(f"\n✅ LLM响应成功!")
            print(f"内容: {content}")
        else:
            print(f"\n⚠️ 响应格式异常: {data}")
    else:
        print(f"\n❌ LLM请求失败: HTTP {response.status_code}")
        
except httpx.ConnectTimeout as e:
    print(f"❌ 连接超时: {e}")
    print("\n可能的原因:")
    print("1. Docker容器网络配置问题")
    print("2. 防火墙阻止了连接")
    print("3. LLM服务不可达")
except Exception as e:
    print(f"❌ 请求失败: {type(e).__name__}: {e}")

print("\n" + "=" * 80)

