"""
测试前端"开始审核"按钮调用一体化审核接口
"""
import requests
import json

# 配置
BASE_URL = "http://192.168.2.17:9001"
USERNAME = "admin"
PASSWORD = "admin123"

def login():
    """登录并获取token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD}
    )
    response.raise_for_status()
    data = response.json()
    return data.get("access_token")

def get_first_project(token):
    """获取第一个项目"""
    response = requests.get(
        f"{BASE_URL}/api/apps/tender/projects",
        headers={"Authorization": f"Bearer {token}"}
    )
    response.raise_for_status()
    projects = response.json()
    
    if not projects or len(projects) == 0:
        raise Exception("没有找到任何项目")
    
    return projects[0]["id"]

def get_bidders(token, project_id):
    """获取投标人列表"""
    # 从项目列表获取
    response = requests.get(
        f"{BASE_URL}/api/apps/tender/projects",
        headers={"Authorization": f"Bearer {token}"}
    )
    response.raise_for_status()
    projects = response.json()
    
    # 找到指定项目
    project = None
    for p in projects:
        if p["id"] == project_id:
            project = p
            break
    
    if not project:
        return []
    
    # 从assets中提取投标人
    assets = project.get("assets", [])
    bidders = set()
    for asset in assets:
        if asset.get("kind") == "bid" and asset.get("bidder_name"):
            bidders.add(asset["bidder_name"])
    
    return list(bidders)

def test_unified_audit(token, project_id, bidder_name):
    """测试一体化审核接口（模拟前端"开始审核"按钮）"""
    print(f"\n{'='*60}")
    print(f"测试项目: {project_id}")
    print(f"投标人: {bidder_name}")
    print(f"{'='*60}\n")
    
    # 调用一体化审核接口
    print("📤 调用一体化审核接口...")
    response = requests.post(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/audit/unified",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "sync": 0,  # 异步执行
            "bidder_name": bidder_name
        }
    )
    
    if response.status_code != 200:
        print(f"❌ API调用失败: {response.status_code}")
        print(f"错误信息: {response.text}")
        return
    
    result = response.json()
    print(f"✅ API调用成功!")
    print(f"📊 结果摘要:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # 获取审核结果
    print("\n🔍 获取审核结果...")
    response = requests.get(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/review",
        headers={"Authorization": f"Bearer {token}"},
        params={"bidder_name": bidder_name}
    )
    
    if response.status_code != 200:
        print(f"❌ 获取审核结果失败: {response.status_code}")
        return
    
    review_data = response.json()
    items = review_data.get("items", [])
    
    print(f"\n📋 审核结果统计:")
    print(f"  总计: {len(items)} 项")
    
    # 按状态统计
    status_counts = {}
    for item in items:
        status = item.get("review_status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    
    for status, count in sorted(status_counts.items()):
        print(f"  - {status}: {count} 项")
    
    # 显示前3项样例
    print(f"\n📄 审核项样例（前3项）:")
    for i, item in enumerate(items[:3], 1):
        print(f"\n  [{i}] {item.get('requirement_text', '')[:50]}...")
        print(f"      状态: {item.get('review_status')}")
        print(f"      结论: {item.get('review_conclusion', '')[:100]}")

if __name__ == "__main__":
    try:
        # 1. 登录
        print("🔐 登录系统...")
        token = login()
        print("✅ 登录成功!")
        
        # 2. 获取第一个项目
        print("\n📂 获取项目...")
        project_id = get_first_project(token)
        print(f"✅ 项目ID: {project_id}")
        
        # 3. 获取投标人列表
        print("\n👥 获取投标人列表...")
        bidders = get_bidders(token, project_id)
        print(f"✅ 找到 {len(bidders)} 个投标人: {', '.join(bidders)}")
        
        if not bidders:
            print("❌ 没有找到投标人，请先上传投标文件")
            exit(1)
        
        # 4. 测试第一个投标人的审核
        test_unified_audit(token, project_id, bidders[0])
        
        print("\n" + "="*60)
        print("✅ 测试完成!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

