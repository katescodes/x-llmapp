"""
测试范文提取工作流
Step 1: Phase 1 测试 - 验证现有功能
"""
import requests
import json
import os
import sys

API_BASE = os.getenv("API_BASE", "http://localhost")
TOKEN = None  # 将在登录后填充

def login(username="admin", password="admin123"):
    """登录获取token"""
    global TOKEN
    response = requests.post(
        f"{API_BASE}/api/auth/login",
        json={"username": username, "password": password}
    )
    if response.status_code == 200:
        data = response.json()
        TOKEN = data.get("access_token") or data.get("token")
        print(f"✅ 登录成功: {username}")
        return True
    else:
        print(f"❌ 登录失败: {response.text}")
        return False

def headers():
    """生成请求头"""
    return {"Authorization": f"Bearer {TOKEN}"}

def create_test_project():
    """创建测试项目"""
    response = requests.post(
        f"{API_BASE}/api/apps/tender/projects",
        json={"name": "范文提取测试项目", "description": "测试范文提取功能"},
        headers=headers()
    )
    if response.status_code == 200:
        project_id = response.json()["project_id"]
        print(f"✅ 项目创建成功: {project_id}")
        return project_id
    else:
        print(f"❌ 项目创建失败: {response.text}")
        return None

def upload_tender_file(project_id, file_path):
    """上传招标文件"""
    if not os.path.exists(file_path):
        print(f"⚠️  测试文件不存在: {file_path}")
        print("   请提供一个招标文件路径，或使用示例文件")
        return None
    
    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f)}
        response = requests.post(
            f"{API_BASE}/api/apps/tender/projects/{project_id}/assets/import",
            files=files,
            data={'kind': 'tender'},
            headers=headers()
        )
    
    if response.status_code == 200:
        assets = response.json()
        if assets:
            asset_id = assets[0]['asset_id']
            storage_path = assets[0].get('storage_path')
            print(f"✅ 文件上传成功: {asset_id}")
            print(f"   存储路径: {storage_path}")
            return storage_path
        return None
    else:
        print(f"❌ 文件上传失败: {response.text}")
        return None

def extract_snippets(project_id, file_path):
    """提取范文"""
    print("\n🔍 开始提取范文...")
    response = requests.post(
        f"{API_BASE}/api/apps/tender/projects/{project_id}/extract-format-snippets",
        json={
            "source_file_path": file_path,
            "model_id": "gpt-oss-120b"
        },
        headers=headers()
    )
    
    if response.status_code == 200:
        result = response.json()
        snippets = result.get("snippets", [])
        print(f"✅ 范文提取成功: {len(snippets)} 个")
        for i, s in enumerate(snippets, 1):
            print(f"   {i}. {s['title']} (置信度: {s['confidence']:.2f})")
        return snippets
    else:
        print(f"❌ 范文提取失败: {response.text}")
        return []

def list_snippets(project_id):
    """获取项目范文列表"""
    response = requests.get(
        f"{API_BASE}/api/apps/tender/projects/{project_id}/format-snippets",
        headers=headers()
    )
    
    if response.status_code == 200:
        snippets = response.json()
        print(f"✅ 获取范文列表成功: {len(snippets)} 个")
        return snippets
    else:
        print(f"❌ 获取范文列表失败: {response.text}")
        return []

def get_snippet_detail(snippet_id):
    """获取范文详情"""
    response = requests.get(
        f"{API_BASE}/api/apps/tender/format-snippets/{snippet_id}",
        headers=headers()
    )
    
    if response.status_code == 200:
        snippet = response.json()
        print(f"✅ 获取范文详情成功: {snippet['title']}")
        print(f"   blocks数量: {len(snippet.get('blocks_json', []))}")
        return snippet
    else:
        print(f"❌ 获取范文详情失败: {response.text}")
        return None

def cleanup_project(project_id):
    """清理测试项目"""
    # 获取删除计划
    response = requests.get(
        f"{API_BASE}/api/apps/tender/projects/{project_id}/delete-plan",
        headers=headers()
    )
    if response.status_code != 200:
        print(f"⚠️  获取删除计划失败")
        return
    
    plan = response.json()
    confirm_token = plan.get("confirm_token")
    
    # 执行删除
    response = requests.delete(
        f"{API_BASE}/api/apps/tender/projects/{project_id}",
        json={"confirm_token": confirm_token},
        headers=headers()
    )
    
    if response.status_code == 204:
        print(f"✅ 测试项目已清理: {project_id}")
    else:
        print(f"⚠️  项目清理失败: {response.text}")

def main():
    """主测试流程"""
    print("=" * 60)
    print("📋 Phase 1 测试: 验证范文提取功能")
    print("=" * 60)
    
    # 登录
    if not login():
        return
    
    # 检查测试文件
    test_file = os.getenv("TEST_TENDER_FILE")
    if not test_file:
        print("\n⚠️  请设置环境变量 TEST_TENDER_FILE 指向招标文件")
        print("   例如: export TEST_TENDER_FILE=/path/to/tender.docx")
        print("\n跳过文件上传测试，仅测试API接口可用性...")
        
        # 测试创建项目
        project_id = create_test_project()
        if project_id:
            # 测试获取空列表
            print("\n📋 测试获取空范文列表...")
            list_snippets(project_id)
            
            # 清理
            print("\n🧹 清理测试数据...")
            cleanup_project(project_id)
        
        print("\n" + "=" * 60)
        print("✅ Phase 1 基础测试完成")
        print("   建议: 提供招标文件路径进行完整测试")
        print("=" * 60)
        return
    
    # 完整测试流程
    project_id = None
    try:
        # Step 1: 创建项目
        print("\n📝 Step 1: 创建测试项目...")
        project_id = create_test_project()
        if not project_id:
            return
        
        # Step 2: 上传招标文件
        print("\n📤 Step 2: 上传招标文件...")
        file_path = upload_tender_file(project_id, test_file)
        if not file_path:
            return
        
        # Step 3: 提取范文
        print("\n🔍 Step 3: 提取格式范文...")
        snippets = extract_snippets(project_id, file_path)
        if not snippets:
            print("⚠️  未提取到范文，测试结束")
            return
        
        # Step 4: 验证存储
        print("\n📋 Step 4: 验证数据库存储...")
        stored_snippets = list_snippets(project_id)
        assert len(stored_snippets) == len(snippets), "范文数量不匹配"
        
        # Step 5: 查看详情
        print("\n🔍 Step 5: 查看范文详情...")
        if snippets:
            first_snippet = snippets[0]
            detail = get_snippet_detail(first_snippet['id'])
            assert detail is not None, "范文详情获取失败"
        
        # 测试成功
        print("\n" + "=" * 60)
        print("✅ Phase 1 测试全部通过！")
        print(f"   ✓ 项目创建")
        print(f"   ✓ 文件上传")
        print(f"   ✓ 范文提取 ({len(snippets)}个)")
        print(f"   ✓ 数据库存储")
        print(f"   ✓ 详情查询")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理
        if project_id:
            print("\n🧹 清理测试数据...")
            cleanup_project(project_id)

if __name__ == "__main__":
    main()
