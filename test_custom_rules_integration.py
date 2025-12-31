#!/usr/bin/env python
"""
测试自定义规则集成到审核流程

测试流程：
1. 创建测试项目
2. 创建自定义规则包（AI生成规则）
3. 提取招标要求
4. 启动审核（启用自定义规则包）
5. 验证审核结果包含自定义规则检查项
"""
import sys
import time
import requests
from pathlib import Path

# 配置
BASE_URL = "http://192.168.2.17:8082"
USERNAME = "admin"
PASSWORD = "admin123"

def login():
    """登录获取token"""
    print("🔐 登录中...")
    resp = requests.post(
        f"{BASE_URL}/api/token",
        data={"username": USERNAME, "password": PASSWORD}
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    print(f"✅ 登录成功: {token[:20]}...")
    return token

def get_headers(token):
    """获取请求头"""
    return {"Authorization": f"Bearer {token}"}

def get_or_create_test_project(token):
    """获取或创建测试项目"""
    print("\n📁 查找测试项目...")
    headers = get_headers(token)
    
    # 列出所有项目
    resp = requests.get(f"{BASE_URL}/api/apps/tender/projects", headers=headers)
    resp.raise_for_status()
    projects = resp.json()
    
    # 查找"测试2"项目
    test_project = None
    for proj in projects:
        if proj["name"] == "测试2":
            test_project = proj
            break
    
    if test_project:
        print(f"✅ 找到测试项目: {test_project['id']}")
        return test_project["id"]
    
    # 创建新项目
    print("❌ 未找到测试项目，请先在系统中创建'测试2'项目")
    sys.exit(1)

def create_custom_rule_pack(token, project_id):
    """创建自定义规则包"""
    print("\n📝 创建自定义规则包...")
    headers = get_headers(token)
    
    rule_requirements = """
    企业内部招投标审核规则：
    1. 投标人必须具有有效的营业执照，注册资本不低于500万元
    2. 投标人必须提供近3年的财务审计报告
    3. 投标报价不得高于招标控制价的105%
    4. 项目经理必须具备一级建造师资质，且至少3年相关经验
    5. 投标文件必须包含完整的施工组织方案
    """
    
    data = {
        "project_id": project_id,
        "pack_name": "企业通用审核规则（测试）",
        "rule_requirements": rule_requirements
    }
    
    resp = requests.post(
        f"{BASE_URL}/api/apps/tender/custom-rules/packs",
        headers=headers,
        json=data
    )
    
    if resp.status_code == 200:
        pack = resp.json()
        print(f"✅ 规则包创建成功: {pack['id']}")
        print(f"   规则数量: {pack.get('rule_count', 0)}")
        return pack["id"]
    else:
        print(f"❌ 规则包创建失败: {resp.status_code}")
        print(f"   错误信息: {resp.text}")
        return None

def check_requirements_extracted(token, project_id):
    """检查招标要求是否已提取"""
    print("\n🔍 检查招标要求提取状态...")
    headers = get_headers(token)
    
    resp = requests.get(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/risk-analysis",
        headers=headers
    )
    
    if resp.status_code == 200:
        data = resp.json()
        total_count = data.get("must_reject_table", {}).get("total_count", 0)
        total_count += data.get("checklist_table", {}).get("total_count", 0)
        
        if total_count > 0:
            print(f"✅ 招标要求已提取: {total_count} 条")
            return True
    
    print("❌ 招标要求未提取，请先在【② 要求】标签页提取")
    return False

def run_audit_with_custom_rules(token, project_id, rule_pack_id):
    """启动审核（启用自定义规则包）"""
    print(f"\n🚀 启动审核（启用自定义规则包: {rule_pack_id[:8]}...）...")
    headers = get_headers(token)
    
    # 选择投标人（假设第一个）
    bidder_name = "测试投标人"  # 根据实际情况修改
    
    # 调用一体化审核API
    url = (
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/audit/unified"
        f"?sync=1&bidder_name={bidder_name}&custom_rule_pack_ids={rule_pack_id}"
    )
    
    resp = requests.post(url, headers=headers)
    
    if resp.status_code == 200:
        result = resp.json()
        print(f"✅ 审核完成!")
        print(f"   运行ID: {result.get('run_id', 'N/A')}")
        print(f"   状态: {result.get('status', 'N/A')}")
        return result
    else:
        print(f"❌ 审核失败: {resp.status_code}")
        print(f"   错误信息: {resp.text}")
        return None

def verify_audit_results(token, project_id):
    """验证审核结果"""
    print("\n✅ 验证审核结果...")
    headers = get_headers(token)
    
    resp = requests.get(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/review",
        headers=headers
    )
    
    if resp.status_code != 200:
        print(f"❌ 获取审核结果失败: {resp.status_code}")
        return False
    
    items = resp.json()
    print(f"\n📊 审核结果统计:")
    print(f"   总条数: {len(items)}")
    
    # 统计来源
    custom_rule_count = 0
    tender_req_count = 0
    
    for item in items:
        req_text = item.get("requirement_text", "")
        # 判断是否为自定义规则（包含规则包名称）
        if "【企业通用审核规则" in req_text:
            custom_rule_count += 1
        else:
            tender_req_count += 1
    
    print(f"   - 自定义规则检查项: {custom_rule_count} 条 ✨")
    print(f"   - 招标要求检查项: {tender_req_count} 条")
    
    # 按状态统计
    status_counts = {}
    for item in items:
        status = item.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print(f"\n   状态分布:")
    for status, count in status_counts.items():
        print(f"   - {status}: {count} 条")
    
    # 显示部分自定义规则检查项
    if custom_rule_count > 0:
        print(f"\n💡 自定义规则检查项示例:")
        count = 0
        for item in items:
            if "【企业通用审核规则" in item.get("requirement_text", ""):
                print(f"   {count+1}. {item['requirement_text'][:80]}...")
                print(f"      结果: {item.get('result', 'N/A')} | 状态: {item.get('status', 'N/A')}")
                count += 1
                if count >= 3:
                    break
    
    return custom_rule_count > 0

def main():
    print("=" * 60)
    print("🧪 测试：自定义规则集成到审核流程")
    print("=" * 60)
    
    try:
        # 1. 登录
        token = login()
        
        # 2. 获取测试项目
        project_id = get_or_create_test_project(token)
        
        # 3. 创建自定义规则包
        rule_pack_id = create_custom_rule_pack(token, project_id)
        if not rule_pack_id:
            print("\n❌ 测试失败：无法创建规则包")
            return
        
        # 4. 检查招标要求是否已提取
        if not check_requirements_extracted(token, project_id):
            print("\n⚠️  测试跳过：请先提取招标要求")
            return
        
        # 5. 启动审核（启用自定义规则包）
        audit_result = run_audit_with_custom_rules(token, project_id, rule_pack_id)
        if not audit_result:
            print("\n❌ 测试失败：审核启动失败")
            return
        
        # 等待一下确保数据保存
        time.sleep(2)
        
        # 6. 验证审核结果
        if verify_audit_results(token, project_id):
            print("\n" + "=" * 60)
            print("✅ 测试通过：自定义规则已成功集成到审核流程！")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("❌ 测试失败：审核结果中未找到自定义规则检查项")
            print("=" * 60)
    
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

