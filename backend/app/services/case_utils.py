from __future__ import annotations

from app.schemas.case import CaseRecord


def case_to_rag_text(case: CaseRecord) -> str:
    """
    Convert a CaseRecord into a compact text block that works well for vector storage / RAG.
    """
    parts = [
        f"【案例标题】{case.title}",
        f"【情境】{case.situation}",
        f"【关键问题】{case.problem}",
        f"【采取的行动】{case.action}",
        f"【结果】{case.result}",
        f"【经验教训】{case.lessons}",
    ]
    if case.tags:
        parts.append(f"【标签】{', '.join(case.tags)}")
    return "\n".join(parts)


