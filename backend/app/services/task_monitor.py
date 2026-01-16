"""
任务监控服务

功能：
1. 定期检测卡死的任务（running状态超过阈值）
2. 自动清理卡死任务，更新为failed状态
3. 可作为后台线程或定时任务运行

解决问题：
- 后台任务异常退出时，数据库状态未同步
- 前端轮询看到running状态，但后台无进程
- 用户被阻塞无法继续操作
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


class TaskMonitor:
    """任务监控器"""
    
    def __init__(
        self, 
        db_conn,
        timeout_minutes: int = 10,
        check_interval_seconds: int = 60
    ):
        """
        初始化任务监控器
        
        Args:
            db_conn: 数据库连接
            timeout_minutes: 任务超时阈值（分钟）
            check_interval_seconds: 检查间隔（秒）
        """
        self.db_conn = db_conn
        self.timeout_minutes = timeout_minutes
        self.check_interval_seconds = check_interval_seconds
        self._running = False
        self._task = None
    
    def find_stuck_runs(self) -> List[Dict[str, Any]]:
        """
        查找卡死的任务
        
        Returns:
            List[Dict]: 卡死的任务列表
        """
        with self.db_conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    id, project_id, kind, status, progress, message,
                    started_at,
                    EXTRACT(EPOCH FROM (NOW() - started_at)) / 60 as running_minutes
                FROM tender_runs
                WHERE status = 'running'
                  AND started_at < NOW() - INTERVAL '%s minutes'
                ORDER BY started_at ASC
            """, (self.timeout_minutes,))
            
            return cur.fetchall()
    
    def fix_stuck_run(self, run_id: str) -> None:
        """
        修复单个卡死的任务
        
        Args:
            run_id: 任务ID
        """
        with self.db_conn.cursor() as cur:
            cur.execute("""
                UPDATE tender_runs
                SET status = 'failed',
                    finished_at = NOW(),
                    error = '任务超时未完成（后台进程可能已退出）',
                    message = '任务异常终止：超时未完成'
                WHERE id = %s
                  AND status = 'running'
            """, (run_id,))
            self.db_conn.commit()
            
            if cur.rowcount > 0:
                logger.warning(f"已清理卡死任务: {run_id}")
    
    async def monitor_once(self) -> int:
        """
        执行一次监控检查
        
        Returns:
            int: 修复的任务数量
        """
        try:
            stuck_runs = self.find_stuck_runs()
            
            if stuck_runs:
                logger.warning(
                    f"发现 {len(stuck_runs)} 个卡死任务 "
                    f"(超过 {self.timeout_minutes} 分钟)"
                )
                
                for run in stuck_runs:
                    logger.warning(
                        f"  - {run['id']}: {run['kind']}, "
                        f"运行 {run['running_minutes']:.1f} 分钟"
                    )
                    self.fix_stuck_run(run['id'])
                
                return len(stuck_runs)
            
            return 0
            
        except Exception as e:
            logger.error(f"任务监控检查失败: {e}", exc_info=True)
            return 0
    
    async def monitor_loop(self) -> None:
        """
        持续监控循环
        """
        logger.info(
            f"任务监控器启动 "
            f"(超时阈值: {self.timeout_minutes}分钟, "
            f"检查间隔: {self.check_interval_seconds}秒)"
        )
        
        while self._running:
            try:
                fixed_count = await self.monitor_once()
                
                if fixed_count > 0:
                    logger.info(f"本次检查修复了 {fixed_count} 个卡死任务")
                
                # 等待下次检查
                await asyncio.sleep(self.check_interval_seconds)
                
            except asyncio.CancelledError:
                logger.info("任务监控器被取消")
                break
            except Exception as e:
                logger.error(f"任务监控循环异常: {e}", exc_info=True)
                # 出错后等待一段时间再继续
                await asyncio.sleep(self.check_interval_seconds)
    
    def start(self) -> None:
        """启动监控器"""
        if self._running:
            logger.warning("任务监控器已在运行中")
            return
        
        self._running = True
        self._task = asyncio.create_task(self.monitor_loop())
        logger.info("任务监控器已启动")
    
    async def stop(self) -> None:
        """停止监控器"""
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("任务监控器已停止")


# 全局监控器实例
_monitor_instance = None


def get_monitor(db_conn, timeout_minutes: int = 10) -> TaskMonitor:
    """
    获取全局监控器实例
    
    Args:
        db_conn: 数据库连接
        timeout_minutes: 任务超时阈值
    
    Returns:
        TaskMonitor: 监控器实例
    """
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = TaskMonitor(db_conn, timeout_minutes)
    return _monitor_instance


def start_background_monitor(db_conn, timeout_minutes: int = 10) -> None:
    """
    启动后台任务监控器
    
    Args:
        db_conn: 数据库连接
        timeout_minutes: 任务超时阈值
    """
    monitor = get_monitor(db_conn, timeout_minutes)
    monitor.start()
    logger.info("后台任务监控器已启动")

