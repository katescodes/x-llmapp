#!/usr/bin/env python3
"""
平台/Work 边界检查脚本
确保 apps/** (Work层) 不包含通用平台逻辑，不直接访问底层实现
"""
import re
import sys
from pathlib import Path


def check_forbidden_imports():
    """检查 Work 层是否违反导入边界规则"""
    apps_dir = Path(__file__).parent.parent.parent / "backend" / "app" / "apps"
    
    violations = []
    
    # 禁止的导入模式（Work层不应直接导入的平台内部实现）
    forbidden_import_patterns = [
        # 禁止直接导入检索内部实现
        (r'from\s+app\.platform\.retrieval\.new_retriever\s+import', 
         'from app.platform.retrieval.new_retriever - Work层应使用 facade'),
        (r'import\s+app\.platform\.retrieval\.new_retriever', 
         'import app.platform.retrieval.new_retriever - Work层应使用 facade'),
        
        # 禁止直接导入文档摄入服务（如果它是平台级服务）
        (r'from\s+app\.services\.doc_ingest_service\s+import', 
         'from app.services.doc_ingest_service - Work层应通过平台入口'),
        
        # 禁止直接导入 pymilvus（Work层不应直接操作向量数据库）
        (r'import\s+pymilvus', 
         'import pymilvus - Work层不应直接操作向量数据库'),
        (r'from\s+pymilvus\s+import', 
         'from pymilvus - Work层不应直接操作向量数据库'),
        
        # 禁止直接导入 psycopg（检索实现不应散落Work层）
        (r'import\s+psycopg', 
         'import psycopg - 检索实现不应在Work层，应使用DAO或平台API'),
        (r'from\s+psycopg\s+import', 
         'from psycopg - 检索实现不应在Work层，应使用DAO或平台API'),
    ]
    
    # 允许的导入模式（白名单）
    allowed_import_patterns = [
        r'from\s+app\.platform\.[\w\.]+\.facade\s+import',  # 允许导入 facade
        r'from\s+app\.platform\.[\w\.]+\.engine\s+import',  # 允许导入公开的 engine
        r'from\s+app\.platform\.extraction\.',  # 允许导入 extraction 平台
        r'from\s+app\.services\.embedding_provider_store\s+import',  # 允许导入 embedding store（公开服务）
    ]
    
    # 扫描所有Python文件
    for py_file in apps_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        
        content = py_file.read_text(encoding='utf-8')
        rel_path = py_file.relative_to(apps_dir.parent.parent.parent)
        
        for pattern, desc in forbidden_import_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                # 检查是否在允许列表中
                line = content[content.rfind('\n', 0, match.start())+1:match.end()]
                is_allowed = any(re.search(allow_pattern, line) for allow_pattern in allowed_import_patterns)
                
                if not is_allowed:
                    violations.append(f"{rel_path}: {desc}")
    
    return violations


def check_tender_boundary():
    """检查 tender 目录是否违反边界规则（保留原有逻辑）"""
    tender_dir = Path(__file__).parent.parent.parent / "backend" / "app" / "apps" / "tender"
    
    violations = []
    
    # 禁止的模式（通用抽取逻辑）
    forbidden_patterns = [
        (r'asyncio\.run\(', 'asyncio.run( - 不应直接调用asyncio'),
        (r'\.complete\(', '.complete( - LLM调用应通过平台层'),
        (r'\.generate\(', '.generate( - LLM调用应通过平台层'),
        (r'def\s+repair_json\(', 'repair_json函数定义 - 应使用platform.extraction.json_utils'),
        (r'def\s+build_marked_context\(', 'build_marked_context函数定义 - 应使用platform.extraction.context'),
        (r'\bchunk_id_set\s*=\s*set\(\)', 'chunk去重逻辑 - 应在platform.extraction.engine中'),
        (r'for\s+query_name\s*,\s*query_text\s+in\s+queries', '多query循环 - 应在platform.extraction.engine中'),
    ]
    
    # 扫描所有Python文件
    for py_file in tender_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        
        content = py_file.read_text(encoding='utf-8')
        rel_path = py_file.relative_to(tender_dir.parent.parent.parent)
        
        for pattern, desc in forbidden_patterns:
            if re.search(pattern, content):
                violations.append(f"{rel_path}: {desc}")
    
    return violations


def check_platform_no_services_import():
    """检查 platform/ 层不应导入 app.services（Step 1.6 锁定白名单）"""
    platform_dir = Path(__file__).parent.parent.parent / "backend" / "app" / "platform"
    
    violations = []
    temp_allows_used = []
    legacy_allows_used = []
    
    # 显式白名单：精确到文件路径（过渡期临时允许）
    # Step 2+ 会逐步消除这些依赖
    # ⚠️ 硬限制：不允许超过 9 项，防止继续膨胀（Step 3 从 11 → 9）
    MAX_ALLOWLIST_HITS = 9
    
    ALLOW_PLATFORM_IMPORT_SERVICES = {
        # 已完成迁移的不再需要白名单
        # "backend/app/platform/ingest/v2_service.py": ["app.services.documents.parser"],  # Step 2 已消除
        # "backend/app/platform/retrieval/new_retriever.py": ["app.services.vectorstore.milvus_docseg_store"],  # Step 3 已消除
        # "backend/app/platform/ingest/v2_service.py": ["app.services.vectorstore.milvus_docseg_store"],  # Step 3 已消除
        
        # 待迁移的（Step 4+）
        "backend/app/platform/ingest/v2_service.py": [
            "app.services.segmenter.chunker",
            "app.services.embedding.http_embedding_client",
            "app.services.embedding_provider_store",
        ],
        "backend/app/platform/retrieval/new_retriever.py": [
            "app.services.embedding.http_embedding_client",
            "app.services.embedding_provider_store",
            "app.services.retrieval.rrf",
        ],
        "backend/app/platform/retrieval/facade.py": [
            "app.services.embedding_provider_store",
            "app.services.db.postgres",
        ],
        "backend/app/platform/rules/evaluator_v2.py": [
            "app.services.embedding_provider_store",
        ],
    }
    
    # Legacy Provider 豁免：这些是遗留实现，允许依赖 app.services
    # 它们在 providers/legacy 下，用于向后兼容，不应影响新架构边界
    LEGACY_PROVIDER_EXEMPTIONS = [
        "backend/app/platform/retrieval/providers/legacy/retriever.py",
        "backend/app/platform/retrieval/providers/legacy/pg_lexical.py",
    ]
    
    # 扫描所有 Python 文件
    for py_file in platform_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        
        content = py_file.read_text(encoding='utf-8')
        rel_path = py_file.relative_to(platform_dir.parent.parent.parent)
        rel_path_str = str(rel_path)
        
        # 查找所有 app.services 导入
        import_matches = list(re.finditer(r'from\s+app\.services\.([^\s]+)\s+import', content))
        
        for match in import_matches:
            import_path = f"app.services.{match.group(1)}"
            line_start = content.rfind('\n', 0, match.start()) + 1
            line_end = content.find('\n', match.end())
            if line_end == -1:
                line_end = len(content)
            line = content[line_start:line_end]
            
            # 检查是否在 Legacy Provider 豁免列表中
            is_legacy_exempt = rel_path_str in LEGACY_PROVIDER_EXEMPTIONS
            if is_legacy_exempt:
                legacy_allows_used.append(f"{rel_path_str} -> {import_path}")
                continue
            
            # 检查是否在显式白名单中
            is_allowed = False
            if rel_path_str in ALLOW_PLATFORM_IMPORT_SERVICES:
                allowed_imports = ALLOW_PLATFORM_IMPORT_SERVICES[rel_path_str]
                if any(import_path.startswith(allowed) for allowed in allowed_imports):
                    is_allowed = True
                    temp_allows_used.append(f"{rel_path_str} -> {import_path}")
            
            if not is_allowed:
                violations.append(
                    f"{rel_path}: platform/ 不应导入 app.services（应使用平台内部模块或 DAO）\n"
                    f"    违规行: {line.strip()}"
                )
    
    # 硬限制：如果 allowlist 命中数超过最大值，则失败
    if len(temp_allows_used) > MAX_ALLOWLIST_HITS:
        violations.append(
            f"ALLOWLIST_BLOAT: allowlist 命中数 {len(temp_allows_used)} > 最大值 {MAX_ALLOWLIST_HITS}\n"
            f"    这意味着新的依赖被引入，不允许继续膨胀！\n"
            f"    当前命中项: {temp_allows_used}"
        )
    
    return violations, temp_allows_used, legacy_allows_used


def check_works_tender_no_services_import():
    """检查 works/tender/** 不应导入 app.services.semantic_outline 或 tender 相关旧 services"""
    # 动态查找 repo root
    script_path = Path(__file__).resolve()
    repo_root = None
    
    # 向上查找 repo root（存在 docker-compose.yml 或 backend/ 目录）
    for parent in script_path.parents:
        if (parent / "docker-compose.yml").exists() or (parent / "backend").exists():
            repo_root = parent
            break
    
    if not repo_root:
        print("  ⚠️ 警告: 无法找到 repo root，跳过 Check4")
        return []
    
    # 尝试多个可能的路径（兼容宿主机和容器）
    possible_paths = [
        repo_root / "backend" / "app" / "works" / "tender",  # 标准路径
        repo_root / "app" / "works" / "tender",  # 容器内路径
        repo_root / "backend" / "app" / "apps" / "tender",  # 旧路径（兼容）
    ]
    
    works_tender_dir = None
    for path in possible_paths:
        if path.exists():
            works_tender_dir = path
            print(f"  ℹ️ 找到 works/tender 目录: {path}")
            break
    
    if not works_tender_dir:
        print(f"  ⚠️ 警告: works/tender 目录不存在于以下路径:")
        for path in possible_paths:
            print(f"    - {path} (存在: {path.exists()})")
        print("  跳过 Check4")
        return []
    
    violations = []
    
    # 禁止的 services 导入（tender 专用能力不应回流到 services）
    forbidden_services = [
        "app.services.semantic_outline",  # 已迁移到 works/tender/outline
        "app.services.tender",  # tender业务逻辑不应在services层
    ]
    
    # 扫描所有 Python 文件
    for py_file in works_tender_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        
        content = py_file.read_text(encoding='utf-8')
        # 使用相对于 repo_root 的路径，更容易理解
        try:
            rel_path = py_file.relative_to(repo_root)
        except ValueError:
            # 如果无法计算相对路径，使用绝对路径
            rel_path = py_file
        
        # 查找所有禁止的导入
        for forbidden in forbidden_services:
            pattern = rf'from\s+{re.escape(forbidden)}\s+import|import\s+{re.escape(forbidden)}'
            matches = list(re.finditer(pattern, content))
            
            for match in matches:
                line_start = content.rfind('\n', 0, match.start()) + 1
                line_end = content.find('\n', match.end())
                if line_end == -1:
                    line_end = len(content)
                line = content[line_start:line_end]
                
                violations.append(
                    f"{rel_path}: works/tender/ 不应导入 {forbidden}（tender专用能力已收口到works/tender）\n"
                    f"    违规行: {line.strip()}"
                )
    
    return violations


def main():
    print("=" * 60)
    print("  Platform/Work 边界检查 (Step 1)")
    print("=" * 60)
    print()
    
    all_violations = []
    
    # 检查1: 禁止的导入边界
    print("检查1: Work层导入边界...")
    import_violations = check_forbidden_imports()
    if not import_violations:
        print("  ✓ PASS: Work层未违反导入边界")
    else:
        print(f"  ✗ FAIL: 发现 {len(import_violations)} 个导入违规")
        all_violations.extend(import_violations)
    print()
    
    # 检查2: tender 目录边界（原有检查）
    print("检查2: apps/tender 边界...")
    tender_violations = check_tender_boundary()
    if not tender_violations:
        print("  ✓ PASS: apps/tender 不包含通用抽取逻辑")
    else:
        print(f"  ✗ FAIL: 发现 {len(tender_violations)} 个tender违规")
        all_violations.extend(tender_violations)
    print()
    
    # 检查3: platform/ 不应导入 app.services（Step 1.5 显式白名单）
    print("检查3: platform/ 不应导入 app.services（显式白名单模式）...")
    platform_violations, temp_allows, legacy_allows = check_platform_no_services_import()
    if not platform_violations:
        print("  ✓ PASS: platform/ 未违反导入边界")
        if temp_allows:
            print(f"  ⚠ 临时白名单放行 {len(temp_allows)} 项（待后续 Step 消除）:")
            for allow in temp_allows:
                print(f"    TEMP ALLOW: {allow}")
        if legacy_allows:
            print(f"  ℹ Legacy Provider 豁免 {len(legacy_allows)} 项（向后兼容）:")
            for allow in legacy_allows:
                print(f"    LEGACY EXEMPT: {allow}")
    else:
        print(f"  ✗ FAIL: 发现 {len(platform_violations)} 个platform违规")
        all_violations.extend(platform_violations)
    print()
    
    # 检查4: works/tender/** 不应导入旧services（tender专用能力收口）
    print("检查4: works/tender/ 不应导入旧services（tender专用能力收口）...")
    works_tender_violations = check_works_tender_no_services_import()
    if not works_tender_violations:
        print("  ✓ PASS: works/tender/ 未导入旧services")
    else:
        print(f"  ✗ FAIL: 发现 {len(works_tender_violations)} 个works/tender违规")
        all_violations.extend(works_tender_violations)
    print()
    
    # 汇总结果
    if not all_violations:
        print("=" * 60)
        print("✓ PASS: 所有边界检查通过")
        print("=" * 60)
        return 0
    else:
        print("=" * 60)
        print("✗ FAIL: 发现边界违规:")
        print("=" * 60)
        print()
        for v in all_violations:
            print(f"  - {v}")
        print()
        print(f"共 {len(all_violations)} 个违规")
        return 1


if __name__ == "__main__":
    sys.exit(main())

