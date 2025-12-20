"""
Cutover control system for gradual migration from old to new logic.

Supports four modes:
- OLD: Use only old logic
- SHADOW: Run both old and new, compare results, return old (for testing)
- PREFER_NEW: Run new, fallback to old if new fails
- NEW_ONLY: Use only new logic

Supports gradual rollout by project_id.

Request-level forced mode (dev-only):
- Set X-Force-Mode header to override mode for the request
"""
import os
from enum import Enum
from typing import Optional, Set
from contextvars import ContextVar


class CutoverMode(str, Enum):
    """Cutover mode for gradual migration"""
    OLD = "OLD"
    SHADOW = "SHADOW"
    PREFER_NEW = "PREFER_NEW"
    NEW_ONLY = "NEW_ONLY"


class CutoverScope(str, Enum):
    """Scope for cutover gradual rollout"""
    PROJECT = "project"
    TENANT = "tenant"
    USER = "user"


# Request-level forced mode (dev-only)
forced_mode_context: ContextVar[Optional[str]] = ContextVar("forced_mode", default=None)


class CutoverConfig:
    """Cutover configuration manager"""
    
    def __init__(self):
        # Scope
        self.scope = os.getenv("CUTOVER_SCOPE", "project")
        
        # Project IDs for gradual rollout (comma-separated)
        project_ids_str = os.getenv("CUTOVER_PROJECT_IDS", "")
        self.project_ids: Set[str] = set(
            pid.strip() 
            for pid in project_ids_str.split(",") 
            if pid.strip()
        )
        
        # Mode for each capability
        self.retrieval_mode = CutoverMode(os.getenv("RETRIEVAL_MODE", "OLD"))
        self.ingest_mode = CutoverMode(os.getenv("INGEST_MODE", "OLD"))
        self.extract_mode = CutoverMode(os.getenv("EXTRACT_MODE", "OLD"))
        self.review_mode = CutoverMode(os.getenv("REVIEW_MODE", "OLD"))
        self.rules_mode = CutoverMode(os.getenv("RULES_MODE", "OLD"))
    
    def should_cutover(self, project_id: str) -> bool:
        """Check if project is in cutover rollout"""
        if not self.project_ids:
            # Empty list means no gradual rollout, apply to all
            return True
        return project_id in self.project_ids
    
    def get_mode(self, kind: str, project_id: Optional[str] = None) -> CutoverMode:
        """Get cutover mode for a specific capability and project"""
        # Request-level forced mode (dev-only)
        forced = forced_mode_context.get()
        if forced and os.getenv("DEBUG", "false").lower() in ("true", "1", "yes"):
            try:
                return CutoverMode(forced)
            except ValueError:
                pass  # Invalid forced mode, fall through to normal logic
        
        # If project_id provided and not in rollout list, return OLD
        if project_id and self.project_ids and not self.should_cutover(project_id):
            return CutoverMode.OLD
        
        # Map kind to mode
        kind_lower = kind.lower()
        if kind_lower == "retrieval":
            return self.retrieval_mode
        elif kind_lower == "ingest":
            return self.ingest_mode
        elif kind_lower == "extract":
            return self.extract_mode
        elif kind_lower == "review":
            return self.review_mode
        elif kind_lower == "rules":
            return self.rules_mode
        else:
            return CutoverMode.OLD
    
    def is_shadow(self, kind: str, project_id: Optional[str] = None) -> bool:
        """Check if in shadow mode (run both, compare)"""
        return self.get_mode(kind, project_id) == CutoverMode.SHADOW
    
    def prefer_new(self, kind: str, project_id: Optional[str] = None) -> bool:
        """Check if prefer new logic"""
        return self.get_mode(kind, project_id) == CutoverMode.PREFER_NEW
    
    def new_only(self, kind: str, project_id: Optional[str] = None) -> bool:
        """Check if use new logic only"""
        return self.get_mode(kind, project_id) == CutoverMode.NEW_ONLY
    
    def use_new_logic(self, kind: str, project_id: Optional[str] = None) -> bool:
        """Check if should use new logic (PREFER_NEW or NEW_ONLY)"""
        mode = self.get_mode(kind, project_id)
        return mode in (CutoverMode.PREFER_NEW, CutoverMode.NEW_ONLY)
    
    def use_old_logic(self, kind: str, project_id: Optional[str] = None) -> bool:
        """Check if should use old logic (OLD, SHADOW, PREFER_NEW as fallback)"""
        mode = self.get_mode(kind, project_id)
        return mode != CutoverMode.NEW_ONLY
    
    def to_dict(self) -> dict:
        """Export configuration as dict"""
        return {
            "scope": self.scope,
            "project_ids": list(self.project_ids),
            "modes": {
                "retrieval": self.retrieval_mode.value,
                "ingest": self.ingest_mode.value,
                "extract": self.extract_mode.value,
                "review": self.review_mode.value,
                "rules": self.rules_mode.value,
            }
        }


# Global instance
_cutover_config: Optional[CutoverConfig] = None


def get_cutover_config() -> CutoverConfig:
    """Get global cutover configuration"""
    global _cutover_config
    if _cutover_config is None:
        _cutover_config = CutoverConfig()
    return _cutover_config


# Convenience functions
def should_cutover(project_id: str) -> bool:
    """Check if project is in cutover rollout"""
    return get_cutover_config().should_cutover(project_id)


def get_mode(kind: str, project_id: Optional[str] = None) -> CutoverMode:
    """Get cutover mode for a specific capability"""
    return get_cutover_config().get_mode(kind, project_id)


def is_shadow(kind: str, project_id: Optional[str] = None) -> bool:
    """Check if in shadow mode"""
    return get_cutover_config().is_shadow(kind, project_id)


def prefer_new(kind: str, project_id: Optional[str] = None) -> bool:
    """Check if prefer new logic"""
    return get_cutover_config().prefer_new(kind, project_id)


def new_only(kind: str, project_id: Optional[str] = None) -> bool:
    """Check if use new logic only"""
    return get_cutover_config().new_only(kind, project_id)


def use_new_logic(kind: str, project_id: Optional[str] = None) -> bool:
    """Check if should use new logic"""
    return get_cutover_config().use_new_logic(kind, project_id)


def use_old_logic(kind: str, project_id: Optional[str] = None) -> bool:
    """Check if should use old logic"""
    return get_cutover_config().use_old_logic(kind, project_id)


def set_forced_mode(mode: Optional[str]):
    """Set forced mode for current request (dev-only)"""
    forced_mode_context.set(mode)


def get_forced_mode() -> Optional[str]:
    """Get forced mode for current request"""
    return forced_mode_context.get()

