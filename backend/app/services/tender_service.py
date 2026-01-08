"""
招投标应用 - 业务逻辑层 (Service)
包含 LLM 调用、文件解析、规则抽取、审核叠加等核心逻辑
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from docx import Document  # type: ignore[import-untyped]
from fastapi import UploadFile

from app.config import get_settings, get_feature_flags
from app.schemas.project_delete import ProjectDeletePlanResponse, ProjectDeleteRequest
from app.services.dao.tender_dao import TenderDAO
from app.services.project_delete import ProjectDeletionOrchestrator
from app.services.template.docx_extractor import DocxBlockExtractor
from app.services.template.llm_analyzer import TemplateLlmAnalyzer, get_analysis_cache
from app.services.template.template_spec import TemplateSpec, create_minimal_spec, BasePolicyMode
from app.services.template.outline_merger import OutlineMerger
from app.services.template.template_parse_preview import DocxTemplateDeterministicParser, TemplatePreviewGenerator

logger = logging.getLogger(__name__)


# ==================== 工具函数 ====================

def _safe_mkdir(p: str):
    """安全创建目录"""
    os.makedirs(p, exist_ok=True)


def _sha256(b: bytes) -> str:
    """计算SHA256哈希"""
    return hashlib.sha256(b).hexdigest()


def _extract_json(text: str) -> Any:
    """
    从 LLM 输出中容错提取 JSON
    支持 markdown code fence 包裹的 JSON
    """
    if not text:
        raise ValueError("empty llm output")
    
    # 尝试提取 markdown code fence 中的内容
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if m:
        text = m.group(1).strip()
    
    # 尝试提取第一个 JSON 对象或数组
    m2 = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text.strip())
    if m2:
        text = m2.group(1)
    
    return json.loads(text)


def _chunk_text(text: str, max_chars: int = 1200, overlap: int = 150) -> List[str]:
    """
    将文本分块
    
    Args:
        text: 原始文本
        max_chars: 每块最大字符数
        overlap: 重叠字符数
    
    Returns:
        文本块列表
    """
    text = (text or "").strip()
    if not text:
        return []
    
    out = []
    i = 0
    n = len(text)
    while i < n:
        j = min(n, i + max_chars)
        out.append(text[i:j])
        if j >= n:
            break
        i = max(0, j - overlap)
    return out


def _read_text_from_file_bytes(filename: str, data: bytes) -> str:
    """
    从文件字节中读取文本
    支持 txt/md/pdf/docx 格式
    """
    name = (filename or "").lower()
    
    # TXT/MD 文件
    if name.endswith(".txt") or name.endswith(".md"):
        try:
            return data.decode("utf-8", errors="ignore")
        except Exception:
            return data.decode(errors="ignore")
    
    # PDF 文件
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(data))
            parts = []
            for page in reader.pages:
                parts.append(page.extract_text() or "")
            return "\n".join(parts)
        except Exception:
            return ""
    
    # DOCX 文件
    if name.endswith(".docx"):
        try:
            import io
            from docx import Document as Doc
            d = Doc(io.BytesIO(data))
            return "\n".join([p.text for p in d.paragraphs if p.text])
        except Exception:
            return ""
    
    # 兜底：尝试 UTF-8 解码
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _build_marked_context(chunks: List[Dict[str, Any]]) -> str:
    """
    将 chunks 构建成带标记的上下文
    用于 LLM 能够引用 chunk_id
    """
    parts = []
    for c in chunks:
        parts.append(f"[DOC {c.get('doc_id')} CHUNK {c.get('chunk_id')} POS {c.get('position')}]")
        parts.append(c.get("content") or "")
        parts.append("")  # 空行
    return "\n".join(parts).strip()


# ==================== LLM 调用数据结构 ====================

@dataclass
class LLMCall:
    """LLM 调用参数"""
    model_id: Optional[str]
    messages: List[Dict[str, str]]


# ==================== Service 主类 ====================

class TenderService:
    """招投标业务逻辑服务"""

    def __init__(self, dao: TenderDAO, llm_orchestrator: Any, jobs_service: Any = None):
        """
        初始化 Service
        
        Args:
            dao: TenderDAO 实例
            llm_orchestrator: LLM 调度器（duck typing）
            jobs_service: 平台任务服务（可选，用于旁路双写）
        """
        self.dao = dao
        self.llm = llm_orchestrator
        self.jobs_service = jobs_service
        self.settings = get_settings()
        self.feature_flags = get_feature_flags()
        self._docx_extractor: Optional[DocxBlockExtractor] = None
        self._llm_analyzer: Optional[TemplateLlmAnalyzer] = None
        self._deletion_orchestrator: Optional[ProjectDeletionOrchestrator] = None

    @property
    def docx_extractor(self) -> DocxBlockExtractor:
        """延迟初始化 DocxBlockExtractor"""
        if self._docx_extractor is None:
            self._docx_extractor = DocxBlockExtractor()
        return self._docx_extractor

    @property
    def llm_analyzer(self) -> TemplateLlmAnalyzer:
        """延迟初始化 TemplateLlmAnalyzer"""
        if self._llm_analyzer is None:
            self._llm_analyzer = TemplateLlmAnalyzer()
        return self._llm_analyzer
    
    @property
    def deletion_orchestrator(self) -> ProjectDeletionOrchestrator:
        """延迟初始化 ProjectDeletionOrchestrator"""
        if self._deletion_orchestrator is None:
            self._deletion_orchestrator = ProjectDeletionOrchestrator(self.dao.pool)
        return self._deletion_orchestrator

    # ==================== LLM 调用（Duck Typing） ====================

    def _llm_text(self, call: LLMCall) -> str:
        """
        调用 LLM 并返回文本
        使用 duck typing 兼容多种 orchestrator 接口
        """
        if not self.llm:
            raise RuntimeError("LLM orchestrator not available")

        # 尝试常见的方法名
        last_error = None
        for method_name in ("chat", "complete", "generate", "run", "ask"):
            fn = getattr(self.llm, method_name, None)
            if not fn:
                continue
            
            try:
                # 尝试 (messages, model_id) 签名
                res = fn(messages=call.messages, model_id=call.model_id)
                
                # 处理返回值
                if isinstance(res, str):
                    return res
                if isinstance(res, dict):
                    # 尝试常见的键
                    for k in ("content", "text", "output"):
                        if k in res and isinstance(res[k], str):
                            return res[k]
                    # OpenAI-like 格式
                    if "choices" in res and res["choices"]:
                        ch = res["choices"][0]
                        if isinstance(ch, dict):
                            msg = ch.get("message") or {}
                            if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                                return msg["content"]
                # 兜底
                return str(res)
            
            except TypeError as e:
                # 尝试 (prompt, model_id) 签名
                try:
                    prompt = "\n".join([f"{m['role']}: {m['content']}" for m in call.messages])
                    res = fn(prompt=prompt, model_id=call.model_id)
                    return res if isinstance(res, str) else str(res)
                except Exception as inner_e:
                    last_error = inner_e
                    continue
            except Exception as e:
                # 保存错误并继续尝试其他方法
                last_error = e
                continue

        # 如果所有方法都失败了，抛出最后一个错误
        if last_error:
            raise RuntimeError(f"LLM call failed: {str(last_error)}") from last_error
        else:
            raise RuntimeError("No compatible LLM method found on orchestrator")

    # ==================== LLM Prompts ====================

    PROJECT_INFO_PROMPT = """
你是招投标助手。请从"招标文件原文片段"中抽取项目信息，并输出严格 JSON：
{
  "data": {
    "projectName": "项目名称",
    "ownerName": "招标人/业主",
    "agencyName": "代理机构",
    "bidDeadline": "投标截止时间",
    "bidOpeningTime": "开标时间",
    "budget": "预算金额",
    "maxPrice": "最高限价",
    "bidBond": "投标保证金",
    "schedule": "工期要求",
    "quality": "质量要求",
    "location": "项目地点/交付地点",
    "contact": "联系人与电话",

    "technicalParameters": [
      {
        "category": "功能/技术要求/设备参数/性能指标/接口协议 等分类（可选）",
        "item": "条目标题或功能点",
        "requirement": "要求描述（可包含型号、数量、范围等）",
        "parameters": [
          {"name": "参数名", "value": "参数值/指标", "unit": "单位（可空）", "remark": "备注（可空）"}
        ],
        "evidence_chunk_ids": ["CHUNK_xxx"]
      }
    ],

    "businessTerms": [
      {
        "term": "条款名称（付款/验收/质保/交付/违约/发票/税费/服务/培训/售后等）",
        "requirement": "条款内容与要求（尽量结构化描述）",
        "evidence_chunk_ids": ["CHUNK_xxx"]
      }
    ],

    "scoringCriteria": {
      "evaluationMethod": "评标办法/评分办法（如综合评分法、最低评标价法等，没有则空字符串）",
      "items": [
        {
          "category": "评分大项（商务/技术/价格/资信/服务等）",
          "item": "评分细则/子项",
          "score": "分值（数字或原文）",
          "rule": "得分规则/扣分条件/加分条件",
          "evidence_chunk_ids": ["CHUNK_xxx"]
        }
      ]
    }
  },
  "evidence_chunk_ids": ["CHUNK_xxx", "CHUNK_yyy"]
}

要求：
- data 里的字段可以为空字符串；数组字段可为空数组；scoringCriteria 可以为 {} 但必须存在
- technicalParameters/businessTerms/scoringCriteria.items 如果文中找不到就输出 []
- evidence_chunk_ids 必须来自上下文标记中的 CHUNK id
- 不要输出除 JSON 以外的任何文字
"""

    RISK_PROMPT = """
你是招投标助手。请从"招标文件原文片段"中提取招标要求与注意事项，输出严格 JSON 数组：
[
  {
    "risk_type": "mustReject",  // 或 "other"
    "title": "风险标题",
    "description": "详细描述",
    "suggestion": "建议措施",
    "severity": "critical",  // low, medium, high, critical
    "tags": ["资格", "保证金"],
    "evidence_chunk_ids": ["chunk_xxx"]
  }
]

要求：
- mustReject：缺关键资质/未按要求签章/保证金/格式性废标等"必废标"点
- other：易错点、扣分点、时间节点、装订/份数/密封等注意事项
- evidence_chunk_ids 必须来自上下文 CHUNK id
- 不要输出除 JSON 以外的任何文字
"""

    DIRECTORY_PROMPT = """
你是招投标助手。你要生成的是【投标文件/响应文件】的目录结构，而不是招标文件本身的目录。

你会收到“招标文件原文片段”（带 CHUNK id）。你必须：
- 只从招标文件中与“投标文件组成/响应文件组成/投标文件格式/提交资料/附件表格/投标文件应包括”相关的段落中抽取要求；
- 生成投标文件目录（按投标文件应提交的材料来组织），不得复刻招标文件目录章节（如：招标公告、投标人须知、评标办法、合同条款、技术规范正文等）。

【严重禁止】如果你输出包含以下任何“招标文件目录式章节”，基本可判为错误（除非招标明确要求投标文件也要按这些章节提交响应）：
- 招标公告 / 投标人须知 / 评标办法 / 合同条款 / 技术规范 / 工程量清单说明 / 开标评标办法 / 资格预审文件 等。

输出严格 JSON 数组（按 numbering 从小到大）：
[
  {
    "numbering": "1",
    "level": 1,
    "title": "投标函及投标函附录",
    "required": true,
    "notes": "可选备注（如：按招标文件附件格式）",
    "evidence_chunk_ids": ["<来自上下文标记的 CHUNK id>"]
  }
]

生成规则：
1) 目录应该体现“投标人要交哪些文件”，而不是“招标文件在讲什么”。
2) 优先从招标文件明确要求中抽取：必须提交/应提交/须提供/按附件格式/表X/附录X。
3) 若招标文件未明确列出完整目录，你可以按行业惯例补齐一个合理的投标文件结构（required=false，evidence_chunk_ids=[]，notes 写“行业惯例补齐”）。
4) 常见（可作为兜底）一级结构建议（按你判断可合并/删减）：
   - 投标函及附录（投标函、报价函/响应函、法定代表人身份证明、授权委托书）
   - 资格审查文件（营业执照、资质、业绩、财务、信誉、承诺等）
   - 商务响应文件（商务条款响应/偏离表、服务承诺、项目管理/进度计划等）
   - 技术响应文件（技术方案、技术参数响应/偏离表、设备/系统说明等）
   - 报价文件（开标一览表/报价汇总表、分项报价表、清单/明细）
   - 其他资料与附件（招标要求的其他表格、声明、证明材料）
5) numbering 必须用 1/1.1/1.1.1 形式，level 与 numbering 对应。
6) evidence_chunk_ids 必须来自上下文标记中的 CHUNK id；找不到证据就用 []。
7) 不要输出除 JSON 以外的任何文字。
"""

    CUSTOM_RULE_PROMPT = """
你是"企业内部招投标审核规则抽取器"。请从"规则文件原文片段"中抽取结构化规则，输出严格 JSON 数组：
[
  {
    "dimension": "资格审查",  // 资格审查|报价审查|技术审查|商务审查|工期与质量|文档结构|其他
    "title": "规则标题",
    "check": "可执行的检查描述（清晰、具体）",
    "rigid": true,  // true表示不满足就应判 fail
    "severity": "high",  // low, medium, high, critical
    "tags": ["资质", "业绩"],
    "evidence_chunk_ids": ["chunk_xxx"]
  }
]

要求：
- rigid=true 表示刚性要求，不满足就应判 fail 或 mustReject
- evidence_chunk_ids 必须来自上下文 CHUNK id
- 不要输出除 JSON 以外的任何文字
"""

    # 注意：CUSTOM_RULE_PROMPT 暂时保留，用于未来可能的规则文件解析功能
    # 当前版本中，规则文件直接作为原文片段叠加，不再单独抽取为 JSON 规则集

    REVIEW_PROMPT = """
你是招投标"投标文件审核员"。你会收到：
1) 招标文件原文片段（带 CHUNK id）
2) 投标文件原文片段（带 CHUNK id）
3) 可选：自定义审核规则文件原文片段（带 CHUNK id，可为空）

请输出严格 JSON 数组：
[
  {
    "dimension": "资格审查",  // 资格审查|报价审查|技术审查|商务审查|工期与质量|文档结构|其他
    "requirement_text": "招标要求（摘要）",
    "response_text": "投标响应（摘要）",
    "result": "pass",  // pass, risk, fail
    "remark": "原因/建议/缺失点/冲突点",
    "rigid": false,  // 是否刚性要求
    "tender_evidence_chunk_ids": ["chunk_xxx"],
    "bid_evidence_chunk_ids": ["chunk_yyy"]
  }
]

规则：
- 结果含义：pass=明确符合；fail=明确不符合；risk=不确定/缺材料/冲突/需要人工确认
- 自定义规则文件（如有）与招标要求"叠加"：也要产出对应的审核项（可合并到同维度）
- evidence_chunk_ids 必须来自上下文 CHUNK id
- 不要输出除 JSON 以外的任何文字
"""

    # ==================== 文件入库 ====================

    def _ingest_to_kb(
        self,
        kb_id: str,
        filename: str,
        kind: str,
        bidder_name: Optional[str],
        data: bytes,
    ) -> str:
        """
        REMOVED: Legacy KB ingest path deleted.
        
        This method previously wrote to kb_documents/kb_chunks (deprecated tables).
        All ingest must now go through platform/ingest/v2_service.py (DocStore).
        
        If you see this error, you are using OLD/SHADOW mode which is no longer supported.
        Set INGEST_MODE=NEW_ONLY in your environment.
        """
        raise RuntimeError(
            f"[REMOVED] Legacy tender pipeline (_ingest_to_kb) has been deleted. "
            f"NEW_ONLY mode is required. Use platform/ingest/v2_service.py (DocStore). "
            f"File: {filename}, kind: {kind}"
        )

    def _load_context_by_assets(
        self,
        project_id: str,
        kinds: List[str],
        bidder_name: Optional[str],
        bid_asset_ids: List[str],
        limit: int,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        根据资产条件加载上下文 chunks
        
        Args:
            kinds: 资产类型列表（如 ["tender"] 或 ["bid"]）
            bidder_name: 投标人名称（用于过滤 bid）
            bid_asset_ids: 投标资产ID列表（精确指定）
            limit: 最多加载多少个 chunks
        
        Returns:
            (chunks, doc_ids)
        """
        # 获取所有资产
        assets = self.dao.list_assets(project_id)
        
        # 过滤资产
        filtered = []
        for a in assets:
            if a.get("kind") not in kinds:
                continue
            
            # 特殊处理 bid 资产
            if a.get("kind") == "bid":
                if bid_asset_ids:
                    # 精确指定
                    if a.get("id") not in bid_asset_ids:
                        continue
                elif bidder_name:
                    # 按投标人名称过滤
                    if (a.get("bidder_name") or "") != bidder_name:
                        continue
            
            filtered.append(a)

        # 提取 doc_ids 并加载 chunks
        doc_ids = [a.get("kb_doc_id") for a in filtered if a.get("kb_doc_id")]
        chunks = self.dao.load_chunks_by_doc_ids(doc_ids, limit=limit)
        return chunks, doc_ids

    # ==================== 公开 API ====================

    async def import_assets(
        self,
        project_id: str,
        kind: str,
        files: List[UploadFile],
        bidder_name: Optional[str],
    ) -> List[Dict[str, Any]]:
        """
        项目内上传文件并自动绑定
        
        Args:
            project_id: 项目ID
            kind: tender | bid | template | custom_rule | company_profile | tech_doc | case_study | finance_doc | cert_doc
            files: 上传的文件列表
            bidder_name: 投标人名称（kind=bid 时必填）
        
        Returns:
            创建的资产列表
        """
        # 获取项目信息
        proj = self.dao.get_project(project_id)
        if not proj:
            raise ValueError("project not found")

        kb_id = proj["kb_id"]
        assets_out = []

        # 创建存储目录
        base_dir = os.path.join("data", "tender_assets", project_id)
        _safe_mkdir(base_dir)

        for f in files:
            b = await f.read()  # 异步读取文件
            filename = f.filename or "file"
            mime = getattr(f, "content_type", None)
            size = len(b)

            kb_doc_id = None
            storage_path: Optional[str] = None
            doc_version_id = None  # 新增：DocStore 版本ID
            tpl_meta = {}  # 初始化 meta_json
            
            # ✅ 检测是否为图片文件
            file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
            image_exts = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff', 'svg'}
            is_image = file_ext in image_exts
            
            # ✅ 如果是图片文件，只保存不入库向量
            if is_image:
                storage_path = os.path.join(base_dir, f"{kind}_{uuid.uuid4().hex}_{filename}")
                with open(storage_path, "wb") as w:
                    w.write(b)
                
                # 创建资产记录（不入库向量）
                asset = self.dao.create_asset(
                    project_id=project_id,
                    kind=kind,
                    filename=filename,
                    storage_path=storage_path,
                    file_size=size,
                    mime_type=mime,
                    kb_doc_id=None,
                    bidder_name=bidder_name,
                    meta_json={"asset_type": "image", "skip_ingest": True}
                )
                assets_out.append(asset)
                continue  # 跳过后续的入库流程

            if kind == "template":
                # 模板文件：保存到磁盘
                storage_path = os.path.join(base_dir, f"{kind}_{uuid.uuid4().hex}_{filename}")
                with open(storage_path, "wb") as w:
                    w.write(b)
                
                # 新增：解析模板目录/样式摘要，写入 meta_json
                tpl_meta = self._parse_template_meta(storage_path)
            
            # Step 4: 新入库逻辑（cutover 控制）
            # 只支持 NEW_ONLY 模式，删除OLD/SHADOW/PREFER_NEW分支
            ingest_v2_result = None
            
            # ✅ 扩展：template 和企业资料也需要入库到知识库
            if kind in ("tender", "bid", "custom_rule", "template", "company_profile", "tech_doc", "case_study", "finance_doc", "cert_doc"):
                from app.core.cutover import get_cutover_config
                cutover = get_cutover_config()
                ingest_mode = cutover.get_mode("ingest", project_id)
                tpl_meta["ingest_mode_used"] = ingest_mode.value
                
                # 强制要求 NEW_ONLY
                if ingest_mode.value != "NEW_ONLY":
                    raise RuntimeError(
                        f"[REMOVED] Legacy tender pipeline deleted. "
                        f"INGEST_MODE={ingest_mode.value} is no longer supported. "
                        f"Set INGEST_MODE=NEW_ONLY. File: {filename}"
                    )
                
                # 只走 NEW_ONLY 路径
                from app.platform.ingest.v2_service import IngestV2Service
                from app.services.db.postgres import _get_pool
                pool = _get_pool()
                ingest_v2 = IngestV2Service(pool)
                
                # 确保 storage_path 存在
                if not storage_path:
                    storage_path = os.path.join(base_dir, f"{kind}_{uuid.uuid4().hex}_{filename}")
                    with open(storage_path, "wb") as w:
                        w.write(b)
                
                temp_asset_id = f"temp_{uuid.uuid4().hex}"
                
                # 映射文档类型到知识库分类
                from app.utils.doc_type_mapper import map_doc_type_to_kb_category
                kb_category = map_doc_type_to_kb_category(kind)
                
                ingest_v2_result = await ingest_v2.ingest_asset_v2(
                    project_id=project_id,
                    asset_id=temp_asset_id,
                    file_bytes=b,
                    filename=filename,
                    doc_type=kb_category,  # 使用映射后的知识库分类
                    owner_id=proj.get("owner_id"),
                    storage_path=storage_path,
                    kb_id=kb_id,  # ✅ 传递 kb_id
                )
                
                # 新入库成功
                tpl_meta["doc_version_id"] = ingest_v2_result.doc_version_id
                tpl_meta["ingest_v2_status"] = "success"
                tpl_meta["ingest_v2_segments"] = ingest_v2_result.segment_count
                
                # 重要：从 doc_version_id 获取 document_id 作为 kb_doc_id
                try:
                    with self.dao.pool.connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("""
                                SELECT document_id 
                                FROM document_versions 
                                WHERE id = %s
                            """, (ingest_v2_result.doc_version_id,))
                            row = cur.fetchone()
                            if row:
                                # pool 使用 dict_row factory，所以 row 是 dict
                                kb_doc_id = row['document_id']
                                logger.info(f"✓ IngestV2: Got document_id={kb_doc_id} from doc_version_id={ingest_v2_result.doc_version_id}")
                            else:
                                logger.error(f"❌ IngestV2: document_versions table has no record for doc_version_id={ingest_v2_result.doc_version_id}")
                except Exception as e:
                    logger.error(f"❌ Failed to query document_id from document_versions: {e}", exc_info=True)
                
                logger.info(
                    f"IngestV2 NEW_ONLY success: "
                    f"doc_version_id={ingest_v2_result.doc_version_id} "
                    f"document_id={kb_doc_id} "
                    f"segments={ingest_v2_result.segment_count}"
                )
            
            # REMOVED: SHADOW mode ingest deleted (lines 612-659)
            # NEW_ONLY is now the only supported mode
            
            # 旧双写逻辑（兼容 Step 2，如果 DOCSTORE_DUALWRITE=true 且未被 v2 覆盖）
            if self.feature_flags.DOCSTORE_DUALWRITE and "doc_version_id" not in tpl_meta:
                try:
                    from app.platform.docstore.service import DocStoreService
                    from app.services.db.postgres import _get_pool
                    pool = _get_pool()
                    docstore = DocStoreService(pool)
                    
                    document_id = docstore.create_document(
                        namespace="tender",
                        doc_type=kind,
                        owner_id=proj.get("owner_id")
                    )
                    
                    doc_version_id = docstore.create_document_version(
                        document_id=document_id,
                        filename=filename,
                        file_content=b,
                        storage_path=storage_path
                    )
                    
                    tpl_meta["doc_version_id"] = doc_version_id
                    
                except Exception as e:
                    logger.error(f"DocStore dual-write failed: {e}", exc_info=True)
            
            # 旁路解析：RuleSet（如果启用且 kind=custom_rule）
            if kind == "custom_rule" and self.feature_flags.RULESET_PARSE_ENABLED:
                try:
                    from app.services.platform.ruleset_service import RuleSetService
                    from app.services.db.postgres import _get_pool
                    pool = _get_pool()
                    ruleset_service = RuleSetService(pool)
                    
                    # 1. 解码文件内容为文本
                    try:
                        content_text = b.decode('utf-8')
                    except UnicodeDecodeError:
                        # 尝试其他编码
                        try:
                            content_text = b.decode('gbk')
                        except Exception:
                            content_text = b.decode('latin-1', errors='ignore')
                    
                    # 2. 解析并校验
                    is_valid, message, parsed_data = ruleset_service.parse_and_validate(content_text)
                    
                    # 3. 创建 rule_set（如果不存在）
                    rule_set_id = None
                    existing_rule_sets = ruleset_service.list_rule_sets_by_project(project_id, limit=1)
                    if existing_rule_sets:
                        rule_set_id = existing_rule_sets[0]["id"]
                    else:
                        rule_set_id = ruleset_service.create_rule_set(
                            namespace="tender",
                            scope="project",
                            name=f"规则集-{project_id}",
                            project_id=project_id
                        )
                    
                    # 4. 创建 rule_set_version
                    validate_status = "valid" if is_valid else "invalid"
                    rule_set_version_id = ruleset_service.create_version(
                        rule_set_id=rule_set_id,
                        content_yaml=content_text,
                        validate_status=validate_status,
                        validate_message=message
                    )
                    
                    # 5. 将 rule_set_version_id 记录到 meta_json
                    tpl_meta["rule_set_version_id"] = rule_set_version_id
                    tpl_meta["validate_status"] = validate_status
                    tpl_meta["validate_message"] = message
                    
                    print(f"[INFO] RuleSet parsed: version_id={rule_set_version_id}, status={validate_status}")
                    
                except Exception as e:
                    # 降级：RuleSet 解析失败不影响主流程
                    print(f"[WARN] Failed to parse RuleSet: {e}")
                    tpl_meta["validate_status"] = "error"
                    tpl_meta["validate_message"] = f"Parsing error: {str(e)}"

            # 创建资产记录
            asset = self.dao.create_asset(
                project_id=project_id,
                kind=kind,
                filename=filename,
                mime_type=mime,
                size_bytes=size,
                kb_doc_id=kb_doc_id,
                storage_path=storage_path,
                bidder_name=bidder_name,
                meta_json=tpl_meta,
            )
            
            # ✅ 同步创建 kb_documents 记录（让文档在知识库中可见）
            # 诊断日志：记录是否满足条件
            logger.info(f"Check kb_document creation: kb_doc_id={kb_doc_id}, kind={kind}, kb_id={kb_id}")
            
            if not kb_doc_id:
                logger.warning(f"⚠️ kb_doc_id is None for {filename}, skipping kb_documents creation. doc_version_id={tpl_meta.get('doc_version_id')}")
            elif kind not in ("tender", "bid", "custom_rule", "template"):  # ✅ 添加 template
                logger.warning(f"⚠️ kind '{kind}' not in allowed list for {filename}, skipping kb_documents creation")
            else:
                try:
                    from app.services.dao import kb_dao
                    
                    # 计算文件哈希
                    import hashlib
                    content_hash = hashlib.sha256(b).hexdigest()
                    
                    # 映射文档分类
                    if kind == "tender":
                        kb_category = "tender_doc"
                    elif kind == "bid":
                        kb_category = "bid_doc"
                    elif kind == "custom_rule":
                        kb_category = "custom_rule"
                    elif kind == "template":
                        kb_category = "template_doc"
                    else:
                        kb_category = "general_doc"
                    
                    logger.info(f"Creating kb_document: kb_id={kb_id}, doc_id={kb_doc_id}, filename={filename}, category={kb_category}")
                    
                    # 创建 kb_documents 记录（使用已有的 document_id）
                    kb_dao.create_kb_document_with_id(
                        kb_id=kb_id,
                        doc_id=kb_doc_id,  # 使用 documents.id
                        filename=filename,
                        source="tender_upload",
                        content_hash=content_hash,
                        status="ready",
                        kb_category=kb_category,
                        meta={
                            "project_id": project_id,
                            "asset_id": asset["id"],
                            "kind": kind,
                            "bidder_name": bidder_name,
                            "doc_version_id": tpl_meta.get("doc_version_id"),
                            "size": size,
                        }
                    )
                    logger.info(f"✓ Successfully created kb_document: kb_id={kb_id}, doc_id={kb_doc_id}, filename={filename}")
                except Exception as e:
                    logger.error(f"❌ Failed to create kb_document for {filename}: {e}", exc_info=True)
                    # 不影响主流程，继续执行
            
            assets_out.append(asset)

        return assets_out

    def list_assets(self, project_id: str) -> List[Dict[str, Any]]:
        """列出项目的所有资产"""
        return self.dao.list_assets(project_id)

    def delete_asset(self, project_id: str, asset_id: str):
        """
        删除资产
        - 删除知识库文档及其chunks（如果有）
        - 删除磁盘文件（如果是模板文件）
        - 删除项目文档绑定记录（兼容旧API）
        - 删除数据库asset记录
        - 如果删除的文档被项目信息、风险、目录、审核等引用，相关的evidence_chunk_ids会自动失效
        """
        import os
        import logging
        logger = logging.getLogger(__name__)
        
        # 获取资产信息
        asset = self.dao.get_asset_by_id(asset_id)
        if not asset:
            raise ValueError("Asset not found")
        
        if asset["project_id"] != project_id:
            raise ValueError("Asset does not belong to this project")
        
        # 获取项目信息（用于获取 kb_id）
        proj = self.dao.get_project(project_id)
        if not proj:
            raise ValueError("Project not found")
        
        kb_id = proj.get("kb_id")
        kb_doc_id = asset.get("kb_doc_id")
        
        # 1. 删除知识库文档及其chunks
        if kb_doc_id and kb_id:
            try:
                from app.services import kb_service
                # 传入 skip_asset_cleanup=True，避免循环调用
                # kb_service.delete_document 会删除：
                # - kb_documents 记录
                # - kb_chunks 记录
                # - milvus 向量
                # 但不会再次删除 asset（避免循环）
                kb_service.delete_document(kb_id, kb_doc_id, skip_asset_cleanup=True)
                logger.info(f"Deleted KB document {kb_doc_id} from knowledge base {kb_id}")
            except Exception as e:
                # 记录错误但继续删除，避免孤儿数据
                logger.warning(f"Failed to delete KB document {kb_doc_id}: {e}")
        
        # 2. 删除磁盘文件（模板文件）
        if asset.get("storage_path"):
            try:
                storage_path = asset["storage_path"]
                if os.path.exists(storage_path):
                    os.remove(storage_path)
                    logger.info(f"Deleted file {storage_path}")
            except Exception as e:
                logger.warning(f"Failed to delete file {storage_path}: {e}")
        
        # 3. 删除项目文档绑定记录（兼容旧API）
        if kb_doc_id:
            try:
                self.dao._execute(
                    "DELETE FROM tender_project_documents WHERE project_id=%s AND kb_doc_id=%s",
                    (project_id, kb_doc_id)
                )
                logger.info(f"Deleted project document binding for doc {kb_doc_id}")
            except Exception as e:
                logger.warning(f"Failed to delete project document binding: {e}")
        
        # 4. 删除asset记录
        self.dao.delete_asset(asset_id)
        logger.info(f"Deleted asset {asset_id} from project {project_id}")
        
        # 注意：不需要显式删除 tender_project_info, tender_directory_nodes, 
        # tender_review_items 中引用该文档 chunks 的数据，因为：
        # - 这些表中的 evidence_chunk_ids 是数组类型，删除chunk后这些ID会自然失效
        # - 保留这些记录可以让用户知道曾经有哪些分析结果，只是证据链断了
        # - 如果需要重新分析，用户可以重新上传文档并运行相应的提取任务

    def extract_project_info(
        self,
        project_id: str,
        model_id: Optional[str],
        run_id: Optional[str] = None,
        owner_id: Optional[str] = None,
    ):
        """
        抽取项目信息
        
        REMOVED: Only NEW_ONLY mode supported.
        OLD/SHADOW/PREFER_NEW modes have been deleted.
        """
        # 强制检查模式
        from app.core.cutover import get_cutover_config
        cutover = get_cutover_config()
        extract_mode = cutover.get_mode("extract", project_id)
        
        if extract_mode.value != "NEW_ONLY":
            raise RuntimeError(
                f"[REMOVED] Legacy tender extraction deleted. "
                f"EXTRACT_MODE={extract_mode.value} is no longer supported. "
                f"Set EXTRACT_MODE=NEW_ONLY. Method: extract_project_info"
            )
        
        # 旁路双写：创建 platform job（如果启用）
        job_id = None
        if self.feature_flags.PLATFORM_JOBS_ENABLED and self.jobs_service and run_id:
            try:
                job_id = self.jobs_service.create_job(
                    namespace="tender",
                    biz_type="extract_project_info",
                    biz_id=project_id,
                    owner_id=owner_id,
                    initial_status="running",
                    initial_message="正在提取项目信息..."
                )
            except Exception as e:
                # 降级：job 创建失败不影响主流程
                print(f"[WARN] Failed to create platform job: {e}")
        
        try:
            # 只执行 NEW_ONLY 路径
            import asyncio
            from app.works.tender.extract_v2_service import ExtractV2Service
            from app.services.db.postgres import _get_pool
            
            logger.info(f"NEW_ONLY extract_project_info: using v2 for project={project_id}")
            pool = _get_pool()
            extract_v2 = ExtractV2Service(pool, self.llm)
            
            # v2 抽取
            v2_result = asyncio.run(extract_v2.extract_project_info_v2(
                project_id=project_id,
                model_id=model_id,
                run_id=run_id
            ))
            
            # ✅ v2_result 已经是完整的 V3 结构，包含 schema_version 和六大类
            # 提取证据和追踪信息
            eids = v2_result.get("evidence_chunk_ids") or []
            trace = v2_result.get("retrieval_trace") or {}
            
            # ✅ 构建要保存的数据：只保留核心字段（六大类 + schema_version）
            data_to_save = {
                "schema_version": v2_result.get("schema_version", "tender_info_v3"),
                "project_overview": v2_result.get("project_overview", {}),
                "bidder_qualification": v2_result.get("bidder_qualification", {}),
                "evaluation_and_scoring": v2_result.get("evaluation_and_scoring", {}),
                "business_terms": v2_result.get("business_terms", {}),
                "technical_requirements": v2_result.get("technical_requirements", {}),
                "document_preparation": v2_result.get("document_preparation", {}),
            }
            
            obj = {"data_json": data_to_save, "evidence_chunk_ids": eids}
            
            # ✅ 数据已经在_extract_project_info_staged中保存过了，这里不需要重复保存
            # 只更新run状态即可
            logger.info(f"项目信息提取完成，准备更新run状态: project={project_id}")
            
            # 更新运行状态
            if run_id:
                # 构建result_json，确保trace是dict格式
                result_json_data = {
                    **obj,
                    "extract_v2_status": "ok",
                    "extract_mode_used": "NEW_ONLY",
                }
                
                # 处理trace：如果是list则包装成dict，如果是dict则展开
                if isinstance(trace, dict):
                    result_json_data.update(trace)
                elif isinstance(trace, list):
                    result_json_data["retrieval_trace"] = trace
                else:
                    result_json_data["retrieval_trace"] = trace
                
                self.dao.update_run(
                    run_id, "success", progress=1.0, 
                    message="项目信息提取完成", 
                    result_json=result_json_data
                )
            
            logger.info(f"NEW_ONLY extract_project_info: v2 succeeded for project={project_id}")
            
            # 旁路双写：更新 job 成功（如果启用）
            if job_id and self.jobs_service:
                try:
                    self.jobs_service.finish_job_success(
                        job_id=job_id,
                        result={"summary": "项目信息提取完成"},
                        message="成功"
                    )
                except Exception as e:
                    print(f"[WARN] Failed to update platform job: {e}")
        
        except Exception as e:
            logger.error(f"项目信息提取失败: {e}", exc_info=True)
            
            # 更新run状态为失败
            if run_id:
                self.dao.update_run(
                    run_id, "failed", progress=0, 
                    message=f"提取失败: {str(e)[:200]}"
                )
            
            # 更新 job 失败状态（如果启用）
            if job_id and self.jobs_service:
                try:
                    self.jobs_service.finish_job_fail(job_id=job_id, error=str(e))
                except Exception as je:
                    print(f"[WARN] Failed to update platform job on error: {je}")
            # 重新抛出原始异常
            raise

    # extract_risks 已删除
    # 请使用 POST /api/apps/tender/projects/{project_id}/extract/risks (实际调用requirements_v1)
    # risks模块已废弃，统一使用requirements模块

    def _filter_chunks_for_bid_directory(self, chunks: List[Dict[str, Any]], limit: int = 80) -> List[Dict[str, Any]]:
        keywords = [
            "投标文件", "响应文件", "文件组成", "应包括", "须提供", "提交", "附件", "格式", "表", "附录",
            "投标函", "授权委托书", "法定代表人", "开标一览表", "报价", "分项报价", "清单",
            "资格", "资质", "业绩", "财务", "信誉", "承诺", "偏离表", "技术响应", "商务响应"
        ]
        scored = []
        for c in chunks:
            t = (c.get("content") or "")
            s = 0
            for k in keywords:
                if k in t:
                    s += 2
            # 轻微加分：越短越可能是条款/清单类
            if 0 < len(t) < 1200:
                s += 1
            scored.append((s, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        # 至少保留一些头部，避免全是0分
        top = [c for s, c in scored if s > 0][:limit]
        if len(top) < 20:
            top = [c for _, c in scored[:limit]]
        return top

    def _looks_like_tender_toc(self, nodes: List[Dict[str, Any]]) -> bool:
        tender_like = ["招标公告", "投标人须知", "评标办法", "合同条款", "技术规范", "工程量清单", "开标", "资格预审"]
        titles = " ".join([(n.get("title") or "") for n in nodes[:20] if isinstance(n, dict)])
        hit = sum(1 for k in tender_like if k in titles)
        return hit >= 2  # 命中两个以上基本可判为跑偏

    def generate_directory(
        self,
        project_id: str,
        model_id: Optional[str],
        run_id: Optional[str] = None,
    ):
        """生成目录 - 使用 V2 引擎"""
        # 1. 检查模式
        from app.core.cutover import get_cutover_config
        cutover = get_cutover_config()
        extract_mode = cutover.get_mode("extract", project_id)
        if extract_mode.value != "NEW_ONLY":
            raise RuntimeError("Legacy directory generation deleted. Set EXTRACT_MODE=NEW_ONLY")
        
        # 2. 创建 platform job (可选)
        if self.jobs_service:
            try:
                job_id = self.jobs_service.create_job(
                    job_type="extract",
                    project_id=project_id,
                    run_id=run_id
                )
                logger.info(f"[generate_directory] platform job created: {job_id}")
            except Exception as e:
                logger.warning(f"[generate_directory] Failed to create platform job: {e}")
        
        # 3. 调用 V2 抽取服务
        from app.works.tender.extract_v2_service import ExtractV2Service
        from app.services.db.postgres import _get_pool
        from app.platform.utils.async_runner import run_async
        
        pool = _get_pool()
        extract_v2 = ExtractV2Service(pool, self.llm)
        
        v2_result = run_async(extract_v2.generate_directory_v2(
            project_id=project_id,
            model_id=model_id,
            run_id=run_id
        ))
        
        # 4. 提取 nodes 和生成模式信息
        nodes = v2_result.get("data", {}).get("nodes", [])
        if not nodes:
            raise ValueError("Directory nodes empty")
        
        # 保存生成模式信息
        generation_mode = v2_result.get("generation_mode", "llm")
        fast_stats = v2_result.get("fast_stats", {})
        
        logger.info(f"[generate_directory] V2 extracted {len(nodes)} nodes, mode={generation_mode}")
        
        # ✅ 4.1 通用目录规范化（新增：wrapper折叠 + 三分册一级 + 语义纠偏）
        nodes = self._normalize_directory_nodes(nodes)
        logger.info(f"[generate_directory] normalized nodes -> {len(nodes)}")
        
        # 5. 后处理: 排序 + 构建树 + 生成 numbering
        nodes_sorted = self._sort_directory_nodes_for_tree(nodes)
        nodes_with_tree = self._build_directory_tree(nodes_sorted)
        
        # 6. 保存（使用replace_directory）
        self.dao.replace_directory(project_id, nodes_with_tree)
        logger.info(f"[generate_directory] Saved {len(nodes_with_tree)} nodes")
        
        # ✨ 7. 自动填充范本（集成：一键完成目录生成+范本填充）
        try:
            logger.info(f"[generate_directory] Starting auto_fill_samples for project {project_id}")
            diag = self.auto_fill_samples(project_id)
            
            # 记录填充结果
            attached = diag.get("attached_sections", 0)
            extracted = diag.get("tender_fragments_upserted", 0)
            
            if diag.get("ok"):
                logger.info(
                    f"[generate_directory] auto_fill_samples success: "
                    f"extracted {extracted} fragments, attached {attached} sections"
                )
            else:
                warnings = diag.get("warnings", [])
                logger.warning(
                    f"[generate_directory] auto_fill_samples partial success: "
                    f"attached {attached} sections, warnings: {warnings}"
                )
        except Exception as e:
            logger.error(f"[generate_directory] auto_fill_samples failed: {type(e).__name__}: {e}")
        
        # 8. 更新状态
        if run_id:
            self.dao.update_run(
                run_id,
                "success",
                progress=1.0,
                message="Directory generated with auto-filled samples",
                result_json=v2_result
            )
    
    # ==================== 目录规范化方法（通用版） ====================
    
    def _bucket_by_title(self, title: str) -> str:
        """根据标题内容判断所属分桶"""
        import re
        _BUCKET_PRICE = re.compile(r"(报价|价格|明细|汇总|总价|分项|报价表|报价单|投标报价|磋商报价|报价响应)", re.I)
        _BUCKET_TECH  = re.compile(r"(技术|方案|规格|参数|偏离|样本|手册|实施|组织|架构|测试|配置|选型|技术规格)", re.I)
        _BUCKET_BIZ   = re.compile(r"(营业执照|资质|证书|社保|信用|授权|委托|承诺|声明|基本情况|信誉|自评|证明|建议|不转包|分包)", re.I)
        
        t = (title or "").strip()
        if not t:
            return "unknown"
        if _BUCKET_PRICE.search(t):
            return "price"
        if _BUCKET_TECH.search(t):
            return "tech"
        if _BUCKET_BIZ.search(t):
            return "biz"
        return "unknown"
    
    def _infer_parent_index_by_level(self, nodes: list) -> list:
        """根据 level 推断父节点索引"""
        parent = [-1] * len(nodes)
        stack = []  # [(level, index)]
        for i, n in enumerate(nodes):
            lv = int(n.get("level") or 1)
            while stack and stack[-1][0] >= lv:
                stack.pop()
            parent[i] = stack[-1][1] if stack else -1
            stack.append((lv, i))
        return parent
    
    def _find_section_titles(self, nodes: list) -> dict:
        """查找三分册和 wrapper 标题"""
        import re
        _WRAPPER_RE = re.compile(r"(投标文件|响应文件|磋商响应文件|投标响应文件|响应文件目录|投标文件目录)", re.I)
        _SECTION_BIZ_RE = re.compile(r"(资信|商务|资格)", re.I)
        _SECTION_TECH_RE = re.compile(r"(技术)", re.I)
        _SECTION_PRICE_RE = re.compile(r"(报价|价格|磋商报价|报价响应)", re.I)
        
        biz = tech = price = wrapper = None
        for n in nodes:
            title = (n.get("title") or "").strip()
            if not title:
                continue
            if wrapper is None and _WRAPPER_RE.search(title):
                wrapper = title
            if biz is None and _SECTION_BIZ_RE.search(title):
                biz = title
            if tech is None and _SECTION_TECH_RE.search(title):
                tech = title
            if price is None and _SECTION_PRICE_RE.search(title):
                price = title
        return {"biz": biz, "tech": tech, "price": price, "wrapper": wrapper}
    
    def _collapse_wrapper(self, nodes: list) -> list:
        """折叠 wrapper 节点（投标文件/响应文件等总标题）"""
        from collections import deque
        
        if not nodes:
            return nodes
        sec = self._find_section_titles(nodes)
        wrapper = sec["wrapper"]
        if not wrapper:
            return nodes
        if not (sec["biz"] and sec["tech"] and sec["price"]):
            return nodes

        title_to_first_idx = {}
        for i, n in enumerate(nodes):
            t = (n.get("title") or "").strip()
            if t and t not in title_to_first_idx:
                title_to_first_idx[t] = i

        w_idx = title_to_first_idx.get(wrapper)
        if w_idx is None:
            return nodes

        parent = self._infer_parent_index_by_level(nodes)
        children = [[] for _ in nodes]
        for i, p in enumerate(parent):
            if p >= 0:
                children[p].append(i)

        sub = set()
        q = deque([w_idx])
        while q:
            x = q.popleft()
            sub.add(x)
            for c in children[x]:
                q.append(c)

        # 三分册必须都在 wrapper 子树里才折叠（避免误伤）
        b = title_to_first_idx.get(sec["biz"])
        t = title_to_first_idx.get(sec["tech"])
        p = title_to_first_idx.get(sec["price"])
        if not (b in sub and t in sub and p in sub):
            return nodes

        new_nodes = []
        for i, n in enumerate(nodes):
            if i == w_idx:
                continue  # remove wrapper
            nn = dict(n)
            if i in sub:
                lv = int(nn.get("level") or 1)
                nn["level"] = max(1, lv - 1)
                title = (nn.get("title") or "").strip()
                if title in (sec["biz"], sec["tech"], sec["price"]):
                    nn["parent_ref"] = ""
            new_nodes.append(nn)

        return new_nodes
    
    def _ensure_sections_are_level1(self, nodes: list) -> list:
        """确保三分册为一级标题"""
        if not nodes:
            return nodes
        sec = self._find_section_titles(nodes)
        if not (sec["biz"] and sec["tech"] and sec["price"]):
            return nodes

        title_to_first_idx = {}
        for i, n in enumerate(nodes):
            t = (n.get("title") or "").strip()
            if t and t not in title_to_first_idx:
                title_to_first_idx[t] = i

        idxs = [title_to_first_idx.get(sec["biz"]), title_to_first_idx.get(sec["tech"]), title_to_first_idx.get(sec["price"])]
        if any(i is None for i in idxs):
            return nodes

        new_nodes = [dict(n) for n in nodes]
        for i in idxs:
            new_nodes[i]["level"] = 1
            new_nodes[i]["parent_ref"] = ""

        # 顶层分册 order_no 按出现顺序重排
        top_seq = 1
        for i in sorted(idxs):
            new_nodes[i]["order_no"] = top_seq
            top_seq += 1

        return new_nodes
    
    def _rebucket_to_sections(self, nodes: list) -> list:
        """语义分桶纠偏：把条目挂到正确分册"""
        from collections import defaultdict
        
        if not nodes:
            return nodes
        sec = self._find_section_titles(nodes)
        if not (sec["biz"] and sec["tech"] and sec["price"]):
            return nodes

        biz_title, tech_title, price_title = sec["biz"], sec["tech"], sec["price"]
        section_titles = {biz_title, tech_title, price_title}

        new_nodes = [dict(n) for n in nodes]

        # 判断是否"全挂报价"的典型错挂，触发 aggressive
        cnt = defaultdict(int)
        for n in new_nodes:
            pr = (n.get("parent_ref") or "").strip()
            if pr in section_titles:
                cnt[pr] += 1
        aggressive = (cnt.get(biz_title, 0) == 0 and cnt.get(tech_title, 0) == 0 and cnt.get(price_title, 0) >= 6)

        for n in new_nodes:
            title = (n.get("title") or "").strip()
            if not title:
                continue
            if title in section_titles:
                continue
            import re
            _WRAPPER_RE = re.compile(r"(投标文件|响应文件|磋商响应文件|投标响应文件|响应文件目录|投标文件目录)", re.I)
            if _WRAPPER_RE.search(title):
                continue  # 兜底：wrapper残留不处理

            bucket = self._bucket_by_title(title)
            if bucket == "unknown":
                continue

            target_parent = {"biz": biz_title, "tech": tech_title, "price": price_title}[bucket]
            cur_pr = (n.get("parent_ref") or "").strip()

            # aggressive 或者明显错挂/无挂载 -> 纠偏
            if aggressive or cur_pr in ("", price_title) or cur_pr not in section_titles:
                n["parent_ref"] = target_parent
                n["level"] = 2  # 压缩到分册下二级，保证稳定可用

        # 分册下二级节点 order_no 稳定重排（按原出现顺序）
        bucket_items = defaultdict(list)
        for idx, n in enumerate(new_nodes):
            if int(n.get("level") or 1) == 2:
                pr = (n.get("parent_ref") or "").strip()
                if pr in section_titles:
                    bucket_items[pr].append((idx, n))

        for pr, items in bucket_items.items():
            items.sort(key=lambda x: x[0])
            seq = 1
            for _, n in items:
                n["order_no"] = seq
                seq += 1

        # 兜底：仍为空的二级节点，默认归入资信及商务（比全挂报价更合理）
        for n in new_nodes:
            if int(n.get("level") or 1) > 1 and not (n.get("parent_ref") or "").strip():
                n["parent_ref"] = biz_title
                n["level"] = 2

        return new_nodes
    
    def _normalize_directory_nodes(self, nodes: list) -> list:
        """通用目录规范化：wrapper折叠 + 三分册一级 + 语义纠偏"""
        nodes = nodes or []
        nodes = self._collapse_wrapper(nodes)
        nodes = self._ensure_sections_are_level1(nodes)
        nodes = self._rebucket_to_sections(nodes)
        return nodes
    
    def _sort_directory_nodes_for_tree(self, nodes: list) -> list:
        """
        关键：不能按 (level, order_no) 全局排序，否则所有 level=2 会堆到最后，
        _build_directory_tree 用栈推 parent 时会全部挂到最后一个 level=1（通常是报价文件）。
        这里按 "所属分册(root)" 分组后再排序，保证每个分册的子节点紧跟其后。
        """
        nodes = nodes or []
        # 找一级分册（按出现顺序）
        top = [n for n in nodes if int(n.get("level") or 1) == 1]
        top = sorted(top, key=lambda n: n.get("order_no", 999))

        section_titles = [ (n.get("title") or "").strip() for n in top if (n.get("title") or "").strip() ]
        section_order = {t: i for i, t in enumerate(section_titles)}

        def root_key(n: dict) -> int:
            title = (n.get("title") or "").strip()
            lv = int(n.get("level") or 1)
            if lv == 1 and title in section_order:
                return section_order[title]
            pr = (n.get("parent_ref") or "").strip()
            if pr in section_order:
                return section_order[pr]
            # fallback：未知的先放最后
            return 999

        return sorted(
            nodes,
            key=lambda n: (
                root_key(n),
                int(n.get("level") or 99),
                int(n.get("order_no") or 999),
            )
        )
    
    def _build_directory_tree(self, nodes: List[Dict]) -> List[Dict]:
        """构建目录树: 两遍法 - 先生成id和title映射，再统一分配parent_id"""
        import uuid
        
        # 0) 预处理：确保每个节点有 id
        out = []
        for n in nodes:
            nn = dict(n)
            nn.setdefault("id", f"node_{uuid.uuid4().hex[:16]}")
            nn["title"] = (nn.get("title") or "").strip()
            nn["parent_ref"] = (nn.get("parent_ref") or "").strip()
            nn["level"] = int(nn.get("level") or 1)
            nn["order_no"] = int(nn.get("order_no") or 0)
            out.append(nn)

        # 1) title -> first id（用于 parent_ref 解析）
        title_to_first_id = {}
        for n in out:
            if n["title"] and n["title"] not in title_to_first_id:
                title_to_first_id[n["title"]] = n["id"]

        # 2) 分配 parent_id：优先 parent_ref，其次 fallback level 栈
        stack = []  # (level, id)
        for n in out:
            if n["parent_ref"] and n["parent_ref"] in title_to_first_id:
                n["parent_id"] = title_to_first_id[n["parent_ref"]]
            else:
                # fallback：栈推断（只对确实缺 parent_ref 的情况）
                while stack and stack[-1][0] >= n["level"]:
                    stack.pop()
                n["parent_id"] = stack[-1][1] if stack else None

            stack.append((n["level"], n["id"]))

        # 3) 构 children 映射
        children = {}
        by_id = {n["id"]: n for n in out}
        for n in out:
            children.setdefault(n["id"], [])
        roots = []
        for n in out:
            pid = n.get("parent_id")
            if not pid:
                roots.append(n)
            else:
                children.setdefault(pid, []).append(n)

        # 4) 每个父节点下按 order_no 排序，递归生成 numbering + 扁平化输出
        def sort_k(x: dict):
            return (int(x.get("order_no") or 0), x.get("title") or "")

        for pid in list(children.keys()):
            children[pid].sort(key=sort_k)

        flat = []
        def walk(node: dict, prefix: str):
            # 根节点 numbering 为 1/2/3...
            flat.append(node)
            kids = children.get(node["id"], [])
            for idx, c in enumerate(kids, start=1):
                c["numbering"] = f"{prefix}.{idx}" if prefix else str(idx)
                walk(c, c["numbering"])

        # roots 必须稳定排序
        roots.sort(key=sort_k)
        for idx, r in enumerate(roots, start=1):
            r["numbering"] = str(idx)
            walk(r, r["numbering"])

        return flat
    
    def _pick_latest_asset(self, assets: List[Dict[str, Any]], require_storage_path: bool = False) -> Optional[Dict[str, Any]]:
        """
        从资产列表中选择“最新”的一条：
        - 优先按 created_at DESC
        - created_at 缺失则保持原顺序，取最后一个（更接近“最新上传”）
        - require_storage_path=True 时，会优先选择 storage_path 非空的记录
        """
        if not assets:
            return None

        cands = assets
        if require_storage_path:
            with_path = [a for a in assets if (a.get("storage_path") or "").strip()]
            cands = with_path or assets

        def _key(a: Dict[str, Any]):
            # psycopg/RealDictCursor 通常会返回 datetime；缺失则用空串兜底
            return a.get("created_at") or ""

        try:
            cands_sorted = sorted(cands, key=_key, reverse=True)
            return cands_sorted[0] if cands_sorted else None
        except Exception:
            return cands[-1] if cands else None

    def _auto_extract_and_attach_samples(self, project_id: str):
        """自动抽取招标书范本并挂载到目录节点"""
        import logging
        logger = logging.getLogger(__name__)

        # 1. 获取招标书文件
        assets = self.dao.list_assets(project_id)
        tender_assets = [a for a in assets if a.get("kind") == "tender"]
        # 选择“最新且可用”的 tender（优先 storage_path 存在）
        tender_asset = self._pick_latest_asset(tender_assets, require_storage_path=True)
        
        if not tender_asset:
            return
        
        # 2. 获取文件路径
        storage_path = tender_asset.get("storage_path")
        if not storage_path:
            logger.warning(f"[samples] tender asset has no storage_path, skip. project_id={project_id}")
            return

        # 支持 DOCX 和 PDF 格式
        ext = os.path.splitext(storage_path.lower())[1]
        if ext not in [".docx", ".pdf"]:
            logger.warning(f"[samples] tender asset is not docx/pdf, skip. project_id={project_id}, storage_path={storage_path}")
            return

        if not os.path.exists(storage_path):
            logger.warning(f"[samples] tender file not found on disk, skip. project_id={project_id}, storage_path={storage_path}")
            return
        
        # 3. 抽取范本（支持DOCX和PDF）
        from app.services.fragment.fragment_extractor import TenderSampleFragmentExtractor
        logger.info(f"[samples] extracting fragments from tender file ({ext}). project_id={project_id}, path={storage_path}")
        extractor = TenderSampleFragmentExtractor(self.dao)
        extractor.extract_and_upsert(
            project_id=project_id,
            tender_docx_path=storage_path,
            file_key=storage_path,
        )

        try:
            fragments_count = len(self.dao.list_fragments("PROJECT", project_id))
        except Exception:
            fragments_count = -1
        logger.info(f"[samples] extracted fragments. project_id={project_id}, count={fragments_count}")
        
        # 4. 挂载到目录节点
        from app.services.fragment.outline_attacher import OutlineSampleAttacher
        nodes = self.dao.list_directory(project_id)
        attacher = OutlineSampleAttacher(self.dao)
        attached_count = attacher.attach(project_id, nodes)
        logger.info(f"[samples] attached fragments to outline nodes. project_id={project_id}, attached_count={attached_count}")

    def save_directory(self, project_id: str, nodes: List[Dict[str, Any]]):
        """保存目录（用户编辑后）"""
        self.dao.replace_directory(project_id, nodes)
    
    def get_directory_with_body_meta(self, project_id: str) -> List[Dict]:
        """
        获取目录（带正文元信息）
        为每个节点附加 bodyMeta 信息
        """
        nodes = self.dao.list_directory(project_id)
        bodies = self.dao.list_section_bodies(project_id)
        
        # 构建 node_id -> body 映射
        body_map = {b["node_id"]: b for b in bodies}
        
        # 为每个节点添加 bodyMeta
        for node in nodes:
            node_id = node.get("id")
            body = body_map.get(node_id)
            
            if body:
                node["bodyMeta"] = {
                    "source": body.get("source"),
                    "fragmentId": body.get("fragment_id"),
                    "hasContent": bool(body.get("content_html")),
                }
            else:
                node["bodyMeta"] = {
                    "source": "EMPTY",
                    "fragmentId": None,
                    "hasContent": False,
                }
        
        return nodes
    
    def get_section_body_content(self, project_id: str, node_id: str) -> Optional[Dict]:
        """
        获取章节正文内容
        - 如果是用户编辑内容，返回 HTML
        - 如果是范本挂载，返回简化的预览HTML（从源文档生成）
        - 如果是PDF语义匹配，直接返回content_html
        """
        body = self.dao.get_section_body(project_id, node_id)
        if not body:
            return None
        
        source = body.get("source")
        
        # 用户编辑内容
        if source == "USER" and body.get("content_html"):
            return {
                "source": source,
                "contentHtml": body["content_html"],
                "fragmentId": body.get("fragment_id"),
            }
        
        # PDF语义匹配 - 直接返回content_html（已在挂载时提取）
        if source == "PDF_SEMANTIC_MATCH" and body.get("content_html"):
            return {
                "source": source,
                "contentHtml": body["content_html"],
                "fragmentId": body.get("fragment_id"),
            }
        
        # 范本挂载 - 生成预览HTML（即使失败也必须返回非空 contentHtml）
        if source == "TEMPLATE_SAMPLE":
            import logging
            logger = logging.getLogger(__name__)

            frag_id = body.get("fragment_id")
            if not frag_id:
                return {
                    "source": source,
                    "contentHtml": "<div class='template-sample-preview' style='color:#92400e'>[该章节已挂载范本，但 fragment_id 为空]</div>",
                    "fragmentId": None,
                }

            fragment = self.dao.get_fragment_by_id(frag_id)
            if not fragment:
                return {
                    "source": source,
                    "contentHtml": "<div class='template-sample-preview' style='color:#92400e'>[该章节已挂载范本，但片段不存在或已被删除]</div>",
                    "fragmentId": frag_id,
                }

            src_docx_path = fragment.get("source_file_key")
            start_idx = fragment.get("start_body_index")
            end_idx = fragment.get("end_body_index")

            if not src_docx_path:
                logger.warning(f"[samples] fragment has no source_file_key. project_id={project_id}, node_id={node_id}, fragment_id={fragment.get('id')}")
                return {
                    "source": source,
                    "contentHtml": "<div class='template-sample-preview' style='color:#92400e'>[已挂载范本：源文件路径缺失，导出时可能无法拷贝]</div>",
                    "fragmentId": fragment.get("id"),
                }
            if not str(src_docx_path).lower().endswith(".docx"):
                logger.warning(f"[samples] fragment source is not docx. project_id={project_id}, node_id={node_id}, fragment_id={fragment.get('id')}, source={src_docx_path}")
                return {
                    "source": source,
                    "contentHtml": "<div class='template-sample-preview' style='color:#92400e'>[已挂载范本：源文件不是 docx，无法预览]</div>",
                    "fragmentId": fragment.get("id"),
                }
            if start_idx is None or end_idx is None:
                logger.warning(f"[samples] fragment indices missing. project_id={project_id}, node_id={node_id}, fragment_id={fragment.get('id')}")
                return {
                    "source": source,
                    "contentHtml": "<div class='template-sample-preview' style='color:#92400e'>[已挂载范本：片段范围缺失，无法预览]</div>",
                    "fragmentId": fragment.get("id"),
                }

            from app.services.fragment.fragment_preview import render_fragment_html
            try:
                html = render_fragment_html(str(src_docx_path), int(start_idx), int(end_idx))
                if not (html or "").strip():
                    html = "<div class='template-sample-preview' style='color:#92400e'>[已挂载范本：预览为空]</div>"
                return {
                    "source": source,
                    "contentHtml": html,
                    "fragmentId": fragment.get("id"),
                }
            except Exception as e:
                logger.warning(f"[samples] render_fragment_html failed: {e}. project_id={project_id}, node_id={node_id}, fragment_id={fragment.get('id')}")
                return {
                    "source": source,
                    "contentHtml": f"<div class='template-sample-preview' style='color:#b00020'>[范本预览渲染失败: {str(e)}]</div>",
                    "fragmentId": fragment.get("id"),
                }
        
        return {
            "source": source or "EMPTY",
            "contentHtml": "",
            "fragmentId": None,
        }
    
    def update_section_body(self, project_id: str, node_id: str, content_html: str):
        """更新章节正文（用户编辑）"""
        # 保留原有的 fragment_id（用于恢复范本）
        existing = self.dao.get_section_body(project_id, node_id)
        fragment_id = existing.get("fragment_id") if existing else None
        
        self.dao.upsert_section_body(
            project_id=project_id,
            node_id=node_id,
            source="USER",
            fragment_id=fragment_id,  # 保留以便恢复
            content_html=content_html,
        )
    
    def restore_sample_for_section(self, project_id: str, node_id: str):
        """恢复章节的范本内容"""
        # 查找该节点的目录信息
        nodes = self.dao.list_directory(project_id)
        node = next((n for n in nodes if n.get("id") == node_id), None)
        
        if not node:
            return
        
        # 尝试重新匹配范本
        from app.services.fragment.fragment_matcher import FragmentTitleMatcher
        matcher = FragmentTitleMatcher()
        
        node_title = node.get("title", "")
        node_title_norm = matcher.normalize(node_title)
        
        ftype = matcher.match_type(node_title_norm)
        if not ftype:
            # 无法匹配，清空正文
            self.dao.upsert_section_body(
                project_id=project_id,
                node_id=node_id,
                source="EMPTY",
                fragment_id=None,
                content_html=None,
            )
            return
        
        # 查找最佳片段
        candidates = self.dao.find_fragments_by_type("PROJECT", project_id, str(ftype))
        if not candidates:
            # 没有匹配片段
            self.dao.upsert_section_body(
                project_id=project_id,
                node_id=node_id,
                source="EMPTY",
                fragment_id=None,
                content_html=None,
            )
            return
        
        # 使用第一个候选（已按置信度排序）
        best = candidates[0]
        self.dao.upsert_section_body(
            project_id=project_id,
            node_id=node_id,
            source="TEMPLATE_SAMPLE",
            fragment_id=best["id"],
            content_html=None,
        )

    # ==================== 范本片段：列表 + 预览（目录页侧边栏） ====================

    def list_sample_fragments(self, project_id: str) -> List[Dict[str, Any]]:
        """
        列出本项目下抽取到的范本片段（轻量列表，不含大正文）。
        """
        rows = self.dao.list_sample_fragments(project_id)
        out: List[Dict[str, Any]] = []
        for r in rows or []:
            out.append(
                {
                    "id": r.get("id"),
                    "title": r.get("title") or "",
                    "fragment_type": r.get("fragment_type") or "",
                    "confidence": r.get("confidence"),
                }
            )
        return out

    def get_sample_fragment_preview(self, project_id: str, fragment_id: str, max_elems: int = 60) -> Dict[str, Any]:
        """
        获取单条范本片段的预览（懒加载）。

        - 防越权：owner_id 必须等于 project_id（且 owner_type=PROJECT）
        - 从 source_file_key 打开 docx，按 [start_body_index..end_body_index] 抽取内容渲染为简易 HTML
        """
        fragment = self.dao.get_fragment_by_id(fragment_id)
        if not fragment:
            raise ValueError("fragment not found")

        if str(fragment.get("owner_type") or "") != "PROJECT" or str(fragment.get("owner_id") or "") != str(project_id):
            raise PermissionError("fragment not in project")

        title = fragment.get("title") or ""
        ftype = fragment.get("fragment_type") or ""
        warnings: List[str] = []

        src = (fragment.get("source_file_key") or "").strip()
        start_idx = fragment.get("start_body_index")
        end_idx = fragment.get("end_body_index")

        if not src:
            warnings.append("source_file_key_missing")
            return {
                "id": fragment_id,
                "title": title,
                "fragment_type": ftype,
                "preview_html": "<div style='color:#92400e'>[源文件缺失，无法预览]</div>",
                "text_len": 0,
                "warnings": warnings,
            }

        if not str(src).lower().endswith(".docx"):
            warnings.append("source_not_docx")
            return {
                "id": fragment_id,
                "title": title,
                "fragment_type": ftype,
                "preview_html": "<div style='color:#92400e'>[源文件不是 docx，无法预览]</div>",
                "text_len": 0,
                "warnings": warnings,
            }

        if not os.path.exists(src):
            warnings.append("source_docx_not_found")
            return {
                "id": fragment_id,
                "title": title,
                "fragment_type": ftype,
                "preview_html": "<div style='color:#92400e'>[源 docx 不存在/未落盘，无法预览]</div>",
                "text_len": 0,
                "warnings": warnings,
            }

        if start_idx is None or end_idx is None:
            warnings.append("range_missing")
            return {
                "id": fragment_id,
                "title": title,
                "fragment_type": ftype,
                "preview_html": "<div style='color:#92400e'>[片段范围缺失，无法预览]</div>",
                "text_len": 0,
                "warnings": warnings,
            }

        from app.services.fragment.fragment_preview import build_fragment_preview_meta

        html_out, text_len, w = build_fragment_preview_meta(
            docx_path=str(src),
            start=int(start_idx),
            end=int(end_idx),
            max_elems=int(max_elems or 60),
        )
        warnings.extend(list(w or []))

        return {
            "id": fragment_id,
            "title": title,
            "fragment_type": ftype,
            "preview_html": html_out,
            "text_len": int(text_len or 0),
            "warnings": warnings,
        }
    
    def auto_fill_samples(self, project_id: str) -> Dict[str, Any]:
        """
        自动填充所有章节的范本（永不抛异常，必须返回诊断 dict，禁止 return None）

        固定返回结构：
        {
          "ok": bool,
          "project_id": str,
          "tender_asset_id": str|None,
          "tender_filename": str|None,
          "tender_storage_path": str|None,
          "storage_path_exists": bool,
          "needs_reupload": bool,
          "tender_fragments_upserted": int,   # 本次从招标书新抽出来并写库的数量
          "tender_fragments_total": int,      # 当前项目库里 fragment 总数（owner=PROJECT）
          "attached_sections_template_sample": int, # 本次挂载 source=TEMPLATE_SAMPLE 的章节数
          "attached_sections_builtin": int,         # 本次挂载 source=BUILTIN_SAMPLE 的章节数
          # 兼容字段（旧前端/脚本）
          "extracted_fragments": int,
          "attached_sections": int,
          "warnings": [str, ...],
          "nodes": [...带 bodyMeta...],
        }
        """
        import logging

        logger = logging.getLogger(__name__)

        # 固定结构初始化（确保任何分支都不会缺字段）
        diag: Dict[str, Any] = {
            "ok": False,
            "project_id": project_id,
            "tender_asset_id": None,
            "tender_filename": None,
            "tender_storage_path": None,
            "storage_path_exists": False,
            "needs_reupload": False,
            "tender_fragments_upserted": 0,
            "tender_fragments_total": 0,
            "attached_sections_template_sample": 0,
            "attached_sections_builtin": 0,
            # 兼容字段
            "extracted_fragments": 0,
            "attached_sections": 0,
            "warnings": [],
            "nodes": [],
            # 诊断增强字段
            "tender_storage_path_ext": "",
            "body_items_count": 0,
            "fragments_detected_by_rules": 0,
            "llm_used": False,
        }

        try:
            warnings: List[str] = []

            # A) 选择 tender 资产（优先最新，严格过滤套用格式产物）
            assets = self.dao.list_assets(project_id)
            
            def _asset_text(a):
                """获取资产文本（用于关键词过滤）"""
                return f"{a.get('filename','')} {a.get('storage_path','')}".lower()
            
            # 排除关键词：套用格式、导出、投标文件产物
            deny_kw = [
                "套用格式", "render_", "template_renders", "export_", "导出",
                "投标文件", "bid_", "skeleton", "骨架"
            ]
            
            tenders = []
            for a in (assets or []):
                if (a or {}).get("kind") != "tender":
                    continue
                sp = (a.get("storage_path") or "").lower()
                if not (sp.endswith(".docx") or sp.endswith(".pdf")):
                    continue
                if any(k in _asset_text(a) for k in deny_kw):
                    continue
                tenders.append(a)
            
            if not tenders:
                diag["needs_reupload"] = True
                warnings.append("未找到可用的招标书(tender)资产：请上传招标文件（docx/pdf），系统已排除套用格式/导出/投标文件产物")
                diag["warnings"] = warnings
                diag["nodes"] = self.get_directory_with_body_meta(project_id)
                return diag

            def _sort_key(a: Dict[str, Any]) -> str:
                v = a.get("created_at")
                return str(v or "")

            try:
                tenders_sorted = sorted(tenders, key=_sort_key, reverse=True)
                tender_asset = tenders_sorted[0]
            except Exception:
                tender_asset = tenders[-1]

            diag["tender_asset_id"] = tender_asset.get("id")
            diag["tender_filename"] = tender_asset.get("filename")

            # B) 只用 storage_path，且必须存在且是 .docx/.pdf；若缺失则尝试恢复/兜底
            path = str((tender_asset.get("storage_path") or "")).strip() or None
            diag["tender_storage_path"] = path
            diag["storage_path_exists"] = bool(path and os.path.exists(path))
            diag["tender_storage_path_ext"] = os.path.splitext(path or "")[1].lower()

            if not path or not diag["storage_path_exists"]:
                # C-2) 旧项目：尝试从磁盘/存储恢复（若系统没有原始 bytes，则通常只能走 fallback）
                restored_path = self._try_restore_tender_docx_from_disk(project_id, tender_asset)
                # 修复：确保 restored_ext 不为空，避免 NoneType 错误
                restored_ext = os.path.splitext(restored_path or "")[1].lower() if restored_path else ""
                
                if restored_path and os.path.exists(restored_path) and restored_ext in (".docx", ".pdf"):
                    path = restored_path
                    diag["tender_storage_path"] = restored_path
                    diag["storage_path_exists"] = True
                else:
                    # C-3) 无法恢复：走内置范本库 fallback（功能可用），并提示需要重传保真抽取
                    diag["needs_reupload"] = True
                    warnings.append(
                        "无法从招标书抽取范本（缺少原件/未落盘），已使用内置范本库；如需保真抽取请重新上传招标书（docx/pdf）"
                    )
                    attached = self._auto_fill_samples_builtin(project_id, warnings)
                    diag["attached_sections_builtin"] = int(attached or 0)
                    diag["attached_sections_template_sample"] = 0
                    diag["tender_fragments_upserted"] = 0
                    try:
                        diag["tender_fragments_total"] = len(self.dao.list_fragments("PROJECT", project_id))
                    except Exception:
                        diag["tender_fragments_total"] = 0
                    # 兼容字段
                    diag["extracted_fragments"] = int(diag["tender_fragments_upserted"])
                    diag["attached_sections"] = int(diag["attached_sections_template_sample"]) + int(diag["attached_sections_builtin"])
                    try:
                        diag["nodes"] = self.get_directory_with_body_meta(project_id)
                    except Exception as e:
                        warnings.append(f"get_directory_with_body_meta exception: {type(e).__name__}: {str(e)}")
                        diag["nodes"] = []
                    diag["ok"] = bool(diag["attached_sections"] and int(diag["attached_sections"]) > 0)
                    diag["warnings"] = warnings
                    return diag

            # C) 允许 PDF / DOCX 都走 extractor；只有 extractor 真的抽不到内容才 fallback
            use_path = path
            
            # ✅ PDF文件跳过fragments抽取，直接使用语义搜索
            pdf_ext = os.path.splitext(use_path)[1].lower()
            if pdf_ext == ".pdf":
                logger.info(f"[auto_fill_samples] PDF detected, skipping fragment extraction, using semantic search")
                diag["tender_storage_path_ext"] = ".pdf"
                diag["body_items_count"] = 0
                diag["tender_fragments_upserted"] = 0
                diag["fragments_detected_by_rules"] = 0
                diag["llm_used"] = False
                # 直接跳到语义搜索部分
            else:
                # DOCX文件走传统的fragments抽取流程
                try:
                    from app.services.fragment.fragment_extractor import TenderSampleFragmentExtractor
                    
                    extractor = TenderSampleFragmentExtractor(self.dao)
                    summary = extractor.extract_and_upsert_summary(
                        project_id=project_id,
                        tender_docx_path=use_path,
                        file_key=path,
                    )
                    
                    diag["body_items_count"] = int(summary.get("body_elements") or 0)
                    diag["tender_fragments_upserted"] = int(summary.get("upserted_fragments") or 0)
                    diag["fragments_detected_by_rules"] = int(summary.get("fragments_detected") or 0)
                    diag["llm_used"] = bool((summary.get("llm_spans_raw") or 0) > 0)
                    diag["tender_storage_path_ext"] = str(summary.get("input_ext") or os.path.splitext(use_path)[1].lower())

                    # 如果DOCX抽取结果为 0，fallback builtin
                    if diag["tender_fragments_upserted"] <= 0:
                        ext_name = diag.get("tender_storage_path_ext", "").upper().replace(".", "")
                        warnings.append(f"{ext_name} 未能抽取到范本片段（可能为扫描件、无范本区域或格式不规范），已使用内置范本库；建议上传标准格式招标文件")
                        attached = self._auto_fill_samples_builtin(project_id, warnings)
                        diag["attached_sections_builtin"] = attached
                        diag["warnings"] = warnings
                        diag["nodes"] = self.get_directory_with_body_meta(project_id)
                        diag["ok"] = True
                        return diag
                except Exception as e:
                    warnings.append(f"extractor exception: {type(e).__name__}: {str(e)}")
                    logger.exception(f"[samples] extractor exception: project_id={project_id}")
                    diag["tender_fragments_upserted"] = 0
                    diag["fragments_detected_by_rules"] = 0

            # 当前库内 fragments 总数（用于区分“本次抽取” vs “历史已存在”）
            try:
                diag["tender_fragments_total"] = len(self.dao.list_fragments("PROJECT", project_id))
            except Exception:
                diag["tender_fragments_total"] = 0

            try:
                from app.services.fragment.outline_attacher import OutlineSampleAttacher

                nodes = self.dao.list_directory(project_id)
                attacher = OutlineSampleAttacher(self.dao, llm_client=self.llm)
                
                # ✅ 新策略：从目录标题出发，语义搜索PDF内容（适用于PDF）
                # 旧策略：从fragments表查找（适用于DOCX）
                if diag["tender_storage_path_ext"] == ".pdf":
                    logger.info(f"[auto_fill_samples] Using PDF semantic search (keyword-only, LLM disabled) for project {project_id}")
                    # ✅ 暂时禁用LLM验证，只使用关键词匹配
                    attached_count = int(attacher.attach_from_pdf_semantic(
                        project_id, nodes, min_confidence=0.4, use_llm=False  # ✅ 禁用LLM
                    ) or 0)
                else:
                    logger.info(f"[auto_fill_samples] Using traditional fragment matching for project {project_id}")
                    attached_count = int(attacher.attach(project_id, nodes, use_llm=True) or 0)
                
                diag["attached_sections_template_sample"] = attached_count
                diag["attached_write_mode"] = "content_json"  # 诊断信息：写入模式
            except Exception as e:
                warnings.append(f"attacher exception: {type(e).__name__}: {str(e)}")
                diag["attached_sections_template_sample"] = 0

            # 本分支未走 builtin
            diag["attached_sections_builtin"] = 0

            # 兼容字段（旧前端/脚本）
            diag["extracted_fragments"] = int(diag["tender_fragments_upserted"])
            diag["attached_sections"] = int(diag["attached_sections_template_sample"]) + int(diag["attached_sections_builtin"])

            # nodes（带 bodyMeta）
            try:
                diag["nodes"] = self.get_directory_with_body_meta(project_id)
            except Exception as e:
                warnings.append(f"get_directory_with_body_meta exception: {type(e).__name__}: {str(e)}")
                diag["nodes"] = []

            diag["ok"] = bool(diag["attached_sections"] and int(diag["attached_sections"]) > 0)
            diag["warnings"] = warnings
            return diag
        except Exception as e:
            # 最后一道防线：绝不抛出
            logger.exception("auto_fill_samples unexpected exception project_id=%s", project_id)
            w = diag.get("warnings")
            if not isinstance(w, list):
                w = []
            w.append(f"auto_fill_samples unexpected: {type(e).__name__}: {str(e)}")
            diag["warnings"] = w
            try:
                diag["nodes"] = self.get_directory_with_body_meta(project_id)
            except Exception:
                diag["nodes"] = []
            return diag

    def _auto_fill_samples_builtin(self, project_id: str, warnings: List[str]) -> int:
        """
        D. 兜底：内置范本库（至少投标函/授权书/报价表三类）
        写入 section_body.source=BUILTIN_SAMPLE（前端可直接展示），并提示 warnings。
        """
        from app.services.fragment.fragment_matcher import FragmentTitleMatcher
        from app.services.fragment.builtin_samples import BUILTIN_SAMPLE_HTML_BY_TYPE

        warnings.append("使用内置范本库填充（非从招标书docx抽取）")

        matcher = FragmentTitleMatcher()
        nodes = self.dao.list_directory(project_id)

        attached = 0
        for node in nodes:
            node_id = node.get("id")
            if not node_id:
                continue
            title_norm = matcher.normalize(node.get("title") or "")
            ftype = matcher.match_type(title_norm)
            if not ftype:
                continue
            html = BUILTIN_SAMPLE_HTML_BY_TYPE.get(ftype)
            if not html:
                continue

            existing = self.dao.get_section_body(project_id, node_id)
            # 不覆盖用户已有内容
            if existing and existing.get("source") == "USER" and (existing.get("content_html") or "").strip():
                continue
            # 不覆盖已有 AI 内容
            if existing and existing.get("source") == "AI":
                continue

            self.dao.upsert_section_body(
                project_id=project_id,
                node_id=node_id,
                source="BUILTIN_SAMPLE",
                fragment_id=None,
                content_html=html,
            )
            attached += 1

        return attached

    def _try_restore_tender_docx_from_disk(self, project_id: str, tender_asset: Dict[str, Any]) -> Optional[str]:
        """
        旧项目恢复尝试（磁盘侧）：如果项目目录下已存在 docx，但 DB storage_path 丢失/为空，
        则选择一个 docx 回写 storage_path 并返回。

        注意：当前系统 KB 仅保存解析后的文本 chunks，通常无法从 KB 还原原始 docx bytes；
        因此这里优先做“磁盘存在但 DB 没写”的自愈。
        """
        import glob
        import logging

        logger = logging.getLogger(__name__)
        base_dir = os.path.join("data", "tender_assets", project_id)
        try:
            cands = sorted(glob.glob(os.path.join(base_dir, "*.docx")), reverse=True)
        except Exception:
            cands = []

        if not cands:
            return None

        # 优先匹配文件名包含 tender_asset.filename
        filename = str((tender_asset or {}).get("filename") or "").strip()
        pick = None
        if filename:
            for p in cands:
                if filename in os.path.basename(p):
                    pick = p
                    break
        if not pick:
            pick = cands[0]

        asset_id = (tender_asset or {}).get("id")
        if asset_id:
            try:
                self.dao.update_asset_storage_path(str(asset_id), pick)
            except Exception as e:
                logger.warning("update_asset_storage_path failed asset_id=%s: %s", asset_id, e)

        logger.info("[samples] restored tender docx from disk. project_id=%s pick=%s", project_id, pick)
        return pick

    # extract_rule_set 方法已删除，规则文件现在直接作为审核上下文叠加

    def run_review(
        self,
        project_id: str,
        model_id: Optional[str],
        custom_rule_asset_ids: List[str],
        bidder_name: Optional[str],
        bid_asset_ids: List[str],
        custom_rule_pack_ids: Optional[List[str]] = None,
        use_llm_semantic: bool = True,  # ✅ 默认启用QA验证
        run_id: Optional[str] = None,
        owner_id: Optional[str] = None,
    ):
        """
        运行审核（招标规则 + 自定义规则文件叠加）
        
        Args:
            custom_rule_asset_ids: 自定义规则文件资产ID列表（直接叠加原文）
            custom_rule_pack_ids: 自定义规则包ID列表（应用规则包中的规则）
            bidder_name: 投标人名称（选择投标人）
            bid_asset_ids: 投标资产ID列表（精确指定文件）
            use_llm_semantic: 是否使用LLM语义审核（QA验证，默认True）
            owner_id: 任务所有者ID（可选）
        """
        # 旁路双写：创建 platform job（如果启用）
        job_id = None
        if self.feature_flags.PLATFORM_JOBS_ENABLED and self.jobs_service and run_id:
            try:
                job_id = self.jobs_service.create_job(
                    namespace="tender",
                    biz_type="review_run",
                    biz_id=project_id,
                    owner_id=owner_id,
                    initial_status="running",
                    initial_message="正在运行审核..."
                )
            except Exception as e:
                print(f"[WARN] Failed to create platform job: {e}")
        
        try:
            # 使用 ReviewV3Service (支持规则引擎和自定义规则包)
            
            # 如果没有指定model_id，使用默认模型
            if not model_id:
                from app.services.llm_model_store import get_llm_store
                store = get_llm_store()
                default_model = store.get_default_model()
                if default_model:
                    model_id = default_model.id
                    logger.info(f"No model_id provided, using default: {model_id}")
                else:
                    logger.warning("No model_id provided and no default model configured")
            
            logger.info(f"ReviewV3 mode: project={project_id}, model_id={model_id}, bidder={bidder_name}, custom_rule_pack_ids={custom_rule_pack_ids}")
            
            arr = []  # 初始化审核项列表
            try:
                import asyncio
                from app.works.tender.review_v3_service import ReviewV3Service
                from app.services.db.postgres import _get_pool
                
                pool = _get_pool()
                review_v3 = ReviewV3Service(pool, self.llm)
                logger.info("Created ReviewV3Service")
                
                # 运行 v3 审核
                logger.info(f"Calling run_review_v3 with use_llm_semantic={use_llm_semantic}...")
                v3_results = asyncio.run(review_v3.run_review_v3(
                    project_id=project_id,
                    bidder_name=bidder_name,
                    model_id=model_id,
                    custom_rule_pack_ids=custom_rule_pack_ids,
                    use_llm_semantic=use_llm_semantic,
                    run_id=run_id
                ))
                logger.info(f"run_review_v3 completed")
                
                # v3 成功：使用 v3 结果
                arr = v3_results.get("items", [])  # 提取 items 列表
                logger.info(f"Extracted {len(arr)} review items")
                
                # ⚠️ 注意：ReviewPipelineV3已经直接保存到tender_review_items表
                # 不需要再调用replace_review_items，否则会删除已保存的V3数据！
                # self.dao.replace_review_items(project_id, arr)  # 已废弃
                
                # 更新运行状态
                if run_id:
                    self.dao.update_run(
                        run_id, "success", progress=1.0,
                        message="ok",
                        result_json={
                            "count": len(arr),
                            "review_v3_status": "ok",
                            "review_mode": v3_results.get("review_mode", "UNKNOWN"),
                            "pass_count": v3_results.get("pass_count", 0),
                            "fail_count": v3_results.get("fail_count", 0),
                            "warn_count": v3_results.get("warn_count", 0),
                            "pending_count": v3_results.get("pending_count", 0)
                        }
                    )
                
                logger.info(f"Review completed successfully for project={project_id}, count={len(arr)}")
                
            except Exception as e:
                # 审核失败：记录并抛错
                error_msg = f"Review failed: {str(e)}"
                logger.error(
                    f"Review failed for project={project_id}: {e}",
                    exc_info=True
                )
                
                # 更新运行状态为失败
                if run_id:
                    self.dao.update_run(
                        run_id, "failed", progress=0.0,
                        message=error_msg,
                        result_json={
                            "review_v3_status": "failed",
                            "review_v3_error": str(e)
                        }
                    )
                
                # 抛出错误
                raise ValueError(error_msg) from e
            
            # 旁路双写：ReviewCase（如果启用）
            case_id = None
            review_run_id = None
            if self.feature_flags.REVIEWCASE_DUALWRITE:
                try:
                    from app.services.platform.reviewcase_service import ReviewCaseService
                    from app.services.db.postgres import _get_pool
                    pool = _get_pool()
                    reviewcase_service = ReviewCaseService(pool)
                    
                    # 1. 收集文档版本ID（从 assets 的 meta_json 中提取）
                    tender_doc_version_ids = []
                    bid_doc_version_ids = []
                    
                    # 获取招标文件的 doc_version_id
                    tender_assets = self.dao.list_assets(project_id)
                    for asset in tender_assets:
                        if asset.get("kind") == "tender":
                            meta_json = asset.get("meta_json") or {}
                            doc_version_id = meta_json.get("doc_version_id")
                            if doc_version_id:
                                tender_doc_version_ids.append(doc_version_id)
                    
                    # 获取投标文件的 doc_version_id
                    for asset in tender_assets:
                        if asset.get("kind") == "bid" and asset.get("bidder_name") == bidder_name:
                            meta_json = asset.get("meta_json") or {}
                            doc_version_id = meta_json.get("doc_version_id")
                            if doc_version_id:
                                bid_doc_version_ids.append(doc_version_id)
                    
                    # 获取 custom_rule 的 rule_set_version_id（如果存在）
                    rule_set_version_id = None
                    for asset in tender_assets:
                        if asset.get("kind") == "custom_rule":
                            meta_json = asset.get("meta_json") or {}
                            rule_set_version_id = meta_json.get("rule_set_version_id")
                            if rule_set_version_id:
                                break  # 只取第一个
                    
                    # 2. 创建 review_case
                    case_id = reviewcase_service.create_case(
                        namespace="tender",
                        project_id=project_id,
                        tender_doc_version_ids=tender_doc_version_ids,
                        bid_doc_version_ids=bid_doc_version_ids
                    )
                    
                    # 3. 创建 review_run（记录 rule_set_version_id）
                    review_run_id = reviewcase_service.create_run(
                        case_id=case_id,
                        model_id=model_id,
                        rule_set_version_id=rule_set_version_id,
                        status="running"
                    )
                    
                    # 4. 批量创建 review_findings（从 arr 转换）
                    findings = []
                    for item in arr:
                        source = item.get("source", "compare")
                        finding = {
                            "source": source,
                            "dimension": item.get("dimension", "其他"),
                            "requirement_text": item.get("requirement_text") or item.get("title", ""),
                            "response_text": item.get("response_text", ""),
                            "result": item.get("result", "risk"),
                            "rigid": item.get("rigid", False),
                            "remark": item.get("remark", ""),
                            "evidence_jsonb": {
                                "tender_chunk_ids": item.get("tender_evidence_chunk_ids", []),
                                "bid_chunk_ids": item.get("bid_evidence_chunk_ids", []),
                                "evidence_chunk_ids": item.get("evidence_chunk_ids", []),
                                "rule_id": item.get("rule_id") if source == "rule" else None
                            }
                        }
                        findings.append(finding)
                    
                    reviewcase_service.batch_create_findings(review_run_id, findings)
                    
                    # 5. 更新 review_run 状态
                    reviewcase_service.update_run_status(
                        review_run_id,
                        status="succeeded",
                        result_json={
                            "total_findings": len(arr),
                            "compare_findings": len(arr)
                        }
                    )
                    
                    print(f"[INFO] ReviewCase dual-write succeeded: case_id={case_id}, review_run_id={review_run_id}")
                    
                except Exception as e:
                    # 降级：ReviewCase 双写失败不影响主流程
                    print(f"[WARN] Failed to write to ReviewCase: {e}")
            
            # 旁路双写：更新 job 成功（如果启用）
            if job_id and self.jobs_service:
                try:
                    self.jobs_service.finish_job_success(
                        job_id=job_id,
                        result={"review_items_count": len(arr)},
                        message="成功"
                    )
                except Exception as e:
                    print(f"[WARN] Failed to update platform job: {e}")
        
        except Exception as e:
            # 更新 job 失败状态（如果启用）
            if job_id and self.jobs_service:
                try:
                    self.jobs_service.finish_job_fail(job_id=job_id, error=str(e))
                except Exception as je:
                    print(f"[WARN] Failed to update platform job on error: {je}")
            # 重新抛出原始异常
            raise

    def generate_docx(
        self,
        project_id: str,
        template_asset_id: Optional[str],
    ) -> bytes:
        """
        生成 Word 文档
        
        Args:
            template_asset_id: 模板资产ID（可选）
        
        Returns:
            Word 文档字节
        """
        # 加载目录节点
        nodes = self.dao.list_directory(project_id)

        # 加载模板（如果指定）
        tpl_doc = None
        template_spec: Optional[TemplateSpec] = None
        
        if template_asset_id:
            assets = self.dao.get_assets_by_ids(project_id, [template_asset_id])
            if assets:
                asset = assets[0]
                path = asset.get("storage_path")
                
                # 尝试加载 TemplateSpec
                meta = asset.get("meta_json") or {}
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}
                
                # 如果是格式模板，尝试加载 spec
                template_db_id = meta.get("format_template_id")
                if template_db_id:
                    template_spec = self.get_format_template_spec(template_db_id)
                
                # 加载模板文档
                if path and os.path.exists(path):
                    try:
                        tpl_doc = Document(path)
                    except Exception:
                        pass

        # 如果有模板且有 spec，使用 spec 指导样式应用
        if tpl_doc and template_spec:
            return self._generate_docx_with_spec(nodes, tpl_doc, template_spec, project_id)
        elif tpl_doc:
            # 传统模式：简单复制模板结构
            doc = tpl_doc
        else:
            # 无模板：创建空文档
            doc = Document()

        # 根据目录生成骨架（并插入正文内容）
        for n in nodes:
            title = n.get("title") or ""
            level = int(n.get("level") or 1)
            # docx heading level 1..9
            h = min(max(level, 1), 9)
            doc.add_heading(title, level=h)
            
            # 插入正文内容（范本或用户编辑）
            self._insert_section_body(doc, project_id, n)
            
            # 添加备注（如果有且未被正文覆盖）
            notes = n.get("notes") or ""
            if notes:
                doc.add_paragraph(notes)

        # 保存到内存
        import io
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()

    def generate_docx_v2(self, project_id: str, format_template_id: Optional[str] = None) -> bytes:
        """
        推荐导出接口：
        - 支持 format_template_id（来自 format_templates 表）
        - 若未传，则尝试从目录节点 meta_json 推断已套用模板
        """
        # 1) 加载目录
        nodes = self.dao.list_directory(project_id)

        # 2) 推断已套用模板（如果未指定）
        if not format_template_id:
            for n in nodes:
                meta = n.get("meta_json") or {}
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}
                if isinstance(meta, dict) and meta.get("format_template_id"):
                    format_template_id = str(meta.get("format_template_id"))
                    break

        # 3) 无模板：直接导出（无底板）
        if not format_template_id:
            return self.generate_docx(project_id, template_asset_id=None)

        # 4) 有模板：加载 spec + 底板 docx
        spec = self.get_format_template_spec(format_template_id)
        tpl_doc = self._load_format_template_doc(format_template_id)
        if not spec:
            return self.generate_docx(project_id, template_asset_id=None)

        if tpl_doc:
            return self._generate_docx_with_spec(nodes, tpl_doc, spec, project_id)

        # 兜底：没找到底板 docx（旧数据/文件丢失），用 REBUILD 避免 style 不存在
        try:
            spec.base_policy.mode = BasePolicyMode.REBUILD
        except Exception:
            pass
        return self._generate_docx_with_spec(nodes, Document(), spec, project_id)

    def _insert_section_body(self, doc: Document, project_id: str, node: Dict):
        """
        插入章节正文内容
        - 如果有用户编辑内容，插入HTML转换的内容
        - 否则如果有挂载的范本，拷贝源docx的内容
        - 否则不插入内容（保持空）
        """
        from app.services.export.docx_copier import DocxBodyElementCopier
        from app.services.export.html_to_docx import HtmlToDocxInserter
        
        node_id = node.get("id")
        if not node_id:
            return
        
        # 查询章节正文
        body = self.dao.get_section_body(project_id, node_id)
        if not body:
            return
        
        source = body.get("source")
        
        # 用户编辑内容优先
        if source == "USER" and body.get("content_html"):
            HtmlToDocxInserter.insert(doc, body["content_html"])
            return
        
        # 范本挂载
        if source == "TEMPLATE_SAMPLE" and body.get("fragment_id"):
            fragment = self.dao.get_fragment_by_id(body["fragment_id"])
            if fragment:
                # 获取源文件路径
                source_file_key = fragment.get("source_file_key")
                start_idx = fragment.get("start_body_index")
                end_idx = fragment.get("end_body_index")
                
                if source_file_key and start_idx is not None and end_idx is not None:
                    try:
                        # 拷贝源文档内容
                        DocxBodyElementCopier.copy_range(
                            source_file_key,
                            start_idx,
                            end_idx,
                            doc
                        )
                    except Exception as e:
                        # 拷贝失败，添加错误提示
                        doc.add_paragraph(f"[范本内容拷贝失败: {str(e)}]")
    
    def _generate_docx_with_spec(
        self,
        nodes: List[Dict],
        tpl_doc: Document,
        spec: TemplateSpec,
        project_id: str,
    ) -> bytes:
        """
        使用 TemplateSpec 生成文档
        
        策略：
        1. 根据 base_policy 构造底板
        2. 使用 style_hints 应用样式
        """
        import io
        
        # 1. 根据 base_policy 处理底板
        if spec.base_policy.mode.value == "REBUILD":
            # 完全重建：创建空文档
            doc = Document()
        else:
            # KEEP_ALL 或 KEEP_RANGE：保留模板
            doc = tpl_doc
            if spec.base_policy.mode.value == "KEEP_RANGE":
                self._apply_keep_range(doc, spec)

        # 1.5 确保样式可用：如果模板中不存在 spec.style_hints 指向的样式，则根据 spec.style_rules 自动创建 AI_* 样式
        try:
            from app.services.export.style_applier import ensure_styles_from_spec
            ensure_styles_from_spec(doc, spec)
        except Exception:
            pass
        
        # 2. 追加目录节点，使用 style_hints
        for n in nodes:
            title = n.get("title") or ""
            level = int(n.get("level") or 1)
            
            # 获取样式提示
            style_name = OutlineMerger.get_style_hint_for_level(level, spec)
            
            if style_name:
                # 尝试使用指定样式
                try:
                    para = doc.add_paragraph(title, style=style_name)
                except Exception:
                    # 样式不存在，回退到 heading
                    h = min(max(level, 1), 9)
                    doc.add_heading(title, level=h)
            else:
                # 使用默认 heading
                h = min(max(level, 1), 9)
                doc.add_heading(title, level=h)
            
            # 插入正文内容（范本或用户编辑）
            self._insert_section_body(doc, project_id, n)
            
            # 添加备注（如果有且未被正文覆盖）
            notes = n.get("notes") or ""
            if notes:
                doc.add_paragraph(notes)
        
        # 保存到内存
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()

    def _apply_keep_range(self, doc: Document, spec: TemplateSpec) -> None:
        """
        KEEP_RANGE：尽量按 range_anchor.start_text/end_text 裁剪模板正文范围，保留页眉页脚/页边距等 section 属性。
        说明：这是“最小可用实现”，不依赖 block_id（python-docx 不保留 extractor 的 block_id）。
        """
        try:
            ra = getattr(spec.base_policy, "range_anchor", None)
            if not ra:
                return
            start_text = (getattr(ra, "start_text", None) or "").strip()
            end_text = (getattr(ra, "end_text", None) or "").strip()
            if not start_text or not end_text:
                return

            body_elms = list(doc.element.body)
            idx_map: List[int] = []
            for i, el in enumerate(body_elms):
                # sectPr 不能删
                if getattr(el, "tag", "").endswith("}sectPr"):
                    continue
                idx_map.append(i)

            def _elm_text(el) -> str:
                try:
                    from docx.text.paragraph import Paragraph
                    p = Paragraph(el, doc)  # type: ignore[arg-type]
                    return p.text or ""
                except Exception:
                    return ""

            start_i = None
            end_i = None
            for i in idx_map:
                t = _elm_text(body_elms[i])
                if start_i is None and start_text in t:
                    start_i = i
                if start_i is not None and end_text in t:
                    end_i = i
                    break

            if start_i is None or end_i is None or start_i > end_i:
                return

            for i in reversed(idx_map):
                if i < start_i or i > end_i:
                    try:
                        doc.element.body.remove(body_elms[i])
                    except Exception:
                        continue
        except Exception:
            return

    # list_rule_sets 方法已删除

    def lookup_chunks(self, chunk_ids: List[str]) -> List[Dict[str, Any]]:
        """查询 chunks（证据回溯）"""
        return self.dao.lookup_chunks(chunk_ids)

    def _parse_template_meta(self, docx_path: str) -> Dict[str, Any]:
        """
        解析模板：
        - outline_nodes: [{numbering, level, title, notes?}]  (从 Heading / 大纲样式推导)
        - style_hint:    简要信息（是否有页眉页脚/图片等）
        """
        try:
            from docx import Document as Doc
        except Exception:
            return {}

        doc = Doc(docx_path)

        # style_hint（MVP：只做存在性）
        has_header = False
        has_footer = False
        has_images = False
        try:
            for s in doc.sections:
                if s.header and s.header.paragraphs:
                    has_header = True
                if s.footer and s.footer.paragraphs:
                    has_footer = True
        except Exception:
            pass
        try:
            # 有无图片（粗略）
            has_images = bool(doc.part._package.image_parts)
        except Exception:
            pass

        # outline：按 paragraph style.name 包含 "Heading" 推 level
        outline = []
        for p in doc.paragraphs:
            txt = (p.text or "").strip()
            if not txt:
                continue
            sname = (getattr(p.style, "name", "") or "")
            if "Heading" in sname:
                # Heading 1/2/3...
                level = 1
                m = re.search(r"Heading\s+(\d+)", sname)
                if m:
                    level = int(m.group(1))
                outline.append({"title": txt, "level": level})

        # 给 outline 生成 numbering（MVP：按 level 自动编号）
        numbering_stack = []
        out_nodes = []
        for node in outline:
            lvl = max(1, min(9, int(node["level"])))
            while len(numbering_stack) < lvl:
                numbering_stack.append(0)
            while len(numbering_stack) > lvl:
                numbering_stack.pop()
            numbering_stack[lvl-1] += 1
            for i in range(lvl, len(numbering_stack)):
                numbering_stack[i] = 0
            nums = [str(n) for n in numbering_stack if n > 0]
            out_nodes.append({
                "numbering": ".".join(nums),
                "level": lvl,
                "title": node["title"],
                "source": "template",
                "is_required": False,
                "evidence_chunk_ids": [],
                "meta_json": {},
            })

        return {
            "template_outline_nodes": out_nodes,
            "style_hint": {
                "has_header": has_header,
                "has_footer": has_footer,
                "has_images": has_images,
            },
        }

    async def analyze_template_with_llm(
        self,
        docx_bytes: bytes,
        template_sha256: str,
        force: bool = False
    ) -> TemplateSpec:
        """
        使用 LLM 分析模板结构
        
        Args:
            docx_bytes: Word 文档字节内容
            template_sha256: 模板文件 SHA256 哈希
            force: 是否强制重新分析（忽略缓存）
            
        Returns:
            TemplateSpec: 模板规格
        """
        # 检查 feature flag
        if not self.settings.TEMPLATE_LLM_ANALYSIS_ENABLED:
            return create_minimal_spec(confidence=0.0, error_msg="LLM analysis disabled")
        
        # 检查缓存
        if not force and self.settings.TEMPLATE_LLM_ANALYSIS_CACHE_BY_SHA256:
            cache = get_analysis_cache()
            cached_spec_json = cache.get(
                template_sha256,
                self.settings.TEMPLATE_LLM_ANALYSIS_VERSION,
                self.settings.TEMPLATE_LLM_ANALYSIS_MODEL
            )
            if cached_spec_json:
                try:
                    return TemplateSpec.from_json(cached_spec_json)
                except Exception:
                    pass  # 缓存失效，继续分析
        
        try:
            # 1. 确定性结构化提取
            extract_result = self.docx_extractor.extract(
                docx_bytes,
                max_blocks=self.settings.TEMPLATE_LLM_ANALYSIS_MAX_BLOCKS,
                max_chars_per_block=self.settings.TEMPLATE_LLM_ANALYSIS_MAX_CHARS_PER_BLOCK
            )
            
            # 2. LLM 分析
            spec = await self.llm_analyzer.analyze(extract_result)
            
            # 3. 写入缓存
            if self.settings.TEMPLATE_LLM_ANALYSIS_CACHE_BY_SHA256 and spec.diagnostics.confidence > 0:
                cache = get_analysis_cache()
                cache.set(
                    template_sha256,
                    self.settings.TEMPLATE_LLM_ANALYSIS_VERSION,
                    self.settings.TEMPLATE_LLM_ANALYSIS_MODEL,
                    spec.to_json()
                )
            
            return spec
            
        except Exception as e:
            # Fallback: 返回最小规格
            error_msg = f"Template analysis failed: {type(e).__name__}: {str(e)}"
            return create_minimal_spec(confidence=0.0, error_msg=error_msg)

    async def import_format_template_with_analysis(
        self,
        name: str,
        docx_bytes: bytes,
        description: Optional[str] = None,
        owner_id: Optional[str] = None,
        is_public: bool = False,
        force_analyze: bool = False
    ) -> Dict[str, Any]:
        """
        导入格式模板并进行 LLM 分析
        
        Args:
            name: 模板名称
            docx_bytes: Word 文档字节内容
            description: 模板描述
            owner_id: 所有者 ID
            is_public: 是否公开
            force_analyze: 是否强制重新分析
            
        Returns:
            模板记录（包含 spec 分析结果）
        """
        # 1. 计算 SHA256
        template_sha256 = _sha256(docx_bytes)
        
        # 2. 检查是否已有相同 hash 的模板（缓存复用）
        cached_template = None
        if not force_analyze and self.settings.TEMPLATE_LLM_ANALYSIS_CACHE_BY_SHA256:
            cached_template = self.dao.get_format_template_by_sha256(template_sha256)
        
        # 3. 创建模板记录
        template = self.dao.create_format_template(
            name=name,
            description=description,
            style_config={},  # 可后续扩展
            owner_id=owner_id,
            is_public=is_public
        )
        
        template_id = template["id"]
        
        # 3.1 落盘保存模板 docx（用于导出 KEEP_ALL/KEEP_RANGE 保留页眉页脚/页边距/底板）
        self._persist_format_template_docx(template_id=template_id, docx_bytes=docx_bytes)
        
        # 4. LLM 分析（异步）
        spec: Optional[TemplateSpec] = None
        
        if cached_template and cached_template.get("template_spec_json"):
            # 复用缓存的 spec
            try:
                spec = TemplateSpec.from_json(cached_template["template_spec_json"])
                spec_json = cached_template["template_spec_json"]
                spec_version = cached_template["template_spec_version"]
                diagnostics_json = cached_template.get("template_spec_diagnostics_json")
            except Exception:
                # 缓存失败，重新分析
                spec = await self.analyze_template_with_llm(docx_bytes, template_sha256, force=False)
                spec_json = spec.to_json()
                spec_version = spec.version
                diagnostics_json = json.dumps(spec.diagnostics.to_dict() if hasattr(spec.diagnostics, 'to_dict') else {})
        else:
            # 新分析
            spec = await self.analyze_template_with_llm(docx_bytes, template_sha256, force=force_analyze)
            spec_json = spec.to_json()
            spec_version = spec.version
            diagnostics_data = {
                "confidence": spec.diagnostics.confidence,
                "warnings": spec.diagnostics.warnings,
                "ignored_as_instructions_block_ids": spec.diagnostics.ignored_as_instructions_block_ids,
                "analysis_duration_ms": spec.diagnostics.analysis_duration_ms,
                "llm_model": spec.diagnostics.llm_model
            }
            diagnostics_json = json.dumps(diagnostics_data)
        
        # 5. 更新模板记录
        self.dao.update_format_template_spec(
            template_id=template_id,
            template_sha256=template_sha256,
            template_spec_json=spec_json,
            template_spec_version=spec_version,
            template_spec_diagnostics_json=diagnostics_json
        )
        
        # 6. 返回完整模板记录
        updated_template = self.dao.get_format_template(template_id)
        result = updated_template or template
        
        # 确保日期字段是字符串（防止未转换的 datetime 对象）
        if result:
            for k in ("created_at", "updated_at", "template_spec_analyzed_at"):
                if result.get(k) and hasattr(result[k], "isoformat"):
                    result[k] = result[k].isoformat()
        
        return result

    async def reanalyze_format_template(
        self,
        template_id: str,
        docx_bytes: bytes,
        force: bool = True,
    ) -> Dict[str, Any]:
        """
        强制重新分析格式模板
        
        Args:
            template_id: 模板 ID
            docx_bytes: Word 文档字节内容
            
        Returns:
            更新后的模板记录
        """
        # 1. 计算 SHA256
        template_sha256 = _sha256(docx_bytes)

        # 1.1 更新模板 docx 文件（用于导出 KEEP_ALL/KEEP_RANGE）
        self._persist_format_template_docx(template_id=template_id, docx_bytes=docx_bytes)
        
        # 2. 强制重新分析
        spec = await self.analyze_template_with_llm(docx_bytes, template_sha256, force=force)
        
        # 3. 更新模板记录
        spec_json = spec.to_json()
        diagnostics_data = {
            "confidence": spec.diagnostics.confidence,
            "warnings": spec.diagnostics.warnings,
            "ignored_as_instructions_block_ids": spec.diagnostics.ignored_as_instructions_block_ids,
            "analysis_duration_ms": spec.diagnostics.analysis_duration_ms,
            "llm_model": spec.diagnostics.llm_model
        }
        diagnostics_json = json.dumps(diagnostics_data)
        
        self.dao.update_format_template_spec(
            template_id=template_id,
            template_sha256=template_sha256,
            template_spec_json=spec_json,
            template_spec_version=spec.version,
            template_spec_diagnostics_json=diagnostics_json
        )
        
        # 4. 返回更新后的模板
        return self.dao.get_format_template(template_id) or {}

    # ==================== 格式模板 docx 存储/加载 ====================

    def _format_templates_storage_dir(self) -> str:
        # 使用 APP_DATA_DIR（docker-compose 已挂载 ./data -> /app/data），保证容器重启可复用
        base = os.path.join(self.settings.APP_DATA_DIR, "format_templates")
        _safe_mkdir(base)
        return base

    def _format_template_docx_path(self, template_id: str) -> str:
        return os.path.join(self._format_templates_storage_dir(), f"{template_id}.docx")

    def _format_template_work_dir(self, template_id: str) -> str:
        """模板解析/预览工作目录（APP_DATA_DIR 下，可持久化）"""
        base = os.path.join(self._format_templates_storage_dir(), template_id)
        _safe_mkdir(base)
        return base

    def _format_template_assets_dir(self, template_id: str) -> str:
        d = os.path.join(self._format_template_work_dir(template_id), "assets")
        _safe_mkdir(d)
        return d

    def _format_template_preview_dir(self, template_id: str) -> str:
        d = os.path.join(self._format_template_work_dir(template_id), "preview")
        _safe_mkdir(d)
        return d

    def _persist_format_template_docx(self, template_id: str, docx_bytes: bytes) -> Optional[str]:
        """把格式模板的 docx 文件保存到磁盘，并写入 format_templates.template_storage_path（如列存在）"""
        try:
            path = self._format_template_docx_path(template_id)
            with open(path, "wb") as w:
                w.write(docx_bytes)
            try:
                self.dao.update_format_template_storage_path(template_id, path)
            except Exception:
                # 兼容：若数据库尚未执行新增列 migration，不阻断主要流程
                pass
            # best-effort：写入 SOURCE_DOCX 资产记录（若已执行 014 migration）
            try:
                self.dao.delete_format_template_assets(template_id, asset_types=["SOURCE_DOCX"])
            except Exception:
                pass
            try:
                self.dao.create_format_template_asset(
                    template_id=template_id,
                    asset_type="SOURCE_DOCX",
                    variant="DEFAULT",
                    storage_path=path,
                    file_name=os.path.basename(path),
                    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            except Exception:
                pass
            return path
        except Exception:
            return None

    # ==================== 格式模板确定性解析 / 解析预览 ====================

    def parse_format_template(self, template_id: str, force: bool = True) -> Dict[str, Any]:
        """
        确定性解析模板（header/footer 图片、section 参数、heading 样式存在性等），并落库：
        - format_templates.parse_status/parse_result_json/parse_error
        - format_template_assets：HEADER_IMG/FOOTER_IMG
        """
        tpl = self.dao.get_format_template(template_id)
        if not tpl:
            raise ValueError("Template not found")

        path = str((tpl.get("template_storage_path") or "")).strip()
        if not path or not os.path.exists(path):
            raise ValueError("Template docx not found on disk (template_storage_path missing)")

        # 重新解析：清理旧资产（DB 记录）+ 预览路径
        if force:
            try:
                self.dao.delete_format_template_assets(
                    template_id,
                    asset_types=["HEADER_IMG", "FOOTER_IMG", "PREVIEW_DOCX", "PREVIEW_PDF"],
                )
            except Exception:
                pass
            try:
                self.dao.clear_format_template_preview_paths(template_id)
            except Exception:
                pass

        assets_dir = self._format_template_assets_dir(template_id)

        try:
            doc = Document(path)
            parser = DocxTemplateDeterministicParser()
            parse_result, images = parser.parse(doc)

            # 写图片资产（原样 bytes）
            for img in images:
                try:
                    out_path = os.path.join(assets_dir, img.file_name)
                    with open(out_path, "wb") as w:
                        w.write(img.blob)
                    self.dao.create_format_template_asset(
                        template_id=template_id,
                        asset_type="HEADER_IMG" if img.where == "header" else "FOOTER_IMG",
                        variant=img.variant,
                        storage_path=out_path,
                        file_name=img.file_name,
                        content_type=img.content_type,
                        width_px=img.width_px,
                        height_px=img.height_px,
                    )
                except Exception:
                    # 单张图片失败不阻断整体解析
                    continue

            # 写 parse_result（best-effort，兼容未执行 migration 的环境）
            try:
                self.dao.update_format_template_parse_result(
                    template_id=template_id,
                    parse_status="SUCCESS",
                    parse_result_json=parse_result,
                    parse_error=None,
                    preview_docx_path=None,
                    preview_pdf_path=None,
                )
            except Exception:
                pass

            return {"template_id": template_id, "parse_status": "SUCCESS", "parse_result": parse_result}
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)}"
            try:
                self.dao.update_format_template_parse_result(
                    template_id=template_id,
                    parse_status="FAILED",
                    parse_result_json={},
                    parse_error=err,
                    preview_docx_path=None,
                    preview_pdf_path=None,
                )
            except Exception:
                pass
            return {"template_id": template_id, "parse_status": "FAILED", "parse_error": err}

    def get_format_template_parse_summary(self, template_id: str) -> Dict[str, Any]:
        tpl = self.dao.get_format_template(template_id)
        if not tpl:
            raise ValueError("Template not found")

        assets: List[Dict[str, Any]] = []
        try:
            assets = self.dao.list_format_template_assets(template_id)
        except Exception:
            assets = []

        # 资产统计：variant -> counts
        by_variant: Dict[str, Dict[str, int]] = {}
        for a in assets:
            v = str((a.get("variant") or "DEFAULT")).strip() or "DEFAULT"
            t = str((a.get("asset_type") or "")).strip()
            by_variant.setdefault(v, {"HEADER_IMG": 0, "FOOTER_IMG": 0, "PREVIEW_DOCX": 0, "PREVIEW_PDF": 0})
            if t in by_variant[v]:
                by_variant[v][t] += 1

        return {
            "template_id": template_id,
            "parse_status": tpl.get("parse_status") or "PENDING",
            "parse_error": tpl.get("parse_error"),
            "parse_updated_at": tpl.get("parse_updated_at"),
            "parse_result": tpl.get("parse_result_json") or {},
            "assets_by_variant": by_variant,
        }

    def generate_format_template_preview(self, template_id: str, fmt: str = "pdf") -> Dict[str, Any]:
        """
        生成并缓存示范预览文件：
        - 总是先确保有 parse_result（必要时触发 parse）
        - 生成 sample.docx（PREVIEW_DOCX）
        - 若 fmt=pdf 且 LibreOffice 可用，则生成 sample.pdf（PREVIEW_PDF）
        """
        tpl = self.dao.get_format_template(template_id)
        if not tpl:
            raise ValueError("Template not found")

        # ensure parse
        status = str((tpl.get("parse_status") or "PENDING")).strip()
        if status != "SUCCESS" or not (tpl.get("parse_result_json") or {}):
            self.parse_format_template(template_id, force=True)
            tpl = self.dao.get_format_template(template_id) or tpl

        fmt = (fmt or "pdf").lower().strip()
        if fmt not in ("pdf", "docx"):
            fmt = "pdf"

        # cache hit: return existing paths if available
        if fmt == "pdf":
            p = str((tpl.get("preview_pdf_path") or "")).strip()
            if p and os.path.exists(p):
                return {"format": "pdf", "path": p}
        else:
            p = str((tpl.get("preview_docx_path") or "")).strip()
            if p and os.path.exists(p):
                return {"format": "docx", "path": p}

        template_docx_path = str((tpl.get("template_storage_path") or "")).strip()
        if not template_docx_path or not os.path.exists(template_docx_path):
            raise ValueError("Template docx not found on disk")

        # collect images from assets table
        assets: List[Dict[str, Any]] = []
        try:
            assets = self.dao.list_format_template_assets(template_id)
        except Exception:
            assets = []

        images_by_variant: Dict[str, Dict[str, List[str]]] = {}
        for a in assets:
            at = str((a.get("asset_type") or "")).strip()
            if at not in ("HEADER_IMG", "FOOTER_IMG"):
                continue
            v = str((a.get("variant") or "DEFAULT")).strip() or "DEFAULT"
            images_by_variant.setdefault(v, {"header": [], "footer": []})
            sp = str((a.get("storage_path") or "")).strip()
            if not sp or not os.path.exists(sp):
                continue
            if at == "HEADER_IMG":
                images_by_variant[v]["header"].append(sp)
            else:
                images_by_variant[v]["footer"].append(sp)

        parse_result = tpl.get("parse_result_json") or {}

        # style hints from spec（如果存在）
        style_hints: Dict[str, Any] = {}
        try:
            spec = self.get_format_template_spec(template_id)
            if spec:
                d = spec.to_dict()
                style_hints = (d.get("style_hints") or {}) if isinstance(d, dict) else {}
        except Exception:
            style_hints = {}

        preview_dir = self._format_template_preview_dir(template_id)
        gen = TemplatePreviewGenerator(work_dir=preview_dir)
        docx_path = gen.generate_sample_docx(
            template_docx_path=template_docx_path,
            parse_result=parse_result,
            images_by_variant=images_by_variant,
            spec_style_hints=style_hints,
        )

        try:
            self.dao.create_format_template_asset(
                template_id=template_id,
                asset_type="PREVIEW_DOCX",
                variant="DEFAULT",
                storage_path=docx_path,
                file_name=os.path.basename(docx_path),
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        except Exception:
            pass

        pdf_path: Optional[str] = None
        if fmt == "pdf":
            pdf_path = gen.convert_to_pdf(docx_path)
            if pdf_path:
                try:
                    self.dao.create_format_template_asset(
                        template_id=template_id,
                        asset_type="PREVIEW_PDF",
                        variant="DEFAULT",
                        storage_path=pdf_path,
                        file_name=os.path.basename(pdf_path),
                        content_type="application/pdf",
                    )
                except Exception:
                    pass

        # update template preview paths (best-effort)
        try:
            self.dao.update_format_template_parse_result(
                template_id=template_id,
                parse_status=tpl.get("parse_status") or "SUCCESS",
                parse_result_json=parse_result,
                parse_error=tpl.get("parse_error"),
                preview_docx_path=docx_path,
                preview_pdf_path=pdf_path if pdf_path else None,
            )
        except Exception:
            pass

        if fmt == "pdf" and pdf_path and os.path.exists(pdf_path):
            return {"format": "pdf", "path": pdf_path}
        return {"format": "docx", "path": docx_path}

    def _load_format_template_doc(self, template_id: str) -> Optional[Document]:
        """
        加载格式模板 docx（用于导出底板）
        - 优先读取 format_templates.template_storage_path
        - 若为空/丢失，则按 template_sha256 在 data/tender_assets 里回溯查找，并回填 storage_path
        """
        tpl = self.dao.get_format_template(template_id)
        if not tpl:
            return None

        path = tpl.get("template_storage_path")
        if path and os.path.exists(path):
            try:
                return Document(path)
            except Exception:
                pass

        sha256 = (tpl.get("template_sha256") or "").strip()
        if sha256:
            found = self._find_docx_by_sha256(sha256)
            if found and os.path.exists(found):
                try:
                    self.dao.update_format_template_storage_path(template_id, found)
                except Exception:
                    pass
                try:
                    return Document(found)
                except Exception:
                    return None

        return None

    def _find_docx_by_sha256(self, target_sha256: str) -> Optional[str]:
        """
        在常见落盘目录下查找匹配 sha256 的 docx 文件（兼容旧数据）。
        - data/tender_assets/**（历史 tender 项目资产）
        - storage/attachments/**（附件上传落盘目录）
        """
        try:
            roots = [
                os.path.join("data", "tender_assets"),
                os.path.join("storage", "attachments"),
            ]

            candidates: List[str] = []
            for root in roots:
                if not os.path.exists(root):
                    continue
                for dirpath, _dirnames, filenames in os.walk(root):
                    for fn in filenames:
                        if not fn.lower().endswith(".docx"):
                            continue
                        # tender_assets 优先 template_；attachments 不做限制
                        if root.endswith(os.path.join("data", "tender_assets")) and "template_" not in fn:
                            continue
                        candidates.append(os.path.join(dirpath, fn))
                    if len(candidates) > 4000:
                        break
                if len(candidates) > 4000:
                    break

            for p in candidates:
                try:
                    with open(p, "rb") as r:
                        b = r.read()
                    if _sha256(b) == target_sha256:
                        return p
                except Exception:
                    continue
        except Exception:
            return None
        return None

    def get_format_template_spec(self, template_id: str) -> Optional[TemplateSpec]:
        """
        获取格式模板的 TemplateSpec
        
        Args:
            template_id: 模板 ID
            
        Returns:
            TemplateSpec 或 None
        """
        template = self.dao.get_format_template(template_id)
        if not template or not template.get("template_spec_json"):
            return None
        
        try:
            spec = TemplateSpec.from_json(template["template_spec_json"])
            self._normalize_template_spec_style_hints(template_id, spec)
            return spec
        except Exception:
            return None

    def _normalize_template_spec_style_hints(self, template_id: str, spec: TemplateSpec) -> None:
        """
        纠错/规范化 style_hints（避免 LLM 输出 '+标题1' 这类 doc.styles 不存在的样式名）：
        - 去掉前缀 '+' 并 trim
        - 若能加载到模板 docx，则把 heading1..5 映射到 doc.styles 中真实存在的样式名
        """
        try:
            hints = getattr(spec, "style_hints", None)
            if not hints:
                return

            def _clean(v: Any) -> Optional[str]:
                if not isinstance(v, str):
                    return None
                s = v.strip()
                while s.startswith("+"):
                    s = s[1:].strip()
                return s or None

            # 先做纯字符串清洗
            for k in (
                "heading1_style",
                "heading2_style",
                "heading3_style",
                "heading4_style",
                "heading5_style",
                "body_style",
                "table_style",
                "list_style",
            ):
                setattr(hints, k, _clean(getattr(hints, k, None)))

            tpl_doc = self._load_format_template_doc(template_id)
            if not tpl_doc:
                return

            available = set()
            try:
                for s in tpl_doc.styles:
                    try:
                        available.add(str(s.name))
                    except Exception:
                        continue
            except Exception:
                return

            def _pick_first(cands: List[str]) -> Optional[str]:
                for c in cands:
                    if c in available:
                        return c
                return None

            # heading 映射（优先英文 Heading N，其次中文 标题 N/标题N）
            level_to_attr = {
                1: "heading1_style",
                2: "heading2_style",
                3: "heading3_style",
                4: "heading4_style",
                5: "heading5_style",
            }
            for lvl, attr in level_to_attr.items():
                cur = getattr(hints, attr, None)
                if cur and cur in available:
                    continue
                fallback = _pick_first(
                    [
                        f"Heading {lvl}",
                        f"标题 {lvl}",
                        f"标题{lvl}",
                    ]
                )
                if fallback:
                    setattr(hints, attr, fallback)
        except Exception:
            return

    def get_format_template_analysis_summary(self, template_id: str) -> Dict[str, Any]:
        """
        获取模板分析摘要
        
        Args:
            template_id: 模板 ID
            
        Returns:
            分析摘要
        """
        template = self.dao.get_format_template(template_id)
        if not template:
            return {"error": "Template not found"}
        
        if not template.get("template_spec_json"):
            return {
                "analyzed": False,
                "message": "Template not analyzed yet"
            }
        
        try:
            spec = TemplateSpec.from_json(template["template_spec_json"])
            
            # 统计 outline 节点数
            def count_nodes(nodes):
                count = len(nodes)
                for node in nodes:
                    count += count_nodes(node.children)
                return count
            
            outline_node_count = count_nodes(spec.outline)
            
            # 统计样式提示
            style_hints_count = sum(1 for key in [
                "heading1_style", "heading2_style", "heading3_style",
                "body_style", "table_style"
            ] if getattr(spec.style_hints, key, None))
            
            return {
                "analyzed": True,
                "version": spec.version,
                "confidence": spec.diagnostics.confidence,
                "warnings": spec.diagnostics.warnings,
                "exclude_block_ids_count": len(spec.base_policy.exclude_block_ids),
                "outline_node_count": outline_node_count,
                "style_hints_count": style_hints_count,
                "base_policy_mode": spec.base_policy.mode.value,
                "analyzed_at": template.get("template_spec_analyzed_at"),
                "analysis_duration_ms": spec.diagnostics.analysis_duration_ms,
                "llm_model": spec.diagnostics.llm_model
            }
        except Exception as e:
            return {
                "analyzed": True,
                "error": f"Failed to parse spec: {str(e)}"
            }

    def apply_format_template_to_directory(self, project_id: str, format_template_id: str) -> List[Dict[str, Any]]:
        """
        将格式模板应用到目录（写库）：
        - 如果模板定义结构（merge_policy.template_defines_structure=true），按模板结构合并目录
        - 无论是否改结构，都把 format_template_id 写入每个节点 meta_json（作为“已套用模板”标记）
        - 返回带 bodyMeta 的目录节点（用于前端原地刷新）
        """
        template_spec = self.get_format_template_spec(format_template_id)
        nodes = self.dao.list_directory(project_id)

        if template_spec and getattr(template_spec, "merge_policy", None) and template_spec.merge_policy.template_defines_structure:
            nodes = OutlineMerger.merge_with_template(nodes, template_spec)

        # 记录所选格式模板（落库在目录节点 meta_json 中，避免额外引入项目 settings 表）
        for n in nodes:
            meta = n.get("meta_json") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            if not isinstance(meta, dict):
                meta = {}
            meta["format_template_id"] = format_template_id
            n["meta_json"] = meta

        self.dao.replace_directory(project_id, nodes)
        return self.get_directory_with_body_meta(project_id)

    async def extract_directory_with_template_merge(
        self,
        project_id: str,
        model_id: Optional[str],
        template_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        提取目录并与模板合并
        
        Args:
            project_id: 项目 ID
            model_id: LLM 模型 ID
            template_id: 格式模板 ID（可选）
            
        Returns:
            合并后的目录节点列表
        """
        # 1. 先用 AI 提取目录
        ai_nodes = await self.extract_directory(project_id, model_id)
        
        # 2. 如果指定了模板，进行合并
        if template_id:
            template_spec = self.get_format_template_spec(template_id)
            if template_spec and template_spec.merge_policy.template_defines_structure:
                # 使用 OutlineMerger 合并
                ai_nodes = OutlineMerger.merge_with_template(ai_nodes, template_spec)
        
        return ai_nodes

    def preview_directory_by_template(self, project_id: str, template_asset_id: str) -> Dict[str, Any]:
        """
        preview 规则：
        - 如果模板解析到 outline：用模板 outline 作为预览目录（source=template）
        - 否则：返回当前目录（source=tender/manual）
        - 同时返回模板的样式提示（style_hints）
        """
        assets = self.dao.get_assets_by_ids(project_id, [template_asset_id])
        if not assets:
            # 兼容：前端“格式模板”选择器传入的是 format_templates 表的 id（tpl_...）
            # 这里做一次 fallback：如果是格式模板ID，返回当前目录 + 该模板的 style_hints
            tpl = self.dao.get_format_template(template_asset_id)
            if tpl:
                spec_raw = tpl.get("template_spec_json")
                spec = {}
                if isinstance(spec_raw, str) and spec_raw.strip():
                    try:
                        spec = json.loads(spec_raw)
                    except Exception:
                        spec = {}
                elif isinstance(spec_raw, dict):
                    spec = spec_raw

                style_hints = {}
                if isinstance(spec, dict):
                    style_hints = spec.get("style_hints") or {}

                # 如果没有 style_hints，尝试使用 style_config（存储在 format_templates.style_config）
                if not style_hints:
                    style_hints = tpl.get("style_config") or {}

                # 兜底默认值（前端只关心这些字段）
                if not style_hints:
                    style_hints = {
                        "page_background": "#ffffff",
                        "font_family": "SimSun, serif",
                        "font_size": "14px",
                        "line_height": "1.6",
                        "toc_indent_1": "0px",
                        "toc_indent_2": "20px",
                        "toc_indent_3": "40px",
                        "toc_indent_4": "60px",
                    }

                # 这里先不强行用模板 outline（格式模板 outline 结构与目录节点结构不完全一致），
                # 先保证“加载样式”可用：返回当前目录 + 模板 style_hints。
                return {
                    "nodes": self.dao.list_directory(project_id),
                    "style_hints": style_hints,
                }

            raise ValueError("template asset not found")
        meta = assets[0].get("meta_json") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        
        # 获取目录节点
        outline = meta.get("template_outline_nodes") or []
        nodes = outline if isinstance(outline, list) and len(outline) > 0 else self.dao.list_directory(project_id)
        
        # 尝试获取 template_spec（如果存在）
        template_spec = meta.get("template_spec") or {}
        style_hints = template_spec.get("style_hints") if isinstance(template_spec, dict) else {}
        
        # 如果没有 style_hints，使用默认值
        if not style_hints:
            style_hints = {
                "page_background": "#ffffff",
                "font_family": "SimSun, serif",
                "font_size": "14px",
                "line_height": "1.6",
                "toc_indent_1": "0px",
                "toc_indent_2": "20px",
                "toc_indent_3": "40px",
                "toc_indent_4": "60px",
            }
        
        return {
            "nodes": nodes,
            "style_hints": style_hints,
        }

    def apply_template_to_directory(self, project_id: str, template_asset_id: str) -> int:
        """套用模板到目录"""
        result = self.preview_directory_by_template(project_id, template_asset_id)
        nodes = result["nodes"]
        # 落库：DAO 会补 parent_id/order_no
        self.dao.replace_directory(project_id, nodes)
        return len(nodes)
    
    # ==================== 项目管理（编辑、删除） ====================
    
    def update_project(self, project_id: str, name: Optional[str], description: Optional[str]) -> Dict[str, Any]:
        """
        更新项目信息
        
        Args:
            project_id: 项目ID
            name: 新项目名称（可选）
            description: 新项目描述（可选）
            
        Returns:
            更新后的项目信息
        """
        if name is not None and not name.strip():
            raise ValueError("Project name cannot be empty")
        
        return self.dao.update_project(project_id, name, description)
    
    def get_project_delete_plan(self, project_id: str) -> ProjectDeletePlanResponse:
        """
        获取项目删除计划（预检）
        
        Args:
            project_id: 项目ID
            
        Returns:
            删除计划（包含资源清单和确认令牌）
        """
        return self.deletion_orchestrator.build_plan(project_id)
    
    def delete_project(self, project_id: str, confirm_request: ProjectDeleteRequest) -> None:
        """
        删除项目（需要确认）
        
        Args:
            project_id: 项目ID
            confirm_request: 删除确认请求（包含确认令牌）
            
        Raises:
            ValueError: 确认信息不匹配
        """
        # 1. 获取当前项目信息
        project = self.dao.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        # 2. 重新生成删除计划并验证令牌
        plan = self.deletion_orchestrator.build_plan(project_id)
        if confirm_request.confirm_token != plan.confirm_token:
            raise ValueError("Confirm token mismatch. Please regenerate the delete plan.")
        
        # 3. 执行删除
        self.deletion_orchestrator.delete(project_id)
    
    # ==================== 格式模板管理扩展 ====================
    
    def update_format_template_meta(
        self,
        template_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_public: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        更新格式模板元数据
        
        Args:
            template_id: 模板ID
            name: 新名称（可选）
            description: 新描述（可选）
            is_public: 是否公开（可选）
            
        Returns:
            更新后的模板记录
        """
        if name is not None and not name.strip():
            raise ValueError("Template name cannot be empty")
        
        return self.dao.update_format_template_meta(template_id, name, description, is_public)
    
    def get_format_template_extract(self, template_id: str, docx_bytes: bytes) -> Dict[str, Any]:
        """
        获取格式模板的解析详情（blocks + exclude 信息）
        
        Args:
            template_id: 模板ID
            docx_bytes: Word 文档字节内容
            
        Returns:
            解析详情（包含 blocks 和 exclude 信息）
        """
        # 1. 提取结构化 blocks
        extract_result = self.docx_extractor.extract(docx_bytes)
        
        # 2. 获取模板的 spec
        spec = self.get_format_template_spec(template_id)
        
        # 3. 整理输出
        blocks = []
        excluded_block_ids = set()
        
        if spec and spec.base_policy and hasattr(spec.base_policy, 'excluded_block_ids'):
            excluded_block_ids = set(spec.base_policy.excluded_block_ids or [])
        
        for block in extract_result.blocks:
            block_info = {
                "block_id": block.block_id,
                "type": block.type,
                "content_preview": (block.content or "")[:100],
                "style": block.style or "",
                "excluded": block.block_id in excluded_block_ids,
            }
            blocks.append(block_info)
        
        return {
            "blocks": blocks,
            "total_blocks": len(blocks),
            "excluded_count": len(excluded_block_ids),
            "style_stats": extract_result.style_stats,
        }

    # ==================== 语义目录生成 ====================

    def generate_semantic_outline(
        self,
        project_id: str,
        mode: str = "FAST",
        max_depth: int = 5,
    ) -> Dict[str, Any]:
        """
        生成语义目录（从评分/要求推导）
        
        现在直接调用 works/tender/outline 的统一入口
        
        Args:
            project_id: 项目ID
            mode: 生成模式 FAST/FULL
            max_depth: 最大层级
            
        Returns:
            语义目录结果
        """
        from app.works.tender.outline.outline_v2_service import generate_outline_v2
        
        # 获取项目信息（用于owner_id）
        project = self.dao.get_project(project_id)
        owner_id = project.get("owner_id") if project else None
        
        # 调用统一入口
        return generate_outline_v2(
            pool=self.pool,
            project_id=project_id,
            owner_id=owner_id,
            mode=mode,
            max_depth=max_depth,
            llm_orchestrator=self.llm,
        )

    def _flatten_outline_nodes(
        self,
        nodes: List[Any],
        outline_id: str,
        project_id: str,
        parent_id: Optional[str] = None,
        order_offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        将树形目录节点扁平化为数据库存储格式
        
        Args:
            nodes: 树形节点列表
            outline_id: 目录ID
            project_id: 项目ID
            parent_id: 父节点ID
            order_offset: 排序偏移量
            
        Returns:
            扁平化节点列表
        """
        result = []
        order_no = order_offset
        
        for node in nodes:
            order_no += 1
            
            flat_node = {
                "node_id": node.node_id,
                "outline_id": outline_id,
                "project_id": project_id,
                "parent_id": parent_id,
                "level": node.level,
                "order_no": order_no,
                "numbering": node.numbering,
                "title": node.title,
                "summary": node.summary,
                "tags": node.tags,
                "evidence_chunk_ids": node.evidence_chunk_ids,
                "covered_req_ids": node.covered_req_ids,
            }
            
            result.append(flat_node)
            
            # 递归处理子节点
            if node.children:
                child_nodes = self._flatten_outline_nodes(
                    nodes=node.children,
                    outline_id=outline_id,
                    project_id=project_id,
                    parent_id=node.node_id,
                    order_offset=order_no,
                )
                result.extend(child_nodes)
                order_no += len(child_nodes)
        
        return result

    def get_semantic_outline(self, outline_id: str) -> Optional[Dict[str, Any]]:
        """
        获取语义目录（包含完整的树形结构）
        
        Args:
            outline_id: 目录ID
            
        Returns:
            完整的语义目录结果，包含树形结构
        """
        # 1. 获取目录基本信息
        outline = self.dao.get_semantic_outline(outline_id)
        if not outline:
            return None
        
        # 2. 获取要求项
        requirements = self.dao.get_requirement_items(outline_id)
        
        # 3. 获取节点（扁平）并重建树形结构
        nodes_flat = self.dao.get_semantic_outline_nodes(outline_id)
        outline_tree = self._rebuild_outline_tree(nodes_flat)
        
        # 4. 组装返回结果
        return {
            "outline_id": outline["outline_id"],
            "project_id": outline["project_id"],
            "mode": outline["mode"],
            "max_depth": outline["max_depth"],
            "status": outline["status"],
            "coverage_rate": outline["coverage_rate"],
            "diagnostics": outline.get("diagnostics_json", {}),
            "outline": outline_tree,
            "requirements": requirements,
            "created_at": outline.get("created_at"),
        }

    def _rebuild_outline_tree(self, nodes_flat: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从扁平节点列表重建树形结构
        
        Args:
            nodes_flat: 扁平节点列表
            
        Returns:
            树形节点列表
        """
        if not nodes_flat:
            return []
        
        # 构建 node_id -> node 映射
        node_map = {}
        for node in nodes_flat:
            node_copy = dict(node)
            node_copy["children"] = []
            node_map[node["node_id"]] = node_copy
        
        # 构建树形结构
        root_nodes = []
        for node in nodes_flat:
            node_obj = node_map[node["node_id"]]
            parent_id = node.get("parent_id")
            
            if parent_id and parent_id in node_map:
                # 添加到父节点的children
                node_map[parent_id]["children"].append(node_obj)
            else:
                # 根节点
                root_nodes.append(node_obj)
        
        return root_nodes

    def get_latest_semantic_outline(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        获取项目最新的语义目录
        
        Args:
            project_id: 项目ID
            
        Returns:
            最新的语义目录结果
        """
        outline = self.dao.get_latest_semantic_outline(project_id)
        if not outline:
            return None
        
        return self.get_semantic_outline(outline["outline_id"])
    
    async def _build_tender_project_context(self, project_id: str) -> str:
        """构建招标项目上下文"""
        context_parts = []
        try:
            project_info = self.dao.get_project_info(project_id)
            if project_info and project_info.get("data_json"):
                data = project_info.get("data_json", {})
                if data.get("project_name"):
                    context_parts.append(f"项目名称：{data['project_name']}")
                if data.get("tenderee"):
                    context_parts.append(f"招标人：{data['tenderee']}")
                if data.get("budget"):
                    context_parts.append(f"预算金额：{data['budget']}")
                if data.get("project_overview"):
                    context_parts.append(f"项目概况：{data['project_overview']}")
        except Exception as e:
            logger.warning(f"[TenderService] 获取项目信息失败: {e}")
        if len(context_parts) < 3:
            context_parts.append("（注：项目信息不足，请根据章节标题生成合理内容）")
        return "\n".join(context_parts)
    
    async def _retrieve_context_for_section(
        self, 
        project_id: str, 
        section_title: str,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        为章节检索相关企业资料
        
        Args:
            project_id: 项目ID
            section_title: 章节标题
            top_k: 返回的最相关片段数量
            
        Returns:
            检索结果: {
                "chunks": [...],  # 检索到的文档片段
                "quality_score": float,  # 检索质量评分 (0-1)
                "has_relevant": bool  # 是否有相关内容
            }
        """
        from app.platform.ingest.v2_service import IngestV2Service
        from app.services.db.postgres import _get_pool
        
        result = {
            "chunks": [],
            "quality_score": 0.0,
            "has_relevant": False
        }
        
        try:
            # 获取项目的知识库ID
            proj = self.dao.get_project(project_id)
            if not proj:
                logger.warning(f"项目不存在: {project_id}")
                return result
            
            kb_id = proj.get("kb_id")
            if not kb_id:
                logger.warning(f"项目未绑定知识库: {project_id}")
                return result
            
            # 构建检索query
            query = self._build_retrieval_query(section_title)
            
            # 从Milvus检索
            ingest_service = IngestV2Service(_get_pool())
            search_results = await ingest_service.search_in_kb(
                kb_id=kb_id,
                query_text=query,
                top_k=top_k,
                filters={
                    "doc_type": [
                        "qualification_doc",  # company_profile, cert_doc
                        "technical_material",  # tech_doc
                        "history_case",       # case_study
                        "financial_doc"       # finance_doc
                    ]
                }
            )
            
            if not search_results:
                return result
            
            # 评估检索质量
            quality_score = self._assess_retrieval_quality(search_results)
            has_relevant = quality_score > 0.4
            
            result = {
                "chunks": search_results,
                "quality_score": quality_score,
                "has_relevant": has_relevant
            }
            
            logger.info(
                f"[检索] 章节={section_title}, "
                f"返回={len(search_results)}条, "
                f"质量={quality_score:.2f}"
            )
            
        except Exception as e:
            logger.error(f"检索失败: {e}", exc_info=True)
        
        return result
    
    def _build_retrieval_query(self, section_title: str) -> str:
        """
        根据章节标题构建检索query
        
        Args:
            section_title: 章节标题
            
        Returns:
            检索query字符串
        """
        # 章节标题 -> 检索意图映射
        title_lower = section_title.lower()
        
        if any(kw in title_lower for kw in ["公司", "企业", "简介", "概况", "资质"]):
            return f"{section_title} 企业简介 资质证书 荣誉奖项"
        elif any(kw in title_lower for kw in ["技术", "方案", "实施", "设计"]):
            return f"{section_title} 技术方案 实施方法 技术路线"
        elif any(kw in title_lower for kw in ["案例", "业绩", "项目经验", "成功案例"]):
            return f"{section_title} 项目案例 成功业绩 类似项目"
        elif any(kw in title_lower for kw in ["财务", "报表", "审计"]):
            return f"{section_title} 财务报表 审计报告"
        else:
            return section_title
    
    def _assess_retrieval_quality(self, search_results: List[Dict]) -> float:
        """
        评估检索质量
        
        Args:
            search_results: 检索结果列表
            
        Returns:
            质量评分 (0-1)
        """
        if not search_results:
            return 0.0
        
        # 基于相似度分数和数量评估
        scores = [chunk.get("score", 0.0) for chunk in search_results]
        
        # 平均相似度
        avg_score = sum(scores) / len(scores)
        
        # 最高相似度
        max_score = max(scores)
        
        # 综合评分 (权重: 最高0.6 + 平均0.4)
        quality = max_score * 0.6 + avg_score * 0.4
        
        return min(quality, 1.0)
    
    async def _generate_section_content(
        self,
        project_id: str,
        title: str,
        level: int,
        project_context: str,
        requirements: Optional[str] = None,  # ✅ 新增：用户自定义要求
        model_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        为单个章节生成内容（使用统一组件）
        
        Returns:
            {
                "content": str,  # HTML格式的章节内容
                "evidence_chunk_ids": List[str]  # 引用的资料片段ID
                "quality_metrics": Dict  # 质量指标
            }
        """
        from app.services.generation import (
            DocumentRetriever,
            RetrievalContext,
            PromptBuilder,
            PromptContext,
            ContentGenerator,
            GenerationContext,
            QualityAssessor
        )
        from app.platform.ingest.v2_service import IngestV2Service
        from app.services.db.postgres import _get_pool
        
        # Step 1: 获取项目信息
        proj = self.dao.get_project(project_id)
        if not proj:
            raise ValueError(f"项目不存在: {project_id}")
        
        kb_id = proj.get("kb_id")
        if not kb_id:
            raise ValueError(f"项目未绑定知识库: {project_id}")
        
        project_info_dict = {}
        try:
            proj_info = self.dao.get_project_info(project_id)
            if proj_info and proj_info.get("data_json"):
                project_info_dict = proj_info["data_json"]
        except Exception as e:
            logger.warning(f"获取项目信息失败: {e}")
        
        # Step 2: 检索相关资料（使用统一组件）
        retriever = DocumentRetriever(_get_pool())
        retrieval_context = RetrievalContext(
            kb_id=kb_id,
            section_title=title,
            section_level=level,
            document_type="tender",
            project_info=project_info_dict
        )
        retrieval_result = await retriever.retrieve(retrieval_context, top_k=5)
        
        # Step 3: 构建Prompt（使用统一组件）
        prompt_builder = PromptBuilder()
        
        # ✅ 如果有用户自定义要求，构建requirements字典
        requirements_dict = None
        if requirements:
            requirements_dict = {"custom_requirements": requirements}
        
        prompt_context = PromptContext(
            document_type="tender",
            section_title=title,
            section_level=level,
            project_info=project_info_dict,
            retrieval_result=retrieval_result,
            requirements=requirements_dict  # ✅ 传递用户要求
        )
        prompt = prompt_builder.build(prompt_context)
        
        # Step 4: 生成内容（使用统一组件）
        generator = ContentGenerator(self.llm)
        gen_context = GenerationContext(
            document_type="tender",
            section_title=title,
            prompt=prompt,
            model_id=model_id
        )
        generation_result = await generator.generate(gen_context)
        
        # Step 5: 评估质量（使用统一组件）
        assessor = QualityAssessor()
        quality_metrics = assessor.assess(
            generation_result,
            retrieval_result,
            level
        )
        
        # Step 6: 记录质量指标
        logger.info(
            f"[生成] 章节={title}, "
            f"字数={generation_result.word_count}, "
            f"证据={len(retrieval_result.chunks)}条, "
            f"质量={quality_metrics.overall_score:.2f}, "
            f"等级={quality_metrics.get_grade()}"
        )
        
        return {
            "content": generation_result.content,
            "evidence_chunk_ids": retrieval_result.get_chunk_ids(),
            "quality_metrics": quality_metrics.to_dict()
        }
    
    async def generate_full_content(
        self,
        project_id: str,
        model_id: Optional[str] = None,
        run_id: Optional[str] = None,
        max_concurrent: int = 5,
    ) -> Dict[str, Any]:
        """
        并行生成标书所有章节内容
        
        Args:
            project_id: 项目ID
            model_id: LLM模型ID
            run_id: 运行记录ID
            max_concurrent: 最大并发数（默认5）
        
        Returns:
            生成结果统计
        """
        import asyncio
        
        try:
            logger.info(f"[TenderService] 开始并行生成标书内容: project_id={project_id}, max_concurrent={max_concurrent}")
            
            # 更新 run 状态
            if run_id:
                self.dao.update_run(run_id, "running", progress=0.0, message="开始生成...")
            
            # 获取所有目录节点
            nodes = self.dao.get_directory_nodes(project_id)
            if not nodes:
                raise ValueError("没有找到目录节点")
            
            # 构建项目上下文
            project_context = await self._build_tender_project_context(project_id)
            
            # 筛选需要生成内容的节点（没有section或section为空）
            nodes_to_generate = []
            for node in nodes:
                node_id = node.get("id")
                section = self.dao.get_section_body(project_id, node_id)
                
                # 如果没有section或内容为空/占位符，则需要生成
                if not section or self._is_empty_section(section):
                    nodes_to_generate.append(node)
            
            total = len(nodes_to_generate)
            logger.info(f"[TenderService] 需要生成内容的节点数: {total}")
            
            if total == 0:
                if run_id:
                    self.dao.update_run(
                        run_id,
                        "success",
                        progress=1.0,
                        message="所有章节已有内容，无需生成",
                        result_json={"generated": 0, "total": len(nodes), "skipped": len(nodes)},
                    )
                return {"generated": 0, "total": len(nodes), "skipped": len(nodes)}
            
            # 创建信号量控制并发
            semaphore = asyncio.Semaphore(max_concurrent)
            
            # 生成任务
            completed = 0
            failed = 0
            
            async def generate_one(node: Dict[str, Any], index: int) -> Tuple[bool, str]:
                """生成单个节点的内容"""
                nonlocal completed, failed
                
                async with semaphore:
                    node_id = node.get("id")
                    title = node.get("title", "")
                    level = node.get("level", 1)
                    
                    try:
                        logger.info(f"[{index+1}/{total}] 开始生成: {title}")
                        
                        # 生成内容（新版本返回字典）
                        result = await self._generate_section_content(
                            project_id=project_id,
                            title=title,
                            level=level,
                            project_context=project_context,
                            model_id=model_id,
                        )
                        
                        # 提取内容和证据
                        content = result.get("content", "")
                        evidence_chunk_ids = result.get("evidence_chunk_ids", [])
                        
                        # 保存到数据库
                        self.dao.upsert_section_body(
                            project_id=project_id,
                            node_id=node_id,
                            source="AI",  # 标记为AI生成
                            fragment_id=None,  # AI生成不关联模板片段
                            content_html=content,
                            content_json=None,
                            evidence_chunk_ids=evidence_chunk_ids,  # 存储证据ID
                        )
                        
                        completed += 1
                        logger.info(
                            f"[{index+1}/{total}] 生成成功: {title}, "
                            f"字数={len(content)}, 证据={len(evidence_chunk_ids)}条"
                        )
                        
                        # 更新进度
                        if run_id:
                            progress = completed / total
                            self.dao.update_run(
                                run_id,
                                "running",
                                progress=progress,
                                message=f"已完成 {completed}/{total} 个章节",
                            )
                        
                        return True, title
                        
                    except Exception as e:
                        failed += 1
                        error_msg = f"生成失败: {str(e)}"
                        logger.error(f"[{index+1}/{total}] {title} - {error_msg}", exc_info=True)
                        return False, title
            
            # 并行执行所有生成任务
            tasks = [generate_one(node, i) for i, node in enumerate(nodes_to_generate)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 统计结果
            success_count = sum(1 for r in results if isinstance(r, tuple) and r[0])
            
            result_json = {
                "generated": success_count,
                "failed": failed,
                "total": total,
                "skipped": len(nodes) - total,
            }
            
            # 更新 run 状态
            if run_id:
                if failed == 0:
                    self.dao.update_run(
                        run_id,
                        "success",
                        progress=1.0,
                        message=f"生成完成！成功 {success_count} 个章节",
                        result_json=result_json,
                    )
                else:
                    self.dao.update_run(
                        run_id,
                        "partial",
                        progress=1.0,
                        message=f"部分完成：成功 {success_count}，失败 {failed}",
                        result_json=result_json,
                    )
            
            logger.info(f"[TenderService] 并行生成完成: {result_json}")
            return result_json
            
        except Exception as e:
            logger.error(f"[TenderService] 并行生成失败: {e}", exc_info=True)
            if run_id:
                self.dao.update_run(
                    run_id,
                    "failed",
                    progress=0.0,
                    message=str(e),
                    result_json={"error": str(e)},
                )
            raise
    
    def _is_empty_section(self, section: Dict[str, Any]) -> bool:
        """判断section是否为空或只有占位符"""
        content_html = (section.get("content_html") or "").strip()
        content_md = (section.get("content_md") or "").strip()
        
        # 如果都为空
        if not content_html and not content_md:
            return True
        
        # 检查是否只有占位符
        placeholders = [
            "【填写】", "【待补】", "【待填写】", "[填写]", "[待补]",
            "待填写", "待补充", "TODO", "TBD", "（待补充）",
        ]
        
        content = content_html or content_md
        content = content.strip()
        
        # 移除HTML标签检查
        import re
        text_only = re.sub(r'<[^>]+>', '', content).strip()
        
        if not text_only or text_only in placeholders:
            return True
        
        # 内容太短也认为需要生成
        if len(text_only) < 10:
            return True
        
        return False