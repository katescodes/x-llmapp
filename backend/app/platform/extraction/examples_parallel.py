"""
并行抽取使用示例
演示如何使用并行功能提升抽取性能
"""
import asyncio
import time
from typing import Any, Dict

from app.platform.extraction.engine import ExtractionEngine
from app.platform.extraction.parallel import (
    ParallelExtractor,
    extract_stages_parallel,
    extract_projects_parallel,
)
from app.platform.extraction.types import ExtractionSpec


# ============================================================================
# 示例 1: 查询级并行（默认启用，无需额外代码）
# ============================================================================

async def example_query_parallel(retriever: Any, llm: Any, project_id: str):
    """
    示例：多查询并行检索
    这是默认启用的，无需额外配置
    """
    print("\n" + "="*80)
    print("示例 1: 查询级并行（Query-level Parallelism）")
    print("="*80)
    
    # 定义包含多个查询的spec
    spec = ExtractionSpec(
        queries={
            "project_name": "项目名称、项目编号",
            "budget": "项目预算金额、投资金额",
            "deadline": "投标截止时间、开标时间",
            "contact": "联系人、联系电话",
        },
        topk_per_query=5,
        topk_total=20,
        prompt="""
请从招标文件中抽取以下项目基本信息，以JSON格式返回：
{
    "project_name": "项目名称",
    "project_code": "项目编号",
    "budget": "预算金额（万元）",
    "deadline": "投标截止时间",
    "contact_person": "联系人",
    "contact_phone": "联系电话"
}
        """.strip(),
        temperature=0.1,
    )
    
    # 执行抽取（会自动并行执行4个查询）
    engine = ExtractionEngine()
    
    start = time.time()
    result = await engine.run(
        spec=spec,
        retriever=retriever,
        llm=llm,
        project_id=project_id,
    )
    elapsed = time.time() - start
    
    print(f"\n✅ 完成！耗时: {elapsed:.2f}秒")
    print(f"📊 检索到的chunks: {len(result.evidence_chunk_ids)}")
    print(f"📄 抽取结果: {result.data}")
    print("\n💡 提示: 4个查询已自动并行执行")


# ============================================================================
# 示例 2: Stage级并行
# ============================================================================

async def example_stage_parallel(retriever: Any, llm: Any, project_id: str):
    """
    示例：并行执行多个独立的Stage
    适用于多个Stage互相独立的场景
    """
    print("\n" + "="*80)
    print("示例 2: Stage级并行（Stage-level Parallelism）")
    print("="*80)
    
    # 定义3个独立的Stage
    stage_specs = {
        1: ExtractionSpec(
            queries="项目基本信息：项目名称、招标单位、预算金额、投标截止时间",
            topk_per_query=10,
            topk_total=10,
            prompt="""
请抽取项目基本信息，以JSON格式返回：
{
    "project_name": "项目名称",
    "tender_unit": "招标单位",
    "budget": "预算金额",
    "deadline": "投标截止时间"
}
            """.strip(),
            temperature=0.1,
        ),
        2: ExtractionSpec(
            queries="评分规则：评分项、分值、评分标准、评分方法",
            topk_per_query=15,
            topk_total=15,
            prompt="""
请抽取评分规则，以JSON格式返回：
{
    "scoring_rules": [
        {
            "item": "评分项名称",
            "score": "分值",
            "standard": "评分标准"
        }
    ]
}
            """.strip(),
            temperature=0.1,
        ),
        3: ExtractionSpec(
            queries="招标要求：资质要求、技术要求、商务要求、业绩要求",
            topk_per_query=20,
            topk_total=20,
            prompt="""
请抽取招标要求，以JSON格式返回：
{
    "requirements": [
        {
            "category": "要求类别",
            "content": "具体要求内容"
        }
    ]
}
            """.strip(),
            temperature=0.1,
        ),
    }
    
    stage_names = {
        1: "项目基本信息",
        2: "评分规则",
        3: "招标要求",
    }
    
    # 方式1: 使用便捷函数
    print("\n🚀 开始并行执行3个Stage...")
    
    start = time.time()
    results = await extract_stages_parallel(
        stage_specs=stage_specs,
        project_id=project_id,
        retriever=retriever,
        llm=llm,
        stage_names=stage_names,
        max_concurrent=3,  # 3个Stage同时执行
    )
    elapsed = time.time() - start
    
    print(f"\n✅ 完成！总耗时: {elapsed:.2f}秒")
    
    for stage_num, result in results.items():
        stage_name = stage_names[stage_num]
        if result:
            print(f"  ✓ Stage {stage_num} ({stage_name}): 成功")
        else:
            print(f"  ✗ Stage {stage_num} ({stage_name}): 失败")
    
    print("\n💡 提示: 如果串行执行，耗时约为 {:.2f}秒 × 3 = {:.2f}秒".format(
        elapsed, elapsed * 3
    ))


# ============================================================================
# 示例 3: 项目级并行
# ============================================================================

async def example_project_parallel(retriever: Any, llm: Any):
    """
    示例：并行处理多个项目
    适用于批量抽取场景
    """
    print("\n" + "="*80)
    print("示例 3: 项目级并行（Project-level Parallelism）")
    print("="*80)
    
    # 假设有5个项目需要处理
    project_ids = [
        "proj_001",
        "proj_002",
        "proj_003",
        "proj_004",
        "proj_005",
    ]
    
    # 所有项目使用相同的抽取规格
    spec = ExtractionSpec(
        queries="项目基本信息：项目名称、招标单位、预算金额",
        topk_per_query=10,
        topk_total=10,
        prompt="""
请抽取项目基本信息，以JSON格式返回：
{
    "project_name": "项目名称",
    "tender_unit": "招标单位",
    "budget": "预算金额"
}
        """.strip(),
        temperature=0.1,
    )
    
    # 构建项目specs字典
    project_specs = {pid: spec for pid in project_ids}
    
    print(f"\n🚀 开始并行处理{len(project_ids)}个项目...")
    
    start = time.time()
    results = await extract_projects_parallel(
        project_specs=project_specs,
        retriever=retriever,
        llm=llm,
        max_concurrent=3,  # 最多3个项目同时处理
    )
    elapsed = time.time() - start
    
    print(f"\n✅ 完成！总耗时: {elapsed:.2f}秒")
    print(f"📊 成功处理: {len(results)}/{len(project_ids)} 个项目")
    
    for project_id, result in results.items():
        if result:
            print(f"  ✓ {project_id}: {result.data.get('project_name', 'N/A')}")
        else:
            print(f"  ✗ {project_id}: 失败")
    
    avg_time = elapsed / len(project_ids)
    serial_time = avg_time * len(project_ids)
    speedup = serial_time / elapsed
    
    print(f"\n💡 性能对比:")
    print(f"  - 并行执行: {elapsed:.2f}秒")
    print(f"  - 串行执行（估算）: {serial_time:.2f}秒")
    print(f"  - 加速比: {speedup:.2f}x")


# ============================================================================
# 示例 4: 组合并行（项目 + Stage）
# ============================================================================

async def example_combined_parallel(retriever: Any, llm: Any):
    """
    示例：组合并行 - 同时并行处理多个项目和多个Stage
    这是最高级的用法，可以获得最大的性能提升
    """
    print("\n" + "="*80)
    print("示例 4: 组合并行（Combined Parallelism）")
    print("="*80)
    
    from app.platform.extraction.parallel import ParallelExtractionTask
    
    # 2个项目 × 3个Stage = 6个任务
    project_ids = ["proj_001", "proj_002"]
    
    stage_specs = {
        1: ExtractionSpec(
            queries="项目基本信息",
            topk_per_query=10,
            topk_total=10,
            prompt="抽取项目基本信息...",
            temperature=0.1,
        ),
        2: ExtractionSpec(
            queries="评分规则",
            topk_per_query=15,
            topk_total=15,
            prompt="抽取评分规则...",
            temperature=0.1,
        ),
        3: ExtractionSpec(
            queries="招标要求",
            topk_per_query=20,
            topk_total=20,
            prompt="抽取招标要求...",
            temperature=0.1,
        ),
    }
    
    stage_names = {
        1: "项目基本信息",
        2: "评分规则",
        3: "招标要求",
    }
    
    # 构建所有任务
    all_tasks = []
    for project_id in project_ids:
        for stage_num, spec in stage_specs.items():
            all_tasks.append(ParallelExtractionTask(
                task_id=f"{project_id}_stage_{stage_num}",
                spec=spec,
                project_id=project_id,
                stage=stage_num,
                stage_name=stage_names[stage_num],
            ))
    
    print(f"\n🚀 开始并行处理{len(all_tasks)}个任务...")
    print(f"  - {len(project_ids)}个项目")
    print(f"  - 每个项目{len(stage_specs)}个Stage")
    print(f"  - 并发数: 4")
    
    # 创建并行抽取器
    extractor = ParallelExtractor(max_concurrent=4)
    
    # 定义进度回调
    completed = [0]
    def on_task_complete(result):
        completed[0] += 1
        status = "✓" if result.result else "✗"
        print(f"  [{completed[0]}/{len(all_tasks)}] {status} {result.task_id} ({result.duration_ms}ms)")
    
    start = time.time()
    results = await extractor.run_parallel(
        tasks=all_tasks,
        retriever=retriever,
        llm=llm,
        on_task_complete=on_task_complete,
    )
    elapsed = time.time() - start
    
    # 统计结果
    success_count = sum(1 for r in results if r.result is not None)
    
    print(f"\n✅ 完成！")
    print(f"📊 统计:")
    print(f"  - 总任务数: {len(all_tasks)}")
    print(f"  - 成功: {success_count}")
    print(f"  - 失败: {len(all_tasks) - success_count}")
    print(f"  - 总耗时: {elapsed:.2f}秒")
    print(f"  - 平均每任务: {elapsed / len(all_tasks):.2f}秒")
    
    # 按项目和Stage组织结果
    print(f"\n📋 结果汇总:")
    for project_id in project_ids:
        print(f"  {project_id}:")
        for stage_num in [1, 2, 3]:
            task_id = f"{project_id}_stage_{stage_num}"
            result = next((r for r in results if r.task_id == task_id), None)
            status = "✓" if result and result.result else "✗"
            print(f"    {status} Stage {stage_num} ({stage_names[stage_num]})")
    
    # 性能分析
    avg_task_time = sum(r.duration_ms for r in results) / len(results) / 1000
    serial_time = avg_task_time * len(all_tasks)
    speedup = serial_time / elapsed
    
    print(f"\n💡 性能分析:")
    print(f"  - 并行执行: {elapsed:.2f}秒")
    print(f"  - 串行执行（估算）: {serial_time:.2f}秒")
    print(f"  - 加速比: {speedup:.2f}x")


# ============================================================================
# 示例 5: 错误处理和重试
# ============================================================================

async def example_error_handling(retriever: Any, llm: Any, project_id: str):
    """
    示例：并行执行时的错误处理和重试策略
    """
    print("\n" + "="*80)
    print("示例 5: 错误处理和重试")
    print("="*80)
    
    stage_specs = {
        1: ExtractionSpec(queries="项目信息", topk_per_query=10, topk_total=10, prompt="...", temperature=0.1),
        2: ExtractionSpec(queries="评分规则", topk_per_query=15, topk_total=15, prompt="...", temperature=0.1),
        3: ExtractionSpec(queries="招标要求", topk_per_query=20, topk_total=20, prompt="...", temperature=0.1),
    }
    
    stage_names = {1: "项目信息", 2: "评分规则", 3: "招标要求"}
    
    print("\n🚀 第一次尝试（并行执行）...")
    
    results = await extract_stages_parallel(
        stage_specs=stage_specs,
        project_id=project_id,
        retriever=retriever,
        llm=llm,
        stage_names=stage_names,
        max_concurrent=3,
    )
    
    # 检查失败的Stage
    failed_stages = [stage for stage, result in results.items() if result is None]
    
    if failed_stages:
        print(f"\n⚠️  {len(failed_stages)}个Stage失败: {failed_stages}")
        print(f"🔄 重试失败的Stage...")
        
        # 只重试失败的Stage
        retry_specs = {stage: stage_specs[stage] for stage in failed_stages}
        
        retry_results = await extract_stages_parallel(
            stage_specs=retry_specs,
            project_id=project_id,
            retriever=retriever,
            llm=llm,
            stage_names=stage_names,
            max_concurrent=len(failed_stages),
        )
        
        # 合并结果
        results.update(retry_results)
        
        still_failed = [stage for stage, result in results.items() if result is None]
        if still_failed:
            print(f"\n❌ 仍有{len(still_failed)}个Stage失败: {still_failed}")
        else:
            print(f"\n✅ 重试成功！所有Stage都已完成")
    else:
        print(f"\n✅ 所有Stage都成功完成")
    
    # 最终结果
    print(f"\n📊 最终结果:")
    for stage, result in results.items():
        status = "✓" if result else "✗"
        print(f"  {status} Stage {stage} ({stage_names[stage]})")


# ============================================================================
# 示例 6: 性能基准测试
# ============================================================================

async def example_benchmark(retriever: Any, llm: Any, project_id: str):
    """
    示例：对比串行和并行的性能
    """
    print("\n" + "="*80)
    print("示例 6: 性能基准测试")
    print("="*80)
    
    stage_specs = {
        1: ExtractionSpec(queries="项目信息", topk_per_query=10, topk_total=10, prompt="...", temperature=0.1),
        2: ExtractionSpec(queries="评分规则", topk_per_query=15, topk_total=15, prompt="...", temperature=0.1),
        3: ExtractionSpec(queries="招标要求", topk_per_query=20, topk_total=20, prompt="...", temperature=0.1),
    }
    
    engine = ExtractionEngine()
    
    # 测试1: 串行执行
    print("\n📏 测试1: 串行执行")
    start = time.time()
    for stage_num, spec in stage_specs.items():
        await engine.run(
            spec=spec,
            retriever=retriever,
            llm=llm,
            project_id=project_id,
            stage=stage_num,
        )
    serial_time = time.time() - start
    print(f"  耗时: {serial_time:.2f}秒")
    
    # 测试2: 并行执行
    print("\n📏 测试2: 并行执行")
    start = time.time()
    await extract_stages_parallel(
        stage_specs=stage_specs,
        project_id=project_id,
        retriever=retriever,
        llm=llm,
        max_concurrent=3,
    )
    parallel_time = time.time() - start
    print(f"  耗时: {parallel_time:.2f}秒")
    
    # 对比
    speedup = serial_time / parallel_time
    print(f"\n📊 性能对比:")
    print(f"  - 串行: {serial_time:.2f}秒")
    print(f"  - 并行: {parallel_time:.2f}秒")
    print(f"  - 加速比: {speedup:.2f}x")
    print(f"  - 节省时间: {serial_time - parallel_time:.2f}秒 ({(1 - parallel_time/serial_time) * 100:.1f}%)")


# ============================================================================
# 主函数
# ============================================================================

async def main():
    """
    运行所有示例
    
    注意：这是演示代码，需要提供实际的 retriever 和 llm 实例
    """
    print("\n" + "="*80)
    print("并行抽取功能演示")
    print("="*80)
    
    # TODO: 初始化 retriever 和 llm
    # from app.platform.retrieval import RetrievalFacade
    # from app.platform.llm import LLMOrchestrator
    # retriever = RetrievalFacade(...)
    # llm = LLMOrchestrator(...)
    
    retriever = None  # 替换为实际的retriever
    llm = None  # 替换为实际的llm
    project_id = "demo_project"
    
    if not retriever or not llm:
        print("\n⚠️  请先配置 retriever 和 llm 实例")
        print("  修改 main() 函数中的初始化代码")
        return
    
    # 运行示例
    try:
        # await example_query_parallel(retriever, llm, project_id)
        # await example_stage_parallel(retriever, llm, project_id)
        # await example_project_parallel(retriever, llm)
        # await example_combined_parallel(retriever, llm)
        # await example_error_handling(retriever, llm, project_id)
        # await example_benchmark(retriever, llm, project_id)
        pass
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

