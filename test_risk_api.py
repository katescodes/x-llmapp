#!/usr/bin/env python3
"""测试risk-analysis API返回的数据"""
import requests
import json

# 直接用一个已知的项目ID测试
# 先获取项目列表
resp = requests.get("http://192.168.2.17:9001/api/apps/tender/projects")
print(f"项目列表API状态: {resp.status_code}")

# 假设测试2的项目ID，或者从响应中获取
# 让我们直接测试risk-analysis端点
project_id = "test_project_id"  # 需要替换

# 尝试几个可能的项目ID
test_ids = []
try:
    data = resp.json()
    if isinstance(data, dict):
        test_ids = list(data.keys())[:3]
    elif isinstance(data, list):
        test_ids = [p.get('id') for p in data[:3] if isinstance(p, dict)]
except:
    pass

print(f"测试项目IDs: {test_ids}")

# 测试第一个项目的risk-analysis
if test_ids:
    for pid in test_ids:
        print(f"\n=== 测试项目: {pid} ===")
        try:
            resp = requests.get(f"http://192.168.2.17:9001/api/apps/tender/projects/{pid}/risk-analysis")
            print(f"状态码: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                print(f"返回数据结构:")
                print(f"  - hard_gate_table: {len(data.get('hard_gate_table', []))} 条")
                print(f"  - must_reject_table: {len(data.get('must_reject_table', []))} 条")
                print(f"  - checklist_table: {len(data.get('checklist_table', []))} 条")
                
                # 检查第一条数据的字段
                if data.get('must_reject_table'):
                    print(f"\nmust_reject_table 第一条字段:")
                    for key in data['must_reject_table'][0].keys():
                        print(f"    {key}")
                
                if data.get('checklist_table'):
                    print(f"\nchecklist_table 第一条字段:")
                    for key in data['checklist_table'][0].keys():
                        print(f"    {key}")
                break
            else:
                print(f"错误: {resp.text}")
        except Exception as e:
            print(f"异常: {e}")

