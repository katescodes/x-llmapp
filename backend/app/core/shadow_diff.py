"""
Shadow diff logger for comparing old vs new logic results.

Used in SHADOW mode to log differences between old and new implementations
for validation before full cutover.
"""
import json
import logging
from typing import Any, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ShadowDiffLogger:
    """Logger for shadow mode differences"""
    
    @staticmethod
    def log(
        kind: str,
        project_id: str,
        old_summary: Any,
        new_summary: Any,
        diff_json: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ):
        """
        Log difference between old and new logic results.
        
        Args:
            kind: Type of operation (retrieval, ingest, extract, etc.)
            project_id: Project ID
            old_summary: Summary of old logic result
            new_summary: Summary of new logic result
            diff_json: Detailed diff if available
            metadata: Additional metadata
        """
        log_entry = {
            "type": "shadow_diff",
            "timestamp": datetime.utcnow().isoformat(),
            "kind": kind,
            "project_id": project_id,
            "old_summary": str(old_summary),
            "new_summary": str(new_summary),
            "diff": diff_json,
            "metadata": metadata or {}
        }
        
        # Log as structured JSON
        logger.info(f"SHADOW_DIFF: {json.dumps(log_entry)}")
    
    @staticmethod
    def log_error(
        kind: str,
        project_id: str,
        error: str,
        which: str,  # "old" or "new"
        metadata: Optional[Dict] = None
    ):
        """
        Log error in shadow mode execution.
        
        Args:
            kind: Type of operation
            project_id: Project ID
            error: Error message
            which: Which logic failed ("old" or "new")
            metadata: Additional metadata
        """
        log_entry = {
            "type": "shadow_error",
            "timestamp": datetime.utcnow().isoformat(),
            "kind": kind,
            "project_id": project_id,
            "error": str(error),
            "failed": which,
            "metadata": metadata or {}
        }
        
        logger.warning(f"SHADOW_ERROR: {json.dumps(log_entry)}")


# Global instance
_shadow_logger = ShadowDiffLogger()


def log_shadow_diff(
    kind: str,
    project_id: str,
    old_summary: Any,
    new_summary: Any,
    diff_json: Optional[Dict] = None,
    metadata: Optional[Dict] = None
):
    """Log shadow mode difference"""
    _shadow_logger.log(kind, project_id, old_summary, new_summary, diff_json, metadata)


def log_shadow_error(
    kind: str,
    project_id: str,
    error: str,
    which: str,
    metadata: Optional[Dict] = None
):
    """Log shadow mode error"""
    _shadow_logger.log_error(kind, project_id, error, which, metadata)

