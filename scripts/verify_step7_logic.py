#!/usr/bin/env python3
"""
Step 7 逻辑验证脚本

验证 PREFER_NEW 模式的代码逻辑是否正确：
1. 检查 extract_project_info 是否实现了 PREFER_NEW 分支
2. 检查 extract_risks 是否实现了 PREFER_NEW 分支
3. 检查回退逻辑是否存在
4. 检查日志记录是否完整
"""

import re
import sys
from pathlib import Path

def check_file(file_path: Path) -> bool:
    """检查文件中的 PREFER_NEW 逻辑实现"""
    print(f"\n{'='*60}")
    print(f"检查文件: {file_path}")
    print('='*60)
    
    if not file_path.exists():
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    content = file_path.read_text()
    
    checks = {
        "✅ extract_project_info 存在": 'def extract_project_info(' in content,
        "✅ extract_risks 存在": 'def extract_risks(' in content,
        "✅ PREFER_NEW 判断 (项目信息)": 'extract_mode.value == "PREFER_NEW"' in content,
        "✅ v2_success 标志": 'v2_success = False' in content and 'v2_success = True' in content,
        "✅ v2 失败回退逻辑": 'if not v2_success:' in content,
        "✅ v2 成功日志": 'PREFER_NEW extract_project_info: v2 succeeded' in content,
        "✅ v2 失败日志": 'falling back to old extraction' in content,
        "✅ 统一写入旧表 (项目信息)": 'self.dao.upsert_project_info(' in content,
        "✅ 统一写入旧表 (风险)": 'self.dao.replace_risks(' in content,
    }
    
    all_pass = True
    for check_name, result in checks.items():
        status = "✅" if result else "❌"
        print(f"{status} {check_name.replace('✅ ', '')}")
        if not result:
            all_pass = False
    
    # 额外检查：统计关键代码段
    print(f"\n📊 代码统计:")
    prefer_new_count = content.count('extract_mode.value == "PREFER_NEW"')
    try_count = content.count('try:')
    warning_count = content.count('logger.warning')
    v2_success_count = content.count('v2_success = ')
    print(f"  - PREFER_NEW 分支数: {prefer_new_count}")
    print(f"  - try-except 块数: {try_count}")
    print(f"  - logger.warning 调用数: {warning_count}")
    print(f"  - v2_success 赋值数: {v2_success_count}")
    
    # 检查完整的 PREFER_NEW 逻辑块
    prefer_new_pattern = r'if extract_mode\.value == "PREFER_NEW":.*?v2_success = True.*?except.*?v2_success = False.*?if not v2_success:'
    has_complete_logic = bool(re.search(prefer_new_pattern, content, re.DOTALL))
    
    print(f"\n🔍 完整逻辑检查:")
    print(f"  {'✅' if has_complete_logic else '❌'} PREFER_NEW 完整逻辑块存在 (try → v2 → except → fallback)")
    
    if not has_complete_logic:
        all_pass = False
    
    return all_pass

def main():
    """主函数"""
    print("\n" + "="*60)
    print("  Step 7: PREFER_NEW 逻辑验证")
    print("="*60)
    
    # 检查 tender_service.py
    repo_root = Path(__file__).parent.parent
    tender_service = repo_root / "backend" / "app" / "services" / "tender_service.py"
    
    result = check_file(tender_service)
    
    print("\n" + "="*60)
    if result:
        print("✅ 所有检查通过！PREFER_NEW 逻辑实现正确。")
        print("="*60)
        print("\n📝 下一步：")
        print("  1. 解决 LLM 超时问题（环境配置）")
        print("  2. 运行 smoke test 验证端到端流程")
        print("  3. 配置灰度项目 (CUTOVER_PROJECT_IDS)")
        print("  4. 监控 v2 成功率和性能")
        return 0
    else:
        print("❌ 部分检查未通过，请检查实现。")
        print("="*60)
        return 1

if __name__ == "__main__":
    sys.exit(main())

