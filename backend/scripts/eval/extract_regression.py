#!/usr/bin/env python3
"""
抽取完整性回归检查
对比 OLD vs NEW_ONLY 模式的抽取结果，确保关键字段不回退
"""
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

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
        json={"name": f"回归测试-{int(time.time())}"},
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
    mode: str
) -> Dict[str, Any]:
    """
    抽取项目信息
    
    Args:
        mode: "OLD" 或 "NEW_ONLY"
    """
    start_time = time.time()
    
    # NEW_ONLY 模式：等待 DocStore 入库
    if mode == "NEW_ONLY":
        log_info(f"等待 DocStore 入库完成...")
        if not wait_for_docstore_ready(base_url, token, project_id):
            raise RuntimeError(f"模式={mode} DocStore 入库超时")
    
    # 提交抽取任务（使用同步模式）
    resp = requests.post(
        f"{base_url}/api/apps/tender/projects/{project_id}/extract/project-info",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Force-Mode": mode
        },
        json={"model_id": None},
        params={"sync": 1},  # 同步执行
        timeout=300  # 5分钟超时
    )
    resp.raise_for_status()
    result = resp.json()
    run_id = result["run_id"]
    
    extract_time_ms = int((time.time() - start_time) * 1000)
    log_info(f"模式={mode}, run_id={run_id}, 耗时={extract_time_ms}ms")
    
    # 检查同步执行结果
    status = result.get("status", "unknown")
    if status not in ("ok", "success"):
        raise RuntimeError(f"模式={mode} 抽取失败: {result.get('message', 'unknown')}")
    
    log_success(f"模式={mode} 抽取完成 (耗时: {extract_time_ms}ms)")
    
    # 获取结果
    resp = requests.get(
        f"{base_url}/api/apps/tender/projects/{project_id}/project-info",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Force-Mode": mode
        },
        timeout=10
    )
    resp.raise_for_status()
    result_data = resp.json()
    result_data["_extract_time_ms"] = extract_time_ms
    return result_data


def check_key_fields(old_data: Dict, new_data: Dict) -> List[str]:
    """
    检查关键字段是否从有值变为空
    
    Returns:
        违规列表
    """
    violations = []
    
    # 定义关键字段（根据实际schema调整）
    key_fields = [
        ("projectName", "项目名称"),
        ("budget", "预算金额"),
        ("bidDeadline", "投标截止时间"),
        ("bidOpeningTime", "开标时间"),
    ]
    
    for field_name, field_desc in key_fields:
        old_val = old_data.get(field_name)
        new_val = new_data.get(field_name)
        
        # 如果OLD有值但NEW为空，视为回退
        if old_val and not new_val:
            violations.append(f"{field_desc}({field_name}): OLD有值但NEW_ONLY为空")
    
    return violations


def check_content_blocks(old_data: Dict, new_data: Dict) -> List[str]:
    """
    检查四块内容不得全空
    
    Returns:
        违规列表
    """
    violations = []
    
    # 技术参数
    old_tech = old_data.get("technicalParameters", [])
    new_tech = new_data.get("technicalParameters", [])
    if len(old_tech) > 0 and len(new_tech) == 0:
        violations.append("技术参数: OLD有内容但NEW_ONLY为空")
    
    # 商务条款
    old_biz = old_data.get("businessTerms", [])
    new_biz = new_data.get("businessTerms", [])
    if len(old_biz) > 0 and len(new_biz) == 0:
        violations.append("商务条款: OLD有内容但NEW_ONLY为空")
    
    # 评分标准
    old_scoring = old_data.get("scoringCriteria", {}).get("items", [])
    new_scoring = new_data.get("scoringCriteria", {}).get("items", [])
    if len(old_scoring) > 0 and len(new_scoring) == 0:
        violations.append("评分标准: OLD有内容但NEW_ONLY为空")
    
    return violations


def check_evidence(result: Dict) -> List[str]:
    """
    检查证据链不为空
    
    Returns:
        违规列表
    """
    violations = []
    
    evidence = result.get("evidence_chunk_ids", [])
    if not evidence or len(evidence) == 0:
        violations.append("evidence_chunk_ids为空，未走检索或证据丢失")
    
    return violations


def main():
    parser = argparse.ArgumentParser(description="抽取完整性回归检查")
    parser.add_argument("--base-url", required=True, help="Backend URL")
    parser.add_argument("--tender-file", required=True, help="招标文件路径")
    args = parser.parse_args()
    
    reports_dir = Path(__file__).parent.parent.parent / "reports" / "verify"
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("  抽取完整性回归检查")
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
        
        # 等待入库（如果需要）
        log_info("等待5秒让入库完成...")
        time.sleep(5)
        
        # 4. OLD模式抽取
        log_info("运行OLD模式抽取...")
        old_result = extract_project_info(args.base_url, token, project_id, "OLD")
        old_data = old_result.get("data", {})
        
        # 保存OLD结果
        with open(reports_dir / "old_project_info.json", 'w', encoding='utf-8') as f:
            json.dump(old_result, f, ensure_ascii=False, indent=2)
        
        # 5. NEW_ONLY模式抽取
        log_info("运行NEW_ONLY模式抽取...")
        new_result = extract_project_info(args.base_url, token, project_id, "NEW_ONLY")
        new_data = new_result.get("data", {})
        
        # 保存NEW结果
        with open(reports_dir / "newonly_project_info.json", 'w', encoding='utf-8') as f:
            json.dump(new_result, f, ensure_ascii=False, indent=2)
        
        # 6. 对比检查
        print()
        log_info("对比检查...")
        
        all_violations = []
        
        # 检查关键字段
        field_violations = check_key_fields(old_data, new_data)
        all_violations.extend(field_violations)
        
        # 检查内容块
        block_violations = check_content_blocks(old_data, new_data)
        all_violations.extend(block_violations)
        
        # 检查NEW_ONLY证据
        evidence_violations = check_evidence(new_result)
        all_violations.extend(evidence_violations)
        
        # 7. 生成diff报告
        diff_report = {
            "project_id": project_id,
            "old_mode": "OLD",
            "new_mode": "NEW_ONLY",
            "violations": all_violations,
            "old_summary": {
                "project_name": old_data.get("projectName"),
                "tech_params_count": len(old_data.get("technicalParameters", [])),
                "biz_terms_count": len(old_data.get("businessTerms", [])),
                "scoring_items_count": len(old_data.get("scoringCriteria", {}).get("items", [])),
                "evidence_count": len(old_result.get("evidence_chunk_ids", []))
            },
            "new_summary": {
                "project_name": new_data.get("projectName"),
                "tech_params_count": len(new_data.get("technicalParameters", [])),
                "biz_terms_count": len(new_data.get("businessTerms", [])),
                "scoring_items_count": len(new_data.get("scoringCriteria", {}).get("items", [])),
                "evidence_count": len(new_result.get("evidence_chunk_ids", []))
            }
        }
        
        with open(reports_dir / "extract_regression_diff.json", 'w', encoding='utf-8') as f:
            json.dump(diff_report, f, ensure_ascii=False, indent=2)
        
        # 8. 输出结果
        print()
        print("=" * 70)
        print("  对比结果")
        print("=" * 70)
        print()
        print(f"OLD模式摘要:")
        print(f"  - 项目名称: {diff_report['old_summary']['project_name']}")
        print(f"  - 技术参数: {diff_report['old_summary']['tech_params_count']} 条")
        print(f"  - 商务条款: {diff_report['old_summary']['biz_terms_count']} 条")
        print(f"  - 评分标准: {diff_report['old_summary']['scoring_items_count']} 条")
        print(f"  - 证据数量: {diff_report['old_summary']['evidence_count']} 个")
        print()
        print(f"NEW_ONLY模式摘要:")
        print(f"  - 项目名称: {diff_report['new_summary']['project_name']}")
        print(f"  - 技术参数: {diff_report['new_summary']['tech_params_count']} 条")
        print(f"  - 商务条款: {diff_report['new_summary']['biz_terms_count']} 条")
        print(f"  - 评分标准: {diff_report['new_summary']['scoring_items_count']} 条")
        print(f"  - 证据数量: {diff_report['new_summary']['evidence_count']} 个")
        print()
        
        if all_violations:
            print("回归检查失败，发现以下问题:")
            for v in all_violations:
                log_error(f"  - {v}")
            print()
            print("✗ 回归检查未通过")
            return 1
        else:
            log_success("所有检查通过")
            print()
            print("✓ 回归检查通过")
            return 0
            
    except Exception as e:
        log_error(f"回归检查异常: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
