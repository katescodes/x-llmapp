#!/usr/bin/env python3
"""
测试模板分析功能

使用方式：
    python scripts/test_template_analysis.py
"""
import os
import sys
import requests
from pathlib import Path

# 配置
API_BASE = os.getenv("API_BASE", "http://localhost:9001")
USERNAME = os.getenv("TEST_USERNAME", "admin@example.com")
PASSWORD = os.getenv("TEST_PASSWORD", "admin123")


def login():
    """登录获取 token"""
    print("登录中...")
    try:
        resp = requests.post(
            f"{API_BASE}/api/auth/login",
            json={"username": USERNAME, "password": PASSWORD},
            timeout=10
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]
        print(f"✓ 登录成功")
        return token
    except Exception as e:
        print(f"✗ 登录失败: {e}")
        return None


def check_api_available():
    """检查API是否可用"""
    print("\n检查API可用性...")
    try:
        resp = requests.get(f"{API_BASE}/docs", timeout=5)
        if resp.status_code == 200:
            print("✓ API 服务正常")
            return True
        else:
            print(f"✗ API 返回状态码: {resp.status_code}")
            return False
    except Exception as e:
        print(f"✗ API 不可用: {e}")
        return False


def list_format_templates(token):
    """列出所有格式模板"""
    print("\n获取格式模板列表...")
    try:
        resp = requests.get(
            f"{API_BASE}/api/apps/tender/format-templates",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        resp.raise_for_status()
        templates = resp.json()
        print(f"✓ 找到 {len(templates)} 个格式模板")
        
        for t in templates:
            print(f"  - {t.get('name')} (ID: {t.get('id')})")
            analysis_json = t.get('analysis_json')
            if analysis_json:
                print(f"    ✓ 已分析")
            else:
                print(f"    ✗ 未分析")
        
        return templates
    except Exception as e:
        print(f"✗ 获取模板列表失败: {e}")
        return []


def test_upload_template(token):
    """测试上传并分析模板"""
    print("\n测试上传并分析模板...")
    print("⚠️  需要准备一个测试模板文件（.docx）")
    print("提示：在模板中添加 [[CONTENT]] 标记以获得最佳效果")
    
    # 这里只是演示，实际需要用户提供文件
    print("\n如果要测试上传功能，请使用以下命令：")
    print(f"""
curl -X POST "{API_BASE}/api/apps/tender/templates/upload-and-analyze" \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -F "name=测试模板" \\
  -F "file=@/path/to/template.docx"
    """)


def test_get_analysis(token, template_id):
    """测试获取模板分析结果"""
    print(f"\n获取模板分析: {template_id}")
    try:
        resp = requests.get(
            f"{API_BASE}/api/apps/tender/templates/{template_id}/analysis",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        resp.raise_for_status()
        result = resp.json()
        
        print("✓ 分析结果：")
        summary = result.get("analysis_summary", {})
        print(f"  - 模板名称: {result.get('template_name')}")
        print(f"  - 置信度: {summary.get('confidence', 0):.2f}")
        print(f"  - Anchors数量: {summary.get('anchorsCount', 0)}")
        print(f"  - 有内容标记: {summary.get('hasContentMarker', False)}")
        print(f"  - 保留blocks: {summary.get('keepBlocksCount', 0)}")
        print(f"  - 删除blocks: {summary.get('deleteBlocksCount', 0)}")
        
        warnings = summary.get('warnings', [])
        if warnings:
            print(f"  ⚠️  警告:")
            for w in warnings:
                print(f"    - {w}")
        
        return result
    except requests.exceptions.HTTPException as e:
        if e.response.status_code == 404:
            print("✗ 模板未分析或不存在")
        else:
            print(f"✗ 获取分析失败: {e}")
        return None
    except Exception as e:
        print(f"✗ 获取分析失败: {e}")
        return None


def main():
    """主函数"""
    print("=" * 60)
    print("模板分析功能测试")
    print("=" * 60)
    
    # 1. 检查API
    if not check_api_available():
        print("\n❌ API 服务不可用，请检查后端是否启动")
        sys.exit(1)
    
    # 2. 登录
    token = login()
    if not token:
        print("\n❌ 登录失败")
        sys.exit(1)
    
    # 3. 列出模板
    templates = list_format_templates(token)
    
    # 4. 测试获取分析（如果有已分析的模板）
    analyzed_templates = [t for t in templates if t.get('analysis_json')]
    if analyzed_templates:
        print(f"\n找到 {len(analyzed_templates)} 个已分析的模板")
        template = analyzed_templates[0]
        test_get_analysis(token, template['id'])
    else:
        print("\n⚠️  没有已分析的模板")
    
    # 5. 提示如何上传新模板
    test_upload_template(token)
    
    print("\n" + "=" * 60)
    print("✓ 测试完成")
    print("=" * 60)
    print("\n📝 功能说明：")
    print("1. 上传模板：POST /api/apps/tender/templates/upload-and-analyze")
    print("2. 查看分析：GET /api/apps/tender/templates/{id}/analysis")
    print("3. 渲染目录：POST /api/apps/tender/templates/render-outline")
    print("\n💡 前端访问：")
    print(f"   Swagger UI: {API_BASE}/docs")
    print(f"   前端应用: http://localhost:6173")
    print("\n📖 详细文档：")
    print("   TEMPLATE_ANALYSIS_AND_RENDERING_GUIDE.md")


if __name__ == "__main__":
    main()

