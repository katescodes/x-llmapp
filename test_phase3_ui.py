#!/usr/bin/env python3
"""
Phase 3 UI测试脚本
测试范文提取和匹配的前端功能
"""
import requests
import json
import time

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
    print(f"✅ 登录成功: {token[:20]}...")
    return token

def get_projects(token):
    """获取项目列表"""
    print("\n2. 获取项目列表...")
    resp = requests.get(
        f"{BASE_URL}/api/apps/tender/projects",
        headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    projects = resp.json()
    print(f"✅ 找到 {len(projects)} 个项目")
    if projects:
        print(f"   最新项目: {projects[0]['name']} (ID: {projects[0]['id']})")
    return projects

def check_snippets(token, project_id):
    """检查项目的范文"""
    print(f"\n3. 检查项目 {project_id} 的范文...")
    resp = requests.get(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/format-snippets",
        headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    snippets = resp.json()
    print(f"✅ 找到 {len(snippets)} 个范文")
    for i, snippet in enumerate(snippets[:5], 1):
        print(f"   {i}. {snippet['title']} (置信度: {snippet['confidence']:.2f})")
    return snippets

def get_directory(token, project_id):
    """获取项目目录"""
    print(f"\n4. 获取项目 {project_id} 的目录...")
    resp = requests.get(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/directory",
        headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    directory = resp.json()
    print(f"✅ 找到 {len(directory)} 个目录节点")
    for i, node in enumerate(directory[:5], 1):
        print(f"   {i}. {node['numbering']} {node['title']}")
    return directory

def test_match_api(token, project_id, directory):
    """测试匹配API"""
    print(f"\n5. 测试匹配API...")
    
    directory_nodes = [
        {
            "id": node["id"],
            "title": node["title"],
            "level": node["level"]
        }
        for node in directory
    ]
    
    resp = requests.post(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/snippets/match",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "directory_nodes": directory_nodes,
            "confidence_threshold": 0.7
        }
    )
    resp.raise_for_status()
    result = resp.json()
    
    print(f"✅ 匹配完成!")
    print(f"   - 成功匹配: {len(result['matches'])} 个")
    print(f"   - 未匹配节点: {len(result['unmatched_nodes'])} 个")
    print(f"   - 未使用范文: {len(result['unmatched_snippets'])} 个")
    
    if result['matches']:
        print("\n   匹配详情:")
        for i, match in enumerate(result['matches'][:5], 1):
            print(f"   {i}. {match['node_title']} ← {match['snippet_title']}")
            print(f"      (置信度: {match['confidence']:.2f}, 类型: {match['match_type']})")
    
    return result

def main():
    print("=" * 60)
    print("Phase 3 UI 测试")
    print("=" * 60)
    
    try:
        # 登录
        token = login()
        
        # 获取项目
        projects = get_projects(token)
        if not projects:
            print("\n❌ 没有找到项目，请先创建项目并上传招标文件")
            return
        
        project_id = projects[0]['id']
        
        # 检查范文
        snippets = check_snippets(token, project_id)
        if not snippets:
            print("\n⚠️  项目没有范文，请在前端点击'提取格式范文'按钮")
            print("   或运行: python test_snippet_workflow.py")
            return
        
        # 获取目录
        directory = get_directory(token, project_id)
        if not directory:
            print("\n❌ 项目没有目录，请先生成投标目录")
            return
        
        # 测试匹配
        result = test_match_api(token, project_id, directory)
        
        print("\n" + "=" * 60)
        print("✅ Phase 3 测试完成！")
        print("=" * 60)
        print("\n下一步:")
        print("1. 打开浏览器访问前端 (通常是 http://localhost:3000)")
        print("2. 进入招投标模块，选择项目")
        print("3. 在'提取信息'步骤，点击'📋 提取格式范文'按钮")
        print("4. 在'生成内容'步骤，点击'📋 插入范文'按钮")
        print("5. 查看匹配确认面板")
        
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
