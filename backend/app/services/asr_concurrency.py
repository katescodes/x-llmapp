"""
ASR转录并发控制管理器
用于限制并发转录请求数量，避免显存溢出
"""
import asyncio
import logging
from typing import Optional, Callable, Any
from datetime import datetime
from ..config import get_settings

logger = logging.getLogger(__name__)


class ASRConcurrencyManager:
    """ASR并发控制管理器（单例模式）"""
    
    _instance: Optional['ASRConcurrencyManager'] = None
    _lock = asyncio.Lock()
    
    def __init__(self):
        settings = get_settings()
        self.max_concurrent = settings.ASR_MAX_CONCURRENT
        self.max_retries = settings.ASR_MAX_RETRIES
        self.retry_delay = settings.ASR_RETRY_DELAY
        
        # 使用信号量控制并发数
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        
        # 队列管理
        self._queue_size = 0
        self._max_queue_size = self.max_concurrent * 10  # 最多排队10倍并发数
        
        # 统计信息
        self._active_tasks = 0
        self._total_tasks = 0
        self._failed_tasks = 0
        self._oom_errors = 0
        self._rejected_tasks = 0  # 被拒绝的任务（队列满）
        
        # 最近的OOM时间（用于智能延迟）
        self._last_oom_time: Optional[datetime] = None
        
        logger.info(
            f"ASR并发管理器初始化: max_concurrent={self.max_concurrent}, "
            f"max_retries={self.max_retries}, max_queue={self._max_queue_size}"
        )
    
    @classmethod
    async def get_instance(cls) -> 'ASRConcurrencyManager':
        """获取单例实例"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def _should_delay_for_oom(self) -> int:
        """
        检查是否应该因为最近的OOM错误而延迟
        返回：建议延迟的秒数
        """
        if self._last_oom_time is None:
            return 0
        
        # 如果最近30秒内发生过OOM，增加延迟
        time_since_oom = (datetime.now() - self._last_oom_time).total_seconds()
        if time_since_oom < 30:
            # 越接近OOM时间，延迟越长
            return min(15, int(30 - time_since_oom))
        
        return 0
    
    async def execute_with_retry(
        self,
        task_func: Callable,
        task_id: str
    ) -> Any:
        """
        在并发控制下执行任务，支持重试和智能排队
        
        Args:
            task_func: 异步任务函数（无参数的callable）
            task_id: 任务ID（用于日志）
            
        Returns:
            任务函数的返回值
            
        Raises:
            最后一次重试失败后抛出异常
        """
        # 检查队列是否已满
        if self._queue_size >= self._max_queue_size:
            self._rejected_tasks += 1
            logger.error(
                f"[ASR并发] 队列已满，拒绝任务 task_id={task_id} "
                f"queue_size={self._queue_size}/{self._max_queue_size}"
            )
            raise RuntimeError(
                f"ASR服务繁忙，当前排队任务过多({self._queue_size})，请稍后重试"
            )
        
        self._total_tasks += 1
        self._queue_size += 1
        
        try:
            for attempt in range(self.max_retries):
                try:
                    # 智能延迟：如果最近有OOM，等待一段时间
                    oom_delay = self._should_delay_for_oom()
                    if oom_delay > 0 and attempt == 0:
                        logger.info(
                            f"[ASR并发] 检测到最近OOM，延迟{oom_delay}秒后开始 task_id={task_id}"
                        )
                        await asyncio.sleep(oom_delay)
                    
                    # 等待获取信号量（控制并发）
                    async with self._semaphore:
                        self._active_tasks += 1
                        try:
                            logger.info(
                                f"[ASR并发] 开始转录 task_id={task_id} "
                                f"attempt={attempt+1}/{self.max_retries} "
                                f"active={self._active_tasks}/{self.max_concurrent} "
                                f"queued={self._queue_size}"
                            )
                            
                            # 执行任务（不传递额外参数，task_func应该是闭包）
                            result = await task_func()
                            
                            logger.info(
                                f"[ASR并发] 转录成功 task_id={task_id} "
                                f"attempt={attempt+1}"
                            )
                            return result
                            
                        finally:
                            self._active_tasks -= 1
                
                except Exception as e:
                    error_str = str(e).lower()
                    is_oom_error = (
                        "out of memory" in error_str or
                        "oom" in error_str or
                        "cuda out of memory" in error_str or
                        "显存不足" in error_str
                    )
                    
                    if is_oom_error:
                        self._oom_errors += 1
                        self._last_oom_time = datetime.now()
                        logger.warning(
                            f"[ASR并发] 显存不足 task_id={task_id} "
                            f"attempt={attempt+1}/{self.max_retries} "
                            f"oom_count={self._oom_errors} "
                            f"active={self._active_tasks} "
                            f"error={str(e)[:300]}"
                        )
                    else:
                        logger.warning(
                            f"[ASR并发] 转录失败 task_id={task_id} "
                            f"attempt={attempt+1}/{self.max_retries} "
                            f"error={str(e)[:300]}"
                        )
                    
                    # 如果是最后一次尝试，抛出异常
                    if attempt >= self.max_retries - 1:
                        self._failed_tasks += 1
                        logger.error(
                            f"[ASR并发] 转录最终失败 task_id={task_id} "
                            f"attempts={self.max_retries} "
                            f"total_oom={self._oom_errors} "
                            f"error={str(e)[:300]}"
                        )
                        raise
                    
                    # 计算重试延迟（OOM错误延迟更长）
                    if is_oom_error:
                        # OOM错误：延迟更长，给GPU时间释放显存
                        delay = self.retry_delay * (3 ** attempt)  # 指数增长更快
                    else:
                        # 其他错误：标准指数退避
                        delay = self.retry_delay * (2 ** attempt)
                    
                    logger.info(
                        f"[ASR并发] 等待重试 task_id={task_id} "
                        f"delay={delay}秒 reason={'OOM' if is_oom_error else '其他错误'}"
                    )
                    await asyncio.sleep(delay)
            
            # 理论上不会到达这里
            raise RuntimeError(f"转录失败: task_id={task_id}")
            
        finally:
            self._queue_size -= 1
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "max_concurrent": self.max_concurrent,
            "active_tasks": self._active_tasks,
            "queued_tasks": self._queue_size,
            "max_queue_size": self._max_queue_size,
            "total_tasks": self._total_tasks,
            "failed_tasks": self._failed_tasks,
            "rejected_tasks": self._rejected_tasks,
            "oom_errors": self._oom_errors,
            "last_oom": (
                self._last_oom_time.isoformat() 
                if self._last_oom_time else None
            ),
            "success_rate": (
                f"{(1 - self._failed_tasks / self._total_tasks) * 100:.1f}%"
                if self._total_tasks > 0 else "N/A"
            ),
            "queue_usage": (
                f"{self._queue_size}/{self._max_queue_size} "
                f"({self._queue_size / self._max_queue_size * 100:.0f}%)"
            )
        }


# 全局函数，方便调用
async def execute_asr_with_concurrency_control(
    task_func: Callable,
    task_id: str
) -> Any:
    """
    使用并发控制执行ASR任务
    
    Args:
        task_func: 异步任务函数（无参数的callable，使用闭包传递参数）
        task_id: 任务ID
        
    Returns:
        任务函数的返回值
    """
    manager = await ASRConcurrencyManager.get_instance()
    return await manager.execute_with_retry(task_func, task_id)


