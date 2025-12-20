"""
LLM Orchestrator 相关的数据模型

支持需求理解、模块化蓝图、详尽度控制的两段式编排
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class IntentType(str, Enum):
    """用户意图类型"""
    INFORMATION = "information"  # 获取信息/知识综述
    HOWTO = "howto"  # 如何做某事/教程
    DECISION = "decision"  # 选型/决策
    TROUBLESHOOT = "troubleshoot"  # 排障/调试
    WRITING = "writing"  # 写作/生成文档
    COMPUTE = "compute"  # 计算/推理
    RESEARCH = "research"  # 研究/深度分析
    OTHER = "other"  # 其他


class DetailLevel(str, Enum):
    """详尽度级别"""
    BRIEF = "brief"  # 精简：只要结论/一句话/不解释
    NORMAL = "normal"  # 正常：平衡的详细程度
    DETAILED = "detailed"  # 详细：展开/更细/深入/多例子


class RequirementJSON(BaseModel):
    """需求理解（Extractor Call 输出）"""
    
    intent: IntentType = Field(
        default=IntentType.INFORMATION,
        description="用户意图类型"
    )
    
    goal: str = Field(
        ...,
        description="用户的核心目标（一句话概括）"
    )
    
    constraints: List[str] = Field(
        default_factory=list,
        description="约束条件（时间、预算、技术栈等）"
    )
    
    preferences: List[str] = Field(
        default_factory=list,
        description="用户偏好（风格、优先级等）"
    )
    
    assumptions: List[str] = Field(
        default_factory=list,
        description="合理假设（当信息不足时）"
    )
    
    success_criteria: List[str] = Field(
        default_factory=list,
        description="成功标准（怎样算满足需求）"
    )
    
    clarification_questions: List[str] = Field(
        default_factory=list,
        max_length=3,
        description="澄清问题（<=3，必须给可选项）"
    )
    
    detail_level: DetailLevel = Field(
        default=DetailLevel.NORMAL,
        description="推断的详尽度级别"
    )
    
    blueprint_modules: List[str] = Field(
        default_factory=list,
        description="答案应包含的模块列表"
    )


class ChatSection(BaseModel):
    """答案的一个模块"""
    
    id: str = Field(
        ...,
        description="模块唯一标识（如 align_summary, core_answer）"
    )
    
    title: str = Field(
        ...,
        description="模块标题（中文）"
    )
    
    markdown: str = Field(
        ...,
        description="模块内容（Markdown 格式）"
    )
    
    collapsed: bool = Field(
        default=False,
        description="是否默认折叠"
    )


class OrchestratedResponse(BaseModel):
    """编排器输出（替代原 ChatResponse.answer）"""
    
    sections: List[ChatSection] = Field(
        default_factory=list,
        description="结构化答案模块列表"
    )
    
    followups: List[str] = Field(
        default_factory=list,
        max_length=3,
        description="可选补充信息提示（非强制追问）"
    )
    
    meta: Optional[dict] = Field(
        default=None,
        description="元数据（intent、detail_level、blueprint等）"
    )


# 预定义模块ID和标题映射
MODULE_TITLES = {
    "align_summary": "理解确认",
    "core_answer": "核心答案",
    "timeline": "时间线",
    "concepts": "核心概念",
    "controversy": "争议与口径",
    "examples": "示例与案例",
    "comparison": "对比矩阵",
    "checklist": "检查清单",
    "steps": "执行步骤",
    "pitfalls": "常见陷阱",
    "next_steps": "下一步建议",
    "sources": "参考来源",
    "verification": "核对路径",
    "alternatives": "替代方案",
    "prerequisites": "前置条件",
    "outline": "大纲结构",
}


# 根据意图类型推荐的模块蓝图
INTENT_BLUEPRINTS = {
    IntentType.INFORMATION: [
        "align_summary",
        "core_answer",
        "timeline",
        "concepts",
        "controversy",
        "verification",
        "sources",
    ],
    IntentType.HOWTO: [
        "align_summary",
        "core_answer",
        "prerequisites",
        "steps",
        "examples",
        "pitfalls",
        "next_steps",
    ],
    IntentType.DECISION: [
        "align_summary",
        "core_answer",
        "comparison",
        "examples",
        "next_steps",
        "sources",
    ],
    IntentType.TROUBLESHOOT: [
        "align_summary",
        "core_answer",
        "checklist",
        "steps",
        "pitfalls",
        "next_steps",
    ],
    IntentType.WRITING: [
        "align_summary",
        "outline",
        "core_answer",
        "examples",
        "next_steps",
    ],
    IntentType.COMPUTE: [
        "align_summary",
        "core_answer",
        "steps",
        "verification",
    ],
    IntentType.RESEARCH: [
        "align_summary",
        "core_answer",
        "timeline",
        "controversy",
        "sources",
        "verification",
    ],
    IntentType.OTHER: [
        "align_summary",
        "core_answer",
        "next_steps",
    ],
}

