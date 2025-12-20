#!/usr/bin/env python3
"""
格式模板数据库验证脚本

验证：
1. 插入模板 -> 更新 analysis/parse -> 绑定目录根 -> 能读出来
2. 所有 DAO 方法正常工作
3. 数据完整性约束生效

运行方式：
  docker exec -it x-llmapp1-backend-1 python scripts/verify_format_templates_db.py
"""
import json
import os
import sys
import uuid
from datetime import datetime

# 添加项目路径
sys.path.insert(0, '/app/backend')

from psycopg_pool import ConnectionPool
from app.services.dao.tender_dao import TenderDAO


def get_pool():
    """获取数据库连接池"""
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/ylyw")
    return ConnectionPool(db_url, min_size=1, max_size=5)


def verify_format_templates(pool: ConnectionPool):
    """验证格式模板功能"""
    dao = TenderDAO(pool)
    
    print("=" * 60)
    print("格式模板数据库验证")
    print("=" * 60)
    print()
    
    # ==================== 1. 创建测试模板 ====================
    print("📝 测试 1: 创建格式模板")
    print("-" * 60)
    
    test_template = dao.create_format_template(
        name=f"测试模板_{uuid.uuid4().hex[:8]}",
        description="自动化测试创建的模板",
        style_config={"test": "config"},
        owner_id="test_user_001",
        is_public=False
    )
    
    template_id = test_template["id"]
    print(f"✅ 创建成功: template_id={template_id}")
    print(f"   名称: {test_template['name']}")
    print(f"   所有者: {test_template['owner_id']}")
    print()
    
    # ==================== 2. 设置存储路径 ====================
    print("📝 测试 2: 设置存储路径和 SHA256")
    print("-" * 60)
    
    test_storage_path = f"/app/storage/templates/test_{uuid.uuid4().hex}.docx"
    test_sha256 = f"sha256_{uuid.uuid4().hex}"
    
    dao.set_format_template_storage(
        template_id=template_id,
        storage_path=test_storage_path,
        sha256=test_sha256
    )
    
    # 验证
    template = dao.get_format_template(template_id)
    assert template["template_storage_path"] == test_storage_path, "存储路径不匹配"
    assert template["file_sha256"] == test_sha256, "SHA256不匹配"
    
    print(f"✅ 设置成功")
    print(f"   存储路径: {test_storage_path}")
    print(f"   SHA256: {test_sha256}")
    print()
    
    # ==================== 3. 设置分析结果 ====================
    print("📝 测试 3: 设置分析结果")
    print("-" * 60)
    
    analysis_json = {
        "styleProfile": {"styles": []},
        "roleMapping": {"h1": "Heading1", "body": "Normal"},
        "applyAssets": {
            "anchors": [],
            "keepPlan": {"keepBlockIds": [], "deleteBlockIds": []},
            "policy": {"confidence": 0.95, "warnings": []}
        },
        "blocks": []
    }
    
    dao.set_format_template_analysis(
        template_id=template_id,
        status="SUCCESS",
        analysis_json=analysis_json,
        error=None
    )
    
    # 验证
    template = dao.get_format_template(template_id)
    assert template["analysis_status"] == "SUCCESS", "分析状态不匹配"
    assert template["analysis_json"] is not None, "analysis_json 为空"
    assert template["analysis_json"]["roleMapping"]["h1"] == "Heading1", "roleMapping 不匹配"
    
    print(f"✅ 设置成功")
    print(f"   状态: {template['analysis_status']}")
    print(f"   confidence: {template['analysis_json']['applyAssets']['policy']['confidence']}")
    print()
    
    # ==================== 4. 设置解析结果 ====================
    print("📝 测试 4: 设置解析结果")
    print("-" * 60)
    
    parse_json = {
        "sections": [{"name": "Section1", "type": "header"}],
        "variants": ["A4_PORTRAIT"],
        "headingLevels": [{"level": 1, "style": "Heading1"}],
        "headerImages": [],
        "footerImages": []
    }
    
    preview_docx = f"/app/storage/previews/test_{uuid.uuid4().hex}.docx"
    preview_pdf = f"/app/storage/previews/test_{uuid.uuid4().hex}.pdf"
    
    dao.set_format_template_parse(
        template_id=template_id,
        status="SUCCESS",
        parse_json=parse_json,
        error=None,
        preview_docx_path=preview_docx,
        preview_pdf_path=preview_pdf
    )
    
    # 验证
    template = dao.get_format_template(template_id)
    assert template["parse_status"] == "SUCCESS", "解析状态不匹配"
    assert template["preview_docx_path"] == preview_docx, "DOCX预览路径不匹配"
    assert template["preview_pdf_path"] == preview_pdf, "PDF预览路径不匹配"
    assert len(template["parse_result_json"]["sections"]) == 1, "sections 不匹配"
    
    print(f"✅ 设置成功")
    print(f"   状态: {template['parse_status']}")
    print(f"   sections: {len(template['parse_result_json']['sections'])}")
    print(f"   预览DOCX: {preview_docx}")
    print(f"   预览PDF: {preview_pdf}")
    print()
    
    # ==================== 5. 创建模板资产 ====================
    print("📝 测试 5: 创建模板资产")
    print("-" * 60)
    
    asset = dao.create_format_template_asset(
        template_id=template_id,
        asset_type="HEADER_IMG",
        variant="A4_PORTRAIT",
        storage_path=f"/app/storage/assets/header_{uuid.uuid4().hex}.png",
        file_name="header.png",
        content_type="image/png",
        width_px=800,
        height_px=100
    )
    
    print(f"✅ 资产创建成功: asset_id={asset['id']}")
    print(f"   类型: {asset['asset_type']}")
    print(f"   变体: {asset['variant']}")
    print()
    
    # 列出资产
    assets = dao.list_format_template_assets(template_id)
    assert len(assets) > 0, "资产列表为空"
    
    print(f"   资产列表: {len(assets)} 个资产")
    for a in assets:
        print(f"   - {a['asset_type']} ({a['variant']})")
    print()
    
    # ==================== 6. 列出所有模板 ====================
    print("📝 测试 6: 列出格式模板")
    print("-" * 60)
    
    templates = dao.list_format_templates(owner_id="test_user_001")
    found = False
    for t in templates:
        if t["id"] == template_id:
            found = True
            break
    
    assert found, "创建的模板未在列表中找到"
    
    print(f"✅ 列表查询成功")
    print(f"   总数: {len(templates)} 个模板")
    print(f"   找到测试模板: {template_id}")
    print()
    
    # ==================== 7. 绑定到项目目录 ====================
    print("📝 测试 7: 绑定格式模板到项目目录")
    print("-" * 60)
    
    # 创建测试项目
    project = dao.create_project(
        name=f"测试项目_{uuid.uuid4().hex[:8]}",
        description="格式模板测试项目",
        owner_id="test_user_001"
    )
    project_id = project["id"]
    
    print(f"   创建测试项目: {project_id}")
    
    # 创建目录根节点
    root_node = dao._fetchone(
        """
        INSERT INTO tender_directory_nodes
          (id, project_id, parent_id, order_no, level, numbering, title, is_required, source, meta_json)
        VALUES
          (%s, %s, NULL, 1, 1, '1', '根节点', true, 'manual', '{}'::jsonb)
        RETURNING *
        """,
        (f"tdn_{uuid.uuid4().hex}", project_id)
    )
    
    print(f"   创建根节点: {root_node['id']}")
    
    # 绑定模板
    updated_root = dao.set_directory_root_format_template(
        project_id=project_id,
        template_id=template_id
    )
    
    assert updated_root is not None, "根节点未找到"
    
    # 验证绑定
    bound_template_id = dao.get_directory_root_format_template(project_id)
    assert bound_template_id == template_id, "模板ID不匹配"
    
    print(f"✅ 绑定成功")
    print(f"   项目ID: {project_id}")
    print(f"   模板ID: {template_id}")
    print(f"   根节点ID: {updated_root['id']}")
    print()
    
    # ==================== 8. 更新元数据 ====================
    print("📝 测试 8: 更新模板元数据")
    print("-" * 60)
    
    updated = dao.update_format_template_meta(
        template_id=template_id,
        name="更新后的模板名称",
        description="更新后的描述",
        is_public=True
    )
    
    assert updated["name"] == "更新后的模板名称", "名称未更新"
    assert updated["description"] == "更新后的描述", "描述未更新"
    assert updated["is_public"] is True, "is_public 未更新"
    
    print(f"✅ 更新成功")
    print(f"   新名称: {updated['name']}")
    print(f"   新描述: {updated['description']}")
    print(f"   公开状态: {updated['is_public']}")
    print()
    
    # ==================== 9. 清理测试数据 ====================
    print("📝 测试 9: 清理测试数据")
    print("-" * 60)
    
    # 删除项目（会级联删除目录节点）
    dao.delete_project(project_id)
    print(f"   删除测试项目: {project_id}")
    
    # 删除资产
    dao.delete_format_template_assets(template_id)
    assets_after = dao.list_format_template_assets(template_id)
    assert len(assets_after) == 0, "资产未完全删除"
    print(f"   删除模板资产: {len(assets)} 个")
    
    # 删除模板
    dao.delete_format_template(template_id)
    deleted_template = dao.get_format_template(template_id)
    assert deleted_template is None, "模板未删除"
    
    print(f"✅ 清理完成")
    print(f"   删除模板: {template_id}")
    print()
    
    # ==================== 总结 ====================
    print("=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)
    print()
    print("验证项目:")
    print("  ✅ 创建格式模板")
    print("  ✅ 设置存储路径和 SHA256")
    print("  ✅ 设置分析结果")
    print("  ✅ 设置解析结果")
    print("  ✅ 创建和列出模板资产")
    print("  ✅ 列出格式模板")
    print("  ✅ 绑定格式模板到项目目录")
    print("  ✅ 更新模板元数据")
    print("  ✅ 清理测试数据")
    print()


def verify_constraints(pool: ConnectionPool):
    """验证数据完整性约束"""
    print("=" * 60)
    print("数据完整性约束验证")
    print("=" * 60)
    print()
    
    dao = TenderDAO(pool)
    
    # ==================== 1. 分析状态约束 ====================
    print("📝 测试 1: 分析状态约束")
    print("-" * 60)
    
    try:
        # 创建测试模板
        test_template = dao.create_format_template(
            name=f"约束测试_{uuid.uuid4().hex[:8]}",
            description="约束测试",
            style_config={},
            owner_id="test_user_001",
            is_public=False
        )
        template_id = test_template["id"]
        
        # 尝试设置无效状态
        dao._execute(
            "UPDATE format_templates SET analysis_status='INVALID_STATUS' WHERE id=%s",
            (template_id,)
        )
        
        print("❌ 约束未生效：允许了无效的 analysis_status")
        
    except Exception as e:
        if "chk_format_templates_analysis_status" in str(e) or "violates check constraint" in str(e):
            print(f"✅ 约束生效：拒绝了无效的 analysis_status")
        else:
            print(f"⚠️  其他错误: {e}")
    
    print()
    
    # 清理
    try:
        dao.delete_format_template(template_id)
    except:
        pass


def main():
    """主函数"""
    try:
        pool = get_pool()
        
        # 基本功能验证
        verify_format_templates(pool)
        
        # 约束验证
        verify_constraints(pool)
        
        print("🎉 格式模板数据库验证完成！")
        return 0
        
    except AssertionError as e:
        print(f"❌ 断言失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

