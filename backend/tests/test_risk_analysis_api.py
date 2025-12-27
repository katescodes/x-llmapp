"""
测试风险分析聚合接口
"""
import pytest
import uuid
import json
from psycopg.types.json import Json
from fastapi.testclient import TestClient
from app.services.db.postgres import _get_pool
from app.main import app


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture
def test_project_id():
    """创建测试项目"""
    pool = _get_pool()
    project_id = str(uuid.uuid4())
    kb_id = str(uuid.uuid4())
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            # 创建测试项目
            cur.execute("""
                INSERT INTO tender_projects (id, kb_id, name, description, owner_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (project_id, kb_id, "测试项目-风险分析", "测试风险分析接口", "test_user"))
            conn.commit()
    
    yield project_id
    
    # 清理
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tender_requirements WHERE project_id = %s", (project_id,))
            cur.execute("DELETE FROM tender_projects WHERE id = %s", (project_id,))
            conn.commit()


@pytest.fixture
def sample_requirements(test_project_id):
    """插入样例 requirements 数据"""
    pool = _get_pool()
    
    requirements = [
        # 1. doc_002 - 包含"否则视为无效投标" → consequence=reject
        {
            "requirement_id": "doc_002",
            "dimension": "doc_structure",
            "req_type": "format",
            "requirement_text": "投标文件须由法定代表人或其授权代理人签字并加盖单位公章，否则视为无效投标。",
            "is_hard": True,
            "allow_deviation": False,
            "value_schema_json": None,
            "evidence_chunk_ids": ["CHUNK_016"],
        },
        # 2. price_001 - 包含"无效投标" → consequence=reject
        {
            "requirement_id": "price_001",
            "dimension": "price",
            "req_type": "threshold",
            "requirement_text": "投标总价不得超过招标控制价1000000元，超过招标控制价的投标为无效投标。",
            "is_hard": True,
            "allow_deviation": False,
            "value_schema_json": {"type": "number", "max": 1000000, "unit": "元", "comparison": "<="},
            "evidence_chunk_ids": ["CHUNK_013"],
        },
        # 3. tech_001 - 硬性但无明确 reject 关键词 → hard_requirement
        {
            "requirement_id": "tech_001",
            "dimension": "technical",
            "req_type": "threshold",
            "requirement_text": "CPU频率不低于2.5GHz，内存不低于16GB，硬盘不低于512GB SSD。",
            "is_hard": True,
            "allow_deviation": False,
            "value_schema_json": {"type": "object", "cpu_ghz": {"min": 2.5}, "memory_gb": {"min": 16}},
            "evidence_chunk_ids": ["CHUNK_006"],
        },
        # 4. biz_002 - 包含"违约金" → consequence=score_loss
        {
            "requirement_id": "biz_002",
            "dimension": "business",
            "req_type": "must_not_deviate",
            "requirement_text": "逾期交付的，每逾期一天，承包人须向招标人支付合同价款万分之五的违约金。",
            "is_hard": True,
            "allow_deviation": False,
            "value_schema_json": None,
            "evidence_chunk_ids": ["CHUNK_011"],
        },
        # 5. qual_003 - scoring soft → checklist
        {
            "requirement_id": "qual_003",
            "dimension": "qualification",
            "req_type": "scoring",
            "requirement_text": "企业信誉评分（满分5分）：获得省级及以上荣誉的得5分，市级荣誉得3分，县级荣誉得1分。",
            "is_hard": False,
            "allow_deviation": False,
            "value_schema_json": {"type": "scoring", "max_score": 5},
            "evidence_chunk_ids": ["CHUNK_003"],
        },
        # 6. other_001 - 0元保证金 soft → checklist
        {
            "requirement_id": "other_001",
            "dimension": "other",
            "req_type": "must_provide",
            "requirement_text": "本项目不收取投标保证金。",
            "is_hard": False,
            "allow_deviation": False,
            "value_schema_json": {"type": "number", "value": 0, "unit": "元"},
            "evidence_chunk_ids": ["CHUNK_020"],
        },
        # 7. sched_001 - allow_deviation=true（将生成额外提醒行）
        {
            "requirement_id": "sched_001",
            "dimension": "schedule_quality",
            "req_type": "threshold",
            "requirement_text": "施工总工期不超过180天，自开工令发出之日起计算。投标人承诺的工期短于招标要求的，应提供相应保障措施。",
            "is_hard": True,
            "allow_deviation": True,
            "value_schema_json": {"type": "number", "max": 180, "unit": "天", "comparison": "<=", "allow_better": True},
            "evidence_chunk_ids": ["CHUNK_017"],
        },
        # 8. qual_001 - qualification 硬性 → high severity
        {
            "requirement_id": "qual_001",
            "dimension": "qualification",
            "req_type": "must_provide",
            "requirement_text": "投标人须具有有效的营业执照，营业执照须在有效期内，经营范围须包含本项目采购内容。",
            "is_hard": True,
            "allow_deviation": False,
            "value_schema_json": None,
            "evidence_chunk_ids": ["CHUNK_001"],
        },
    ]
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            for req in requirements:
                # 将 dict 包装为 Json 对象用于 JSONB 字段
                value_schema = Json(req["value_schema_json"]) if req["value_schema_json"] else None
                
                cur.execute("""
                    INSERT INTO tender_requirements (
                        id, project_id, requirement_id, dimension, req_type,
                        requirement_text, is_hard, allow_deviation,
                        value_schema_json, evidence_chunk_ids
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    str(uuid.uuid4()),
                    test_project_id,
                    req["requirement_id"],
                    req["dimension"],
                    req["req_type"],
                    req["requirement_text"],
                    req["is_hard"],
                    req["allow_deviation"],
                    value_schema,
                    req["evidence_chunk_ids"],
                ))
            conn.commit()
    
    return requirements


def test_risk_analysis_api_basic(client, test_project_id, sample_requirements):
    """测试风险分析接口基本功能"""
    response = client.get(f"/api/apps/tender/projects/{test_project_id}/risk-analysis")
    
    assert response.status_code == 200
    data = response.json()
    
    # 验证结构
    assert "must_reject_table" in data
    assert "checklist_table" in data
    assert "stats" in data
    
    # 验证统计
    stats = data["stats"]
    assert stats["total_requirements"] == 8  # 8条样例数据
    assert stats["must_reject_count"] >= 5  # 至少5条硬性要求
    assert stats["checklist_count"] >= 2  # 至少2条软性要求


def test_risk_analysis_consequence_inference(client, test_project_id, sample_requirements):
    """测试 consequence 推断"""
    response = client.get(f"/api/apps/tender/projects/{test_project_id}/risk-analysis")
    assert response.status_code == 200
    data = response.json()
    
    must_reject = data["must_reject_table"]
    
    # 找到 doc_002（包含"视为无效投标"）
    doc_002 = next((r for r in must_reject if r["requirement_id"] == "doc_002"), None)
    assert doc_002 is not None
    assert doc_002["consequence"] == "reject"
    
    # 找到 price_001（包含"无效投标"）
    price_001 = next((r for r in must_reject if r["requirement_id"] == "price_001"), None)
    assert price_001 is not None
    assert price_001["consequence"] == "reject"
    
    # 找到 biz_002（包含"违约金"）
    biz_002 = next((r for r in must_reject if r["requirement_id"] == "biz_002"), None)
    assert biz_002 is not None
    assert biz_002["consequence"] == "score_loss"
    
    # 找到 tech_001（硬性但无关键词）
    tech_001 = next((r for r in must_reject if r["requirement_id"] == "tech_001"), None)
    assert tech_001 is not None
    assert tech_001["consequence"] == "hard_requirement"


def test_risk_analysis_severity_inference(client, test_project_id, sample_requirements):
    """测试 severity 推断"""
    response = client.get(f"/api/apps/tender/projects/{test_project_id}/risk-analysis")
    assert response.status_code == 200
    data = response.json()
    
    must_reject = data["must_reject_table"]
    
    # reject → high
    doc_002 = next((r for r in must_reject if r["requirement_id"] == "doc_002"), None)
    assert doc_002["severity"] == "high"
    
    # qualification dimension → high
    qual_001 = next((r for r in must_reject if r["requirement_id"] == "qual_001"), None)
    assert qual_001["severity"] == "high"


def test_risk_analysis_checklist_table(client, test_project_id, sample_requirements):
    """测试 checklist_table（注意事项表）"""
    response = client.get(f"/api/apps/tender/projects/{test_project_id}/risk-analysis")
    assert response.status_code == 200
    data = response.json()
    
    checklist = data["checklist_table"]
    
    # 找到 qual_003（scoring）
    qual_003 = next((r for r in checklist if r["requirement_id"] == "qual_003"), None)
    assert qual_003 is not None
    assert qual_003["category"] == "得分点"
    assert qual_003["severity"] == "low"
    
    # 找到 other_001（保证金说明）
    other_001 = next((r for r in checklist if r["requirement_id"] == "other_001"), None)
    assert other_001 is not None
    assert other_001["category"] == "保证金说明"


def test_risk_analysis_suggestion_generation(client, test_project_id, sample_requirements):
    """测试 suggestion 生成"""
    response = client.get(f"/api/apps/tender/projects/{test_project_id}/risk-analysis")
    assert response.status_code == 200
    data = response.json()
    
    must_reject = data["must_reject_table"]
    checklist = data["checklist_table"]
    
    # must_provide 类型
    qual_001 = next((r for r in must_reject if r["requirement_id"] == "qual_001"), None)
    assert "准备并按要求签章提交" in qual_001["suggestion"]
    
    # threshold 类型
    tech_001 = next((r for r in must_reject if r["requirement_id"] == "tech_001"), None)
    assert "阈值要求" in tech_001["suggestion"]
    
    # scoring 类型
    qual_003 = next((r for r in checklist if r["requirement_id"] == "qual_003"), None)
    assert "得分点" in qual_003["suggestion"]


def test_risk_analysis_sorting(client, test_project_id, sample_requirements):
    """测试排序逻辑"""
    response = client.get(f"/api/apps/tender/projects/{test_project_id}/risk-analysis")
    assert response.status_code == 200
    data = response.json()
    
    must_reject = data["must_reject_table"]
    
    # qualification 应该排在前面
    first_item = must_reject[0]
    assert first_item["dimension"] in ["qualification", "price", "doc_structure"]


def test_risk_analysis_empty_project(client, test_project_id):
    """测试空项目（无 requirements）"""
    response = client.get(f"/api/apps/tender/projects/{test_project_id}/risk-analysis")
    assert response.status_code == 200
    data = response.json()
    
    assert data["must_reject_table"] == []
    assert data["checklist_table"] == []
    assert data["stats"]["total_requirements"] == 0


def test_risk_analysis_evidence_chunk_ids(client, test_project_id, sample_requirements):
    """测试 evidence_chunk_ids 正确返回"""
    response = client.get(f"/api/apps/tender/projects/{test_project_id}/risk-analysis")
    assert response.status_code == 200
    data = response.json()
    
    must_reject = data["must_reject_table"]
    
    # 验证至少有一个有 evidence_chunk_ids
    has_evidence = any(len(r["evidence_chunk_ids"]) > 0 for r in must_reject)
    assert has_evidence
    
    # 验证 doc_002 的 evidence
    doc_002 = next((r for r in must_reject if r["requirement_id"] == "doc_002"), None)
    assert "CHUNK_016" in doc_002["evidence_chunk_ids"]

