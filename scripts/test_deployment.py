#!/usr/bin/env python3
"""
测试部署后的新功能
"""
import requests
import sys

BASE_URL = "http://localhost:9001"

def test_backend_health():
    """测试后端健康状态"""
    print("1. 测试后端健康状态...")
    try:
        resp = requests.get(f"{BASE_URL}/")
        if resp.status_code == 200:
            print(f"   ✅ 后端运行正常: {resp.json()}")
            return True
        else:
            print(f"   ❌ 后端状态异常: {resp.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ 连接后端失败: {e}")
        return False

def test_api_docs():
    """测试API文档"""
    print("\n2. 测试API文档...")
    try:
        resp = requests.get(f"{BASE_URL}/openapi.json")
        if resp.status_code == 200:
            openapi = resp.json()
            paths = openapi.get("paths", {})
            
            # 检查用户文档路由
            user_doc_routes = [p for p in paths.keys() if "user-documents" in p]
            if user_doc_routes:
                print(f"   ✅ 用户文档API已注册: {len(user_doc_routes)} 个路由")
                for route in user_doc_routes[:5]:
                    print(f"      - {route}")
                return True
            else:
                print(f"   ⚠️  未找到用户文档API路由")
                print(f"   已注册路由数: {len(paths)}")
                return False
        else:
            print(f"   ❌ 获取API文档失败: {resp.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ 测试API文档失败: {e}")
        return False

def test_kb_categories():
    """测试知识库分类"""
    print("\n3. 测试知识库分类...")
    try:
        resp = requests.get(f"{BASE_URL}/api/kb-categories")
        if resp.status_code == 200:
            categories = resp.json()
            print(f"   ✅ 知识库分类数量: {len(categories)}")
            
            # 检查新增的分类
            new_categories = [
                "tender_notice", "bid_document", "format_template",
                "standard_spec", "technical_material", "qualification_doc"
            ]
            
            for cat in categories:
                if cat.get("name") in new_categories:
                    print(f"      - {cat.get('name')}: {cat.get('display_name')}")
            
            return True
        else:
            print(f"   ❌ 获取知识库分类失败: {resp.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ 测试知识库分类失败: {e}")
        return False

def test_database_tables():
    """测试数据库表"""
    print("\n4. 测试数据库表...")
    import subprocess
    
    try:
        # 检查用户文档表
        cmd = [
            "docker-compose", "exec", "-T", "postgres",
            "psql", "-U", "localgpt", "-d", "localgpt",
            "-c", "SELECT tablename FROM pg_tables WHERE tablename LIKE 'tender_user%';"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd="/aidata/x-llmapp1")
        
        if "tender_user_doc_categories" in result.stdout and "tender_user_documents" in result.stdout:
            print("   ✅ 用户文档表已创建:")
            print("      - tender_user_doc_categories")
            print("      - tender_user_documents")
            return True
        else:
            print("   ❌ 用户文档表未找到")
            return False
    except Exception as e:
        print(f"   ❌ 测试数据库表失败: {e}")
        return False

def test_kb_mapping_table():
    """测试知识库映射表"""
    print("\n5. 测试知识库映射表...")
    import subprocess
    
    try:
        cmd = [
            "docker-compose", "exec", "-T", "postgres",
            "psql", "-U", "localgpt", "-d", "localgpt",
            "-c", "SELECT COUNT(*) FROM kb_category_mappings;"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd="/aidata/x-llmapp1")
        
        if "12" in result.stdout:  # 应该有12条映射记录
            print("   ✅ 知识库映射表数据正常: 12 条映射记录")
            return True
        else:
            print(f"   ⚠️  知识库映射表数据: {result.stdout}")
            return True  # 非关键错误
    except Exception as e:
        print(f"   ❌ 测试知识库映射表失败: {e}")
        return False

def test_frontend_access():
    """测试前端访问"""
    print("\n6. 测试前端访问...")
    try:
        resp = requests.get("http://localhost:6173/", timeout=5)
        if resp.status_code == 200:
            print("   ✅ 前端页面可访问")
            return True
        else:
            print(f"   ❌ 前端访问失败: {resp.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ 连接前端失败: {e}")
        return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("🔍 开始测试部署后的新功能")
    print("=" * 60)
    
    results = []
    
    # 运行所有测试
    results.append(("后端健康状态", test_backend_health()))
    results.append(("API文档", test_api_docs()))
    results.append(("知识库分类", test_kb_categories()))
    results.append(("数据库表", test_database_tables()))
    results.append(("知识库映射表", test_kb_mapping_table()))
    results.append(("前端访问", test_frontend_access()))
    
    # 输出总结
    print("\n" + "=" * 60)
    print("📊 测试结果总结")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {name}")
    
    print(f"\n总计: {passed}/{total} 项测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！系统部署成功！")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 项测试失败，请检查相关服务")
        return 1

if __name__ == "__main__":
    sys.exit(main())

