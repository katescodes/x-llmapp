#!/usr/bin/env python3
"""
测试LLM语义审核功能

测试步骤：
1. 使用"测试2"项目
2. 调用审核API with use_llm_semantic=True
3. 检查返回结果
"""
import requests
import json
import time

API_BASE = "http://192.168.2.16:9001/api"

def login():
    """登录获取token"""
    print("🔑 登录...")
    response = requests.post(
        f"{API_BASE}/auth/login",
        json={
            "username": "admin",
            "password": "password123"
        }
    )
    if response.status_code != 200:
        print(f"❌ 登录失败: {response.status_code} {response.text}")
        return None
    
    data = response.json()
    token = data.get("access_token")
    print(f"✅ 登录成功，token: {token[:20]}...")
    return token

def get_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

def get_test_project(token):
    """获取"测试2"项目ID"""
    print("\n📋 查找'测试2'项目...")
    response = requests.get(
        f"{API_BASE}/apps/tender/projects",
        headers=get_headers(token)
    )
    if response.status_code != 200:
        print(f"❌ 获取项目列表失败: {response.status_code}")
        return None
    
    projects = response.json()
    for proj in projects:
        if proj["name"] == "测试2":
            print(f"✅ 找到'测试2'项目: {proj['id']}")
            return proj["id"]
    
    print("❌ 未找到'测试2'项目")
    return None

def check_bid_responses(token, project_id):
    """检查投标响应数据"""
    print("\n📊 检查投标响应数据...")
    response = requests.get(
        f"{API_BASE}/apps/tender/projects/{project_id}/bid-responses",
        headers=get_headers(token)
    )
    if response.status_code != 200:
        print(f"❌ 获取投标响应失败: {response.status_code}")
        return False
    
    data = response.json()
    responses = data.get("responses", [])
    stats = data.get("stats", [])
    
    print(f"✅ 投标响应数: {len(responses)}")
    print(f"✅ 统计数据: {len(stats)} 个投标人")
    
    if len(responses) == 0:
        print("⚠️  没有投标响应数据，请先运行'抽取投标响应'")
        return False
    
    return True

def test_llm_semantic_review(token, project_id):
    """测试LLM语义审核"""
    print("\n🚀 开始LLM语义审核测试...")
    
    # 发起审核请求
    print("发送审核请求...")
    response = requests.post(
        f"{API_BASE}/apps/tender/projects/{project_id}/review/run?sync=1",
        headers=get_headers(token),
        json={
            "bidder_name": "123",
            "use_llm_semantic": True,
            "custom_rule_pack_ids": []
        }
    )
    
    if response.status_code != 200:
        print(f"❌ 审核请求失败: {response.status_code}")
        print(f"响应内容: {response.text}")
        return False
    
    result = response.json()
    print(f"✅ 审核请求成功")
    print(f"结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    # 等待审核完成
    run_id = result.get("id")
    if not run_id:
        print("❌ 未获取到run_id")
        return False
    
    print(f"\n⏳ 等待审核完成 (run_id={run_id})...")
    max_wait = 120  # 最多等待120秒
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        response = requests.get(
            f"{API_BASE}/apps/tender/runs/{run_id}",
            headers=get_headers(token)
        )
        if response.status_code != 200:
            print(f"❌ 查询任务状态失败: {response.status_code}")
            return False
        
        run = response.json()
        status = run.get("status")
        progress = run.get("progress", 0)
        message = run.get("message", "")
        
        print(f"状态: {status}, 进度: {progress*100:.1f}%, 消息: {message}")
        
        if status == "success":
            print(f"\n✅ 审核完成!")
            result_json = run.get("result_json", {})
            print(f"\n📊 审核结果统计:")
            print(f"  - 审核模式: {result_json.get('review_mode', 'UNKNOWN')}")
            print(f"  - 总审核项: {result_json.get('count', 0)}")
            print(f"  - PASS: {result_json.get('pass_count', 0)}")
            print(f"  - FAIL: {result_json.get('fail_count', 0)}")
            print(f"  - WARN: {result_json.get('warn_count', 0)}")
            return True
        elif status == "failed":
            print(f"\n❌ 审核失败: {message}")
            return False
        
        time.sleep(3)
    
    print(f"\n⏱️ 审核超时 ({max_wait}秒)")
    return False

def test_compare_modes(token, project_id):
    """对比三种审核模式"""
    print("\n📊 对比三种审核模式...")
    
    modes = [
        ("基础要求模式", {"use_llm_semantic": False, "custom_rule_pack_ids": []}),
        ("自定义规则模式", {"use_llm_semantic": False, "custom_rule_pack_ids": ["auto"]}),
        ("LLM语义模式", {"use_llm_semantic": True, "custom_rule_pack_ids": []})
    ]
    
    results = {}
    
    for mode_name, params in modes:
        print(f"\n{'='*60}")
        print(f"测试模式: {mode_name}")
        print(f"{'='*60}")
        
        response = requests.post(
            f"{API_BASE}/apps/tender/projects/{project_id}/review/run?sync=1",
            headers=get_headers(token),
            json={
                "bidder_name": "123",
                **params
            }
        )
        
        if response.status_code != 200:
            print(f"❌ 请求失败: {response.status_code}")
            continue
        
        result = response.json()
        run_id = result.get("id")
        
        # 等待完成
        print(f"等待审核完成...")
        max_wait = 120
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            run_response = requests.get(
                f"{API_BASE}/apps/tender/runs/{run_id}",
                headers=get_headers(token)
            )
            if run_response.status_code != 200:
                break
            
            run = run_response.json()
            if run.get("status") == "success":
                result_json = run.get("result_json", {})
                results[mode_name] = result_json
                print(f"✅ 完成")
                print(f"  - 审核模式: {result_json.get('review_mode', 'UNKNOWN')}")
                print(f"  - 总数: {result_json.get('count', 0)}")
                print(f"  - PASS: {result_json.get('pass_count', 0)}")
                print(f"  - FAIL: {result_json.get('fail_count', 0)}")
                print(f"  - WARN: {result_json.get('warn_count', 0)}")
                break
            elif run.get("status") == "failed":
                print(f"❌ 失败: {run.get('message')}")
                break
            
            time.sleep(3)
    
    # 打印对比表
    print(f"\n{'='*80}")
    print("审核模式对比")
    print(f"{'='*80}")
    print(f"{'模式':<20} {'审核模式':<20} {'总数':<8} {'PASS':<8} {'FAIL':<8} {'WARN':<8}")
    print(f"{'-'*80}")
    
    for mode_name, data in results.items():
        print(f"{mode_name:<20} {data.get('review_mode', 'N/A'):<20} {data.get('count', 0):<8} {data.get('pass_count', 0):<8} {data.get('fail_count', 0):<8} {data.get('warn_count', 0):<8}")
    
    print(f"{'='*80}")

def main():
    print("=" * 80)
    print("LLM语义审核功能测试")
    print("=" * 80)
    
    # 1. 登录
    token = login()
    if not token:
        return
    
    # 2. 获取测试项目
    project_id = get_test_project(token)
    if not project_id:
        return
    
    # 3. 检查投标响应数据
    if not check_bid_responses(token, project_id):
        print("\n⚠️  请先运行'抽取投标响应'以生成测试数据")
        print("   在前端的'投标响应抽取'tab中点击'抽取投标响应'按钮")
        return
    
    # 4. 测试LLM语义审核
    if test_llm_semantic_review(token, project_id):
        print("\n✅ LLM语义审核测试通过!")
    else:
        print("\n❌ LLM语义审核测试失败!")
        return
    
    # 5. 对比三种模式（可选）
    print("\n是否要对比三种审核模式？(y/N)")
    # 自动执行对比
    test_compare_modes(token, project_id)

if __name__ == "__main__":
    main()

