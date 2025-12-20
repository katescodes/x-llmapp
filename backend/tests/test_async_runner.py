"""
Async Runner Tests - 测试同步/异步环境中的 async 执行
"""
import asyncio
import pytest
from app.platform.utils.async_runner import run_async, run_async_multiple


# 测试用的 async 函数
async def simple_async_func(value: int) -> int:
    """简单的 async 函数，返回输入值的两倍"""
    await asyncio.sleep(0.01)  # 模拟异步操作
    return value * 2


async def async_func_with_error():
    """会抛出异常的 async 函数"""
    await asyncio.sleep(0.01)
    raise ValueError("Test error from async function")


def test_run_async_without_event_loop():
    """测试在无 event loop 时执行 async 函数"""
    # 在普通同步函数中调用（无 event loop）
    result = run_async(simple_async_func(5))
    assert result == 10


def test_run_async_with_exception():
    """测试 async 函数抛出异常时的处理"""
    with pytest.raises(ValueError, match="Test error from async function"):
        run_async(async_func_with_error())


@pytest.mark.asyncio
async def test_run_async_within_event_loop():
    """测试在已有 event loop 时执行 async 函数"""
    # 在 async 函数中调用 run_async（已有 event loop）
    # 这模拟了在 async 环境中调用同步包装的场景
    result = run_async(simple_async_func(7))
    assert result == 14


def test_run_async_multiple_coros():
    """测试批量执行多个 async 函数"""
    coros = [
        simple_async_func(1),
        simple_async_func(2),
        simple_async_func(3),
    ]
    results = run_async_multiple(coros)
    assert results == [2, 4, 6]


@pytest.mark.asyncio
async def test_run_async_multiple_within_loop():
    """测试在 async 环境中批量执行"""
    coros = [
        simple_async_func(10),
        simple_async_func(20),
    ]
    results = run_async_multiple(coros)
    assert results == [20, 40]


def test_run_async_returns_complex_object():
    """测试返回复杂对象"""
    async def return_dict():
        await asyncio.sleep(0.01)
        return {"key": "value", "number": 42}
    
    result = run_async(return_dict())
    assert result == {"key": "value", "number": 42}
    assert isinstance(result, dict)

