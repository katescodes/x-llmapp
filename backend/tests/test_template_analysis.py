"""
模板 LLM 分析器单元测试
"""
import json
import pytest
from app.services.template.docx_extractor import DocxBlock, DocxExtractResult, BlockType
from app.services.template.llm_analyzer import TemplateLlmAnalyzer
from app.services.template.template_spec import TemplateSpec
from app.services.template.spec_validator import get_validator, SchemaValidationException


@pytest.fixture
def sample_extract_result():
    """创建测试用的 DocxExtractResult"""
    blocks = [
        DocxBlock(
            id="block-1",
            type=BlockType.PARAGRAPH,
            text="本模板使用说明",
            style_name="标题 1",
            outline_level=1,
            sequence=0
        ),
        DocxBlock(
            id="block-2",
            type=BlockType.PARAGRAPH,
            text="请按照以下格式填写",
            style_name="正文",
            sequence=1
        ),
        DocxBlock(
            id="block-3",
            type=BlockType.PARAGRAPH,
            text="第一卷 商务标",
            style_name="标题 1",
            outline_level=1,
            sequence=2
        ),
        DocxBlock(
            id="block-4",
            type=BlockType.PARAGRAPH,
            text="1. 投标函",
            style_name="标题 2",
            outline_level=2,
            num_id=1,
            ilvl=0,
            sequence=3
        ),
    ]
    
    style_stats = {
        "style_count": {"标题 1": 2, "标题 2": 1, "正文": 1},
        "heading_styles": ["标题 1", "标题 2"],
        "top_styles": ["标题 1", "标题 2", "正文"],
        "total_blocks": 4
    }
    
    numbering_stats = {
        "numbering_count": {1: 1},
        "level_count": {0: 1},
        "has_numbering": True
    }
    
    header_footer_stats = {
        "header_count": 0,
        "footer_count": 0,
        "has_header": False,
        "has_footer": False
    }
    
    return DocxExtractResult(
        blocks=blocks,
        style_stats=style_stats,
        numbering_stats=numbering_stats,
        header_footer_stats=header_footer_stats
    )


def test_template_spec_validator():
    """测试 TemplateSpec 校验器"""
    validator = get_validator()
    
    # 有效的 JSON
    valid_json = json.dumps({
        "version": "v1",
        "language": "zh-CN",
        "base_policy": {
            "mode": "KEEP_ALL",
            "exclude_block_ids": ["block-1", "block-2"]
        },
        "style_hints": {
            "heading1_style": "标题 1",
            "heading2_style": "标题 2"
        },
        "outline": [
            {
                "id": "node-1",
                "title": "第一卷",
                "level": 1,
                "order_no": 1,
                "required": True,
                "children": []
            }
        ],
        "merge_policy": {
            "template_defines_structure": True,
            "ai_only_fill_missing": True
        },
        "diagnostics": {
            "confidence": 0.95,
            "warnings": [],
            "ignored_as_instructions_block_ids": ["block-1", "block-2"]
        }
    })
    
    # 应该通过校验
    data = validator.validate(valid_json)
    assert data["version"] == "v1"
    assert data["diagnostics"]["confidence"] == 0.95


def test_template_spec_validator_invalid():
    """测试无效 JSON 的校验"""
    validator = get_validator()
    
    # 缺少必需字段
    invalid_json = json.dumps({
        "version": "v1"
    })
    
    # 应该抛出异常
    with pytest.raises(SchemaValidationException):
        validator.validate(invalid_json)


def test_template_spec_from_json():
    """测试 TemplateSpec.from_json"""
    spec_json = json.dumps({
        "version": "v1",
        "language": "zh-CN",
        "base_policy": {
            "mode": "KEEP_ALL",
            "exclude_block_ids": ["block-1"]
        },
        "style_hints": {
            "heading1_style": "标题 1"
        },
        "outline": [],
        "merge_policy": {
            "template_defines_structure": True,
            "ai_only_fill_missing": True
        },
        "diagnostics": {
            "confidence": 0.8,
            "warnings": ["测试警告"]
        }
    })
    
    spec = TemplateSpec.from_json(spec_json)
    
    assert spec.version == "v1"
    assert spec.base_policy.mode.value == "KEEP_ALL"
    assert len(spec.base_policy.exclude_block_ids) == 1
    assert spec.diagnostics.confidence == 0.8


def test_template_spec_to_json():
    """测试 TemplateSpec.to_json"""
    from app.services.template.template_spec import (
        TemplateSpec, BasePolicy, BasePolicyMode,
        StyleHints, MergePolicy, Diagnostics
    )
    
    spec = TemplateSpec(
        version="v1",
        language="zh-CN",
        base_policy=BasePolicy(
            mode=BasePolicyMode.KEEP_ALL,
            exclude_block_ids=["block-1"]
        ),
        style_hints=StyleHints(heading1_style="标题 1"),
        outline=[],
        merge_policy=MergePolicy(
            template_defines_structure=True,
            ai_only_fill_missing=True
        ),
        diagnostics=Diagnostics(confidence=0.9)
    )
    
    json_str = spec.to_json()
    data = json.loads(json_str)
    
    assert data["version"] == "v1"
    assert data["base_policy"]["mode"] == "KEEP_ALL"
    assert data["diagnostics"]["confidence"] == 0.9


@pytest.mark.asyncio
async def test_llm_analyzer_extract_json():
    """测试 LLM 输出 JSON 提取"""
    analyzer = TemplateLlmAnalyzer()
    
    # 测试 markdown code fence 包裹
    text1 = """这是一些解释文字
```json
{"version": "v1", "language": "zh-CN"}
```
更多文字"""
    
    result1 = analyzer._extract_json(text1)
    data1 = json.loads(result1)
    assert data1["version"] == "v1"
    
    # 测试纯 JSON
    text2 = '{"version": "v1", "language": "zh-CN"}'
    result2 = analyzer._extract_json(text2)
    data2 = json.loads(result2)
    assert data2["version"] == "v1"


def test_outline_merger():
    """测试 OutlineMerger"""
    from app.services.template.outline_merger import OutlineMerger
    from app.services.template.template_spec import (
        TemplateSpec, OutlineNode, MergePolicy
    )
    
    # 创建模板 spec
    spec = TemplateSpec()
    spec.merge_policy = MergePolicy(
        template_defines_structure=True,
        ai_only_fill_missing=True,
        preserve_template_order=True
    )
    spec.outline = [
        OutlineNode(
            id="node-1",
            title="第一卷",
            level=1,
            order_no=1,
            children=[]
        ),
        OutlineNode(
            id="node-2",
            title="第二卷",
            level=1,
            order_no=2,
            children=[]
        )
    ]
    
    # AI 生成的节点
    ai_nodes = [
        {"title": "第一卷", "level": 1, "numbering": "1"},
        {"title": "第三卷", "level": 1, "numbering": "3"},  # AI 补充的
    ]
    
    # 合并
    merged = OutlineMerger.merge_with_template(ai_nodes, spec)
    
    # 验证：应该包含模板的两个节点 + AI 补充的一个
    assert len(merged) >= 2
    titles = [n["title"] for n in merged]
    assert "第一卷" in titles
    assert "第二卷" in titles


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
