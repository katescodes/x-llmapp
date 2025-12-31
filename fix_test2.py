"""清除测试2项目的审核结果并重新审核"""
import requests
import time

BASE_URL = "http://192.168.2.17:9001"

# 登录
resp = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "admin123"})
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

project_id = "tp_259c05d1979e402db656a58a930467e2"
bidder_name = "123"

print("="*60)
print("清除并重新审核测试2项目")
print("="*60)

# 1. 删除旧的审核结果
print("\n1️⃣ 清除旧的审核结果...")
import subprocess
result = subprocess.run([
    "docker", "exec", "localgpt-backend", "python", "-c",
    f"import psycopg; conn = psycopg.connect('host=postgres dbname=localgpt user=localgpt password=localgpt'); "
    f"cur = conn.cursor(); "
    f"cur.execute('DELETE FROM tender_review_items WHERE project_id = %s', ('{project_id}',)); "
    f"deleted1 = cur.rowcount; "
    f"cur.execute('DELETE FROM tender_bid_response_items WHERE project_id = %s', ('{project_id}',)); "
    f"deleted2 = cur.rowcount; "
    f"conn.commit(); print(f'✅ 已清除 {{deleted1}} 条审核结果, {{deleted2}} 条投标响应')"
], capture_output=True, text=True)
print(result.stdout)

#2. 重新审核
print("\n2️⃣ 重新审核...")
resp = requests.post(
    f"{BASE_URL}/api/apps/tender/projects/{project_id}/audit/unified",
    headers=headers,
    params={
        "sync": 1,
        "bidder_name": bidder_name
    }
)

if resp.status_code == 200:
    result = resp.json()
    audit_result = result.get("result", {})
    stats = audit_result.get("statistics", {})
    
    print(f"✅ 审核完成!")
    print(f"   - 总计: {stats.get('total', 0)}")
    print(f"   - 通过: {stats.get('pass_count', 0)}")
    print(f"   - 不合规: {stats.get('fail_count', 0)}")
    print(f"   - 缺失: {stats.get('missing_count', 0)}")
    print(f"   - 待审核: {stats.get('pending_count', 0)}")
else:
    print(f"❌ 审核失败: {resp.status_code}")
    print(resp.text[:500])
    exit(1)

# 3. 测试前端API
print("\n3️⃣ 测试前端API...")
resp = requests.get(
    f"{BASE_URL}/api/apps/tender/projects/{project_id}/review",
    headers=headers,
    params={"bidder_name": bidder_name}
)

if resp.status_code == 200:
    data = resp.json()
    
    # API可能返回list或dict
    if isinstance(data, list):
        items = data
    else:
        items = data.get("items", [])
    
    print(f"✅ 前端API成功!")
    print(f"   返回 {len(items)} 条审核结果")
    
    if len(items) > 0:
        print(f"\n   前3条样例:")
        for i, item in enumerate(items[:3], 1):
            req_text = item.get("requirement_text", "") or item.get("tender_requirement", "")
            req_text = req_text[:50]
            result = item.get("result", "")
            status = item.get("status", "")
            print(f"   {i}. [{result}/{status}] {req_text}...")
else:
    print(f"❌ 前端API失败: {resp.status_code}")
    print(resp.text[:500])

print(f"\n{'='*60}")
print("完成")
print(f"{'='*60}")

