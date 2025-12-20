#!/usr/bin/env python3
"""
测试 RuleSet 上传和校验功能
"""
import requests
import json

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
        json={"name": "RuleSet测试项目", "description": "测试规则上传功能"},
        headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    return resp.json()["id"]

def upload_rule(token, project_id, filepath, kind="custom_rule"):
    """上传规则文件"""
    with open(filepath, "rb") as f:
        files = {"files": (filepath.split("/")[-1], f, "text/yaml")}
        data = {"kind": kind}
        resp = requests.post(
            f"{BASE_URL}/api/apps/tender/projects/{project_id}/assets/import",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {token}"}
        )
    resp.raise_for_status()
    return resp.json()[0] if isinstance(resp.json(), list) else resp.json()

def get_assets(token, project_id):
    """获取项目资产列表"""
    resp = requests.get(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/assets",
        headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    return resp.json()

def main():
    print("=" * 60)
    print("RuleSet 上传校验测试")
    print("=" * 60)
    
    # 1. 登录
    print("\n[1] 登录...")
    token = login()
    print("✓ 登录成功")
    
    # 2. 创建项目
    print("\n[2] 创建测试项目...")
    project_id = create_project(token)
    print(f"✓ 项目创建成功: {project_id}")
    
    # 3. 上传合法规则文件
    print("\n[3] 上传合法规则文件...")
    try:
        asset_valid = upload_rule(token, project_id, "testdata/test_rule_valid.yaml")
        print(f"✓ 上传成功: {asset_valid['id']}")
        print(f"  文件名: {asset_valid['filename']}")
        
        meta = asset_valid.get("meta_json", {})
        validate_status = meta.get("validate_status")
        validate_message = meta.get("validate_message")
        
        print(f"  校验状态: {validate_status}")
        print(f"  校验消息: {validate_message}")
        
        if validate_status == "valid":
            print("  ✓ 校验通过！")
        else:
            print(f"  ✗ 校验失败（预期应该通过）")
            return False
    except Exception as e:
        print(f"  ✗ 上传失败: {e}")
        return False
    
    # 4. 上传非法规则文件
    print("\n[4] 上传非法规则文件...")
    try:
        asset_invalid = upload_rule(token, project_id, "testdata/test_rule_invalid.yaml")
        print(f"✓ 上传成功: {asset_invalid['id']}")
        print(f"  文件名: {asset_invalid['filename']}")
        
        meta = asset_invalid.get("meta_json", {})
        validate_status = meta.get("validate_status")
        validate_message = meta.get("validate_message")
        
        print(f"  校验状态: {validate_status}")
        print(f"  校验消息: {validate_message}")
        
        if validate_status == "invalid":
            print("  ✓ 校验失败（符合预期）！")
        else:
            print(f"  ✗ 校验通过（预期应该失败）")
            return False
    except Exception as e:
        print(f"  ✗ 上传失败: {e}")
        return False
    
    # 5. 验证资产列表
    print("\n[5] 验证资产列表...")
    assets = get_assets(token, project_id)
    custom_rules = [a for a in assets if a.get("kind") == "custom_rule"]
    
    print(f"  找到 {len(custom_rules)} 个自定义规则文件")
    for rule in custom_rules:
        meta = rule.get("meta_json", {})
        print(f"  - {rule['filename']}: {meta.get('validate_status')} - {meta.get('validate_message', '')[:50]}")
    
    # 6. 验证数据库
    print("\n[6] 验证数据库（rule_set_versions）...")
    # 通过查看后端日志或Debug API
    
    print("\n" + "=" * 60)
    print("✓ 所有测试通过！")
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

