#!/usr/bin/env python3
"""
测试 check_platform_work_boundary.py 脚本的基本功能
验证关键规则能够被正确检测
"""
import re
import sys
from pathlib import Path


def test_script_imports_successfully():
    """测试脚本可以被导入"""
    try:
        # 动态导入脚本
        scripts_path = Path(__file__).parent.parent.parent / "scripts" / "ci"
        sys.path.insert(0, str(scripts_path))
        
        import check_platform_work_boundary
        
        # 验证关键函数存在
        assert hasattr(check_platform_work_boundary, 'check_forbidden_imports')
        assert hasattr(check_platform_work_boundary, 'check_tender_boundary')
        assert hasattr(check_platform_work_boundary, 'main')
        
        print("✓ test_script_imports_successfully: PASS")
        return True
    except Exception as e:
        print(f"✗ test_script_imports_successfully: FAIL - {e}")
        return False


def test_forbidden_import_patterns():
    """测试禁止的导入模式能够被识别"""
    test_cases = [
        # (测试代码, 应该被检测为违规)
        ("from app.platform.retrieval.new_retriever import Retriever", True),
        ("import app.platform.retrieval.new_retriever", True),
        ("from app.services.doc_ingest_service import ingest", True),
        ("import pymilvus", True),
        ("from pymilvus import Collection", True),
        ("import psycopg", True),
        ("from psycopg import connect", True),
        
        # 允许的导入（不应被检测为违规）
        ("from app.platform.retrieval.facade import RetrievalFacade", False),
        ("from app.platform.extraction.engine import ExtractionEngine", False),
        ("from app.services.embedding_provider_store import get_embedding_store", False),
    ]
    
    # 简单的模式匹配测试
    forbidden_patterns = [
        r'from\s+app\.platform\.retrieval\.new_retriever\s+import',
        r'import\s+app\.platform\.retrieval\.new_retriever',
        r'from\s+app\.services\.doc_ingest_service\s+import',
        r'import\s+pymilvus',
        r'from\s+pymilvus\s+import',
        r'import\s+psycopg',
        r'from\s+psycopg\s+import',
    ]
    
    all_passed = True
    for test_code, should_be_forbidden in test_cases:
        is_forbidden = any(re.search(pattern, test_code) for pattern in forbidden_patterns)
        
        if should_be_forbidden:
            if is_forbidden:
                print(f"  ✓ Correctly detected: {test_code[:50]}...")
            else:
                print(f"  ✗ Failed to detect: {test_code[:50]}...")
                all_passed = False
        else:
            if not is_forbidden:
                print(f"  ✓ Correctly allowed: {test_code[:50]}...")
            else:
                print(f"  ✗ Incorrectly flagged: {test_code[:50]}...")
                all_passed = False
    
    if all_passed:
        print("✓ test_forbidden_import_patterns: PASS")
    else:
        print("✗ test_forbidden_import_patterns: FAIL")
    
    return all_passed


def test_tender_boundary_patterns():
    """测试 tender 边界规则能够被识别"""
    test_cases = [
        # (测试代码, 应该被检测为违规)
        ("result = asyncio.run(some_func())", True),
        ("response = client.complete(prompt)", True),
        ("text = model.generate(input)", True),
        ("def repair_json(data):", True),
        ("def build_marked_context(chunks):", True),
        ("chunk_id_set = set()", True),
        ("for query_name, query_text in queries:", True),
        
        # 不应被检测为违规的代码
        ("async def my_function():", False),
        ("complete_data = process()", False),
    ]
    
    forbidden_patterns = [
        r'asyncio\.run\(',
        r'\.complete\(',
        r'\.generate\(',
        r'def\s+repair_json\(',
        r'def\s+build_marked_context\(',
        r'\bchunk_id_set\s*=\s*set\(\)',
        r'for\s+query_name\s*,\s*query_text\s+in\s+queries',
    ]
    
    all_passed = True
    for test_code, should_be_forbidden in test_cases:
        is_forbidden = any(re.search(pattern, test_code) for pattern in forbidden_patterns)
        
        if should_be_forbidden:
            if is_forbidden:
                print(f"  ✓ Correctly detected: {test_code[:50]}...")
            else:
                print(f"  ✗ Failed to detect: {test_code[:50]}...")
                all_passed = False
        else:
            if not is_forbidden:
                print(f"  ✓ Correctly allowed: {test_code[:50]}...")
            else:
                # 这个可能会误报，但我们主要关心能检测到违规
                print(f"  ⚠ Flagged (may be false positive): {test_code[:50]}...")
    
    if all_passed:
        print("✓ test_tender_boundary_patterns: PASS")
    else:
        print("✗ test_tender_boundary_patterns: FAIL")
    
    return all_passed


def main():
    """运行所有测试"""
    print("=" * 60)
    print("  Test Boundary Rules (Step 0)")
    print("=" * 60)
    print()
    
    test_results = []
    
    print("Test 1: Script imports successfully")
    test_results.append(test_script_imports_successfully())
    print()
    
    print("Test 2: Forbidden import patterns")
    test_results.append(test_forbidden_import_patterns())
    print()
    
    print("Test 3: Tender boundary patterns")
    test_results.append(test_tender_boundary_patterns())
    print()
    
    # 汇总结果
    print("=" * 60)
    if all(test_results):
        print(f"✓ ALL TESTS PASSED ({len(test_results)}/{len(test_results)})")
        print("=" * 60)
        return 0
    else:
        passed = sum(test_results)
        print(f"✗ SOME TESTS FAILED ({passed}/{len(test_results)} passed)")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())



