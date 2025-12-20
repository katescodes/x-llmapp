"""
申报书目录 Schema (v2)
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, root_validator


class DirectoryNodeV2(BaseModel):
    """单个目录节点"""
    title: str = Field(..., min_length=1, description="章节标题")
    level: int = Field(..., ge=1, le=6, description="章节层级")
    order_no: int = Field(..., description="章节序号")
    parent_ref: Optional[str] = Field(None, description="引用父节点标题或本地ID")
    required: bool = Field(True, description="该章节是否为必须提交")
    notes: Optional[str] = Field(None, description="说明或备注")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="证据片段ID列表")

    def to_dict_exclude_none(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class DirectoryDataV2(BaseModel):
    """目录数据"""
    nodes: List[DirectoryNodeV2] = Field(..., min_items=1, description="目录节点列表")

    def to_dict_exclude_none(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class DirectoryResultV2(BaseModel):
    """目录生成结果"""
    data: DirectoryDataV2 = Field(..., description="结构化目录数据")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="所有引用的证据片段ID列表")

    @root_validator(pre=True)
    def collect_all_evidence_chunk_ids(cls, values):
        """自动收集所有节点的 evidence_chunk_ids 到顶层"""
        data = values.get("data")
        if data and isinstance(data, dict) and "nodes" in data:
            all_ids = set()
            for node in data["nodes"]:
                if isinstance(node, dict) and "evidence_chunk_ids" in node:
                    all_ids.update(node["evidence_chunk_ids"])
            values["evidence_chunk_ids"] = sorted(list(all_ids))
        return values

    def to_dict_exclude_none(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)

