"""
测试一体化审核
"""
import requests
import json
import time

BASE_URL = "http://192.168.2.17:9001"

def login():
    """登录"""
    print("登录中...")
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "admin123"}
    )
    
    if response.status_code == 200:
        token = response.json().get("access_token")
        print("✓ 登录成功")
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
        projects = response.json()
        if isinstance(projects, dict):
            projects = projects.get("items", [])
        print(f"✓ 找到 {len(projects)} 个项目")
        for p in projects[:3]:
            print(f"  - {p.get('name')} (ID: {p.get('id')})")
        return projects
    return []

def run_unified_audit(token, project_id, bidder_name="测试投标人"):
    """执行一体化审核"""
    print(f"\n执行一体化审核...")
    print(f"  项目ID: {project_id}")
    print(f"  投标人: {bidder_name}")
    
    start_time = time.time()
    
    response = requests.post(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/audit/unified?sync=1&bidder_name={bidder_name}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    elapsed = time.time() - start_time
    
    print(f"  状态码: {response.status_code}")
    print(f"  耗时: {elapsed:.2f}秒")
    
    if response.status_code == 200:
        data = response.json()
        result = data.get("result", {})
        stats = result.get("statistics", {})
        summary = result.get("summary", {})
        
        print(f"\n✓ 审核完成")
        print(f"\n  统计信息:")
        print(f"    总要求数: {stats.get('total', 0)}")
        print(f"    通过: {stats.get('pass_count', 0)}")
        print(f"    不合规: {stats.get('fail_count', 0)}")
        print(f"    待审核: {stats.get('pending_count', 0)}")
        print(f"    缺失: {stats.get('missing_count', 0)}")
        print(f"    高置信度: {stats.get('high_confidence_count', 0)}")
        print(f"    低置信度: {stats.get('low_confidence_count', 0)}")
        
        print(f"\n  汇总:")
        print(f"    通过率: {summary.get('pass_rate', 0):.1%}")
        print(f"    高置信度率: {summary.get('high_confidence_rate', 0):.1%}")
        print(f"    需人工复核: {summary.get('need_manual_review', 0)}")
        
        # 显示维度分布
        by_dimension = result.get("by_dimension", {})
        if by_dimension:
            print(f"\n  维度分布:")
            for dim, items in by_dimension.items():
                pass_items = [i for i in items if i.get('review_status') == 'PASS']
                print(f"    {dim}: {len(items)}条（{len(pass_items)}条通过）")
        
        # 显示示例
        print(f"\n  审核示例（前3条）:")
        for dim, items in list(by_dimension.items())[:1]:
            for idx, item in enumerate(items[:3], 1):
                print(f"\n    [{idx}] {item.get('requirement_id')}")
                req_text = item.get('requirement_text', '') or ''
                resp_text = item.get('response_text') or '(缺失)'
                conclusion = item.get('review_conclusion') or ''
                
                print(f"        要求: {req_text[:60]}...")
                print(f"        响应: {resp_text[:60]}...")
                print(f"        状态: {item.get('review_status')}")
                print(f"        结论: {conclusion[:60]}...")
                print(f"        置信度: {item.get('confidence', 0):.2f}")
        
        return data
    else:
        print(f"\n✗ 审核失败: {response.status_code}")
        print(f"  错误: {response.text}")
        return None

def check_saved_data(token, project_id, bidder_name="测试投标人"):
    """检查保存的数据"""
    print(f"\n检查保存的审核结果...")
    
    # 检查审核结果
    response = requests.get(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/review?bidder_name={bidder_name}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        review_items = response.json()
        print(f"✓ 审核记录: {len(review_items)} 条")
        
        # 统计状态
        status_counts = {}
        for item in review_items:
            status = item.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"  状态分布: {status_counts}")
    else:
        print(f"✗ 获取审核记录失败: {response.status_code}")

def main():
    print("=" * 60)
    print("一体化审核测试")
    print("=" * 60)
    
    # 1. 登录
    token = login()
    if not token:
        return False
    
    # 2. 获取项目
    projects = get_projects(token)
    if not projects:
        return False
    
    # 3. 选择测试项目
    project = projects[0]
    project_id = project.get("id")
    project_name = project.get("name")
    
    print(f"\n选择测试项目: {project_name}")
    
    # 4. 执行一体化审核
    result = run_unified_audit(token, project_id)
    
    if not result:
        return False
    
    # 5. 检查保存的数据
    check_saved_data(token, project_id)
    
    print("\n" + "=" * 60)
    print("✅ 一体化审核测试成功！")
    print("=" * 60)
    return True

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)

