"""
Platform Extraction Module 骨架测试
验证模块可导入和基础功能
"""
import json
import pytest

from app.platform.extraction.types import (
    ExtractionSpec,
    ExtractionResult,
    RetrievalTrace,
    RetrievedChunk,
)
from app.platform.extraction.context import build_marked_context
from app.platform.extraction.json_utils import extract_json, repair_json
from app.platform.extraction.engine import ExtractionEngine


def test_types_can_be_instantiated():
    """测试类型可以实例化"""
    chunk = RetrievedChunk(
        chunk_id="chunk_001",
        text="Test content",
        meta={"page_no": 1},
        score=0.95
    )
    assert chunk.chunk_id == "chunk_001"
    assert chunk.text == "Test content"
    
    spec = ExtractionSpec(
        prompt="Test prompt",
        queries="test query",
        topk_per_query=10,
        topk_total=50
    )
    assert spec.prompt == "Test prompt"
    assert spec.topk_per_query == 10
    
    trace = RetrievalTrace(
        retrieval_provider="new",
        retrieval_strategy="multi_query",
        retrieved_count_total=10
    )
    assert trace.retrieval_provider == "new"
    
    result = ExtractionResult(
        data={"key": "value"},
        evidence_chunk_ids=["chunk_001"],
        raw_model_output="test output"
    )
    assert result.data == {"key": "value"}


def test_build_marked_context_format():
    """测试 build_marked_context 输出格式稳定"""
    chunks = [
        {"chunk_id": "chunk_001", "text": "First chunk content"},
        {"chunk_id": "chunk_002", "text": "Second chunk content"},
    ]
    
    ctx = build_marked_context(chunks)
    
    # 验证格式
    assert '[0] <chunk id="chunk_001">' in ctx
    assert '[1] <chunk id="chunk_002">' in ctx
    assert "First chunk content" in ctx
    assert "Second chunk content" in ctx
    assert "</chunk>" in ctx


def test_build_marked_context_empty():
    """测试空输入"""
    ctx = build_marked_context([])
    assert ctx == ""


def test_extract_json_plain():
    """测试提取纯 JSON"""
    text = '{"key": "value", "count": 42}'
    result = extract_json(text)
    assert result == {"key": "value", "count": 42}


def test_extract_json_with_markdown():
    """测试提取 markdown 代码块中的 JSON"""
    text = """
Here is the result:
```json
{
  "key": "value",
  "items": [1, 2, 3]
}
```
    """
    result = extract_json(text)
    assert result == {"key": "value", "items": [1, 2, 3]}


def test_extract_json_with_plain_code_block():
    """测试提取普通代码块中的 JSON"""
    text = """
```
{"status": "ok"}
```
    """
    result = extract_json(text)
    assert result == {"status": "ok"}


def test_repair_json_single_quotes():
    """测试修复单引号 JSON"""
    text = "{'key': 'value', 'count': 42}"
    result = repair_json(text)
    assert result == {"key": "value", "count": 42}


def test_repair_json_fails_on_invalid():
    """测试无法修复的 JSON 会抛出异常"""
    text = "{invalid json"
    with pytest.raises(json.JSONDecodeError):
        repair_json(text)


def test_extraction_engine_can_be_imported():
    """测试引擎可以导入和实例化"""
    engine = ExtractionEngine()
    assert engine is not None


@pytest.mark.asyncio
async def test_extraction_engine_run_not_implemented():
    """测试引擎 run 方法（骨架版本应抛出 NotImplementedError）"""
    engine = ExtractionEngine()
    spec = ExtractionSpec(prompt="test", queries="test query")
    
    with pytest.raises(NotImplementedError):
        await engine.run(
            spec=spec,
            retriever=None,
            llm=None,
            project_id="test_project"
        )

