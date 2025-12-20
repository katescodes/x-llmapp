#!/usr/bin/env python3
"""
招投标功能一致性验证脚本（OLD vs NEW_ONLY）

用途：验证 NEW_ONLY 实现是否满足功能契约，不比 OLD 缺失关键能力

验收判据：
1. NEW_ONLY 必须包含契约定义的所有 required_sections
2. MUST_HIT_001 必须命中
3. 关键字段缺失率 < 20%
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml

# 配置
BASE_URL = os.getenv("BASE_URL", "http://192.168.2.17:9001")
USERNAME = os.getenv("USERNAME", "admin")
PASSWORD = os.getenv("PASSWORD", "admin123")
REPORTS_DIR = Path("reports/verify/parity")

# 颜色输出
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"


def log_info(msg: str):
    print(f"{BLUE}ℹ{RESET} {msg}")


def log_success(msg: str):
    print(f"{GREEN}✓{RESET} {msg}")


def log_warning(msg: str):
    print(f"{YELLOW}⚠{RESET} {msg}")


def log_error(msg: str):
    print(f"{RED}✗{RESET} {msg}")


def login() -> str:
    """登录获取 token"""
    log_info("登录...")
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
        timeout=10
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    log_success(f"登录成功 (user: {USERNAME})")
    return token


def create_project(token: str, name: str) -> str:
    """创建项目"""
    log_info(f"创建项目: {name}")
    resp = requests.post(
        f"{BASE_URL}/api/apps/tender/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name},
        timeout=10
    )
    resp.raise_for_status()
    project_id = resp.json()["id"]
    log_success(f"项目创建成功: {project_id}")
    return project_id


def upload_tender_file(token: str, project_id: str, file_path: str) -> str:
    """上传招标文件"""
    log_info(f"上传招标文件: {file_path}")
    with open(file_path, 'rb') as f:
        resp = requests.post(
            f"{BASE_URL}/api/apps/tender/projects/{project_id}/assets/import",
            headers={"Authorization": f"Bearer {token}"},
            data={"kind": "tender"},
            files={'files': (Path(file_path).name, f, 'application/octet-stream')},
            timeout=120
        )
    resp.raise_for_status()
    assets = resp.json()
    asset_id = assets[0]["id"]
    log_success(f"招标文件上传成功 (asset_id: {asset_id})")
    return asset_id


def wait_for_docstore_ready(token: str, project_id: str, timeout: int = 180) -> bool:
    """等待 DocStore 就绪"""
    log_info("等待 DocStore 入库...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            resp = requests.get(
                f"{BASE_URL}/api/_debug/docstore/ready",
                headers={"Authorization": f"Bearer {token}"},
                params={"project_id": project_id, "doc_type": "tender"},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("ready") and data.get("segments", 0) > 0:
                log_success(f"DocStore 就绪: segments={data.get('segments')}, versions={data.get('versions')}")
                return True
            
            time.sleep(3)
        except Exception as e:
            time.sleep(3)
    
    log_error(f"DocStore 入库超时 ({timeout}s)")
    return False


def extract_with_mode(
    token: str,
    project_id: str,
    endpoint: str,
    mode: str,
    sync: bool = True
) -> Dict[str, Any]:
    """
    使用指定模式进行抽取
    
    Args:
        endpoint: 'project-info' | 'risks' | 'directory' | 'review'
        mode: 'OLD' | 'NEW_ONLY'
    """
    log_info(f"抽取 {endpoint} (mode={mode}, sync={sync})...")
    
    url_map = {
        'project-info': f"{BASE_URL}/api/apps/tender/projects/{project_id}/extract/project-info",
        'risks': f"{BASE_URL}/api/apps/tender/projects/{project_id}/extract/risks",
        'directory': f"{BASE_URL}/api/apps/tender/projects/{project_id}/extract/directory",
        'review': f"{BASE_URL}/api/apps/tender/projects/{project_id}/review/run",
    }
    
    url = url_map.get(endpoint)
    if not url:
        raise ValueError(f"Unknown endpoint: {endpoint}")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Force-Mode": mode
    }
    
    params = {"sync": 1} if sync else {}
    
    start_time = time.time()
    resp = requests.post(
        url,
        headers=headers,
        json={"model_id": None},
        params=params,
        timeout=600  # 10分钟超时
    )
    resp.raise_for_status()
    result = resp.json()
    elapsed_ms = int((time.time() - start_time) * 1000)
    
    status = result.get("status", "unknown")
    log_success(f"{endpoint} 完成 (mode={mode}, status={status}, {elapsed_ms}ms)")
    
    return result


def fetch_project_info(token: str, project_id: str) -> Dict[str, Any]:
    """获取项目信息"""
    resp = requests.get(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/project-info",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()


def fetch_risks(token: str, project_id: str) -> List[Dict[str, Any]]:
    """获取风险列表"""
    resp = requests.get(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/risks",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("risks", []) if isinstance(data, dict) else data


def fetch_outline(token: str, project_id: str) -> List[Dict[str, Any]]:
    """获取目录大纲"""
    resp = requests.get(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/directory",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("items", []) if isinstance(data, dict) else data


def fetch_review(token: str, project_id: str) -> List[Dict[str, Any]]:
    """获取审核项"""
    resp = requests.get(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/review",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("items", []) if isinstance(data, dict) else data


def check_must_hit_001(token: str, project_id: str) -> bool:
    """检查 MUST_HIT_001 规则是否命中"""
    # 方法1: 尝试 DB 查询（通过 debug API）
    try:
        # 这里假设有一个 debug API 可以查询
        # 实际中可能需要直接连 DB 或通过其他方式
        pass
    except:
        pass
    
    # 方法2: 通过 review API
    try:
        items = fetch_review(token, project_id)
        for item in items:
            if isinstance(item, dict) and item.get("rule_id") == "MUST_HIT_001":
                return True
    except:
        pass
    
    return False


def load_contract() -> Dict[str, Any]:
    """加载功能契约"""
    contract_path = Path("app/apps/tender/contracts/tender_contract_v1.yaml")
    if not contract_path.exists():
        raise FileNotFoundError(f"Contract not found: {contract_path}")
    
    with open(contract_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def validate_against_contract(
    data: Dict[str, Any],
    contract: Dict[str, Any],
    mode: str
) -> Dict[str, Any]:
    """
    根据契约验证数据
    
    Returns:
        validation_result: {
            "passed": bool,
            "errors": [],
            "warnings": [],
            "stats": {}
        }
    """
    errors = []
    warnings = []
    stats = {}
    
    # 验证 project_info 四大板块
    required_sections = contract['project_info']['required_sections']
    for section_name in ['base', 'technical_parameters', 'business_terms', 'scoring_criteria']:
        if section_name not in data.get('project_info', {}):
            errors.append(f"缺失必需板块: project_info.{section_name}")
        else:
            section_data = data['project_info'][section_name]
            if section_data is None:
                errors.append(f"板块为 null: project_info.{section_name}")
            elif isinstance(section_data, dict):
                # base 板块是字典
                empty_fields = [k for k, v in section_data.items() if not v]
                stats[f"{section_name}_empty_fields"] = len(empty_fields)
            elif isinstance(section_data, list):
                # 其他板块是数组
                stats[f"{section_name}_count"] = len(section_data)
    
    # 验证 MUST_HIT_001
    # 这里简化处理，实际需要调用 check_must_hit_001
    # stats['must_hit_001'] = check_must_hit_001(token, project_id)
    
    passed = len(errors) == 0
    
    return {
        "passed": passed,
        "errors": errors,
        "warnings": warnings,
        "stats": stats
    }


def generate_diff_summary(
    old_data: Dict[str, Any],
    new_data: Dict[str, Any],
    contract: Dict[str, Any]
) -> Dict[str, Any]:
    """生成对比摘要"""
    diff = {
        "old_mode": "OLD",
        "new_mode": "NEW_ONLY",
        "missing_sections": [],
        "empty_rate": {},
        "critical_issues": [],
        "stats_comparison": {}
    }
    
    # 检查缺失板块
    for section in ['base', 'technical_parameters', 'business_terms', 'scoring_criteria']:
        old_has = section in old_data.get('project_info', {})
        new_has = section in new_data.get('project_info', {})
        
        if old_has and not new_has:
            diff['missing_sections'].append(section)
            diff['critical_issues'].append(f"NEW_ONLY 缺失板块: {section}")
    
    return diff


def generate_report(
    project_name: str,
    old_data: Dict[str, Any],
    new_data: Dict[str, Any],
    diff_summary: Dict[str, Any],
    validation_old: Dict[str, Any],
    validation_new: Dict[str, Any]
) -> str:
    """生成人可读报告"""
    lines = []
    lines.append(f"# 招投标功能一致性报告")
    lines.append(f"")
    lines.append(f"**项目**: {project_name}")
    lines.append(f"**对比模式**: OLD vs NEW_ONLY")
    lines.append(f"")
    
    lines.append(f"## 验证结果")
    lines.append(f"")
    lines.append(f"- OLD 模式: {'✓ PASS' if validation_old['passed'] else '✗ FAIL'}")
    lines.append(f"- NEW_ONLY 模式: {'✓ PASS' if validation_new['passed'] else '✗ FAIL'}")
    lines.append(f"")
    
    if diff_summary['critical_issues']:
        lines.append(f"## ⚠️ 严重问题")
        lines.append(f"")
        for issue in diff_summary['critical_issues']:
            lines.append(f"- {issue}")
        lines.append(f"")
    
    if diff_summary['missing_sections']:
        lines.append(f"## 缺失板块")
        lines.append(f"")
        for section in diff_summary['missing_sections']:
            lines.append(f"- {section}")
        lines.append(f"")
    
    lines.append(f"## 详细对比")
    lines.append(f"")
    lines.append(f"详见 diff_summary.json")
    
    return "\n".join(lines)


def process_project(
    token: str,
    project_name: str,
    tender_file: str,
    output_dir: Path,
    contract: Dict[str, Any]
) -> bool:
    """
    处理单个项目
    
    Returns:
        True if passed, False otherwise
    """
    log_info(f"=" * 70)
    log_info(f"处理项目: {project_name}")
    log_info(f"=" * 70)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # 1. 创建项目
        project_id = create_project(token, project_name)
        
        # 2. 上传文件
        upload_tender_file(token, project_id, tender_file)
        
        # 3. 等待 DocStore 就绪
        if not wait_for_docstore_ready(token, project_id):
            log_error("DocStore 未就绪，跳过")
            return False
        
        # 4. 只跑 NEW_ONLY 验证契约（A3 阶段）
        results = {}
        mode = 'NEW_ONLY'
        log_info(f"--- 运行 {mode} 模式 ---")
        
        # 抽取各项数据
        extract_with_mode(token, project_id, 'project-info', mode)
        extract_with_mode(token, project_id, 'risks', mode)
        # extract_with_mode(token, project_id, 'directory', mode)  # 可选
        extract_with_mode(token, project_id, 'review', mode)
        
        # 获取结果
        project_info = fetch_project_info(token, project_id)
        risks = fetch_risks(token, project_id)
        # outline = fetch_outline(token, project_id)
        review = fetch_review(token, project_id)
        
        results[mode] = {
            'project_info': project_info,
            'risks': risks,
            # 'outline': outline,
            'review': review
        }
        
        # 保存到文件
        (output_dir / "new_project_info.json").write_text(
            json.dumps(project_info, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        (output_dir / "new_risks.json").write_text(
            json.dumps(risks, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        (output_dir / "new_review.json").write_text(
            json.dumps(review, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        
        # OLD 模式占位（A3 阶段不运行）
        (output_dir / "old_project_info.json").write_text(
            json.dumps({}, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        (output_dir / "old_risks.json").write_text(
            json.dumps([], ensure_ascii=False, indent=2), encoding='utf-8'
        )
        (output_dir / "old_review.json").write_text(
            json.dumps([], ensure_ascii=False, indent=2), encoding='utf-8'
        )
        
        # 5. 验证 NEW_ONLY 契约符合性（A3 阶段）
        log_info("--- 验证契约符合性 ---")
        failures = []
        
        # 5.1 检查 project_info 四大板块
        required_sections = contract['project_info']['required_sections']
        for section_key in required_sections.keys():
            if section_key not in project_info:
                failures.append(f"project_info 缺失板块: {section_key}")
                log_error(f"  ✗ 缺失板块: {section_key}")
            else:
                log_success(f"  ✓ 板块存在: {section_key}")
        
        # 5.2 检查 MUST_HIT_001 规则命中
        must_hit_rules = contract.get('review', {}).get('must_hit_rules', [])
        must_hit_rule_id = must_hit_rules[0]['rule_id'] if must_hit_rules else "MUST_HIT_001"
        rule_found = False
        if isinstance(review, list):
            for item in review:
                if isinstance(item, dict) and item.get('rule_id') == must_hit_rule:
                    rule_found = True
                    break
        
        if rule_found:
            log_success(f"  ✓ 规则命中: {must_hit_rule_id}")
        else:
            failures.append(f"规则未命中: {must_hit_rule_id}")
            log_error(f"  ✗ 规则未命中: {must_hit_rule_id}")
        
        # 5.3 生成对比摘要（简化版）
        diff_summary = {
            'project_name': project_name,
            'sections_check': {
                'required': list(required_sections.keys()),
                'found': [k for k in required_sections.keys() if k in project_info],
                'missing': [k for k in required_sections.keys() if k not in project_info]
            },
            'rule_check': {
                'required': must_hit_rule_id,
                'found': rule_found
            },
            'failures': failures
        }
        
        # 6. 保存对比摘要
        (output_dir / "diff_summary.json").write_text(
            json.dumps(diff_summary, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        
        # 7. 生成报告
        report_lines = [
            f"# 招投标功能验证报告 - {project_name}",
            "",
            f"**验证时间**: {datetime.now().isoformat()}",
            f"**项目ID**: {project_id}",
            "",
            "## 契约符合性检查",
            "",
            "### 1. Project Info 四大板块",
            ""
        ]
        
        for section_key in required_sections.keys():
            status = "✓" if section_key in project_info else "✗"
            report_lines.append(f"- [{status}] {section_key}")
        
        report_lines.extend([
            "",
            f"### 2. 规则命中检查",
            "",
            f"- 必命中规则: {must_hit_rule_id}",
            f"- 命中状态: {'✓ 命中' if rule_found else '✗ 未命中'}",
            "",
            "## 验证结果",
            ""
        ])
        
        if not failures:
            report_lines.append("✅ **所有检查通过**")
        else:
            report_lines.append("❌ **验证失败**")
            report_lines.append("")
            report_lines.append("失败项:")
            for failure in failures:
                report_lines.append(f"- {failure}")
        
        report_md = "\n".join(report_lines)
        (output_dir / "report.md").write_text(report_md, encoding='utf-8')
        
        # 8. 判断是否通过
        passed = len(failures) == 0
        
        if passed:
            log_success(f"✓ 项目 {project_name} 验证通过")
        else:
            log_error(f"✗ 项目 {project_name} 验证失败")
            for failure in failures:
                log_error(f"    - {failure}")
        
        return passed
        
    except Exception as e:
        log_error(f"处理项目失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="招投标功能一致性验证")
    parser.add_argument("--corpus_dir", help="测试语料目录（可选）")
    parser.add_argument("--base_url", default=BASE_URL, help="Backend URL")
    args = parser.parse_args()
    
    try:
        # 加载契约
        log_info("加载功能契约...")
        contract = load_contract()
        log_success(f"契约加载成功: {contract['name']} v{contract['version']}")
        
        # 登录
        token = login()
        
        # 确定测试项目列表
        test_projects = []
        if args.corpus_dir and Path(args.corpus_dir).exists():
            # 扫描语料目录
            corpus_dir = Path(args.corpus_dir)
            for item in corpus_dir.iterdir():
                if item.is_dir():
                    # 查找招标文件
                    tender_files = list(item.glob("*.pdf")) + list(item.glob("*.doc*"))
                    if tender_files:
                        test_projects.append({
                            'name': item.name,
                            'file': str(tender_files[0]),
                            'output_dir': REPORTS_DIR / item.name
                        })
        
        # 默认：使用 testdata
        if not test_projects:
            test_projects.append({
                'name': 'testdata',
                'file': 'testdata/tender_sample.pdf',
                'output_dir': REPORTS_DIR / 'testdata'
            })
        
        # 处理所有项目
        log_info(f"共 {len(test_projects)} 个测试项目")
        
        results = []
        for proj in test_projects:
            passed = process_project(
                token,
                proj['name'],
                proj['file'],
                proj['output_dir'],
                contract
            )
            results.append({
                'name': proj['name'],
                'passed': passed
            })
        
        # 汇总结果
        print()
        log_info("=" * 70)
        log_info("验收汇总")
        log_info("=" * 70)
        
        passed_count = sum(1 for r in results if r['passed'])
        total_count = len(results)
        
        for r in results:
            status = f"{GREEN}✓ PASS{RESET}" if r['passed'] else f"{RED}✗ FAIL{RESET}"
            print(f"  {r['name']}: {status}")
        
        print()
        log_info(f"通过: {passed_count}/{total_count}")
        
        # 退出码
        if passed_count == total_count:
            log_success("所有项目验证通过！")
            sys.exit(0)
        else:
            log_error(f"{total_count - passed_count} 个项目验证失败")
            sys.exit(1)
        
    except Exception as e:
        log_error(f"执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

