#!/usr/bin/env python3
"""
语义目录生成 E2E 测试脚本
测试从招标文档chunks中生成语义目录的完整流程
"""
import requests
import json
import sys
import time
from typing import Optional


BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/apps/tender"


def login(username: str = "admin", password: str = "admin123") -> Optional[str]:
    """登录并获取token"""
    print(f"登录用户: {username}...")
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password},
    )
    if resp.status_code != 200:
        print(f"登录失败: {resp.status_code} - {resp.text}")
        return None
    
    data = resp.json()
    token = data.get("access_token")
    print(f"✓ 登录成功，token: {token[:20]}...")
    return token


def get_headers(token: str) -> dict:
    """获取请求头"""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def list_projects(token: str) -> list:
    """列出所有项目"""
    print("\n列出项目...")
    resp = requests.get(
        f"{BASE_URL}{API_PREFIX}/projects",
        headers=get_headers(token),
    )
    if resp.status_code != 200:
        print(f"列出项目失败: {resp.status_code} - {resp.text}")
        return []
    
    projects = resp.json()
    print(f"✓ 找到 {len(projects)} 个项目")
    for p in projects:
        print(f"  - {p['id']}: {p['name']}")
    return projects


def generate_semantic_outline(
    token: str,
    project_id: str,
    mode: str = "FAST",
    max_depth: int = 5,
) -> Optional[dict]:
    """生成语义目录"""
    print(f"\n生成语义目录: project_id={project_id}, mode={mode}...")
    
    start_time = time.time()
    resp = requests.post(
        f"{BASE_URL}{API_PREFIX}/projects/{project_id}/semantic-outline/generate",
        headers=get_headers(token),
        json={"mode": mode, "max_depth": max_depth},
    )
    elapsed = time.time() - start_time
    
    if resp.status_code != 200:
        print(f"生成失败: {resp.status_code} - {resp.text}")
        return None
    
    result = resp.json()
    print(f"✓ 生成完成，耗时: {elapsed:.2f}秒")
    
    # 解析结果
    if result.get("success"):
        outline_result = result.get("result", {})
        outline_id = outline_result.get("outline_id")
        status = outline_result.get("status")
        diagnostics = outline_result.get("diagnostics", {})
        
        print(f"  outline_id: {outline_id}")
        print(f"  status: {status}")
        print(f"  覆盖率: {diagnostics.get('coverage_rate', 0):.2%}")
        print(f"  要求项总数: {diagnostics.get('total_req_count', 0)}")
        print(f"  被覆盖要求项: {diagnostics.get('covered_req_count', 0)}")
        print(f"  总节点数: {diagnostics.get('total_nodes', 0)}")
        print(f"  一级节点数: {diagnostics.get('l1_nodes', 0)}")
        print(f"  最大深度: {diagnostics.get('max_depth', 0)}")
        
        # 显示要求项类型统计
        req_type_counts = diagnostics.get('req_type_counts', {})
        if req_type_counts:
            print("\n  要求项类型统计:")
            for req_type, count in req_type_counts.items():
                print(f"    {req_type}: {count}")
        
        # 显示目录结构（前3章）
        outline = outline_result.get("outline", [])
        if outline:
            print("\n  目录结构（前3章）:")
            for i, node in enumerate(outline[:3]):
                print_outline_node(node, indent=2)
        
        return outline_result
    else:
        print(f"✗ 生成失败: {result.get('message')}")
        return None


def print_outline_node(node: dict, indent: int = 0, max_depth: int = 3):
    """打印目录节点（递归）"""
    prefix = "  " * indent
    numbering = node.get("numbering", "")
    title = node.get("title", "")
    summary = node.get("summary", "")
    
    print(f"{prefix}{numbering} {title}")
    if summary:
        print(f"{prefix}   说明: {summary[:50]}...")
    
    # 递归打印子节点（限制深度）
    if node.get("children") and indent < max_depth:
        for child in node["children"][:3]:  # 每级只显示前3个
            print_outline_node(child, indent + 1, max_depth)
        
        if len(node["children"]) > 3:
            print(f"{prefix}  ... 还有 {len(node['children']) - 3} 个子节点")


def get_latest_semantic_outline(token: str, project_id: str) -> Optional[dict]:
    """获取最新的语义目录"""
    print(f"\n获取最新语义目录: project_id={project_id}...")
    
    resp = requests.get(
        f"{BASE_URL}{API_PREFIX}/projects/{project_id}/semantic-outline/latest",
        headers=get_headers(token),
    )
    
    if resp.status_code != 200:
        print(f"获取失败: {resp.status_code} - {resp.text}")
        return None
    
    result = resp.json()
    print(f"✓ 获取成功")
    print(f"  outline_id: {result.get('outline_id')}")
    print(f"  status: {result.get('status')}")
    print(f"  created_at: {result.get('created_at')}")
    
    return result


def main():
    """主测试流程"""
    print("=" * 60)
    print("语义目录生成 E2E 测试")
    print("=" * 60)
    
    # 1. 登录
    token = login()
    if not token:
        sys.exit(1)
    
    # 2. 列出项目
    projects = list_projects(token)
    if not projects:
        print("\n✗ 没有找到项目，请先创建项目并上传招标文档")
        sys.exit(1)
    
    # 3. 选择第一个项目（或指定项目ID）
    if len(sys.argv) > 1:
        project_id = sys.argv[1]
        print(f"\n使用指定的项目ID: {project_id}")
    else:
        project_id = projects[0]["id"]
        print(f"\n使用第一个项目: {project_id}")
    
    # 4. 生成语义目录（FAST模式）
    outline_result = generate_semantic_outline(
        token=token,
        project_id=project_id,
        mode="FAST",
        max_depth=5,
    )
    
    if not outline_result:
        print("\n✗ 语义目录生成失败")
        sys.exit(1)
    
    # 5. 获取最新的语义目录（验证保存）
    print("\n" + "=" * 60)
    latest_result = get_latest_semantic_outline(token, project_id)
    
    if latest_result:
        print("\n✓ 所有测试通过！")
        print("\n提示：可以在前端查看完整的语义目录和证据链")
    else:
        print("\n✗ 获取最新语义目录失败")
        sys.exit(1)


if __name__ == "__main__":
    main()

