"""
测试框架式招标要求提取的API
"""
import requests
import json

BASE_URL = "http://192.168.2.17:9001"

def login():
    """登录获取token"""
    print("登录中...")
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "admin123"}
    )
    
    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token")
        print(f"✓ 登录成功，获得token")
        return token
    else:
        print(f"✗ 登录失败: {response.status_code}")
        print(response.text)
        return None

def get_projects(token):
    """获取项目列表"""
    print("\n获取项目列表...")
    response = requests.get(
        f"{BASE_URL}/api/apps/tender/projects",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        data = response.json()
        # 如果返回的直接是列表
        if isinstance(data, list):
            projects = data
        else:
            projects = data.get("items", [])
        
        print(f"✓ 找到 {len(projects)} 个项目")
        
        for project in projects[:3]:
            print(f"  - {project.get('name')} (ID: {project.get('id')})")
        
        return projects
    else:
        print(f"✗ 获取项目失败: {response.status_code}")
        return []

def extract_requirements(token, project_id):
    """提取招标要求（框架式）"""
    print(f"\n提取招标要求（项目ID: {project_id}）...")
    print("使用新的框架式自主提取方法...")
    
    response = requests.post(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/extract/requirements?sync=1",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "model_id": None,
            "checklist_template": "engineering"
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n完整响应: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}...")
        
        # 处理可能的嵌套结构
        result = data.get("result", data)
        count = result.get("count", 0)
        method = result.get("extraction_method", "unknown")
        schema = result.get("schema_version", "unknown")
        dimension_dist = result.get("dimension_distribution", {})
        
        print(f"✓ 成功提取 {count} 条要求")
        print(f"  提取方法: {method}")
        print(f"  数据版本: {schema}")
        print(f"\n  维度分布:")
        for dim, cnt in dimension_dist.items():
            print(f"    - {dim}: {cnt} 条")
        
        # 显示前5条要求
        requirements = data.get("requirements", [])
        if requirements:
            print(f"\n  前5条要求示例:")
            for idx, req in enumerate(requirements[:5], 1):
                print(f"\n  [{idx}] {req.get('title', '无标题')}")
                print(f"      维度: {req.get('dimension')}")
                print(f"      类型: {req.get('requirement_type') or req.get('req_type')}")
                print(f"      内容: {req.get('requirement_text', '')[:80]}...")
                print(f"      必须: {req.get('is_mandatory') or req.get('is_hard')}")
        
        return data
    else:
        print(f"✗ 提取失败: {response.status_code}")
        print(response.text)
        return None

def main():
    print("=" * 60)
    print("测试框架式招标要求提取")
    print("=" * 60)
    
    # 1. 登录
    token = login()
    if not token:
        print("无法继续测试")
        return False
    
    # 2. 获取项目列表
    projects = get_projects(token)
    if not projects:
        print("没有可测试的项目")
        return False
    
    # 3. 选择第一个项目进行测试
    test_project = projects[0]
    project_id = test_project.get("id")
    project_name = test_project.get("name")
    
    print(f"\n选择测试项目: {project_name}")
    
    # 4. 提取招标要求
    result = extract_requirements(token, project_id)
    
    if result:
        print("\n" + "=" * 60)
        print("✅ 框架式提取测试成功！")
        print("=" * 60)
        return True
    else:
        print("\n" + "=" * 60)
        print("✗ 测试失败")
        print("=" * 60)
        return False

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)

