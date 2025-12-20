#!/usr/bin/env python3
"""
批量验证现有项目的新旧抽取一致性
扫描所有现有项目，对比 OLD vs NEW_ONLY 模式
"""
import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# 配置
BASE_URL = os.getenv("BASE_URL", "http://localhost:9001")
USERNAME = os.getenv("USERNAME", "admin")
PASSWORD = os.getenv("PASSWORD", "admin123")
THRESH_MISS_RATIO = float(os.getenv("THRESH_MISS_RATIO", "0.10"))
OUTPUT_DIR = Path("reports/batch_eval")

# 关键字段列表
KEY_FIELDS = {
    "项目名称", "project_name", "name",
    "招标人", "tenderee", "buyer",
    "预算金额", "budget", "budget_amount",
    "开标时间", "bidding_time", "bid_opening_time",
    "投标截止时间", "deadline", "bid_deadline",
}

def log_info(msg: str):
    """打印信息"""
    print(f"[INFO] {msg}")

def log_success(msg: str):
    """打印成功"""
    print(f"[✅] {msg}")

def log_error(msg: str):
    """打印错误"""
    print(f"[❌] {msg}", file=sys.stderr)

def log_warning(msg: str):
    """打印警告"""
    print(f"[⚠️] {msg}")

def login() -> str:
    """登录获取 token"""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD}
    )
    resp.raise_for_status()
    return resp.json()["access_token"]

def get_all_projects(token: str) -> List[Dict]:
    """获取所有项目"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BASE_URL}/api/apps/tender/projects", headers=headers)
    resp.raise_for_status()
    return resp.json()

def extract_with_mode(token: str, project_id: str, mode: str) -> Dict:
    """使用指定模式运行抽取"""
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Force-Mode": mode,
        "Content-Type": "application/json"
    }
    
    log_info(f"  [{mode}] 开始抽取项目信息...")
    resp = requests.post(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/extract/project-info",
        headers=headers,
        json={}
    )
    
    if resp.status_code != 200:
        log_error(f"  [{mode}] 抽取失败: {resp.status_code}")
        return {"error": resp.text}
    
    run_id = resp.json().get("run_id")
    log_info(f"  [{mode}] run_id={run_id}, 轮询等待完成...")
    
    # 轮询等待完成
    max_wait = 120  # 最多等待 2 分钟
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        time.sleep(2)
        status_resp = requests.get(
            f"{BASE_URL}/api/apps/tender/runs/{run_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if status_resp.status_code != 200:
            continue
        
        status_data = status_resp.json()
        status = status_data.get("status")
        
        if status == "succeeded":
            log_success(f"  [{mode}] 抽取成功")
            break
        elif status in ("failed", "error"):
            log_error(f"  [{mode}] 抽取失败: {status_data.get('message', 'Unknown error')}")
            return {"error": status_data.get("message")}
        elif status == "running":
            continue
        else:
            log_warning(f"  [{mode}] 未知状态: {status}")
    else:
        log_error(f"  [{mode}] 抽取超时")
        return {"error": "Timeout"}
    
    # 获取结果
    result_resp = requests.get(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/project-info",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if result_resp.status_code != 200:
        log_error(f"  [{mode}] 获取结果失败")
        return {"error": "Failed to get result"}
    
    return result_resp.json()

def flatten_json(data: Dict, prefix: str = "") -> Dict:
    """扁平化 JSON"""
    result = {}
    
    if not isinstance(data, dict):
        return {prefix: data}
    
    for key, value in data.items():
        new_key = f"{prefix}.{key}" if prefix else key
        
        if isinstance(value, dict):
            result.update(flatten_json(value, new_key))
        elif isinstance(value, list):
            result[new_key] = json.dumps(value, ensure_ascii=False)
        else:
            result[new_key] = value
    
    return result

def normalize_value(value) -> str:
    """归一化值"""
    if value is None:
        return ""
    
    s = str(value).strip()
    
    # 去除多余空白
    s = " ".join(s.split())
    
    # 全角转半角
    s = s.replace("　", " ")
    
    return s

def is_key_field(field_name: str) -> bool:
    """判断是否为关键字段"""
    field_lower = field_name.lower()
    for kf in KEY_FIELDS:
        if kf.lower() in field_lower:
            return True
    return False

def compare_results(old_result: Dict, new_result: Dict) -> Dict:
    """对比 OLD 和 NEW_ONLY 结果"""
    old_flat = flatten_json(old_result)
    new_flat = flatten_json(new_result)
    
    # 归一化
    old_normalized = {k: normalize_value(v) for k, v in old_flat.items()}
    new_normalized = {k: normalize_value(v) for k, v in new_flat.items()}
    
    # 对比字段
    all_fields = set(old_normalized.keys()) | set(new_normalized.keys())
    missing_fields = []
    key_fields_missing = []
    
    for field in all_fields:
        old_val = old_normalized.get(field, "")
        new_val = new_normalized.get(field, "")
        
        # OLD 有值，NEW 没值 -> 缺失
        if old_val and not new_val:
            missing_fields.append(field)
            if is_key_field(field):
                key_fields_missing.append(field)
    
    # 计算缺失率
    non_empty_old_count = sum(1 for v in old_normalized.values() if v)
    missing_ratio = len(missing_fields) / non_empty_old_count if non_empty_old_count > 0 else 0.0
    
    # 判断 NEW 是否全空
    new_empty = all(not v for v in new_normalized.values())
    
    return {
        "missing_ratio": missing_ratio,
        "missing_fields": missing_fields,
        "key_fields_missing": key_fields_missing,
        "new_empty": new_empty,
        "old_field_count": len(old_normalized),
        "new_field_count": len(new_normalized),
    }

def is_project_pass(comparison: Dict) -> bool:
    """判断项目是否通过"""
    # 1. NEW 不能全空
    if comparison["new_empty"]:
        return False
    
    # 2. 关键字段不能缺失
    if len(comparison["key_fields_missing"]) > 0:
        return False
    
    # 3. 缺失率不能超过阈值
    if comparison["missing_ratio"] > THRESH_MISS_RATIO:
        return False
    
    return True

def generate_project_report(project: Dict, comparison: Dict, project_dir: Path):
    """生成项目报告"""
    project_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成 Markdown 报告
    report_path = project_dir / "report.md"
    
    passed = is_project_pass(comparison)
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# 项目验证报告\n\n")
        f.write(f"## 基本信息\n\n")
        f.write(f"- **项目名称**: {project['name']}\n")
        f.write(f"- **项目 ID**: {project['id']}\n")
        f.write(f"- **验证时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write(f"## 验证结果\n\n")
        if passed:
            f.write(f"### ✅ **通过**\n\n")
        else:
            f.write(f"### ❌ **失败**\n\n")
        
        f.write(f"- **缺失率**: {comparison['missing_ratio']:.2%}\n")
        f.write(f"- **缺失字段数**: {len(comparison['missing_fields'])} / {comparison['old_field_count']}\n")
        f.write(f"- **关键字段缺失数**: {len(comparison['key_fields_missing'])}\n")
        f.write(f"- **NEW 全空**: {'是' if comparison['new_empty'] else '否'}\n\n")
        
        if comparison["key_fields_missing"]:
            f.write(f"## 关键字段缺失\n\n")
            for field in comparison["key_fields_missing"]:
                f.write(f"- `{field}`\n")
            f.write("\n")
        
        if comparison["missing_fields"][:20]:
            f.write(f"## 缺失字段 Top 20\n\n")
            for field in comparison["missing_fields"][:20]:
                f.write(f"- `{field}`\n")
            f.write("\n")
    
    log_info(f"  报告已生成: {report_path}")

def main():
    """主函数"""
    log_info("批量验证现有项目的新旧抽取一致性")
    log_info(f"阈值: 缺失率 <= {THRESH_MISS_RATIO:.0%}")
    log_info("")
    
    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 登录
    log_info("登录...")
    token = login()
    log_success("登录成功")
    
    # 获取所有项目
    log_info("获取项目列表...")
    projects = get_all_projects(token)
    log_success(f"找到 {len(projects)} 个项目")
    
    if not projects:
        log_warning("没有找到项目，退出")
        sys.exit(0)
    
    # 验证每个项目
    results = []
    
    for i, project in enumerate(projects, 1):
        project_id = project["id"]
        project_name = project["name"]
        
        log_info(f"\n{'='*60}")
        log_info(f"[{i}/{len(projects)}] 项目: {project_name}")
        log_info(f"{'='*60}")
        
        # 检查是否有资产
        try:
            assets_resp = requests.get(
                f"{BASE_URL}/api/apps/tender/projects/{project_id}/assets",
                headers={"Authorization": f"Bearer {token}"}
            )
            assets = assets_resp.json() if assets_resp.status_code == 200 else []
            
            if not assets:
                log_warning(f"  项目无资产，跳过")
                continue
        except Exception as e:
            log_warning(f"  获取资产失败: {e}")
            continue
        
        # OLD 模式抽取
        old_result = extract_with_mode(token, project_id, "OLD")
        
        if "error" in old_result:
            log_error(f"  OLD 模式抽取失败，跳过项目")
            results.append({
                "project_name": project_name,
                "project_id": project_id,
                "passed": False,
                "error": "OLD 模式失败",
            })
            continue
        
        # NEW_ONLY 模式抽取
        new_result = extract_with_mode(token, project_id, "NEW_ONLY")
        
        if "error" in new_result:
            log_error(f"  NEW_ONLY 模式抽取失败，跳过项目")
            results.append({
                "project_name": project_name,
                "project_id": project_id,
                "passed": False,
                "error": "NEW_ONLY 模式失败",
            })
            continue
        
        # 对比结果
        log_info(f"  对比结果...")
        comparison = compare_results(old_result, new_result)
        
        passed = is_project_pass(comparison)
        
        log_info(f"  缺失率: {comparison['missing_ratio']:.2%}")
        log_info(f"  关键字段缺失: {len(comparison['key_fields_missing'])} 个")
        
        if passed:
            log_success(f"  ✅ 项目通过")
        else:
            log_error(f"  ❌ 项目失败")
        
        # 生成项目报告
        project_dir = OUTPUT_DIR / project_name.replace("/", "_")
        generate_project_report(project, comparison, project_dir)
        
        # 保存对比数据
        (project_dir / "old_result.json").write_text(
            json.dumps(old_result, ensure_ascii=False, indent=2)
        )
        (project_dir / "new_result.json").write_text(
            json.dumps(new_result, ensure_ascii=False, indent=2)
        )
        (project_dir / "comparison.json").write_text(
            json.dumps(comparison, ensure_ascii=False, indent=2)
        )
        
        results.append({
            "project_name": project_name,
            "project_id": project_id,
            "passed": passed,
            "missing_ratio": comparison["missing_ratio"],
            "key_fields_missing": len(comparison["key_fields_missing"]),
            "missing_fields": len(comparison["missing_fields"]),
        })
    
    # 生成总结报告
    log_info(f"\n{'='*60}")
    log_info("生成总结报告...")
    log_info(f"{'='*60}")
    
    summary_path = OUTPUT_DIR / "_summary.csv"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("项目名称,项目ID,通过,缺失率,关键字段缺失,普通字段缺失,错误\n")
        for r in results:
            f.write(
                f"{r['project_name']},"
                f"{r['project_id']},"
                f"{'通过' if r['passed'] else '失败'},"
                f"{r.get('missing_ratio', 0):.2%},"
                f"{r.get('key_fields_missing', 0)},"
                f"{r.get('missing_fields', 0)},"
                f"{r.get('error', '')}\n"
            )
    
    log_success(f"总结报告已生成: {summary_path}")
    
    # 统计
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    
    log_info(f"\n{'='*60}")
    log_info("验证统计")
    log_info(f"{'='*60}")
    log_info(f"总项目数: {total}")
    log_success(f"通过: {passed}")
    if failed > 0:
        log_error(f"失败: {failed}")
    log_info(f"通过率: {passed/total*100:.1f}%")
    
    # 退出码
    if failed == 0:
        log_success("\n✅ 所有项目验证通过！")
        sys.exit(0)
    else:
        log_error(f"\n❌ {failed} 个项目验证失败")
        log_info(f"详细报告: {OUTPUT_DIR}")
        sys.exit(1)

if __name__ == "__main__":
    main()

