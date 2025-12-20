"""
Redis 连接管理
"""
import logging
import os
from typing import Optional

import redis
from rq import Queue

logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None


def get_redis_connection() -> redis.Redis:
    """获取 Redis 连接"""
    global _redis_client
    
    if _redis_client is not None:
        return _redis_client
    
    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_db = int(os.getenv("REDIS_DB", "0"))
    redis_password = os.getenv("REDIS_PASSWORD", None)
    
    try:
        _redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password,
            decode_responses=False,  # RQ需要bytes模式
            socket_connect_timeout=10,
            socket_timeout=None,  # Worker需要长连接，不设置超时
        )
        # 测试连接
        _redis_client.ping()
        logger.info(f"Redis connected: {redis_host}:{redis_port}/{redis_db}")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        # 在开发环境下，如果 Redis 不可用，返回一个 Mock 对象
        # 生产环境应该抛出异常
        raise
    
    return _redis_client


def get_queue(name: str = "default") -> Queue:
    """获取队列实例"""
    conn = get_redis_connection()
    return Queue(name, connection=conn)


def is_redis_available() -> bool:
    """检查 Redis 是否可用"""
    try:
        conn = get_redis_connection()
        conn.ping()
        return True
    except Exception:
        return False

