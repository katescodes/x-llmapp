"""
测试框架式投标响应提取
"""
import requests
import json
import time

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
        print(f"✓ 登录成功")
        return token
    else:
        print(f"✗ 登录失败: {response.status_code}")
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
        projects = data if isinstance(data, list) else data.get("items", [])
        print(f"✓ 找到 {len(projects)} 个项目")
        
        for project in projects[:3]:
            print(f"  - {project.get('name')} (ID: {project.get('id')})")
        
        return projects
    else:
        print(f"✗ 获取项目失败: {response.status_code}")
        return []

def extract_framework_responses(token, project_id, bidder_name="测试投标人"):
    """框架式提取投标响应"""
    print(f"\n框架式提取投标响应...")
    print(f"  项目ID: {project_id}")
    print(f"  投标人: {bidder_name}")
    
    response = requests.post(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/extract-bid-responses-framework?sync=1&bidder_name={bidder_name}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    print(f"  状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        status = data.get("status", "unknown")
        result = data.get("result", {})
        
        print(f"\n✓ 提取完成")
        print(f"  状态: {status}")
        print(f"  提取方法: {result.get('extraction_method', 'unknown')}")
        print(f"  数据版本: {result.get('schema_version', 'unknown')}")
        print(f"  保存响应数: {result.get('added_count', 0)} 条")
        
        # 显示响应示例
        responses = result.get("responses", [])
        if responses:
            print(f"\n  响应示例（前5条）:")
            for idx, resp in enumerate(responses[:5], 1):
                req_id = resp.get("requirement_id", "N/A")
                response_text = resp.get("response_text", "")
                is_compliant = resp.get("is_compliant", None)
                confidence = resp.get("confidence", 0.0)
                
                print(f"\n  [{idx}] 要求ID: {req_id}")
                print(f"      响应: {response_text[:80] if response_text else '(无响应)'}...")
                print(f"      合规: {is_compliant}, 置信度: {confidence:.2f}")
        
        return data
    else:
        print(f"\n✗ 提取失败: {response.status_code}")
        print(f"  错误: {response.text}")
        return None

def compare_methods(token, project_id, bidder_name="测试投标人"):
    """对比两种提取方法"""
    print("\n" + "=" * 60)
    print("对比测试：传统方法 vs 框架式方法")
    print("=" * 60)
    
    # 方法2：框架式提取
    print("\n【方法2：框架式提取】")
    start_time = time.time()
    framework_result = extract_framework_responses(token, project_id, bidder_name)
    framework_time = time.time() - start_time
    
    print(f"\n框架式提取耗时: {framework_time:.2f} 秒")
    
    if framework_result:
        result = framework_result.get("result", {})
        print(f"提取响应数: {result.get('added_count', 0)} 条")
    
    return framework_result

def main():
    print("=" * 60)
    print("框架式投标响应提取测试")
    print("=" * 60)
    
    # 1. 登录
    token = login()
    if not token:
        return False
    
    # 2. 获取项目列表
    projects = get_projects(token)
    if not projects:
        return False
    
    # 3. 选择测试项目
    test_project = projects[0]
    project_id = test_project.get("id")
    project_name = test_project.get("name")
    
    print(f"\n选择测试项目: {project_name}")
    
    # 4. 进行对比测试
    result = compare_methods(token, project_id)
    
    if result:
        print("\n" + "=" * 60)
        print("✅ 框架式投标响应提取测试成功！")
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

