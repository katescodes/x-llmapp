#!/usr/bin/env python3
"""
测试自定义规则管理功能
"""
import requests
import json

# 配置
BASE_URL = "http://localhost:8000"
PROJECT_ID = "test_project_id"  # 替换为实际的项目ID

# 测试数据
RULE_REQUIREMENTS = """
1. 投标人必须具有有效的营业执照，且注册资本不低于500万元
2. 投标人必须提供近三年的财务审计报告
3. 投标报价不得高于预算的110%
4. 投标文件必须按照规定格式装订，页码连续
5. 投标人必须提供项目负责人的资格证书
"""


def test_create_rule_pack():
    """测试创建规则包"""
    print("\n=== 测试1: 创建规则包 ===")
    
    url = f"{BASE_URL}/custom-rules/rule-packs"
    payload = {
        "project_id": PROJECT_ID,
        "pack_name": "测试规则包",
        "rule_requirements": RULE_REQUIREMENTS,
    }
    
    print(f"请求URL: {url}")
    print(f"请求数据: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        result = response.json()
        print(f"✓ 创建成功")
        print(f"规则包ID: {result['id']}")
        print(f"规则包名称: {result['pack_name']}")
        print(f"规则数量: {result.get('rule_count', 0)}")
        
        return result['id']
    except Exception as e:
        print(f"✗ 创建失败: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"响应内容: {e.response.text}")
        return None


def test_list_rule_packs():
    """测试列出规则包"""
    print("\n=== 测试2: 列出规则包 ===")
    
    url = f"{BASE_URL}/custom-rules/rule-packs"
    params = {"project_id": PROJECT_ID}
    
    print(f"请求URL: {url}")
    print(f"请求参数: {params}")
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        result = response.json()
        print(f"✓ 查询成功")
        print(f"规则包数量: {len(result)}")
        
        for pack in result:
            print(f"\n规则包: {pack['pack_name']}")
            print(f"  ID: {pack['id']}")
            print(f"  规则数量: {pack.get('rule_count', 0)}")
            print(f"  创建时间: {pack.get('created_at', 'N/A')}")
        
        return result
    except Exception as e:
        print(f"✗ 查询失败: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"响应内容: {e.response.text}")
        return []


def test_get_rule_pack_detail(pack_id):
    """测试获取规则包详情"""
    print(f"\n=== 测试3: 获取规则包详情 (ID: {pack_id}) ===")
    
    url = f"{BASE_URL}/custom-rules/rule-packs/{pack_id}"
    
    print(f"请求URL: {url}")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        result = response.json()
        print(f"✓ 查询成功")
        print(f"规则包名称: {result['pack_name']}")
        print(f"规则数量: {result.get('rule_count', 0)}")
        
        return result
    except Exception as e:
        print(f"✗ 查询失败: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"响应内容: {e.response.text}")
        return None


def test_list_rules(pack_id):
    """测试列出规则"""
    print(f"\n=== 测试4: 列出规则 (规则包ID: {pack_id}) ===")
    
    url = f"{BASE_URL}/custom-rules/rule-packs/{pack_id}/rules"
    
    print(f"请求URL: {url}")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        result = response.json()
        print(f"✓ 查询成功")
        print(f"规则数量: {len(result)}")
        
        for idx, rule in enumerate(result, 1):
            print(f"\n规则 {idx}: {rule['rule_name']}")
            print(f"  ID: {rule['id']}")
            print(f"  Key: {rule['rule_key']}")
            print(f"  维度: {rule['dimension']}")
            print(f"  执行器: {rule['evaluator']}")
            print(f"  严重程度: {rule['severity']}")
            print(f"  硬性要求: {rule['is_hard']}")
            print(f"  条件: {json.dumps(rule['condition_json'], ensure_ascii=False, indent=4)}")
        
        return result
    except Exception as e:
        print(f"✗ 查询失败: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"响应内容: {e.response.text}")
        return []


def test_delete_rule_pack(pack_id):
    """测试删除规则包"""
    print(f"\n=== 测试5: 删除规则包 (ID: {pack_id}) ===")
    
    url = f"{BASE_URL}/custom-rules/rule-packs/{pack_id}"
    
    print(f"请求URL: {url}")
    
    # 先确认
    confirm = input("确认删除? (yes/no): ")
    if confirm.lower() != 'yes':
        print("取消删除")
        return
    
    try:
        response = requests.delete(url)
        response.raise_for_status()
        
        print(f"✓ 删除成功")
        return True
    except Exception as e:
        print(f"✗ 删除失败: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"响应内容: {e.response.text}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("自定义规则管理功能测试")
    print("=" * 60)
    print(f"\n配置:")
    print(f"  API地址: {BASE_URL}")
    print(f"  项目ID: {PROJECT_ID}")
    print("\n注意: 请确保后端服务已启动，并且已经创建了测试项目")
    print("=" * 60)
    
    # 测试1: 创建规则包
    pack_id = test_create_rule_pack()
    if not pack_id:
        print("\n✗ 测试中断：无法创建规则包")
        return
    
    # 测试2: 列出规则包
    test_list_rule_packs()
    
    # 测试3: 获取规则包详情
    test_get_rule_pack_detail(pack_id)
    
    # 测试4: 列出规则
    test_list_rules(pack_id)
    
    # 测试5: 删除规则包（可选）
    test_delete_rule_pack(pack_id)
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()

