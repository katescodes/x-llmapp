"""直接查询数据库检查测试2项目的数据"""
import psycopg
from psycopg.rows import dict_row

# 连接数据库（从Docker内部连接）
conn = psycopg.connect(
    "host=postgres port=5432 dbname=localgpt user=localgpt password=localgpt"
)

print("="*60)
print("查询测试2项目的数据")
print("="*60)

# 1. 查找测试2项目
print("\n1️⃣ 查找项目...")
cur = conn.cursor(row_factory=dict_row)
cur.execute("""
    SELECT id, name, description, created_at
    FROM tender_projects
    WHERE name LIKE '%测试2%'
    ORDER BY created_at DESC
""")
projects = cur.fetchall()

if not projects:
    print("❌ 未找到'测试2'项目")
    exit(1)

project = projects[0]
project_id = project["id"]
project_name = project["name"]

print(f"✅ 找到项目:")
print(f"   ID: {project_id}")
print(f"   名称: {project_name}")
print(f"   创建时间: {project['created_at']}")

# 2. 查询文件
print(f"\n2️⃣ 查询上传的文件...")
cur.execute("""
    SELECT id, kind, bidder_name, filename, size_bytes, created_at
    FROM tender_project_assets
    WHERE project_id = %s
    ORDER BY created_at
""", (project_id,))
assets = cur.fetchall()

if assets:
    print(f"✅ 找到 {len(assets)} 个文件:")
    for asset in assets:
        kind = asset["kind"]
        filename = asset["filename"]
        bidder = asset.get("bidder_name", "")
        size_mb = asset["size_bytes"] / 1024 / 1024 if asset["size_bytes"] else 0
        print(f"   - [{kind}] {filename} ({size_mb:.2f}MB)")
        if bidder:
            print(f"     投标人: {bidder}")
else:
    print("❌ 没有上传的文件")

# 3. 查询文档chunks
print(f"\n3️⃣ 查询文档chunks...")
cur.execute("""
    SELECT COUNT(*) as chunk_count, doc_role
    FROM tender_project_documents
    WHERE project_id = %s
    GROUP BY doc_role
""", (project_id,))
doc_stats = cur.fetchall()

if doc_stats:
    print(f"✅ 文档chunks统计:")
    for stat in doc_stats:
        print(f"   - {stat['doc_role']}: {stat['chunk_count']} chunks")
else:
    print("❌ 没有文档chunks（文件未切片）")

# 4. 查询招标要求
print(f"\n4️⃣ 查询招标要求...")
cur.execute("""
    SELECT COUNT(*) as req_count
    FROM tender_requirements
    WHERE project_id = %s
""", (project_id,))
req_count = cur.fetchone()["req_count"]

if req_count > 0:
    print(f"✅ 已提取 {req_count} 条招标要求")
    
    # 显示前5条
    cur.execute("""
        SELECT requirement_id, dimension, requirement_text
        FROM tender_requirements
        WHERE project_id = %s
        ORDER BY requirement_id
        LIMIT 5
    """, (project_id,))
    reqs = cur.fetchall()
    print(f"\n   前5条招标要求:")
    for i, req in enumerate(reqs, 1):
        text = req["requirement_text"][:60]
        print(f"   {i}. [{req['dimension']}] {text}...")
else:
    print("❌ 没有招标要求")

# 5. 查询投标响应
print(f"\n5️⃣ 查询投标响应...")
cur.execute("""
    SELECT COUNT(*) as resp_count, bidder_name
    FROM tender_bid_response_items
    WHERE project_id = %s
    GROUP BY bidder_name
""", (project_id,))
resp_stats = cur.fetchall()

if resp_stats:
    print(f"✅ 投标响应统计:")
    for stat in resp_stats:
        print(f"   - {stat['bidder_name']}: {stat['resp_count']} 条")
else:
    print("❌ 没有投标响应")

# 6. 查询审核结果
print(f"\n6️⃣ 查询审核结果...")
cur.execute("""
    SELECT COUNT(*) as review_count, bidder_name, status
    FROM tender_review_items
    WHERE project_id = %s
    GROUP BY bidder_name, status
    ORDER BY bidder_name, status
""", (project_id,))
review_stats = cur.fetchall()

if review_stats:
    print(f"✅ 审核结果统计:")
    current_bidder = None
    for stat in review_stats:
        bidder = stat['bidder_name']
        if bidder != current_bidder:
            print(f"\n   投标人: {bidder}")
            current_bidder = bidder
        print(f"      - {stat['status']}: {stat['review_count']} 条")
    
    # 显示前5条审核结果
    print(f"\n   前5条审核结果:")
    cur.execute("""
        SELECT requirement_id, result, remark
        FROM tender_review_items
        WHERE project_id = %s
        LIMIT 5
    """, (project_id,))
    reviews = cur.fetchall()
    for i, review in enumerate(reviews, 1):
        result = review.get("result", "")
        remark = review.get("remark", "")[:60]
        print(f"   {i}. [{result}] {remark}...")
else:
    print("❌ 没有审核结果")

# 7. 查询运行记录
print(f"\n7️⃣ 查询最近的运行记录...")
cur.execute("""
    SELECT kind, status, message, created_at
    FROM tender_runs
    WHERE project_id = %s
    ORDER BY created_at DESC
    LIMIT 5
""", (project_id,))
runs = cur.fetchall()

if runs:
    print(f"✅ 最近5次运行:")
    for run in runs:
        status = run['status']
        kind = run['kind']
        msg = run.get('message', '')[:40]
        print(f"   - [{kind}] {status}: {msg}")
else:
    print("⚠️  没有运行记录")

cur.close()
conn.close()

print(f"\n{'='*60}")
print("查询完成")
print(f"{'='*60}")

