#!/usr/bin/env python3
"""
项目信息提取功能诊断脚本
用于检查项目信息提取流程中的各个环节
"""
import os
import sys
import requests
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = os.getenv("BASE_URL", "http://localhost:9001")
USERNAME = os.getenv("USERNAME", "admin")
PASSWORD = os.getenv("PASSWORD", "admin123")

def login():
    """登录获取 token"""
    print("🔐 登录中...")
    try:
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": USERNAME, "password": PASSWORD},
            timeout=10
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]
        print(f"✓ 登录成功")
        return token
    except Exception as e:
        print(f"✗ 登录失败: {e}")
        sys.exit(1)

def check_projects(token):
    """检查项目列表"""
    print("\n📋 检查项目列表...")
    try:
        resp = requests.get(
            f"{BASE_URL}/api/apps/tender/projects",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        resp.raise_for_status()
        projects = resp.json()
        print(f"✓ 找到 {len(projects)} 个项目")
        
        if len(projects) == 0:
            print("⚠ 没有项目，请先创建项目并上传招标文件")
            return None
        
        # 显示项目列表
        for i, p in enumerate(projects, 1):
            print(f"  {i}. {p['name']} (ID: {p['id']})")
        
        return projects
    except Exception as e:
        print(f"✗ 获取项目列表失败: {e}")
        return None

def check_project_assets(token, project_id):
    """检查项目资产"""
    print(f"\n📦 检查项目 {project_id} 的资产...")
    try:
        resp = requests.get(
            f"{BASE_URL}/api/apps/tender/projects/{project_id}/assets",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        resp.raise_for_status()
        assets = resp.json()
        print(f"✓ 找到 {len(assets)} 个资产")
        
        tender_count = sum(1 for a in assets if a.get("kind") == "tender")
        bid_count = sum(1 for a in assets if a.get("kind") == "bid")
        print(f"  - 招标文件: {tender_count} 个")
        print(f"  - 投标文件: {bid_count} 个")
        
        if tender_count == 0:
            print("⚠ 没有招标文件，项目信息提取需要招标文件")
            
        return assets
    except Exception as e:
        print(f"✗ 获取资产列表失败: {e}")
        return []

def check_kb_chunks(token, project_id):
    """检查知识库chunks（通过项目信息间接查询）"""
    print(f"\n🗃️  检查项目 {project_id} 的知识库数据...")
    try:
        # 尝试通过数据库直接查询（需要数据库访问权限）
        from app.services.db.postgres import _get_pool
        from app.services.dao.tender_dao import TenderDAO
        
        pool = _get_pool()
        dao = TenderDAO(pool)
        
        # 获取项目信息
        proj = dao.get_project(project_id)
        if not proj:
            print(f"✗ 项目不存在: {project_id}")
            return False
        
        kb_id = proj.get("kb_id")
        print(f"  - 知识库ID: {kb_id}")
        
        # 获取资产
        assets = dao.list_assets(project_id)
        tender_assets = [a for a in assets if a.get("kind") == "tender"]
        
        if not tender_assets:
            print("⚠ 没有招标文件资产")
            return False
        
        # 检查chunks
        doc_ids = [a.get("kb_doc_id") for a in tender_assets if a.get("kb_doc_id")]
        print(f"  - 招标文件文档ID: {doc_ids}")
        
        if not doc_ids:
            print("⚠ 招标文件没有关联知识库文档")
            return False
        
        chunks = dao.load_chunks_by_doc_ids(doc_ids, limit=10)
        print(f"✓ 找到 {len(chunks)} 个文本块（限制10个）")
        
        if len(chunks) == 0:
            print("✗ 知识库中没有文本块，文件可能没有正确入库")
            return False
        
        # 显示前3个chunk的预览
        for i, chunk in enumerate(chunks[:3], 1):
            content = chunk.get("content", "")[:100]
            print(f"  {i}. Chunk {chunk.get('chunk_id')}: {content}...")
        
        return True
    except Exception as e:
        print(f"✗ 检查知识库失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_project_info(token, project_id):
    """检查项目信息提取结果"""
    print(f"\n🔍 检查项目 {project_id} 的提取结果...")
    try:
        resp = requests.get(
            f"{BASE_URL}/api/apps/tender/projects/{project_id}/project-info",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        if resp.status_code == 404:
            print("⚠ 项目信息未提取（404）")
            return None
        
        resp.raise_for_status()
        data = resp.json()
        
        if not data:
            print("⚠ 项目信息为空（null）")
            return None
        
        print("✓ 找到项目信息")
        
        # 显示数据概览
        data_json = data.get("data_json", {})
        evidence_ids = data.get("evidence_chunk_ids", [])
        
        print(f"  - 字段数: {len(data_json)}")
        print(f"  - 证据chunks: {len(evidence_ids)} 个")
        print(f"  - 更新时间: {data.get('updated_at')}")
        
        # 显示主要字段
        if data_json:
            print("\n  主要字段:")
            for key in ["projectName", "ownerName", "budget", "bidDeadline"]:
                if key in data_json:
                    value = data_json[key]
                    if isinstance(value, str) and len(value) > 50:
                        value = value[:50] + "..."
                    print(f"    - {key}: {value}")
        
        return data
    except Exception as e:
        print(f"✗ 获取项目信息失败: {e}")
        return None

def trigger_extract(token, project_id):
    """触发项目信息提取"""
    print(f"\n🚀 触发项目信息提取...")
    try:
        resp = requests.post(
            f"{BASE_URL}/api/apps/tender/projects/{project_id}/extract/project-info",
            headers={"Authorization": f"Bearer {token}"},
            json={"model_id": None},
            timeout=10
        )
        resp.raise_for_status()
        result = resp.json()
        run_id = result.get("run_id")
        print(f"✓ 提取任务已提交 (run_id: {run_id})")
        return run_id
    except Exception as e:
        print(f"✗ 触发提取失败: {e}")
        return None

def check_run_status(token, run_id):
    """检查任务状态"""
    print(f"\n⏳ 检查任务状态 (run_id: {run_id})...")
    try:
        import time
        max_wait = 60  # 最多等待60秒
        interval = 2   # 每2秒检查一次
        
        for i in range(max_wait // interval):
            resp = requests.get(
                f"{BASE_URL}/api/apps/tender/runs/{run_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            resp.raise_for_status()
            run = resp.json()
            
            status = run.get("status")
            progress = run.get("progress", 0)
            message = run.get("message", "")
            
            print(f"  [{i*interval}s] 状态: {status}, 进度: {progress:.1%}, 消息: {message}")
            
            if status == "success":
                print("✓ 任务完成")
                result_json = run.get("result_json")
                if result_json:
                    data = result_json.get("data", {})
                    print(f"  - 提取字段数: {len(data)}")
                return True
            elif status == "failed":
                print(f"✗ 任务失败: {message}")
                return False
            
            time.sleep(interval)
        
        print(f"⚠ 任务超时（{max_wait}秒）")
        return False
    except Exception as e:
        print(f"✗ 检查任务状态失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("项目信息提取功能诊断")
    print("=" * 60)
    
    # 1. 登录
    token = login()
    
    # 2. 检查项目
    projects = check_projects(token)
    if not projects:
        return
    
    # 选择第一个项目
    project = projects[0]
    project_id = project["id"]
    print(f"\n🎯 诊断项目: {project['name']} ({project_id})")
    
    # 3. 检查资产
    assets = check_project_assets(token, project_id)
    
    # 4. 检查知识库数据
    has_chunks = check_kb_chunks(token, project_id)
    
    # 5. 检查现有的项目信息
    existing_info = check_project_info(token, project_id)
    
    # 6. 如果没有chunks，无法提取
    if not has_chunks:
        print("\n" + "=" * 60)
        print("❌ 诊断失败：知识库中没有文本数据")
        print("=" * 60)
        print("\n建议操作：")
        print("1. 确保已上传招标文件")
        print("2. 检查文件入库是否成功")
        print("3. 查看后端日志是否有错误")
        return
    
    # 7. 询问是否触发新的提取
    if existing_info:
        print("\n" + "=" * 60)
        print("✓ 项目信息已存在")
        print("=" * 60)
        
        choice = input("\n是否重新提取？(y/N): ").strip().lower()
        if choice != 'y':
            print("跳过提取")
            return
    
    # 8. 触发提取
    run_id = trigger_extract(token, project_id)
    if not run_id:
        return
    
    # 9. 等待完成
    success = check_run_status(token, run_id)
    
    # 10. 检查最终结果
    if success:
        print("\n" + "=" * 60)
        final_info = check_project_info(token, project_id)
        if final_info:
            print("✓ 诊断成功：项目信息已成功提取")
        else:
            print("⚠ 提取完成，但无法获取结果")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ 诊断失败：提取任务未成功")
        print("=" * 60)

if __name__ == "__main__":
    main()


