#!/usr/bin/env python3
"""
RQ Worker 启动脚本 - Step 10
用于处理异步任务（ingest, extract, review）
"""
import logging
import os
import sys
from pathlib import Path

# 添加 app 到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

import redis
from rq import Worker

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)


def get_worker_redis_connection() -> redis.Redis:
    """
    为 Worker 创建专门的 Redis 连接，使用更大的超时以支持长连接
    """
    # 优先使用 REDIS_URL
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        # 从环境变量读取超时配置
        socket_connect_timeout = int(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "30"))
        socket_timeout = int(os.getenv("REDIS_SOCKET_TIMEOUT", "300"))
        
        conn = redis.from_url(
            redis_url,
            decode_responses=False,  # RQ需要bytes模式
            socket_connect_timeout=socket_connect_timeout,
            socket_timeout=socket_timeout,  # 读取超时设置为5分钟
            socket_keepalive=True,
            health_check_interval=30,
        )
        logger.info(f"Worker Redis connected via URL: {redis_url}")
    else:
        # Fallback到独立参数
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))
        redis_password = os.getenv("REDIS_PASSWORD", None)
        socket_connect_timeout = int(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "30"))
        socket_timeout = int(os.getenv("REDIS_SOCKET_TIMEOUT", "300"))
        
        conn = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password,
            decode_responses=False,
            socket_connect_timeout=socket_connect_timeout,
            socket_timeout=socket_timeout,
            socket_keepalive=True,
            health_check_interval=30,
        )
        logger.info(f"Worker Redis connected: {redis_host}:{redis_port}/{redis_db}")
    
    # 测试连接
    conn.ping()
    
    return conn


def main():
    """启动 RQ Worker"""
    logger.info("Starting RQ Worker...")
    
    # 获取 Redis 连接（Worker 专用配置）
    try:
        conn = get_worker_redis_connection()
        logger.info("Redis connection established")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        sys.exit(1)
    
    # 监听的队列列表（按优先级排序）
    queues = ['default', 'ingest', 'extract', 'review']
    
    # 创建并启动 Worker
    worker = Worker(queues, connection=conn)
    
    logger.info(f"Worker listening on queues: {queues}")
    
    try:
        worker.work(logging_level="INFO")
    except KeyboardInterrupt:
        logger.info("Worker interrupted, shutting down...")
    except Exception as e:
        logger.error(f"Worker error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

