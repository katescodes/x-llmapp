"""
测试：当没有招标要求时，审核接口是否正确提示
方案：创建一个新项目（没有招标要求），然后调用审核接口
"""
import requests
import time

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

def create_project(token, name):
    """创建新项目"""
    response = requests.post(
        f"{BASE_URL}/api/apps/tender/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name}
    )
    return response.json()["id"]

def delete_project(token, project_id):
    """删除项目"""
    try:
        requests.delete(
            f"{BASE_URL}/api/apps/tender/projects/{project_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
    except:
        pass

def test_audit_without_requirements(token, project_id):
    """测试：没有招标要求时调用审核接口"""
    print(f"\n{'='*60}")
    print("测试场景：未提取招标要求时调用审核接口")
    print(f"项目ID: {project_id}")
    print(f"{'='*60}\n")
    
    # 1. 调用审核接口（同步模式）
    print("1️⃣ 测试同步模式...")
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
            return True
        else:
            print("   ⚠️  错误提示可能不够友好")
            return False
    elif response.status_code == 500:
        print(f"   ❌ 返回500错误（应该是400）")
        print(f"   错误信息: {response.text[:300]}")
        return False
    else:
        print(f"   ⚠️  返回其他状态码: {response.status_code}")
        print(f"   响应: {response.text[:300]}")
        return False

def test_audit_without_requirements_async(token, project_id):
    """测试：异步模式"""
    print(f"\n2️⃣ 测试异步模式...")
    response = requests.post(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/audit/unified",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "sync": 0,  # 异步执行
            "bidder_name": "测试投标人"
        }
    )
    
    if response.status_code != 200:
        print(f"   ❌ 异步任务启动失败: {response.status_code}")
        print(f"   响应: {response.text[:200]}")
        return False
    
    result = response.json()
    run_id = result.get("run_id")
    print(f"   ✅ 异步任务已启动: {run_id}")
    
    # 轮询run状态
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
                return True
            else:
                print(f"   ⚠️  错误消息可能不够友好")
                print(f"   完整消息: {message}")
                return False
        elif status == "success":
            print(f"\n   ❌ 任务成功（不应该成功）")
            return False
    
    print(f"\n   ⚠️  任务超时未完成")
    return False

if __name__ == "__main__":
    token = None
    project_id = None
    
    try:
        print("🔐 登录...")
        token = login()
        print("✅ 登录成功!\n")
        
        print("📂 创建测试项目...")
        project_name = f"测试项目_未提取要求_{int(time.time())}"
        project_id = create_project(token, project_name)
        print(f"✅ 项目已创建: {project_id}\n")
        
        # 测试1: 同步模式
        result1 = test_audit_without_requirements(token, project_id)
        
        # 测试2: 异步模式
        result2 = test_audit_without_requirements_async(token, project_id)
        
        print("\n" + "="*60)
        if result1 and result2:
            print("✅ 所有测试通过!")
        elif result1 or result2:
            print("⚠️  部分测试通过")
        else:
            print("❌ 测试失败")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理测试项目
        if token and project_id:
            print(f"\n🗑️  清理测试项目...")
            delete_project(token, project_id)
            print("✅ 测试项目已删除")

