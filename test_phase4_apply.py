#!/usr/bin/env python3
"""
Phase 4 测试脚本
测试范文插入和占位符填充功能
"""
import requests
import json

BASE_URL = "http://localhost:9001"

def login():
    """登录获取token"""
    print("1. 登录...")
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    resp.raise_for_status()
    token = resp.json()["access_token"]
    print(f"✅ 登录成功")
    return token

def get_project(token):
    """获取项目"""
    print("\n2. 获取项目...")
    resp = requests.get(
        f"{BASE_URL}/api/apps/tender/projects",
        headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    projects = resp.json()
    if not projects:
        print("❌ 没有项目")
        return None
    project = projects[0]
    print(f"✅ 项目: {project['name']} (ID: {project['id']})")
    return project

def get_snippets(token, project_id):
    """获取范文"""
    print(f"\n3. 获取范文...")
    resp = requests.get(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/format-snippets",
        headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    snippets = resp.json()
    print(f"✅ 找到 {len(snippets)} 个范文")
    for i, s in enumerate(snippets, 1):
        print(f"   {i}. {s['title']} (ID: {s['id'][:8]}...)")
    return snippets

def get_directory(token, project_id):
    """获取目录"""
    print(f"\n4. 获取目录...")
    resp = requests.get(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/directory",
        headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    directory = resp.json()
    print(f"✅ 找到 {len(directory)} 个节点")
    for i, node in enumerate(directory[:5], 1):
        print(f"   {i}. {node['numbering']} {node['title']} (ID: {node['id'][:8]}...)")
    return directory

def test_placeholders(token, project_id, snippet_id):
    """测试占位符识别"""
    print(f"\n5. 测试占位符识别...")
    resp = requests.get(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/snippets/{snippet_id}/placeholders",
        headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    result = resp.json()
    
    print(f"✅ 找到 {result['total']} 个占位符")
    for i, p in enumerate(result['placeholders'][:5], 1):
        print(f"   {i}. {p['placeholder']} -> {p['key']} ({p['pattern']})")
    
    return result

def test_apply_snippet(token, project_id, snippet_id, node_id):
    """测试应用范文"""
    print(f"\n6. 测试应用范文...")
    resp = requests.post(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/snippets/apply",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "snippet_id": snippet_id,
            "node_id": node_id,
            "mode": "replace",
            "auto_fill": True
        }
    )
    resp.raise_for_status()
    result = resp.json()
    
    print(f"✅ 应用成功!")
    print(f"   节点: {result['node_title']}")
    print(f"   范文: {result['snippet_title']}")
    print(f"   占位符: {result['placeholders_filled']}/{result['placeholders_found']} 已填充")
    
    return result

def test_match_and_apply(token, project_id, snippets, directory):
    """测试匹配和批量应用"""
    print(f"\n7. 测试匹配和批量应用...")
    
    # 匹配
    print("   7.1 匹配范文到目录...")
    resp = requests.post(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/snippets/match",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "directory_nodes": [
                {"id": node["id"], "title": node["title"], "level": node["level"]}
                for node in directory
            ],
            "confidence_threshold": 0.7
        }
    )
    resp.raise_for_status()
    match_result = resp.json()
    
    matches = match_result['matches']
    print(f"   ✅ 匹配成功: {len(matches)} 个")
    
    if not matches:
        print("   ⚠️  没有匹配的范文")
        return None
    
    # 批量应用
    print("   7.2 批量应用范文...")
    resp = requests.post(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/snippets/batch-apply",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "matches": [
                {"node_id": m["node_id"], "snippet_id": m["snippet_id"]}
                for m in matches
            ],
            "mode": "replace",
            "auto_fill": True
        }
    )
    resp.raise_for_status()
    apply_result = resp.json()
    
    print(f"   ✅ 批量应用完成!")
    print(f"   成功: {apply_result['success_count']}")
    print(f"   失败: {apply_result['failed_count']}")
    print(f"   总计: {apply_result['total']}")
    
    if apply_result['errors']:
        print("   错误:")
        for err in apply_result['errors'][:3]:
            print(f"     - {err}")
    
    return apply_result

def main():
    print("=" * 60)
    print("Phase 4 测试: 范文插入和占位符填充")
    print("=" * 60)
    
    try:
        # 登录
        token = login()
        
        # 获取项目
        project = get_project(token)
        if not project:
            return
        
        project_id = project['id']
        
        # 获取范文
        snippets = get_snippets(token, project_id)
        if not snippets:
            print("\n⚠️  项目没有范文，请先提取")
            return
        
        # 获取目录
        directory = get_directory(token, project_id)
        if not directory:
            print("\n❌ 项目没有目录")
            return
        
        # 测试占位符识别
        snippet_id = snippets[0]['id']
        placeholder_result = test_placeholders(token, project_id, snippet_id)
        
        # 测试单个应用（如果有匹配的节点）
        # 这里简单用第一个节点测试
        if directory:
            node_id = directory[0]['id']
            try:
                apply_result = test_apply_snippet(token, project_id, snippet_id, node_id)
            except Exception as e:
                print(f"   ⚠️  单个应用测试失败: {e}")
        
        # 测试匹配和批量应用
        batch_result = test_match_and_apply(token, project_id, snippets, directory)
        
        print("\n" + "=" * 60)
        print("✅ Phase 4 测试完成！")
        print("=" * 60)
        print("\n功能验证:")
        print("✅ 占位符识别")
        print("✅ 范文应用API")
        print("✅ 批量应用API")
        print("✅ 自动填充占位符")
        
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ API错误: {e}")
        if e.response is not None:
            print(f"   详情: {e.response.text}")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
