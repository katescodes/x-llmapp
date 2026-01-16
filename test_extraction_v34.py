#!/usr/bin/env python3
"""
测试V3.4版本的招标要求提取效果
项目：储能技术公司金坛、刘庄储气库控制系统国产化升级改造工程施工项目
"""
import sys
import os
import asyncio
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def main():
    from app.services.db.postgres import _get_pool
    from app.works.tender.extract_v2_service import ExtractV2Service
    from app.llm.llm_orchestrator import LLMOrchestrator
    
    # 项目信息
    project_id = "tp_f379d279606a4ff89a6aa2cfabc0a6c5"
    project_name = "储能技术公司金坛、刘庄储气库控制系统国产化升级改造工程施工项目"
    
    print(f"\n{'='*100}")
    print(f"📋 招标要求提取测试（V3.4版本）")
    print(f"{'='*100}")
    print(f"项目ID: {project_id}")
    print(f"项目名称: {project_name}")
    print(f"{'='*100}\n")
    
    # 初始化服务
    pool = _get_pool()
    llm_orchestrator = LLMOrchestrator()
    
    extract_svc = ExtractV2Service(
        pool=pool,
        llm_orchestrator=llm_orchestrator
    )
    
    # 执行提取
    print("🚀 开始提取招标要求...")
    print("-" * 100)
    
    try:
        result = await extract_svc.extract_requirements_v2(
            project_id=project_id,
            model_id="gpt-4o-mini",  # 使用gpt-4o-mini模型
            checklist_template="engineering",
            run_id=None
        )
        
        print(f"\n✅ 提取完成！")
        print(f"\n{'='*100}")
        print(f"📊 提取统计")
        print(f"{'='*100}")
        
        # 统计信息
        total_count = len(result.get('requirements', []))
        veto_count = sum(1 for req in result.get('requirements', []) if req.get('is_veto'))
        non_veto_count = total_count - veto_count
        
        print(f"总计提取：{total_count} 条")
        print(f"  - 废标项：{veto_count} 条")
        print(f"  - 其他要求：{non_veto_count} 条")
        
        # 按category统计
        category_stats = {}
        for req in result.get('requirements', []):
            cat = req.get('category', '未分类')
            category_stats[cat] = category_stats.get(cat, 0) + 1
        
        print(f"\n按类别统计：")
        for cat, count in sorted(category_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {cat}: {count} 条")
        
        # 按consequence统计
        consequence_stats = {}
        for req in result.get('requirements', []):
            cons = req.get('consequence', 'null')
            if cons:
                consequence_stats[cons] = consequence_stats.get(cons, 0) + 1
        
        if consequence_stats:
            print(f"\n按后果统计：")
            for cons, count in sorted(consequence_stats.items(), key=lambda x: x[1], reverse=True):
                print(f"  - {cons}: {count} 条")
        
        # 显示部分提取结果
        print(f"\n{'='*100}")
        print(f"📝 提取结果示例（前20条）")
        print(f"{'='*100}\n")
        
        for i, req in enumerate(result.get('requirements', [])[:20], 1):
            veto_tag = "🚫" if req.get('is_veto') else "  "
            category = req.get('category', '未分类')
            title = req.get('title', '')
            consequence = req.get('consequence', '')
            cons_tag = f"[{consequence}]" if consequence else ""
            
            print(f"{i:2d}. {veto_tag} [{category}] {cons_tag} {title}")
            
            # 显示requirement_text的前100字
            req_text = req.get('requirement_text', '')
            if len(req_text) > 100:
                req_text = req_text[:100] + "..."
            print(f"    {req_text}")
            print()
        
        if total_count > 20:
            print(f"... 还有 {total_count - 20} 条未显示\n")
        
        # 保存完整结果到文件
        output_file = "/aidata/x-llmapp1/extraction_result_v34.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"{'='*100}")
        print(f"💾 完整结果已保存到：{output_file}")
        print(f"{'='*100}\n")
        
        # 现在读取原始招标文档进行比对
        print(f"{'='*100}")
        print(f"📄 读取原始招标文档进行比对分析")
        print(f"{'='*100}\n")
        
        # 查询招标文档chunks
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT chunk_id, chunk_index, content, doc_type
                    FROM tender_document_chunks
                    WHERE project_id = %s AND doc_type = 'tender'
                    ORDER BY chunk_index
                """, (project_id,))
                
                chunks = cur.fetchall()
                print(f"招标文档总chunks数：{len(chunks)}")
                
                # 查找关键章节
                print(f"\n🔍 扫描关键章节...")
                
                key_chapters = {
                    '投标人须知': [],
                    '评审办法': [],
                    '评分标准': [],
                    '资格条件': [],
                    '技术要求': [],
                    '采购需求': [],
                    '废标': [],
                    '否决': [],
                    '表格': []
                }
                
                for chunk in chunks:
                    content = chunk['content']
                    for key in key_chapters:
                        if key in content:
                            key_chapters[key].append({
                                'chunk_id': chunk['chunk_id'],
                                'chunk_index': chunk['chunk_index'],
                                'content': content[:200] + "..." if len(content) > 200 else content
                            })
                
                print(f"\n关键章节分布：")
                for key, matches in key_chapters.items():
                    print(f"  - {key}: {len(matches)} 个chunks")
                
                # 检查是否有表格标记
                table_indicators = ['|', '┃', '│', '├', '┬', '─']
                table_chunks = []
                for chunk in chunks:
                    content = chunk['content']
                    if any(indicator in content for indicator in table_indicators):
                        table_chunks.append(chunk)
                
                print(f"\n📋 疑似表格chunks数：{len(table_chunks)}")
                
                # 显示一些表格示例
                if table_chunks:
                    print(f"\n表格示例（前3个）：")
                    for i, chunk in enumerate(table_chunks[:3], 1):
                        print(f"\n表格示例 {i} (chunk_index: {chunk['chunk_index']}):")
                        content = chunk['content']
                        # 只显示前500字符
                        display_content = content[:500] + "..." if len(content) > 500 else content
                        print(display_content)
                        print("-" * 80)
        
        print(f"\n{'='*100}")
        print(f"📊 初步分析")
        print(f"{'='*100}\n")
        
        print(f"1. 提取数量：{total_count} 条")
        print(f"   - 预期范围（标准项目）：110-230条")
        
        if total_count < 100:
            print(f"   ⚠️ 警告：提取数量少于100条，可能有遗漏！")
        elif total_count < 110:
            print(f"   ⚠️ 注意：提取数量在100-110之间，略低于预期")
        elif total_count > 230:
            print(f"   ✅ 提取数量超过230条，非常全面！")
        else:
            print(f"   ✅ 提取数量在预期范围内")
        
        print(f"\n2. 废标项：{veto_count} 条")
        print(f"   - 预期范围：20-40条")
        if veto_count < 20:
            print(f"   ⚠️ 警告：废标项可能有遗漏")
        else:
            print(f"   ✅ 废标项数量合理")
        
        print(f"\n3. 文档覆盖情况：")
        print(f"   - 招标文档总chunks：{len(chunks)}")
        print(f"   - 送入LLM的chunks：800（V3.4设置）")
        coverage = min(800 / len(chunks) * 100, 100) if len(chunks) > 0 else 0
        print(f"   - 覆盖率：{coverage:.1f}%")
        
        print(f"\n4. 表格处理情况：")
        print(f"   - 疑似表格chunks：{len(table_chunks)}")
        print(f"   - 如果表格内容较多，应该有相应数量的提取项")
        
        print(f"\n{'='*100}")
        print(f"💡 下一步分析建议")
        print(f"{'='*100}\n")
        print(f"1. 查看 extraction_result_v34.json 获取完整提取结果")
        print(f"2. 对比原文，检查以下关键内容是否遗漏：")
        print(f"   - 投标人须知中的程序要求")
        print(f"   - 评审办法中的评分标准")
        print(f"   - 资格条件表（如有）")
        print(f"   - 技术参数表（如有）")
        print(f"   - 所有标注▲/★/*的条款")
        print(f"3. 检查表格内容是否逐行提取")
        print(f"4. 检查复杂条款是否拆分为多条")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ 提取失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

