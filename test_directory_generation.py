#!/usr/bin/env python3
"""测试目录生成的generation_mode显示"""
import requests
import time
import json

BASE_URL = "http://192.168.2.17:9001"

# 登录
login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
    "username": "admin",
    "password": "admin123"
})

if login_resp.status_code != 200:
    print(f"❌ 登录失败: {login_resp.status_code}")
    print(login_resp.text)
    exit(1)

token = login_resp.json().get("access_token")
headers = {"Authorization": f"Bearer {token}"}

print("✅ 登录成功")

# 获取项目列表
projects_resp = requests.get(f"{BASE_URL}/api/apps/tender/projects", headers=headers)
projects_data = projects_resp.json()

print(f"\n📊 项目列表返回类型: {type(projects_data)}")

# 处理不同的返回格式
if isinstance(projects_data, dict):
    projects = list(projects_data.values())
else:
    projects = projects_data

print(f"📊 找到 {len(projects)} 个项目")

# 找到测试2项目
test_project = None
for p in projects:
    if isinstance(p, dict) and p.get('name') == '测试2':
        test_project = p
        break

if not test_project:
    print("❌ 未找到测试2项目")
    exit(1)

project_id = test_project['id']
print(f"✅ 找到测试2项目: {project_id}")

# 触发目录生成
print("\n🔄 触发目录生成...")
gen_resp = requests.post(
    f"{BASE_URL}/api/apps/tender/projects/{project_id}/directory/generate",
    headers=headers,
    json={"model_id": None}
)

if gen_resp.status_code != 200:
    print(f"❌ 目录生成失败: {gen_resp.status_code}")
    print(gen_resp.text)
    exit(1)

run_id = gen_resp.json().get("run_id")
print(f"✅ 目录生成任务已提交: {run_id}")

# 轮询任务状态
print("\n⏳ 等待任务完成...")
max_wait = 60  # 最多等待60秒
waited = 0

while waited < max_wait:
    time.sleep(3)
    waited += 3
    
    run_resp = requests.get(f"{BASE_URL}/api/apps/tender/runs/{run_id}", headers=headers)
    run = run_resp.json()
    
    status = run.get("status")
    print(f"  状态: {status}, 进度: {run.get('progress', 0):.1%}")
    
    if status == "success":
        print("\n✅ 任务完成!")
        result_json = run.get("result_json", {})
        
        print(f"\n📊 result_json keys: {list(result_json.keys())}")
        print(f"  - generation_mode: {result_json.get('generation_mode')}")
        print(f"  - fast_stats: {result_json.get('fast_stats')}")
        
        if result_json.get('generation_mode'):
            print(f"\n🎉 生成模式信息已正确返回: {result_json.get('generation_mode')}")
        else:
            print(f"\n⚠️ generation_mode 字段缺失")
        
        break
    elif status == "failed":
        print(f"\n❌ 任务失败: {run.get('message')}")
        break

if waited >= max_wait:
    print(f"\n⏰ 等待超时")

