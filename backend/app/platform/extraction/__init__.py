"""
Platform Extraction Module
通用抽取引擎基础设施
"""

from .types import ExtractionSpec, ExtractionResult, RetrievalTrace, RetrievedChunk
from .engine import ExtractionEngine
from .parallel import (
    ParallelExtractor,
    ParallelExtractionTask,
    ParallelExtractionResult,
    extract_stages_parallel,
    extract_projects_parallel,
)

__all__ = [
    # Types
    "ExtractionSpec",
    "ExtractionResult",
    "RetrievalTrace",
    "RetrievedChunk",
    # Engine
    "ExtractionEngine",
    # Parallel
    "ParallelExtractor",
    "ParallelExtractionTask",
    "ParallelExtractionResult",
    "extract_stages_parallel",
    "extract_projects_parallel",
]

