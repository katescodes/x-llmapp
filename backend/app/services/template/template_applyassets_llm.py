"""
LLM 生成模板 ApplyAssets
用于智能识别模板中应保留/删除的内容和插入锚点
"""
from __future__ import annotations
import json
import logging

logger = logging.getLogger(__name__)


def build_applyassets_prompt(template_name: str, blocks: list[dict]) -> str:
    """
    构建 LLM prompt 用于生成 applyAssets
    
    Args:
        template_name: 模板名称
        blocks: 文档块列表
        
    Returns:
        prompt 字符串
    """
    # 只发送必要信息，避免 prompt 过长
    payload = [{
        "blockId": b["blockId"],
        "type": b["type"],
        "styleName": b.get("styleName"),
        "textSnippet": (b.get("text") or "")[:240],  # 限制每个块的文本长度
        "markerFlags": b.get("markerFlags") or {}
    } for b in blocks]
    
    return f"""你是"Word 标书模板分析器"。我会给你一个 DOCX 模板拆出来的 blocks 列表（按顺序）。

你的任务：判断哪些 block 属于模板底板必须保留（封面、声明、固定章节框架、附录结构等），哪些属于示例/填写说明/占位符/演示内容应删除或在生成时替换。
同时找出"正文内容插入点(anchor)"——生成标书目录与正文应从那里开始插入。

请输出严格 JSON，符合 schema：
{{
  "anchors":[{{"blockId":"b12","type":"marker|semantic","reason":"...","confidence":0.0-1.0}}],
  "keepPlan":{{
    "keepBlockIds":["b0","b1",...],
    "deleteBlockIds":["b20",...],
    "notes":"..."
  }},
  "policy":{{
    "confidence":0.0-1.0,
    "warnings":[...]
  }}
}}

分类判断规则：
- 必须保留：封面、声明页、章节框架（标题层级结构）、附录标题框架。
- 应删除：带"示例/样例/参考/填写说明/请在此处填写/（填写）/【填写】/演示项目"等指示性文本。
- Anchor 优先级：
  1) 包含 [[CONTENT]] 的 block
  2) 语义上表示"正文开始/投标文件正文/目录后正文"的标题 block
  3) 如果都没有，返回空 anchors，并在 warnings 说明需要模板加 [[CONTENT]]

模板名：{template_name}
blocks: {json.dumps(payload, ensure_ascii=False)}

请直接返回 JSON，不要有其他文字。"""


def validate_applyassets(apply: dict, blocks: list[dict]) -> dict:
    """
    验证和修正 LLM 生成的 applyAssets
    
    Args:
        apply: LLM 返回的原始结果
        blocks: 文档块列表
        
    Returns:
        修正后的 applyAssets
    """
    if not isinstance(apply, dict):
        logger.error("LLM 返回非字典类型，使用空结果")
        return {
            "anchors": [],
            "keepPlan": {
                "keepBlockIds": [],
                "deleteBlockIds": [],
                "notes": ""
            },
            "policy": {
                "confidence": 0.0,
                "warnings": ["LLM_INVALID_JSON"]
            }
        }
    
    # 确保必要字段存在
    apply.setdefault("anchors", [])
    apply.setdefault("keepPlan", {
        "keepBlockIds": [],
        "deleteBlockIds": [],
        "notes": ""
    })
    apply.setdefault("policy", {
        "confidence": 0.0,
        "warnings": []
    })
    
    # 验证 blockId 有效性
    block_ids = {b["blockId"] for b in blocks}
    
    keep_plan = apply["keepPlan"]
    keep_ids = keep_plan.get("keepBlockIds", [])
    delete_ids = keep_plan.get("deleteBlockIds", [])
    
    # 过滤无效的 blockId
    valid_keep = [bid for bid in keep_ids if bid in block_ids]
    valid_delete = [bid for bid in delete_ids if bid in block_ids]
    
    if len(valid_keep) != len(keep_ids):
        logger.warning(f"过滤了 {len(keep_ids) - len(valid_keep)} 个无效的 keepBlockIds")
        apply["policy"]["warnings"].append(f"过滤了无效的 keepBlockIds")
    
    if len(valid_delete) != len(delete_ids):
        logger.warning(f"过滤了 {len(delete_ids) - len(valid_delete)} 个无效的 deleteBlockIds")
        apply["policy"]["warnings"].append(f"过滤了无效的 deleteBlockIds")
    
    apply["keepPlan"]["keepBlockIds"] = valid_keep
    apply["keepPlan"]["deleteBlockIds"] = valid_delete
    
    return apply


def get_fallback_apply_assets() -> dict:
    """
    获取默认的 applyAssets（当 LLM 失败时使用）
    
    Returns:
        默认 applyAssets
    """
    return {
        "anchors": [],
        "keepPlan": {
            "keepBlockIds": [],
            "deleteBlockIds": [],
            "notes": "使用默认清理策略：删除锚点后所有内容"
        },
        "policy": {
            "confidence": 0.5,
            "warnings": ["LLM 分析未执行，使用默认策略"]
        }
    }
