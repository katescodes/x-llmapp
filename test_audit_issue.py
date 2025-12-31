"""诊断测试2项目的审核问题"""
import requests
import time

BASE_URL = "http://192.168.2.17:9001"

# 登录
print("🔐 登录...")
resp = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "admin123"})
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("✅ 登录成功\n")

# 获取所有项目
print("📂 获取项目列表...")
projects = requests.get(f"{BASE_URL}/api/apps/tender/projects", headers=headers).json()
print(f"找到 {len(projects)} 个项目：")
for i, p in enumerate(projects, 1):
    name = p.get("name", "")
    pid = p.get("id", "")
    assets = p.get("assets", [])
    print(f"  {i}. {name} (ID: {pid}, 文件数: {len(assets)})")

# 找到测试2项目
test2_project = None
for p in projects:
    if "测试2" in p.get("name", "") or "test2" in p.get("name", "").lower():
        test2_project = p
        break

if not test2_project:
    print("\n❌ 未找到'测试2'项目，请提供项目名称")
    print("可用项目：")
    for p in projects:
        print(f"  - {p['name']}")
    exit(1)

project_id = test2_project["id"]
project_name = test2_project["name"]
assets = test2_project.get("assets", [])

print(f"\n{'='*60}")
print(f"测试项目: {project_name}")
print(f"项目ID: {project_id}")
print(f"{'='*60}\n")

# 1. 检查文件
print("📄 检查上传的文件...")
bidders = set()
tender_count = 0
bid_count = 0
for asset in assets:
    kind = asset.get("kind", "")
    bidder = asset.get("bidder_name", "")
    filename = asset.get("filename", "")
    
    if kind == "tender":
        tender_count += 1
        print(f"  ✅ 招标书: {filename}")
    elif kind == "bid":
        bid_count += 1
        if bidder:
            bidders.add(bidder)
        print(f"  ✅ 投标书: {filename} (投标人: {bidder})")

if tender_count == 0:
    print("  ❌ 未找到招标书文件")
if bid_count == 0:
    print("  ❌ 未找到投标书文件")

bidders = list(bidders)
print(f"\n投标人列表: {', '.join(bidders) if bidders else '无'}\n")

# 2. 检查招标要求
print("📋 检查招标要求...")
resp = requests.get(
    f"{BASE_URL}/api/apps/tender/projects/{project_id}/requirements",
    headers=headers
)
if resp.status_code == 200:
    requirements = resp.json()
    req_count = len(requirements) if isinstance(requirements, list) else 0
    print(f"  ✅ 已提取 {req_count} 条招标要求")
    if req_count == 0:
        print("  ⚠️  需要先提取招标要求！")
else:
    print(f"  ❌ 获取招标要求失败: {resp.status_code}")
    req_count = 0

# 3. 如果没有招标要求，先提取
if req_count == 0 and tender_count > 0:
    print("\n🚀 开始提取招标要求...")
    resp = requests.post(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/extract/requirements",
        headers=headers,
        params={"sync": 1},
        json={"model_id": None}
    )
    if resp.status_code == 200:
        result = resp.json()
        print(f"  ✅ 招标要求提取成功")
        # 重新获取要求数量
        resp = requests.get(
            f"{BASE_URL}/api/apps/tender/projects/{project_id}/requirements",
            headers=headers
        )
        if resp.status_code == 200:
            requirements = resp.json()
            req_count = len(requirements) if isinstance(requirements, list) else 0
            print(f"  ✅ 共提取 {req_count} 条招标要求")
    else:
        print(f"  ❌ 招标要求提取失败: {resp.status_code}")
        print(f"  错误: {resp.text[:200]}")

# 4. 测试审核
if req_count > 0 and bidders:
    bidder = bidders[0]
    print(f"\n🔍 开始审核投标人: {bidder}")
    
    resp = requests.post(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/audit/unified",
        headers=headers,
        params={
            "sync": 1,  # 同步模式便于测试
            "bidder_name": bidder
        }
    )
    
    if resp.status_code == 200:
        result = resp.json()
        audit_result = result.get("result", {})
        stats = audit_result.get("statistics", {})
        
        print(f"  ✅ 审核完成!")
        print(f"  📊 审核统计:")
        print(f"     - 总计: {stats.get('total', 0)}")
        print(f"     - 通过: {stats.get('pass_count', 0)}")
        print(f"     - 不合规: {stats.get('fail_count', 0)}")
        print(f"     - 缺失: {stats.get('missing_count', 0)}")
        print(f"     - 待审核: {stats.get('pending_count', 0)}")
        
        # 5. 获取审核结果（前端展示的数据）
        print(f"\n📄 获取前端审核结果...")
        resp = requests.get(
            f"{BASE_URL}/api/apps/tender/projects/{project_id}/review",
            headers=headers,
            params={"bidder_name": bidder}
        )
        
        if resp.status_code == 200:
            review_data = resp.json()
            items = review_data.get("items", [])
            print(f"  ✅ 前端审核结果: {len(items)} 条")
            
            if len(items) == 0:
                print("  ❌ 前端没有审核结果数据！")
            else:
                print(f"\n  前3条审核结果样例:")
                for i, item in enumerate(items[:3], 1):
                    req_text = item.get("requirement_text", "")[:50]
                    status = item.get("review_status", "")
                    conclusion = item.get("review_conclusion", "")[:60]
                    print(f"    {i}. [{status}] {req_text}...")
                    print(f"       结论: {conclusion}")
        else:
            print(f"  ❌ 获取前端审核结果失败: {resp.status_code}")
            print(f"  错误: {resp.text[:200]}")
    
    elif resp.status_code == 400:
        error = resp.json().get("detail", "")
        print(f"  ⚠️  审核失败: {error}")
        if "招标要求" in error:
            print(f"  提示: 请先在前端提取招标要求")
    else:
        print(f"  ❌ 审核失败: {resp.status_code}")
        print(f"  错误: {resp.text[:200]}")
else:
    if req_count == 0:
        print("\n⚠️  无法审核：缺少招标要求")
    if not bidders:
        print("\n⚠️  无法审核：没有投标人")

print(f"\n{'='*60}")
print("诊断完成")
print(f"{'='*60}")

