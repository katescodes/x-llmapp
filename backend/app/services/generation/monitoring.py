"""
监控和日志系统
追踪性能指标和审计日志
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """性能指标"""
    operation: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def finish(self, success: bool = True, error: Optional[str] = None):
        """完成操作"""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.success = success
        self.error = error
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "operation": self.operation,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
            "duration_ms": round(self.duration * 1000, 2) if self.duration else None,
            "success": self.success,
            "error": self.error,
            **self.metadata
        }


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._metrics: List[PerformanceMetrics] = []
    
    @contextmanager
    def track(self, operation: str, **metadata):
        """
        追踪操作性能
        
        Usage:
            with monitor.track("retrieval", section="公司简介"):
                # do retrieval
                pass
        """
        if not self.enabled:
            yield None
            return
        
        metrics = PerformanceMetrics(
            operation=operation,
            start_time=time.time(),
            metadata=metadata
        )
        
        try:
            yield metrics
            metrics.finish(success=True)
        except Exception as e:
            metrics.finish(success=False, error=str(e))
            raise
        finally:
            self._metrics.append(metrics)
            self._log_metrics(metrics)
    
    def _log_metrics(self, metrics: PerformanceMetrics):
        """记录指标日志"""
        duration_ms = round(metrics.duration * 1000, 2) if metrics.duration else 0
        
        if metrics.success:
            logger.info(
                f"[Performance] {metrics.operation} completed in {duration_ms}ms | "
                f"{' | '.join(f'{k}={v}' for k, v in metrics.metadata.items())}"
            )
        else:
            logger.error(
                f"[Performance] {metrics.operation} failed in {duration_ms}ms | "
                f"error={metrics.error} | "
                f"{' | '.join(f'{k}={v}' for k, v in metrics.metadata.items())}"
            )
    
    def get_metrics(self, operation: Optional[str] = None) -> List[PerformanceMetrics]:
        """
        获取指标
        
        Args:
            operation: 操作名称，None表示获取所有
            
        Returns:
            指标列表
        """
        if operation:
            return [m for m in self._metrics if m.operation == operation]
        return self._metrics.copy()
    
    def get_summary(self) -> Dict[str, Any]:
        """获取统计摘要"""
        if not self._metrics:
            return {}
        
        summary = {}
        operations = set(m.operation for m in self._metrics)
        
        for op in operations:
            op_metrics = [m for m in self._metrics if m.operation == op]
            durations = [m.duration for m in op_metrics if m.duration]
            success_count = sum(1 for m in op_metrics if m.success)
            
            if durations:
                summary[op] = {
                    "count": len(op_metrics),
                    "success_count": success_count,
                    "fail_count": len(op_metrics) - success_count,
                    "avg_duration_ms": round(sum(durations) / len(durations) * 1000, 2),
                    "min_duration_ms": round(min(durations) * 1000, 2),
                    "max_duration_ms": round(max(durations) * 1000, 2),
                }
        
        return summary
    
    def clear(self):
        """清空指标"""
        self._metrics.clear()


@dataclass
class AuditLog:
    """审计日志"""
    timestamp: datetime
    user_id: Optional[str]
    operation: str
    resource_type: str
    resource_id: str
    action: str  # create, read, update, delete, generate
    status: str  # success, failed
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "operation": self.operation,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "status": self.status,
            "details": self.details
        }


class AuditLogger:
    """审计日志记录器"""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._logs: List[AuditLog] = []
    
    def log(
        self,
        operation: str,
        resource_type: str,
        resource_id: str,
        action: str,
        status: str = "success",
        user_id: Optional[str] = None,
        **details
    ):
        """
        记录审计日志
        
        Args:
            operation: 操作名称
            resource_type: 资源类型（project, section, document等）
            resource_id: 资源ID
            action: 操作动作
            status: 状态
            user_id: 用户ID
            **details: 其他详情
        """
        if not self.enabled:
            return
        
        audit_log = AuditLog(
            timestamp=datetime.now(),
            user_id=user_id,
            operation=operation,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            status=status,
            details=details
        )
        
        self._logs.append(audit_log)
        self._write_log(audit_log)
    
    def _write_log(self, audit_log: AuditLog):
        """写入日志"""
        logger.info(
            f"[Audit] {audit_log.action} {audit_log.resource_type}/{audit_log.resource_id} | "
            f"operation={audit_log.operation} | status={audit_log.status} | "
            f"user={audit_log.user_id or 'system'}"
        )
    
    def get_logs(
        self,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[str] = None
    ) -> List[AuditLog]:
        """
        获取审计日志
        
        Args:
            resource_type: 资源类型过滤
            resource_id: 资源ID过滤
            action: 操作动作过滤
            
        Returns:
            审计日志列表
        """
        logs = self._logs
        
        if resource_type:
            logs = [log for log in logs if log.resource_type == resource_type]
        
        if resource_id:
            logs = [log for log in logs if log.resource_id == resource_id]
        
        if action:
            logs = [log for log in logs if log.action == action]
        
        return logs
    
    def clear(self):
        """清空日志"""
        self._logs.clear()


# 全局监控实例
_performance_monitor = None
_audit_logger = None


def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器"""
    global _performance_monitor
    if _performance_monitor is None:
        from .config_loader import get_config
        config = get_config()
        enabled = config.get("monitoring.enabled", True)
        _performance_monitor = PerformanceMonitor(enabled=enabled)
    return _performance_monitor


def get_audit_logger() -> AuditLogger:
    """获取全局审计日志记录器"""
    global _audit_logger
    if _audit_logger is None:
        from .config_loader import get_config
        config = get_config()
        enabled = config.get("monitoring.enabled", True)
        _audit_logger = AuditLogger(enabled=enabled)
    return _audit_logger

