"""
Async Runner - 同步入口安全调用 async 的桥接工具

提供在同步代码中安全执行 async 函数的能力，兼容以下场景：
1. 当前线程无 event loop：使用 asyncio.run() 执行
2. 当前线程已有 event loop：在独立线程中执行，避免嵌套 loop 错误

用途：
- TenderService 等同步服务需要调用 async 的 ExtractV2Service
- 未来支持在 worker/job 执行环境中调用 async 函数
"""
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Coroutine, TypeVar

T = TypeVar('T')

# 全局线程池，用于在有 loop 的环境中执行 async
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="async_runner")


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """
    在同步代码中安全执行 async 函数
    
    Args:
        coro: 要执行的 coroutine 对象
    
    Returns:
        coroutine 的返回值
    
    Raises:
        任何 coroutine 内部抛出的异常
    
    Examples:
        # 在同步函数中调用 async 函数
        async def fetch_data():
            return {"data": "value"}
        
        result = run_async(fetch_data())  # 安全执行
    
    Notes:
        - 如果当前线程没有运行中的 event loop，直接使用 asyncio.run()
        - 如果当前线程已有 event loop（如在 async 函数中被同步包装调用），
          则在独立线程中创建新的 loop 执行，避免 "asyncio.run() cannot 
          be called from a running event loop" 错误
        - 此函数是为了桥接同步/异步代码，未来可支持 worker/job 环境
    """
    try:
        # 尝试获取当前运行的 event loop
        loop = asyncio.get_running_loop()
        # 如果能获取到，说明当前在 async 环境中，不能直接 asyncio.run
        # 在独立线程中执行
        return _run_in_new_thread(coro)
    except RuntimeError:
        # 没有运行中的 loop，可以直接使用 asyncio.run
        return asyncio.run(coro)


def _run_in_new_thread(coro: Coroutine[Any, Any, T]) -> T:
    """
    在独立线程中创建新的 event loop 并执行 coroutine
    
    这避免了在已有 event loop 的线程中调用 asyncio.run() 的问题
    """
    result_container = {}
    exception_container = {}
    
    def run_in_thread():
        try:
            # 在新线程中创建新的 event loop
            result = asyncio.run(coro)
            result_container['value'] = result
        except Exception as e:
            exception_container['error'] = e
    
    # 使用线程池执行
    future = _executor.submit(run_in_thread)
    future.result()  # 等待完成
    
    # 检查是否有异常
    if 'error' in exception_container:
        raise exception_container['error']
    
    return result_container['value']


def run_async_multiple(coros: list[Coroutine]) -> list[Any]:
    """
    批量执行多个 async 函数（并发执行）
    
    Args:
        coros: coroutine 列表
    
    Returns:
        结果列表（顺序与输入一致）
    
    Notes:
        所有 coroutine 会并发执行以提高效率
    """
    async def _gather():
        return await asyncio.gather(*coros)
    
    return run_async(_gather())










