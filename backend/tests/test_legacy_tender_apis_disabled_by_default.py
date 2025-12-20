"""
测试：默认情况下Legacy Tender APIs不暴露

确保LEGACY_TENDER_APIS_ENABLED=false时，旧接口不在OpenAPI中出现
"""
import os
import pytest


def test_legacy_tender_apis_disabled_by_default():
    """测试默认情况下legacy APIs不暴露"""
    # 确保环境变量是默认值（不启用legacy）
    os.environ["LEGACY_TENDER_APIS_ENABLED"] = "false"
    
    # 需要重新导入app以应用环境变量
    # 注意：由于Python模块缓存，这个测试最好在独立进程运行
    from app.main import app
    
    paths = list(app.openapi()["paths"].keys())
    
    # 检查关键的legacy路径不存在
    legacy_paths = [
        "/api/apps/tender/projects/{project_id}/documents",  # list_legacy_documents
    ]
    
    for legacy_path in legacy_paths:
        assert legacy_path not in paths, (
            f"Legacy API {legacy_path} should not be exposed when "
            f"LEGACY_TENDER_APIS_ENABLED=false"
        )
    
    # 检查tags中不包含tender-legacy
    tags = set()
    for path_info in app.openapi()["paths"].values():
        for method_info in path_info.values():
            if isinstance(method_info, dict) and "tags" in method_info:
                tags.update(method_info["tags"])
    
    assert "tender-legacy" not in tags, (
        "tender-legacy tag should not exist when LEGACY_TENDER_APIS_ENABLED=false"
    )


def test_legacy_apis_structure_exists():
    """测试legacy API结构存在（但未挂载）"""
    # 验证legacy router文件存在
    import app.routers.legacy.tender_legacy as legacy_module
    
    # 验证包含DEPRECATED标识
    assert "DEPRECATED" in legacy_module.__doc__, (
        "Legacy module must contain DEPRECATED marker"
    )
    
    # 验证router存在
    assert hasattr(legacy_module, "router"), (
        "Legacy module must have router defined"
    )

