"""
Parallel Extraction Utilities
并行抽取工具
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass

from .engine import ExtractionEngine
from .types import ExtractionSpec, ExtractionResult

logger = logging.getLogger(__name__)


@dataclass
class ParallelExtractionTask:
    """并行抽取任务"""
    task_id: str  # 任务标识（如 "stage_1", "project_123"）
    spec: ExtractionSpec
    project_id: str
    stage: Optional[int] = None
    stage_name: Optional[str] = None
    context_info: Optional[str] = None
    module_name: Optional[str] = None


@dataclass
class ParallelExtractionResult:
    """并行抽取结果"""
    task_id: str
    result: Optional[ExtractionResult] = None
    error: Optional[str] = None
    duration_ms: int = 0


class ParallelExtractor:
    """
    并行抽取器
    
    支持：
    1. 并行执行多个Stage的抽取
    2. 并行处理多个项目
    3. 限制并发数量（避免资源耗尽）
    """
    
    def __init__(
        self,
        engine: Optional[ExtractionEngine] = None,
        max_concurrent: int = 5,
    ):
        """
        Args:
            engine: 抽取引擎实例（如果为None，会创建新实例）
            max_concurrent: 最大并发数
        """
        self.engine = engine or ExtractionEngine()
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    async def run_parallel(
        self,
        tasks: List[ParallelExtractionTask],
        retriever: Any,
        llm: Any,
        model_id: Optional[str] = None,
        run_id: Optional[str] = None,
        embedding_provider: Optional[str] = None,
        on_task_complete: Optional[Callable[[ParallelExtractionResult], None]] = None,
    ) -> List[ParallelExtractionResult]:
        """
        并行执行多个抽取任务
        
        Args:
            tasks: 任务列表
            retriever: 检索器
            llm: LLM 编排器
            model_id: 模型 ID
            run_id: 运行 ID
            embedding_provider: 嵌入提供者
            on_task_complete: 任务完成时的回调函数（可选，用于实时监控）
        
        Returns:
            结果列表（顺序与tasks相同）
        """
        logger.info(f"[ParallelExtractor] START run_id={run_id} task_count={len(tasks)} max_concurrent={self.max_concurrent}")
        
        async def execute_one_task(task: ParallelExtractionTask, index: int) -> ParallelExtractionResult:
            """执行单个任务（带信号量控制）"""
            async with self._semaphore:
                import time
                start_time = time.time()
                
                try:
                    logger.info(f"[ParallelExtractor] TASK_START task_id={task.task_id} index={index} project_id={task.project_id} stage={task.stage}")
                    
                    result = await self.engine.run(
                        spec=task.spec,
                        retriever=retriever,
                        llm=llm,
                        project_id=task.project_id,
                        model_id=model_id,
                        run_id=run_id,
                        embedding_provider=embedding_provider,
                        stage=task.stage,
                        stage_name=task.stage_name,
                        context_info=task.context_info,
                        module_name=task.module_name,
                    )
                    
                    duration_ms = int((time.time() - start_time) * 1000)
                    logger.info(f"[ParallelExtractor] TASK_SUCCESS task_id={task.task_id} index={index} duration_ms={duration_ms}")
                    
                    task_result = ParallelExtractionResult(
                        task_id=task.task_id,
                        result=result,
                        duration_ms=duration_ms,
                    )
                    
                    # 调用完成回调
                    if on_task_complete:
                        try:
                            on_task_complete(task_result)
                        except Exception as callback_error:
                            logger.warning(f"[ParallelExtractor] CALLBACK_ERROR task_id={task.task_id}: {callback_error}")
                    
                    return task_result
                    
                except Exception as e:
                    duration_ms = int((time.time() - start_time) * 1000)
                    logger.error(f"[ParallelExtractor] TASK_FAILED task_id={task.task_id} index={index} duration_ms={duration_ms} error={e}")
                    
                    return ParallelExtractionResult(
                        task_id=task.task_id,
                        error=str(e),
                        duration_ms=duration_ms,
                    )
        
        # 并行执行所有任务
        task_coroutines = [execute_one_task(task, i) for i, task in enumerate(tasks)]
        results = await asyncio.gather(*task_coroutines, return_exceptions=True)
        
        # 处理异常结果
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"[ParallelExtractor] GATHER_EXCEPTION index={i} error={result}")
                final_results.append(ParallelExtractionResult(
                    task_id=tasks[i].task_id,
                    error=str(result),
                ))
            else:
                final_results.append(result)
        
        # 统计
        success_count = sum(1 for r in final_results if r.result is not None)
        error_count = sum(1 for r in final_results if r.error is not None)
        total_duration = sum(r.duration_ms for r in final_results)
        avg_duration = total_duration // len(final_results) if final_results else 0
        
        logger.info(
            f"[ParallelExtractor] DONE run_id={run_id} "
            f"total={len(tasks)} success={success_count} error={error_count} "
            f"total_duration_ms={total_duration} avg_duration_ms={avg_duration}"
        )
        
        return final_results
    
    async def run_stages_parallel(
        self,
        stage_specs: Dict[int, ExtractionSpec],
        project_id: str,
        retriever: Any,
        llm: Any,
        model_id: Optional[str] = None,
        run_id: Optional[str] = None,
        embedding_provider: Optional[str] = None,
        stage_names: Optional[Dict[int, str]] = None,
    ) -> Dict[int, ExtractionResult]:
        """
        并行执行多个Stage的抽取（适用于互相独立的Stage）
        
        Args:
            stage_specs: {stage_num: ExtractionSpec} 字典
            project_id: 项目 ID
            retriever: 检索器
            llm: LLM 编排器
            model_id: 模型 ID
            run_id: 运行 ID
            embedding_provider: 嵌入提供者
            stage_names: {stage_num: stage_name} 字典（可选）
        
        Returns:
            {stage_num: ExtractionResult} 字典
        """
        stage_names = stage_names or {}
        
        # 构建任务列表
        tasks = [
            ParallelExtractionTask(
                task_id=f"stage_{stage_num}",
                spec=spec,
                project_id=project_id,
                stage=stage_num,
                stage_name=stage_names.get(stage_num),
            )
            for stage_num, spec in stage_specs.items()
        ]
        
        # 执行并行抽取
        results = await self.run_parallel(
            tasks=tasks,
            retriever=retriever,
            llm=llm,
            model_id=model_id,
            run_id=run_id,
            embedding_provider=embedding_provider,
        )
        
        # 转换为字典格式
        stage_results = {}
        for task, result in zip(tasks, results):
            if result.result:
                stage_num = task.stage
                stage_results[stage_num] = result.result
            else:
                logger.warning(f"[ParallelExtractor] Stage {task.stage} failed: {result.error}")
        
        return stage_results
    
    async def run_projects_parallel(
        self,
        project_specs: Dict[str, ExtractionSpec],
        retriever: Any,
        llm: Any,
        model_id: Optional[str] = None,
        run_id: Optional[str] = None,
        embedding_provider: Optional[str] = None,
    ) -> Dict[str, ExtractionResult]:
        """
        并行处理多个项目的抽取
        
        Args:
            project_specs: {project_id: ExtractionSpec} 字典
            retriever: 检索器
            llm: LLM 编排器
            model_id: 模型 ID
            run_id: 运行 ID
            embedding_provider: 嵌入提供者
        
        Returns:
            {project_id: ExtractionResult} 字典
        """
        # 构建任务列表
        tasks = [
            ParallelExtractionTask(
                task_id=f"project_{project_id}",
                spec=spec,
                project_id=project_id,
            )
            for project_id, spec in project_specs.items()
        ]
        
        # 执行并行抽取
        results = await self.run_parallel(
            tasks=tasks,
            retriever=retriever,
            llm=llm,
            model_id=model_id,
            run_id=run_id,
            embedding_provider=embedding_provider,
        )
        
        # 转换为字典格式
        project_results = {}
        for task, result in zip(tasks, results):
            if result.result:
                project_results[task.project_id] = result.result
            else:
                logger.warning(f"[ParallelExtractor] Project {task.project_id} failed: {result.error}")
        
        return project_results


# 便捷函数

async def extract_stages_parallel(
    stage_specs: Dict[int, ExtractionSpec],
    project_id: str,
    retriever: Any,
    llm: Any,
    model_id: Optional[str] = None,
    run_id: Optional[str] = None,
    embedding_provider: Optional[str] = None,
    stage_names: Optional[Dict[int, str]] = None,
    max_concurrent: int = 5,
) -> Dict[int, ExtractionResult]:
    """
    便捷函数：并行执行多个Stage的抽取
    
    Example:
        stage_specs = {
            1: ExtractionSpec(queries="项目基本信息", ...),
            2: ExtractionSpec(queries="评分规则", ...),
            3: ExtractionSpec(queries="招标要求", ...),
        }
        results = await extract_stages_parallel(
            stage_specs=stage_specs,
            project_id="proj_123",
            retriever=retriever,
            llm=llm,
        )
    """
    extractor = ParallelExtractor(max_concurrent=max_concurrent)
    return await extractor.run_stages_parallel(
        stage_specs=stage_specs,
        project_id=project_id,
        retriever=retriever,
        llm=llm,
        model_id=model_id,
        run_id=run_id,
        embedding_provider=embedding_provider,
        stage_names=stage_names,
    )


async def extract_projects_parallel(
    project_specs: Dict[str, ExtractionSpec],
    retriever: Any,
    llm: Any,
    model_id: Optional[str] = None,
    run_id: Optional[str] = None,
    embedding_provider: Optional[str] = None,
    max_concurrent: int = 5,
) -> Dict[str, ExtractionResult]:
    """
    便捷函数：并行处理多个项目的抽取
    
    Example:
        project_specs = {
            "proj_1": ExtractionSpec(queries="项目信息", ...),
            "proj_2": ExtractionSpec(queries="项目信息", ...),
        }
        results = await extract_projects_parallel(
            project_specs=project_specs,
            retriever=retriever,
            llm=llm,
        )
    """
    extractor = ParallelExtractor(max_concurrent=max_concurrent)
    return await extractor.run_projects_parallel(
        project_specs=project_specs,
        retriever=retriever,
        llm=llm,
        model_id=model_id,
        run_id=run_id,
        embedding_provider=embedding_provider,
    )

