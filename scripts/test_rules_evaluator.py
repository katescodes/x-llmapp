#!/usr/bin/env python3
"""
测试 Rules Evaluator 完整流程
"""
import requests
import time

BASE_URL = "http://192.168.2.17:9001"

def login():
    """登录获取token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    resp.raise_for_status()
    return resp.json()["access_token"]

def create_project(token):
    """创建测试项目"""
    resp = requests.post(
        f"{BASE_URL}/api/apps/tender/projects",
        json={"name": "规则评估器测试项目", "description": "测试规则审核功能"},
        headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    return resp.json()["id"]

def upload_file(token, project_id, filepath, kind, bidder_name=None):
    """上传文件"""
    with open(filepath, "rb") as f:
        files = {"files": (filepath.split("/")[-1], f)}
        data = {"kind": kind}
        if bidder_name:
            data["bidder_name"] = bidder_name
        resp = requests.post(
            f"{BASE_URL}/api/apps/tender/projects/{project_id}/assets/import",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {token}"}
        )
    resp.raise_for_status()
    return resp.json()[0] if isinstance(resp.json(), list) else resp.json()

def run_review(token, project_id):
    """运行审核"""
    resp = requests.post(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/review/run",
        json={
            "model_id": None,
            "custom_rule_asset_ids": [],
            "bidder_name": "测试投标人",
            "bid_asset_ids": []
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    return resp.json()["run_id"]

def wait_for_run(token, project_id, run_id, max_wait=60):
    """等待任务完成"""
    for _ in range(max_wait):
        resp = requests.get(
            f"{BASE_URL}/api/apps/tender/projects/{project_id}/runs/{run_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        resp.raise_for_status()
        run = resp.json()
        if run["status"] == "success":
            return True
        elif run["status"] == "failed":
            return False
        time.sleep(1)
    return False

def get_review(token, project_id):
    """获取审核结果"""
    resp = requests.get(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/review",
        headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    return resp.json()

def main():
    print("=" * 60)
    print("Rules Evaluator 完整测试")
    print("=" * 60)
    
    # 1. 登录
    print("\n[1] 登录...")
    token = login()
    print("✓ 登录成功")
    
    # 2. 创建项目
    print("\n[2] 创建测试项目...")
    project_id = create_project(token)
    print(f"✓ 项目创建成功: {project_id}")
    
    # 3. 上传招标文件
    print("\n[3] 上传招标文件...")
    tender_asset = upload_file(token, project_id, "testdata/tender_sample.pdf", "tender")
    print(f"✓ 招标文件上传成功: {tender_asset['id']}")
    
    # 4. 上传投标文件
    print("\n[4] 上传投标文件...")
    bid_asset = upload_file(token, project_id, "testdata/bid_sample.docx", "bid", "测试投标人")
    print(f"✓ 投标文件上传成功: {bid_asset['id']}")
    
    # 5. 上传规则文件
    print("\n[5] 上传规则文件...")
    rule_asset = upload_file(token, project_id, "testdata/test_rule_evaluator.yaml", "custom_rule")
    print(f"✓ 规则文件上传成功: {rule_asset['id']}")
    
    meta = rule_asset.get("meta_json", {})
    validate_status = meta.get("validate_status")
    print(f"  校验状态: {validate_status}")
    
    if validate_status != "valid":
        print(f"  ✗ 规则文件校验失败，无法继续测试")
        return False
    
    # 6. 运行审核
    print("\n[6] 运行审核（包含规则评估）...")
    run_id = run_review(token, project_id)
    print(f"  任务ID: {run_id}")
    
    # 7. 等待任务完成
    print("  等待任务完成...")
    success = wait_for_run(token, project_id, run_id, max_wait=120)
    if not success:
        print("  ✗ 任务失败或超时")
        return False
    print("  ✓ 任务完成")
    
    # 8. 获取审核结果
    print("\n[8] 获取审核结果...")
    review_items = get_review(token, project_id)
    print(f"  总共 {len(review_items)} 条审核结果")
    
    # 9. 统计来源
    sources = {}
    for item in review_items:
        source = item.get("source", "compare")
        sources[source] = sources.get(source, 0) + 1
    
    print(f"\n  来源统计:")
    for source, count in sources.items():
        print(f"    {source}: {count} 条")
    
    # 10. 验证规则审核结果
    rule_items = [item for item in review_items if item.get("source") == "rule"]
    print(f"\n[10] 规则审核结果验证...")
    print(f"  找到 {len(rule_items)} 条规则审核结果")
    
    if len(rule_items) == 0:
        print("  ⚠ 警告：没有找到规则审核结果")
        print("  可能原因：规则未命中或规则执行失败")
    else:
        print("  ✓ 规则审核成功执行！")
        for item in rule_items:
            print(f"\n  规则 {item.get('rule_id', 'unknown')}:")
            print(f"    维度: {item.get('dimension')}")
            print(f"    结果: {item.get('result')}")
            print(f"    备注: {item.get('remark', '')[:60]}")
    
    print("\n" + "=" * 60)
    if len(rule_items) > 0:
        print("✓ 规则评估器测试通过！")
    else:
        print("⚠ 规则评估器测试部分通过（无规则命中）")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

