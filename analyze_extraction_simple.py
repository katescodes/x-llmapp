#!/usr/bin/env python3
"""
简化版分析脚本：查询历史提取结果和原始文档
"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def main():
    from app.services.db.postgres import _get_pool
    
    project_id = "tp_f379d279606a4ff89a6aa2cfabc0a6c5"
    project_name = "储能技术公司金坛、刘庄储气库控制系统国产化升级改造工程施工项目"
    
    print(f"\n{'='*100}")
    print(f"📋 招标要求提取分析")
    print(f"{'='*100}")
    print(f"项目ID: {project_id}")
    print(f"项目名称: {project_name}")
    print(f"{'='*100}\n")
    
    pool = _get_pool()
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            # 1. 查询历史提取记录
            print("🔍 查询历史提取记录...")
            cur.execute("""
                SELECT run_id, status, progress, created_at, updated_at, result_json
                FROM tender_analysis_runs
                WHERE project_id = %s AND run_type = 'extract_requirements_v2'
                ORDER BY created_at DESC
                LIMIT 5
            """, (project_id,))
            
            runs = cur.fetchall()
            
            if runs:
                print(f"找到 {len(runs)} 条历史记录\n")
                
                for i, run in enumerate(runs, 1):
                    print(f"记录 {i}:")
                    print(f"  Run ID: {run['run_id']}")
                    print(f"  状态: {run['status']}")
                    print(f"  进度: {run['progress']}")
                    print(f"  创建时间: {run['created_at']}")
                    print(f"  更新时间: {run['updated_at']}")
                    
                    if run['result_json'] and run['status'] == 'success':
                        result = run['result_json']
                        requirements = result.get('requirements', [])
                        print(f"  提取数量: {len(requirements)} 条")
                        
                        veto_count = sum(1 for req in requirements if req.get('is_veto'))
                        print(f"    - 废标项: {veto_count} 条")
                        print(f"    - 其他要求: {len(requirements) - veto_count} 条")
                        
                        # 保存最新的成功结果
                        if i == 1:
                            latest_result = result
                            latest_requirements = requirements
                    print()
                
                # 分析最新的提取结果
                if 'latest_result' in locals():
                    print(f"{'='*100}")
                    print(f"📊 最新提取结果详细分析")
                    print(f"{'='*100}\n")
                    
                    # 按类别统计
                    category_stats = {}
                    for req in latest_requirements:
                        cat = req.get('category', '未分类')
                        category_stats[cat] = category_stats.get(cat, 0) + 1
                    
                    print(f"按类别统计：")
                    for cat, count in sorted(category_stats.items(), key=lambda x: x[1], reverse=True):
                        print(f"  - {cat}: {count} 条")
                    
                    # 按consequence统计
                    consequence_stats = {}
                    for req in latest_requirements:
                        cons = req.get('consequence', 'null')
                        if cons and cons != 'null':
                            consequence_stats[cons] = consequence_stats.get(cons, 0) + 1
                    
                    if consequence_stats:
                        print(f"\n按后果统计：")
                        for cons, count in sorted(consequence_stats.items(), key=lambda x: x[1], reverse=True):
                            print(f"  - {cons}: {count} 条")
                    
                    # 按source_hint统计
                    source_stats = {}
                    for req in latest_requirements:
                        source = req.get('source_hint', '未知')
                        if source:
                            source_stats[source] = source_stats.get(source, 0) + 1
                    
                    if source_stats:
                        print(f"\n按来源章节统计（top 10）：")
                        for source, count in sorted(source_stats.items(), key=lambda x: x[1], reverse=True)[:10]:
                            print(f"  - {source}: {count} 条")
                    
                    # 显示前30条提取结果
                    print(f"\n{'='*100}")
                    print(f"📝 提取结果示例（前30条）")
                    print(f"{'='*100}\n")
                    
                    for i, req in enumerate(latest_requirements[:30], 1):
                        veto_tag = "🚫" if req.get('is_veto') else "  "
                        category = req.get('category', '未分类')
                        title = req.get('title', '')
                        consequence = req.get('consequence', '')
                        cons_tag = f"[{consequence}]" if consequence and consequence != 'null' else ""
                        source = req.get('source_hint', '')
                        
                        print(f"{i:2d}. {veto_tag} [{category:8s}] {cons_tag:8s} {title}")
                        if source:
                            print(f"    来源: {source}")
                        
                        # 显示requirement_text的前150字
                        req_text = req.get('requirement_text', '')
                        if len(req_text) > 150:
                            req_text = req_text[:150] + "..."
                        print(f"    {req_text}")
                        print()
                    
                    if len(latest_requirements) > 30:
                        print(f"... 还有 {len(latest_requirements) - 30} 条未显示\n")
                    
                    # 保存完整结果
                    output_file = "/aidata/x-llmapp1/latest_extraction_result.json"
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(latest_result, f, ensure_ascii=False, indent=2)
                    print(f"💾 完整结果已保存到：{output_file}\n")
            else:
                print("未找到历史提取记录\n")
            
            # 2. 分析原始文档
            print(f"{'='*100}")
            print(f"📄 原始招标文档分析")
            print(f"{'='*100}\n")
            
            # 查询文档chunks
            cur.execute("""
                SELECT chunk_id, chunk_index, content, doc_type
                FROM tender_document_chunks
                WHERE project_id = %s AND doc_type = 'tender'
                ORDER BY chunk_index
            """, (project_id,))
            
            chunks = cur.fetchall()
            print(f"招标文档总chunks数：{len(chunks)}\n")
            
            # 扫描关键内容
            print("🔍 扫描关键内容...")
            
            keywords_stats = {
                '废标': 0,
                '否决': 0,
                '无效': 0,
                '取消资格': 0,
                '不得': 0,
                '禁止': 0,
                '必须': 0,
                '应当': 0,
                '投标人须知': 0,
                '评审办法': 0,
                '评分标准': 0,
                '资格条件': 0,
                '技术要求': 0,
                '采购需求': 0,
                '▲': 0,
                '★': 0,
                '*': 0,
                '投标保证金': 0,
                '最高限价': 0,
                '控制价': 0,
            }
            
            for chunk in chunks:
                content = chunk['content']
                for keyword in keywords_stats:
                    if keyword in content:
                        keywords_stats[keyword] += 1
            
            print(f"\n关键词分布（在多少个chunks中出现）：")
            for keyword, count in sorted(keywords_stats.items(), key=lambda x: x[1], reverse=True):
                if count > 0:
                    print(f"  - '{keyword}': {count} 个chunks")
            
            # 检查表格
            print(f"\n📋 表格分析...")
            table_indicators = ['|', '┃', '│', '├', '┬', '─', '┌', '└', '┐', '┘']
            table_chunks = []
            
            for chunk in chunks:
                content = chunk['content']
                # 检查是否包含表格标记
                indicator_count = sum(1 for indicator in table_indicators if indicator in content)
                if indicator_count >= 3:  # 至少包含3种表格标记
                    table_chunks.append(chunk)
            
            print(f"疑似表格chunks数：{len(table_chunks)}")
            
            if table_chunks:
                print(f"\n表格内容示例（前2个）：")
                for i, chunk in enumerate(table_chunks[:2], 1):
                    print(f"\n{'='*80}")
                    print(f"表格示例 {i} (chunk_index: {chunk['chunk_index']})")
                    print(f"{'='*80}")
                    content = chunk['content']
                    # 显示前800字符
                    display_content = content[:800] + "..." if len(content) > 800 else content
                    print(display_content)
            
            # 查找评分标准相关内容
            print(f"\n{'='*100}")
            print(f"📊 评分标准相关内容分析")
            print(f"{'='*100}\n")
            
            scoring_chunks = []
            for chunk in chunks:
                content = chunk['content']
                if '评分' in content or '打分' in content or '计分' in content or '分值' in content:
                    scoring_chunks.append(chunk)
            
            print(f"包含评分相关内容的chunks：{len(scoring_chunks)}")
            
            if scoring_chunks:
                print(f"\n评分内容示例（前2个）：")
                for i, chunk in enumerate(scoring_chunks[:2], 1):
                    print(f"\n{'='*80}")
                    print(f"评分示例 {i} (chunk_index: {chunk['chunk_index']})")
                    print(f"{'='*80}")
                    content = chunk['content']
                    # 显示前600字符
                    display_content = content[:600] + "..." if len(content) > 600 else content
                    print(display_content)
            
            # 3. 对比分析
            if 'latest_requirements' in locals():
                print(f"\n{'='*100}")
                print(f"📊 对比分析")
                print(f"{'='*100}\n")
                
                print(f"1. 提取数量对比：")
                print(f"   - 实际提取：{len(latest_requirements)} 条")
                print(f"   - 预期范围（V3.4）：110-230条")
                
                if len(latest_requirements) < 100:
                    print(f"   ⚠️ 警告：提取数量远低于预期！")
                    print(f"   建议：重新检查提取逻辑和Prompt")
                elif len(latest_requirements) < 110:
                    print(f"   ⚠️ 注意：提取数量略低于预期下限")
                elif len(latest_requirements) > 230:
                    print(f"   ✅ 提取数量超过预期，非常全面！")
                else:
                    print(f"   ✅ 提取数量在预期范围内")
                
                print(f"\n2. 废标项对比：")
                veto_count = sum(1 for req in latest_requirements if req.get('is_veto'))
                print(f"   - 实际提取：{veto_count} 条")
                print(f"   - 预期范围：20-40条")
                print(f"   - 文档中'废标'关键词出现：{keywords_stats.get('废标', 0)} 个chunks")
                print(f"   - 文档中'否决'关键词出现：{keywords_stats.get('否决', 0)} 个chunks")
                
                if veto_count < 20:
                    print(f"   ⚠️ 警告：废标项可能有遗漏")
                else:
                    print(f"   ✅ 废标项数量合理")
                
                print(f"\n3. 覆盖率分析：")
                print(f"   - 文档总chunks：{len(chunks)}")
                print(f"   - 送入LLM（V3.4设置）：800 chunks")
                coverage = min(800 / len(chunks) * 100, 100) if len(chunks) > 0 else 0
                print(f"   - 理论覆盖率：{coverage:.1f}%")
                
                print(f"\n4. 表格处理分析：")
                print(f"   - 文档中疑似表格chunks：{len(table_chunks)}")
                # 估算表格行数（粗略估计）
                estimated_table_rows = len(table_chunks) * 5  # 假设每个chunk平均5行
                print(f"   - 估算表格总行数：约{estimated_table_rows}行")
                print(f"   - 如果表格内容较多，提取结果中应包含相应数量的逐行提取项")
                
                print(f"\n5. 评分标准分析：")
                print(f"   - 文档中包含评分内容的chunks：{len(scoring_chunks)}")
                scoring_requirements = [req for req in latest_requirements if req.get('category') == '评分标准']
                print(f"   - 提取的评分标准相关要求：{len(scoring_requirements)} 条")
                print(f"   - 预期范围：30-60条（含细分项）")
                
                if len(scoring_requirements) < 30:
                    print(f"   ⚠️ 警告：评分标准可能提取不够细致")
                else:
                    print(f"   ✅ 评分标准提取较为全面")
            
            print(f"\n{'='*100}")
            print(f"💡 总结与建议")
            print(f"{'='*100}\n")
            
            if 'latest_requirements' in locals():
                print(f"提取结果总览：")
                print(f"  - 总提取数：{len(latest_requirements)} 条")
                print(f"  - 废标项：{veto_count} 条")
                print(f"  - 其他要求：{len(latest_requirements) - veto_count} 条")
                print()
                
                if len(latest_requirements) < 110:
                    print(f"问题诊断：")
                    print(f"  1. 提取数量低于预期，可能原因：")
                    print(f"     - LLM可能合并了多个相似要求")
                    print(f"     - 表格内容未完全逐行提取")
                    print(f"     - 复杂条款未充分拆分")
                    print(f"  2. 建议检查：")
                    print(f"     - 查看latest_extraction_result.json中的具体内容")
                    print(f"     - 对比原文表格，确认是否逐行提取")
                    print(f"     - 检查评分标准是否细化到二级项")
                else:
                    print(f"总体评价：✅ 提取效果良好")
                    print(f"  - 数量在合理范围内")
                    print(f"  - 建议抽查部分内容确认质量")
            else:
                print(f"未找到历史提取记录，建议执行新的提取任务")
            
    return 0


if __name__ == "__main__":
    sys.exit(main())

