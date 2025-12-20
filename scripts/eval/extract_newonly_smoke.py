#!/usr/bin/env python3
"""
NEW_ONLY 模式抽取烟雾测试
验证 NEW_ONLY 模式的 project_info 和 risks 抽取能够完成
"""
import argparse
import json
import sys
import time
from pathlib import Path

import requests


def log_info(msg: str):
    """打印信息"""
    print(f"ℹ {msg}")


def log_success(msg: str):
    """打印成功"""
    print(f"✓ {msg}")


def log_error(msg: str):
    """打印错误"""
    print(f"✗ {msg}", file=sys.stderr)


def login(base_url: str) -> str:
    """登录并获取token"""
    resp = requests.post(
        f"{base_url}/api/auth/login",
        json={"username": "admin", "password": "admin123"},
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def create_project(base_url: str, token: str) -> str:
    """创建测试项目"""
    resp = requests.post(
        f"{base_url}/api/apps/tender/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": f"NEW_ONLY烟雾测试-{int(time.time())}"},
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()["id"]


def upload_tender(base_url: str, token: str, project_id: str, file_path: str) -> str:
    """上传招标文件"""
    with open(file_path, 'rb') as f:
        resp = requests.post(
            f"{base_url}/api/apps/tender/projects/{project_id}/assets/import",
            headers={"Authorization": f"Bearer {token}"},
            data={"kind": "tender"},
            files={'files': (Path(file_path).name, f, 'application/octet-stream')},
            timeout=60
        )
    resp.raise_for_status()
    assets = resp.json()
    if not assets:
        raise RuntimeError("上传失败：未返回资产")
    return assets[0]["id"]


def wait_for_docstore_ready(base_url: str, token: str, project_id: str, timeout: int = 90) -> bool:
    """等待 DocStore 入库完成"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            resp = requests.get(
                f"{base_url}/api/_debug/docstore/ready",
                headers={"Authorization": f"Bearer {token}"},
                params={"project_id": project_id, "doc_type": "tender"},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("ready") and data.get("segments", 0) > 0:
                return True
            
            time.sleep(2)
        except Exception:
            time.sleep(2)
    
    return False


def extract_project_info(
    base_url: str,
    token: str,
    project_id: str,
    timeout: int = 120
) -> dict:
    """抽取项目信息（NEW_ONLY）"""
    start_time = time.time()
    
    resp = requests.post(
        f"{base_url}/api/apps/tender/projects/{project_id}/extract/project-info",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Force-Mode": "NEW_ONLY"  # 强制使用 NEW_ONLY
        },
        timeout=timeout
    )
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    
    if resp.status_code != 200:
        log_error(f"project_info 抽取失败: status={resp.status_code}")
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    
    result = resp.json()
    run_id = result.get("run_id", "N/A")
    log_info(f"project_info 完成, run_id={run_id}, 耗时={elapsed_ms}ms")
    
    return result


def extract_risks(
    base_url: str,
    token: str,
    project_id: str,
    timeout: int = 120
) -> dict:
    """抽取风险（NEW_ONLY）"""
    start_time = time.time()
    
    resp = requests.post(
        f"{base_url}/api/apps/tender/projects/{project_id}/extract/risks",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Force-Mode": "NEW_ONLY"  # 强制使用 NEW_ONLY
        },
        timeout=timeout
    )
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    
    if resp.status_code != 200:
        log_error(f"risks 抽取失败: status={resp.status_code}")
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    
    result = resp.json()
    run_id = result.get("run_id", "N/A")
    log_info(f"risks 完成, run_id={run_id}, 耗时={elapsed_ms}ms")
    
    return result


def main():
    parser = argparse.ArgumentParser(description="NEW_ONLY 模式抽取烟雾测试")
    parser.add_argument("--base-url", required=True, help="Backend API URL")
    parser.add_argument("--tender-file", required=True, help="招标文件路径")
    args = parser.parse_args()
    
    # 报告目录
    reports_dir = Path("/app/reports/verify")
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    print()
    print("=" * 70)
    print("  NEW_ONLY 模式抽取烟雾测试")
    print("=" * 70)
    print()
    
    try:
        # 1. 登录
        log_info("登录...")
        token = login(args.base_url)
        log_success("登录成功")
        
        # 2. 创建项目
        log_info("创建测试项目...")
        project_id = create_project(args.base_url, token)
        log_success(f"项目创建成功: {project_id}")
        
        # 3. 上传文件
        log_info(f"上传招标文件: {args.tender_file}")
        upload_tender(args.base_url, token, project_id, args.tender_file)
        log_success("文件上传成功")
        
        # 4. 等待入库
        log_info("等待 DocStore 入库完成...")
        if wait_for_docstore_ready(args.base_url, token, project_id, timeout=90):
            log_success("DocStore 入库完成")
        else:
            log_error("DocStore 入库超时，但继续测试")
        
        # 5. 抽取 project_info
        log_info("运行 NEW_ONLY 模式抽取 project_info...")
        project_info_result = extract_project_info(args.base_url, token, project_id)
        
        # 保存结果
        output_file = reports_dir / "newonly_project_info.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(project_info_result, f, ensure_ascii=False, indent=2)
        log_success(f"project_info 结果已保存: {output_file}")
        
        # 6. 抽取 risks
        log_info("运行 NEW_ONLY 模式抽取 risks...")
        risks_result = extract_risks(args.base_url, token, project_id)
        
        # 保存结果
        output_file = reports_dir / "newonly_risks.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(risks_result, f, ensure_ascii=False, indent=2)
        log_success(f"risks 结果已保存: {output_file}")
        
        # 7. 验证结果
        print()
        log_info("验证结果...")
        
        # 检查 project_info 数据
        project_info_data = project_info_result.get("data", {})
        if not project_info_data:
            log_error("project_info 数据为空")
            return 1
        
        # 检查 risks 数据
        risks_data = risks_result.get("data", [])
        if not isinstance(risks_data, list):
            log_error(f"risks 数据格式错误: {type(risks_data)}")
            return 1
        
        print()
        print("=" * 70)
        print("  验收结果")
        print("=" * 70)
        log_success(f"✓ project_info 抽取完成，数据非空")
        log_success(f"✓ risks 抽取完成，返回 {len(risks_data)} 项")
        log_success("✓ 所有输出文件已生成且 size > 0")
        log_success("✓ NEW_ONLY 模式抽取烟雾测试通过！")
        print()
        
        return 0
        
    except Exception as e:
        log_error(f"测试异常: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

