#!/usr/bin/env python3
"""
招投标目录生成测试 - 详细日志版本
"""
import os
import sys
import time
import json
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional


# 配置
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:9001")
USERNAME = os.getenv("USERNAME", "admin")
PASSWORD = os.getenv("PASSWORD", "admin123")

# 颜色输出
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def log(level: str, message: str):
    """带时间戳的日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    if level == "SUCCESS":
        color = Colors.OKGREEN
        prefix = "✓"
    elif level == "ERROR":
        color = Colors.FAIL
        prefix = "✗"
    elif level == "WARNING":
        color = Colors.WARNING
        prefix = "⚠"
    else:
        color = Colors.OKCYAN
        prefix = ""
    
    print(f"[{timestamp}] [{color}{level}{Colors.ENDC}] {prefix} {message}")


def print_section(title: str):
    """打印分节标题"""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def get_access_token() -> str:
    """获取访问令牌"""
    log("INFO", "尝试使用默认用户登录...")
    
    response = requests.post(
        f"{API_BASE_URL}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD}
    )
    
    if response.status_code != 200:
        raise Exception(f"登录失败: {response.status_code} - {response.text}")
    
    data = response.json()
    token = data.get("access_token")
    
    if not token:
        raise Exception("无法获取访问令牌")
    
    log("SUCCESS", f"登录成功，获取到token: {token[:20]}...")
    return token


def get_existing_project(token: str) -> Optional[str]:
    """获取已有项目（有文档的）"""
    headers = {"Authorization": f"Bearer {token}"}
    
    log("INFO", "查找已有项目...")
    response = requests.get(
        f"{API_BASE_URL}/api/apps/tender/projects",
        headers=headers
    )
    
    if response.status_code == 200:
        projects = response.json()
        if projects and len(projects) > 0:
            for p in projects:
                project_id = p["id"]
                
                # 检查是否有文档入库
                check_resp = requests.get(
                    f"{API_BASE_URL}/api/_debug/docstore/ready",
                    headers=headers,
                    params={"project_id": project_id, "doc_type": "tender"}
                )
                
                if check_resp.status_code == 200:
                    check_data = check_resp.json()
                    if check_data.get("ready") and check_data.get("documents", 0) > 0:
                        log("SUCCESS", f"找到已有项目: {project_id}")
                        log("INFO", f"项目名称: {p.get('name')}")
                        log("INFO", f"文档数: {check_data.get('documents', 0)}, 文档块数: {check_data.get('segments', 0)}")
                        return project_id
    
    return None


def generate_directory(token: str, project_id: str) -> Dict[str, Any]:
    """生成目录"""
    log("INFO", "开始生成目录...")
    log("INFO", "调用API: POST /api/apps/tender/projects/{project_id}/directory/generate")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    start_time = time.time()
    response = requests.post(
        f"{API_BASE_URL}/api/apps/tender/projects/{project_id}/directory/generate",
        headers=headers,
        json={"model_id": None}
    )
    
    if response.status_code not in [200, 201]:
        raise Exception(f"生成失败: {response.status_code} - {response.text}")
    
    result = response.json()
    run_id = result.get("run_id")
    
    log("SUCCESS", f"目录生成任务已提交")
    log("INFO", f"Run ID: {run_id}")
    
    # 轮询状态
    log("INFO", "等待生成完成...")
    for i in range(60):  # 最多等待2分钟
        time.sleep(2)
        
        status_resp = requests.get(
            f"{API_BASE_URL}/api/apps/tender/runs/{run_id}",
            headers=headers
        )
        
        if status_resp.status_code == 200:
            status_data = status_resp.json()
            status = status_data.get("status")
            progress = status_data.get("progress", 0)
            message = status_data.get("message", "")
            
            if status == "success":
                elapsed = time.time() - start_time
                log("SUCCESS", f"目录生成完成，耗时: {elapsed:.2f}秒")
                return status_data
            elif status == "failed":
                raise Exception(f"生成失败: {message}")
            else:
                log("INFO", f"[轮询 #{i+1}] 状态={status}, 进度={progress:.1%}, {message}")
        else:
            log("WARNING", f"无法获取状态: {status_resp.status_code}")
    
    raise Exception("生成超时")


def get_directory(token: str, project_id: str) -> List[Dict[str, Any]]:
    """获取目录"""
    log("INFO", "获取目录结构...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{API_BASE_URL}/api/apps/tender/projects/{project_id}/directory",
        headers=headers
    )
    
    if response.status_code != 200:
        raise Exception(f"获取目录失败: {response.status_code} - {response.text}")
    
    nodes = response.json()
    log("SUCCESS", f"成功获取目录")
    
    return nodes


def build_tree(nodes: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """构建树形结构（按parent_id分组）"""
    tree = {}
    for node in nodes:
        parent_id = node.get("parent_id") or "root"
        if parent_id not in tree:
            tree[parent_id] = []
        tree[parent_id].append(node)
    return tree


def print_tree(nodes: List[Dict[str, Any]], tree: Dict[str, List[Dict[str, Any]]], parent_id: str = "root", indent: int = 0):
    """递归打印树形目录"""
    children = tree.get(parent_id, [])
    # 按 order_no 排序
    children_sorted = sorted(children, key=lambda n: n.get("order_no", 0))
    
    for node in children_sorted:
        node_id = node.get("id")
        title = node.get("title", "无标题")
        level = node.get("level", 0)
        numbering = node.get("numbering", "")
        required = node.get("required", True)
        volume = node.get("volume", "")
        evidence_count = len(node.get("evidence_chunk_ids", []))
        
        # 格式化输出
        prefix = "  " * indent
        required_mark = "[必填]" if required else "[选填]"
        volume_text = f" ({volume})" if volume else ""
        
        print(f"{prefix}{numbering} {title}{volume_text} {required_mark} - 证据:{evidence_count}")
        
        # 递归打印子节点
        print_tree(nodes, tree, node_id, indent + 1)


def analyze_directory(nodes: List[Dict[str, Any]]):
    """分析目录结构"""
    log("INFO", f"\n目录结构统计:")
    print("-" * 80)
    
    if not nodes:
        log("WARNING", "未生成任何目录节点")
        return
    
    log("INFO", f"总节点数: {len(nodes)}")
    
    # 按层级统计
    by_level = {}
    for node in nodes:
        level = node.get("level", 0)
        by_level[level] = by_level.get(level, 0) + 1
    
    print("\n层级分布:")
    for level in sorted(by_level.keys()):
        log("INFO", f"  第{level}级: {by_level[level]}个节点")
    
    # 必填/选填统计
    required_count = sum(1 for n in nodes if n.get("required", True))
    optional_count = len(nodes) - required_count
    
    print("\n必填/选填:")
    log("INFO", f"  必填项: {required_count}")
    log("INFO", f"  选填项: {optional_count}")
    
    # 卷号统计
    volumes = set(n.get("volume", "") for n in nodes if n.get("volume"))
    if volumes:
        print("\n分卷:")
        for vol in sorted(volumes):
            vol_count = sum(1 for n in nodes if n.get("volume") == vol)
            log("INFO", f"  {vol}: {vol_count}个节点")
    
    # 打印树形结构
    print("\n目录树:")
    print("-" * 80)
    tree = build_tree(nodes)
    print_tree(nodes, tree)
    print("-" * 80)
    
    log("SUCCESS", "目录分析完成")


def main():
    """主函数"""
    start_time = time.time()
    
    print("\n" + "=" * 80)
    print(" 招投标目录生成测试 - 详细日志版本")
    print("=" * 80)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API地址: {API_BASE_URL}")
    print("=" * 80)
    
    try:
        # 步骤1: 获取访问令牌
        print_section("步骤 1: 获取访问令牌")
        token = get_access_token()
        
        # 步骤2: 获取已有项目
        print_section("步骤 2: 获取已有项目")
        project_id = get_existing_project(token)
        
        if not project_id:
            log("ERROR", "未找到已有项目，请先运行项目信息提取测试")
            return 1
        
        # 步骤3: 生成目录
        print_section("步骤 3: 生成目录")
        gen_result = generate_directory(token, project_id)
        
        # 步骤4: 获取目录
        print_section("步骤 4: 获取目录结构")
        nodes = get_directory(token, project_id)
        
        # 步骤5: 分析目录
        print_section("步骤 5: 分析目录结构")
        analyze_directory(nodes)
        
        # 完成
        total_time = time.time() - start_time
        print_section(" 测试完成")
        log("SUCCESS", f"总耗时: {total_time:.2f}秒")
        log("SUCCESS", f"项目ID: {project_id}")
        log("SUCCESS", f"目录节点数: {len(nodes)}")
        print("=" * 80 + "\n")
        
        return 0
        
    except Exception as e:
        log("ERROR", f"测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

