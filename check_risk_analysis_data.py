#!/usr/bin/env python3
"""检查招标要求提取的数据结构"""
import requests
import json

# 获取项目列表
resp = requests.get("http://192.168.2.17:9001/api/apps/tender/projects")
projects_data = resp.json()

print(f"API返回类型: {type(projects_data)}")
if isinstance(projects_data, dict):
    print(f"字典keys: {list(projects_data.keys())[:5]}")
    # 可能是 {"project_id": {...}} 格式
    projects = list(projects_data.values()) if projects_data else []
else:
    projects = projects_data

print(f"项目数量: {len(projects)}")
if projects:
    print(f"第一个项目keys: {list(projects[0].keys()) if isinstance(projects[0], dict) else type(projects[0])}")

# 找到测试2项目
test_project = None
for p in projects:
    if isinstance(p, dict):
        print(f"  - {p.get('name', 'N/A')}: {p.get('id', 'N/A')}")
        if p.get('name') == '测试2':
            test_project = p
            break

if not test_project:
    print("❌ 未找到测试2项目")
    exit(1)

project_id = test_project['id']
print(f"✅ 找到测试2项目: {project_id}")

# 获取风险分析数据（招标要求）
resp = requests.get(f"http://192.168.2.17:9001/api/apps/tender/projects/{project_id}/risk-analysis")
data = resp.json()

print(f"\n📊 API返回数据结构:")
print(f"  - hard_gate_table: {len(data.get('hard_gate_table', []))} 条")
print(f"  - checklist_table: {len(data.get('checklist_table', []))} 条")

# 检查hard_gate_table的字段
if data.get('hard_gate_table'):
    print(f"\n🔍 hard_gate_table 第一条数据的字段:")
    first = data['hard_gate_table'][0]
    for key in sorted(first.keys()):
        value = first[key]
        if isinstance(value, str) and len(value) > 50:
            value = value[:50] + "..."
        print(f"  - {key}: {value}")

# 检查checklist_table的字段
if data.get('checklist_table'):
    print(f"\n🔍 checklist_table 第一条数据的字段:")
    first = data['checklist_table'][0]
    for key in sorted(first.keys()):
        value = first[key]
        if isinstance(value, str) and len(value) > 50:
            value = value[:50] + "..."
        print(f"  - {key}: {value}")

print("\n✅ 数据检查完成")

