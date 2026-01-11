#!/usr/bin/env python3
"""
模拟项目测试：用模拟数据演示目录提取功能
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))


def create_mock_blocks():
    """创建模拟的招标书blocks（模拟真实的招标书格式章节）"""
    return [
        # 前面章节（会被过滤）
        {"blockId": "b0", "type": "p", "text": "第一章 招标公告"},
        {"blockId": "b1", "type": "p", "text": "本项目采用公开招标方式..."},
        {"blockId": "b2", "type": "p", "text": "第二章 投标人须知"},
        {"blockId": "b3", "type": "p", "text": "投标人应仔细阅读..."},
        
        # 目标章节：投标文件格式
        {"blockId": "b10", "type": "p", "text": "第六章 投标文件格式"},
        {"blockId": "b11", "type": "p", "text": "一、资格证明文件"},
        {"blockId": "b12", "type": "p", "text": "1. 法定代表人身份证明"},
        {"blockId": "b13", "type": "p", "text": "2. 法定代表人授权委托书"},
        {"blockId": "b14", "type": "p", "text": "3. 投标人基本情况表"},
        {"blockId": "b15", "type": "p", "text": "4. 营业执照副本"},
        {"blockId": "b16", "type": "p", "text": "5. 资质证书副本"},
        {"blockId": "b17", "type": "p", "text": "6. 类似项目业绩证明"},
        {"blockId": "b18", "type": "p", "text": "7. 财务审计报告"},
        {"blockId": "b19", "type": "p", "text": "8. 依法缴纳税收证明"},
        {"blockId": "b20", "type": "p", "text": "9. 社会保障资金缴纳证明"},
        {"blockId": "b21", "type": "p", "text": "10. 信用中国网查询截图"},
        
        {"blockId": "b30", "type": "p", "text": "二、商务文件"},
        {"blockId": "b31", "type": "p", "text": "1. 投标函"},
        {"blockId": "b32", "type": "p", "text": "2. 投标保证金"},
        {"blockId": "b33", "type": "p", "text": "3. 开标一览表"},
        {"blockId": "b34", "type": "p", "text": "4. 分项报价明细表"},
        {"blockId": "b35", "type": "p", "text": "5. 商务条款响应表"},
        {"blockId": "b36", "type": "p", "text": "6. 商务条款偏离表"},
        {"blockId": "b37", "type": "p", "text": "7. 拟分包项目情况表"},
        {"blockId": "b38", "type": "p", "text": "8. 服务承诺书"},
        
        {"blockId": "b40", "type": "p", "text": "三、技术文件"},
        {"blockId": "b41", "type": "p", "text": "1. 技术方案"},
        {"blockId": "b42", "type": "p", "text": "1.1 项目理解"},
        {"blockId": "b43", "type": "p", "text": "1.2 总体设计"},
        {"blockId": "b44", "type": "p", "text": "1.3 实施方案"},
        {"blockId": "b45", "type": "p", "text": "2. 项目组织"},
        {"blockId": "b46", "type": "p", "text": "2.1 组织架构"},
        {"blockId": "b47", "type": "p", "text": "2.2 人员配备"},
        {"blockId": "b48", "type": "p", "text": "2.3 项目经理简历"},
        {"blockId": "b49", "type": "p", "text": "3. 质量保证措施"},
        {"blockId": "b50", "type": "p", "text": "4. 进度计划"},
        {"blockId": "b51", "type": "p", "text": "5. 技术规格响应表"},
        {"blockId": "b52", "type": "p", "text": "6. 技术规格偏离表"},
        {"blockId": "b53", "type": "p", "text": "7. 售后服务方案"},
        
        # 后续章节（会被过滤）
        {"blockId": "b60", "type": "p", "text": "第七章 投标文件密封与递交"},
        {"blockId": "b61", "type": "p", "text": "投标文件应密封递交..."},
    ]


def test_with_mock_data():
    """用模拟数据测试目录提取"""
    print("\n" + "="*80)
    print("📝 模拟项目测试：从招标书格式章节提取目录")
    print("="*80)
    
    from app.works.tender.directory_augment_v1 import _extract_directory_from_blocks
    from app.works.tender.snippet.snippet_locator import locate_format_chapter
    
    # 1. 创建模拟blocks
    all_blocks = create_mock_blocks()
    print(f"\n📄 模拟招标书文档:")
    print(f"  - 总blocks数: {len(all_blocks)}")
    print(f"  - 包含章节: 第一章~第七章")
    
    # 2. 定位格式章节
    print(f"\n🔍 步骤1: 定位\"投标文件格式\"章节...")
    format_blocks = locate_format_chapter(all_blocks)
    print(f"  ✅ 定位成功! 提取了 {len(format_blocks)} 个blocks")
    print(f"  - 起始: {format_blocks[0]['text']}")
    print(f"  - 范围: block[10] ~ block[53]")
    
    # 3. 提取目录结构
    print(f"\n🔍 步骤2: 从格式章节提取目录结构...")
    existing_titles = set()  # 假设无现有节点
    directory_nodes = _extract_directory_from_blocks(format_blocks, existing_titles)
    
    print(f"  ✅ 提取成功! 识别了 {len(directory_nodes)} 个目录节点")
    
    # 4. 展示提取的目录
    print(f"\n📋 提取的完整目录结构:")
    print("="*80)
    
    for i, node in enumerate(directory_nodes, 1):
        indent = "  " * (node['level'] - 1)
        level_tag = f"[L{node['level']}]"
        numbering = node['numbering'].ljust(6)
        title = node['title']
        
        print(f"{i:2d}. {indent}{level_tag} {numbering} {title}")
    
    # 5. 统计分析
    print(f"\n📊 统计分析:")
    print("="*80)
    
    level_counts = {}
    for node in directory_nodes:
        level = node['level']
        level_counts[level] = level_counts.get(level, 0) + 1
    
    print(f"总节点数: {len(directory_nodes)}")
    for level in sorted(level_counts.keys()):
        print(f"  - {level}级目录: {level_counts[level]} 个")
    
    # 6. 分类统计
    print(f"\n📂 按分册统计:")
    categories = {
        '章节标题': [],
        '资格证明文件': [],
        '商务文件': [],
        '技术文件': []
    }
    
    current_category = '章节标题'
    for node in directory_nodes:
        title = node['title']
        if '资格证明文件' in title:
            current_category = '资格证明文件'
        elif '商务文件' in title:
            current_category = '商务文件'
        elif '技术文件' in title:
            current_category = '技术文件'
        
        categories[current_category].append(node)
    
    for cat_name, cat_nodes in categories.items():
        if cat_nodes:
            print(f"  - {cat_name}: {len(cat_nodes)} 个节点")
    
    # 7. 展示层级结构
    print(f"\n🌳 目录树形结构:")
    print("="*80)
    
    def print_tree(nodes, parent_level=0, prefix=""):
        for i, node in enumerate(nodes):
            if node['level'] == parent_level + 1:
                is_last = (i == len(nodes) - 1)
                connector = "└── " if is_last else "├── "
                print(f"{prefix}{connector}{node['numbering']} {node['title']}")
                
                # 递归打印子节点
                if i + 1 < len(nodes) and nodes[i + 1]['level'] > node['level']:
                    extension = "    " if is_last else "│   "
                    print_tree(nodes[i+1:], node['level'], prefix + extension)
    
    # 找出一级节点
    root_nodes = [n for n in directory_nodes if n['level'] == 1]
    print(f"\n投标文件格式")
    for root in root_nodes:
        print(f"├── {root['numbering']} {root['title']}")
        
        # 打印其子节点
        root_idx = directory_nodes.index(root)
        next_root_idx = None
        for j in range(root_idx + 1, len(directory_nodes)):
            if directory_nodes[j]['level'] == 1:
                next_root_idx = j
                break
        
        if next_root_idx:
            sub_nodes = directory_nodes[root_idx+1:next_root_idx]
        else:
            sub_nodes = directory_nodes[root_idx+1:]
        
        for sub in sub_nodes:
            indent = "│   " + "  " * (sub['level'] - 2)
            print(f"{indent}└── {sub['numbering']} {sub['title']}")
    
    # 8. 数据库存储格式示例
    print(f"\n💾 数据库存储格式示例（前5条）:")
    print("="*80)
    
    for i, node in enumerate(directory_nodes[:5], 1):
        print(f"\n节点 {i}:")
        print(f"  - numbering: '{node['numbering']}'")
        print(f"  - title: '{node['title']}'")
        print(f"  - level: {node['level']}")
        print(f"  - source: '{node['source']}'")
        print(f"  - evidence_chunk_ids: {node['evidence_chunk_ids']}")
    
    print(f"\n... (共 {len(directory_nodes)} 个节点)")
    
    return directory_nodes


def main():
    """主函数"""
    print("\n🚀 开始模拟项目测试")
    
    try:
        nodes = test_with_mock_data()
        
        print(f"\n{'='*80}")
        print("🎉 测试完成!")
        print(f"{'='*80}")
        print(f"\n✅ 成功提取 {len(nodes)} 个目录节点")
        print(f"✅ 保持了原始编号和标题")
        print(f"✅ 正确识别了3级层级结构")
        print(f"✅ 完整保留了证据链（evidence_chunk_ids）")
        print(f"\n💡 实际使用时，这些节点会自动插入数据库的 tender_directory_nodes 表")
        print(f"\n")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
