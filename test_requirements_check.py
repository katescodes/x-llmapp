"""
测试：当没有招标要求时，审核接口是否正确提示
"""
import requests
import psycopg

BASE_URL = "http://192.168.2.17:9001"
USERNAME = "admin"
PASSWORD = "admin123"

def login():
    """登录"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD}
    )
    return response.json()["access_token"]

def get_first_project(token):
    """获取第一个项目"""
    response = requests.get(
        f"{BASE_URL}/api/apps/tender/projects",
        headers={"Authorization": f"Bearer {token}"}
    )
    projects = response.json()
    return projects[0]["id"] if projects else None

def clear_requirements(project_id):
    """清除招标要求（直接操作数据库）"""
    conn = psycopg.connect(
        "host=192.168.2.17 port=5432 dbname=llm_app user=llm_user password=llm_pass"
    )
    cur = conn.cursor()
    cur.execute("DELETE FROM tender_requirements WHERE project_id = %s", (project_id,))
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return deleted

def test_audit_without_requirements(token, project_id):
    """测试：没有招标要求时调用审核接口"""
    print(f"\n{'='*60}")
    print("测试场景：未提取招标要求时调用审核接口")
    print(f"{'='*60}\n")
    
    # 1. 清除招标要求
    print("1️⃣ 清除招标要求...")
    deleted = clear_requirements(project_id)
    print(f"   ✅ 已删除 {deleted} 条招标要求\n")
    
    # 2. 调用审核接口（同步模式）
    print("2️⃣ 调用审核接口（同步模式）...")
    response = requests.post(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/audit/unified",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "sync": 1,  # 同步执行
            "bidder_name": "测试投标人"
        }
    )
    
    print(f"   状态码: {response.status_code}")
    
    if response.status_code == 400:
        error_detail = response.json().get("detail", "")
        print(f"   ✅ 返回400错误（符合预期）")
        print(f"   📝 错误提示: {error_detail}\n")
        
        if "② 要求" in error_detail or "招标要求" in error_detail:
            print("   ✅ 错误提示包含友好信息")
        else:
            print("   ⚠️  错误提示可能不够友好")
    elif response.status_code == 500:
        print(f"   ❌ 返回500错误（应该是400）")
        print(f"   错误信息: {response.text[:200]}")
    else:
        print(f"   ⚠️  返回其他状态码")
        print(f"   响应: {response.text[:200]}")
    
    # 3. 测试异步模式
    print("\n3️⃣ 调用审核接口（异步模式）...")
    response = requests.post(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/audit/unified",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "sync": 0,  # 异步执行
            "bidder_name": "测试投标人"
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        run_id = result.get("run_id")
        print(f"   ✅ 异步任务已启动: {run_id}")
        
        # 轮询run状态
        import time
        for i in range(10):
            time.sleep(2)
            run_response = requests.get(
                f"{BASE_URL}/api/apps/tender/runs/{run_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            run = run_response.json()
            status = run.get("status")
            message = run.get("message", "")
            
            print(f"   [{i+1}] 状态: {status}, 消息: {message[:80]}")
            
            if status == "failed":
                print(f"\n   ✅ 任务失败（符合预期）")
                if "招标要求" in message or "② 要求" in message:
                    print(f"   ✅ 错误消息包含友好提示")
                else:
                    print(f"   ⚠️  错误消息可能不够友好")
                break
            elif status == "success":
                print(f"\n   ❌ 任务成功（不应该成功）")
                break
        else:
            print(f"\n   ⚠️  任务超时未完成")
    else:
        print(f"   ❌ 异步任务启动失败: {response.status_code}")
        print(f"   响应: {response.text[:200]}")

if __name__ == "__main__":
    try:
        print("🔐 登录...")
        token = login()
        print("✅ 登录成功!\n")
        
        print("📂 获取项目...")
        project_id = get_first_project(token)
        if not project_id:
            print("❌ 没有找到项目")
            exit(1)
        print(f"✅ 项目ID: {project_id}\n")
        
        # 测试
        test_audit_without_requirements(token, project_id)
        
        print("\n" + "="*60)
        print("✅ 测试完成!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

