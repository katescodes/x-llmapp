"""测试前端审核API"""
import requests

BASE_URL = "http://192.168.2.17:9001"

# 登录
resp = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "admin123"})
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

project_id = "tp_259c05d1979e402db656a58a930467e2"
bidder_name = "123"

print("="*60)
print("测试前端审核结果API")
print("="*60)

# 1. 测试审核结果API（前端用的）
print(f"\n1️⃣ 调用前端审核结果API...")
print(f"   URL: /api/apps/tender/projects/{project_id}/review")
print(f"   参数: bidder_name={bidder_name}")

resp = requests.get(
    f"{BASE_URL}/api/apps/tender/projects/{project_id}/review",
    headers=headers,
    params={"bidder_name": bidder_name}
)

print(f"\n   状态码: {resp.status_code}")

if resp.status_code == 200:
    data = resp.json()
    print(f"   ✅ API调用成功")
    print(f"\n   返回的数据结构:")
    print(f"   - 数据类型: {type(data)}")
    
    if isinstance(data, dict):
        print(f"   - 字段: {list(data.keys())}")
        items = data.get("items", [])
        print(f"   - items数量: {len(items)}")
        
        if len(items) > 0:
            print(f"\n   ✅ 有 {len(items)} 条审核结果")
            print(f"\n   前3条样例:")
            for i, item in enumerate(items[:3], 1):
                print(f"\n   [{i}]")
                print(f"      - requirement_text: {item.get('requirement_text', '')[:50]}...")
                print(f"      - result: {item.get('result', '')}")
                print(f"      - status: {item.get('status', '')}")
                print(f"      - remark: {item.get('remark', '')[:60]}...")
        else:
            print(f"\n   ❌ items数组为空！")
    elif isinstance(data, list):
        print(f"   - 数组长度: {len(data)}")
        if len(data) > 0:
            print(f"\n   前3条样例:")
            for i, item in enumerate(data[:3], 1):
                print(f"\n   [{i}] {item}")
        else:
            print(f"\n   ❌ 返回空数组！")
else:
    print(f"   ❌ API调用失败")
    print(f"   错误: {resp.text[:500]}")

print(f"\n{'='*60}")
print("测试完成")
print(f"{'='*60}")

