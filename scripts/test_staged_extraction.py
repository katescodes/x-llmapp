#!/usr/bin/env python3
"""
测试四阶段项目信息抽取
"""
import sys
import time
import requests
import json

# 配置
BASE_URL = "http://localhost:3000"  # 前端端口
API_URL = "http://localhost:8000"
USERNAME = "admin"
PASSWORD = "admin123"

def login():
    """登录获取token"""
    resp = requests.post(
        f"{API_URL}/api/platform/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
        timeout=10
    )
    resp.raise_for_status()
    token = resp.json()["token"]
    print(f"✅ 登录成功")
    return token

def list_projects(token):
    """获取项目列表"""
    resp = requests.get(
        f"{API_URL}/api/apps/tender/projects",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    resp.raise_for_status()
    projects = resp.json()
    return projects

def extract_project_info(token, project_id):
    """执行项目信息抽取（四阶段）"""
    print(f"\n🚀 开始四阶段抽取: project_id={project_id}")
    
    start_time = time.time()
    
    # 提交抽取任务（同步执行）
    resp = requests.post(
        f"{API_URL}/api/apps/tender/projects/{project_id}/extract/project-info",
        headers={"Authorization": f"Bearer {token}"},
        json={"model_id": None},
        params={"sync": 1},  # 同步执行
        timeout=300  # 5分钟超时
    )
    
    elapsed = time.time() - start_time
    
    if resp.status_code != 200:
        print(f"❌ 抽取失败: {resp.status_code}")
        print(f"   响应: {resp.text}")
        return None
    
    result = resp.json()
    run_id = result["run_id"]
    status = result.get("status", "unknown")
    
    print(f"✅ 抽取完成 (耗时: {elapsed:.2f}s)")
    print(f"   run_id: {run_id}")
    print(f"   status: {status}")
    
    # 获取抽取结果
    resp = requests.get(
        f"{API_URL}/api/apps/tender/projects/{project_id}/project-info",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    resp.raise_for_status()
    data = resp.json()
    
    return data

def analyze_result(data):
    """分析抽取结果"""
    if not data:
        print("❌ 没有抽取结果")
        return
    
    print("\n" + "=" * 60)
    print("📊 抽取结果分析")
    print("=" * 60)
    
    # 基本信息
    base = data.get("base", {})
    base_fields = [k for k, v in base.items() if v and k != "evidence"]
    print(f"\n1️⃣  Stage 1 - 项目基本信息:")
    print(f"   ✓ 字段数: {len(base_fields)}")
    print(f"   ✓ 字段: {', '.join(base_fields[:10])}")
    if base_fields:
        for field in ["projectName", "ownerName", "budget", "maxPrice", "bidDeadline"]:
            if field in base and base[field]:
                print(f"     - {field}: {base[field][:50]}...")
    
    # 技术参数
    tech_params = data.get("technical_parameters", [])
    print(f"\n2️⃣  Stage 2 - 技术参数:")
    print(f"   ✓ 参数数量: {len(tech_params)}")
    if tech_params:
        categories = {}
        for param in tech_params:
            cat = param.get("category", "未分类")
            categories[cat] = categories.get(cat, 0) + 1
        print(f"   ✓ 类别分布: {categories}")
        print(f"   ✓ 示例: {tech_params[0].get('name', '')} = {tech_params[0].get('value', '')[:50]}...")
    
    # 商务条款
    biz_terms = data.get("business_terms", [])
    print(f"\n3️⃣  Stage 3 - 商务条款:")
    print(f"   ✓ 条款数量: {len(biz_terms)}")
    if biz_terms:
        clause_types = {}
        for term in biz_terms:
            ct = term.get("clause_type", "未分类")
            clause_types[ct] = clause_types.get(ct, 0) + 1
        print(f"   ✓ 类型分布: {clause_types}")
        print(f"   ✓ 示例: [{biz_terms[0].get('clause_type', '')}] {biz_terms[0].get('content', '')[:50]}...")
    
    # 评分规则
    scoring = data.get("scoring_criteria", {})
    method = scoring.get("evaluationMethod", "")
    items = scoring.get("items", [])
    print(f"\n4️⃣  Stage 4 - 评分规则:")
    print(f"   ✓ 评标方法: {method}")
    print(f"   ✓ 评分项数: {len(items)}")
    if items:
        categories = {}
        for item in items:
            cat = item.get("category", "未分类")
            categories[cat] = categories.get(cat, 0) + 1
        print(f"   ✓ 类别分布: {categories}")
    
    # 证据
    evidence_ids = data.get("evidence_chunk_ids", [])
    print(f"\n📌 证据块数量: {len(evidence_ids)}")
    
    print("\n" + "=" * 60)

def main():
    print("=" * 60)
    print("测试四阶段项目信息抽取")
    print("=" * 60)
    
    try:
        # 1. 登录
        token = login()
        
        # 2. 获取项目列表
        projects = list_projects(token)
        if not projects:
            print("❌ 没有可用的项目")
            sys.exit(1)
        
        # 使用第一个项目进行测试
        project = projects[0]
        project_id = project["id"]
        project_name = project["name"]
        
        print(f"\n📋 测试项目:")
        print(f"   ID: {project_id}")
        print(f"   名称: {project_name}")
        
        # 3. 执行抽取
        data = extract_project_info(token, project_id)
        
        # 4. 分析结果
        if data:
            analyze_result(data)
        
        print("\n" + "=" * 60)
        print("✅ 测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

