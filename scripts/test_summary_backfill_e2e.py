#!/usr/bin/env python3
"""
测试 Summary 回填功能（E2E 测试）

使用方式：
    python scripts/test_summary_backfill_e2e.py
"""
import os
import sys
import requests
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 配置
API_BASE = os.getenv("API_BASE", "http://localhost:9001")
USERNAME = os.getenv("TEST_USERNAME", "admin@example.com")
PASSWORD = os.getenv("TEST_PASSWORD", "admin123")


def login():
    """登录获取 token"""
    print("登录中...")
    resp = requests.post(
        f"{API_BASE}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD}
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    print(f"✓ 登录成功")
    return token


def list_projects(token):
    """列出所有项目"""
    print("\n获取项目列表...")
    resp = requests.get(
        f"{API_BASE}/api/apps/tender/projects",
        headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    projects = resp.json()
    print(f"✓ 找到 {len(projects)} 个项目")
    return projects


def get_directory(token, project_id):
    """获取项目目录"""
    print(f"\n获取项目 {project_id} 的目录...")
    resp = requests.get(
        f"{API_BASE}/api/apps/tender/projects/{project_id}/directory",
        headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    directory = resp.json()
    print(f"✓ 目录包含 {len(directory)} 个节点")
    return directory


def count_summaries(directory):
    """统计有 summary 的节点数量"""
    count = 0
    for node in directory:
        meta_json = node.get("meta_json") or {}
        if isinstance(meta_json, dict):
            summary = meta_json.get("summary")
            if summary and summary.strip():
                count += 1
    return count


def backfill_summary(token, project_id, force_overwrite=False):
    """回填 summary"""
    print(f"\n回填 summary: project_id={project_id}, force={force_overwrite}...")
    
    resp = requests.post(
        f"{API_BASE}/api/apps/tender/projects/{project_id}/directory/backfill-summary",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "min_title_similarity": 0.86,
            "force_overwrite": force_overwrite,
        }
    )
    
    if resp.status_code != 200:
        print(f"✗ 回填失败: {resp.status_code}")
        print(resp.text)
        return None
    
    result = resp.json()
    print(f"✓ 回填成功")
    return result


def print_backfill_result(result):
    """打印回填结果"""
    print("\n" + "=" * 60)
    print("回填结果：")
    print("=" * 60)
    print(f"总计更新: {result.get('total_updated')} 个节点")
    print(f"  - 通过 numbering 匹配: {result.get('matched_by_numbering')}")
    print(f"  - 通过 title 相似度匹配: {result.get('matched_by_title')}")
    
    examples = result.get("examples", [])
    if examples:
        print(f"\n示例节点（前 {len(examples)} 个）:")
        for i, ex in enumerate(examples, 1):
            print(f"\n  {i}. 节点 ID: {ex.get('node_id')}")
            print(f"     匹配方式: {ex.get('match_method')}")
            print(f"     旧 summary: {ex.get('old_summary') or '(空)'}")
            print(f"     新 summary: {ex.get('new_summary')}")
    
    print("=" * 60)


def main():
    """主函数"""
    print("=" * 60)
    print("Summary 回填功能测试")
    print("=" * 60)
    
    try:
        # 1. 登录
        token = login()
        
        # 2. 列出项目
        projects = list_projects(token)
        if not projects:
            print("\n⚠ 没有项目，请先创建项目")
            return
        
        # 3. 选择第一个项目
        project = projects[0]
        project_id = project["id"]
        project_name = project.get("name", "未命名")
        print(f"\n使用项目: {project_name} ({project_id})")
        
        # 4. 获取目录（验证有目录数据）
        directory_before = get_directory(token, project_id)
        if not directory_before:
            print("\n⚠ 项目没有目录数据，请先生成目录")
            return
        
        count_before = count_summaries(directory_before)
        print(f"回填前有 summary 的节点: {count_before}/{len(directory_before)}")
        
        # 5. 回填 summary
        result = backfill_summary(token, project_id, force_overwrite=False)
        if not result:
            print("\n✗ 测试失败")
            sys.exit(1)
        
        # 6. 打印结果
        print_backfill_result(result)
        
        # 7. 验证结果
        directory_after = get_directory(token, project_id)
        count_after = count_summaries(directory_after)
        print(f"\n回填后有 summary 的节点: {count_after}/{len(directory_after)}")
        
        if count_after > count_before:
            print(f"✓ 成功回填 {count_after - count_before} 个节点的 summary")
        elif result.get('total_updated') == 0:
            print("✓ 所有节点已有 summary，无需回填")
        else:
            print("⚠ 节点数量未变化，可能所有节点已有 summary")
        
        print("\n" + "=" * 60)
        print("✓ 测试成功")
        print("=" * 60)
    
    except requests.exceptions.HTTPError as e:
        print(f"\n✗ HTTP 错误: {e}")
        print(f"响应: {e.response.text}")
        sys.exit(1)
    
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

