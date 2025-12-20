#!/usr/bin/env python3
"""
测试文档导出功能（E2E 测试）

使用方式：
    python scripts/test_export_docx_e2e.py
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


def export_project(token, project_id, format_template_id=None):
    """导出项目为 Word 文档"""
    print(f"\n导出项目 {project_id}...")
    
    params = {
        "include_toc": True,
        "prefix_numbering": False,
        "merge_semantic_summary": True,
    }
    
    if format_template_id:
        params["format_template_id"] = format_template_id
    
    resp = requests.post(
        f"{API_BASE}/api/apps/tender/projects/{project_id}/export/docx",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        stream=True,
    )
    
    if resp.status_code != 200:
        print(f"✗ 导出失败: {resp.status_code}")
        print(resp.text)
        return None
    
    # 保存文件
    output_dir = Path("./output")
    output_dir.mkdir(exist_ok=True)
    
    output_path = output_dir / f"project_{project_id}.docx"
    
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    
    file_size = output_path.stat().st_size
    print(f"✓ 导出成功: {output_path} ({file_size / 1024:.1f} KB)")
    
    return output_path


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


def list_format_templates(token):
    """列出所有格式模板"""
    print("\n获取格式模板列表...")
    resp = requests.get(
        f"{API_BASE}/api/apps/tender/format-templates",
        headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    templates = resp.json()
    print(f"✓ 找到 {len(templates)} 个格式模板")
    return templates


def main():
    """主函数"""
    print("=" * 60)
    print("文档导出功能测试")
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
        directory = get_directory(token, project_id)
        if not directory:
            print("\n⚠ 项目没有目录数据，请先生成目录")
            return
        
        # 5. 列出格式模板
        templates = list_format_templates(token)
        format_template_id = None
        if templates:
            template = templates[0]
            format_template_id = template["id"]
            template_name = template.get("name", "未命名")
            print(f"使用格式模板: {template_name} ({format_template_id})")
        else:
            print("⚠ 没有格式模板，将使用简单导出")
        
        # 6. 导出文档
        output_path = export_project(token, project_id, format_template_id)
        
        if output_path:
            print("\n" + "=" * 60)
            print("✓ 测试成功")
            print(f"输出文件: {output_path}")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("✗ 测试失败")
            print("=" * 60)
            sys.exit(1)
    
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

