# 统一文档生成器完整实施方案

## 📋 项目概述

将招投标（Tender）和申报书（Declare）的文档生成逻辑统一到一个通用框架，实现代码复用和技术积累。

---

## 🎯 已完成步骤

### ✅ Phase 1.1: Tender资料上传功能

#### Step 1.1.1: 前端UI ✅
- **文件**: `frontend/src/components/TenderWorkspaceV2.tsx`
- **改动**:
  ```typescript
  // 添加新的资料类型
  type TenderAssetKind = 'tender' | 'bid' | 'template' | 'custom_rule' | 
                         'company_profile' | 'tech_doc' | 'case_study' | 
                         'finance_doc' | 'cert_doc';
  
  // 上传下拉框新增选项
  <option value="company_profile">企业资料</option>
  <option value="tech_doc">技术文档</option>
  <option value="case_study">案例证明</option>
  <option value="finance_doc">财务文档</option>
  <option value="cert_doc">证书资质</option>
  ```

#### Step 1.1.2: 数据库迁移 ✅
- **文件**: `backend/migrations/027_alter_tender_assets_add_company_kinds.sql`
- **改动**:
  - 更新`tender_project_assets.kind`字段注释
  - 添加`asset_type`字段（document|image|image_description）
  - 创建复合索引`idx_tender_project_assets_kind_type`

---

## 📝 待实施步骤清单

### Phase 1.1: 资料上传功能（剩余3步）

#### Step 1.1.3: 实现Tender资料上传接口
**文件**: `backend/app/services/tender_service.py`

```python
async def import_company_assets(
    self,
    project_id: str,
    kind: str,  # company_profile|tech_doc|case_study|finance_doc|cert_doc
    files: List[Any],
    user_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    导入企业资料文件（复用Declare的逻辑）
    
    流程:
    1. 保存文件到磁盘
    2. 调用IngestV2Service向量化
    3. 创建asset记录
    4. 返回asset列表
    """
    # 复用 declare_service.import_assets 的逻辑
    # 映射 doc_type: company_profile -> tender_company_profile
    pass
```

**路由**: `backend/app/routers/tender.py`
```python
@router.post("/projects/{project_id}/company-assets/import")
async def import_company_assets(
    project_id: str,
    kind: str = Form(...),
    files: List[UploadFile] = File(...),
    user=Depends(get_current_user),
):
    service = _get_service()
    assets = await service.import_company_assets(project_id, kind, files, user.user_id)
    return {"assets": assets}
```

#### Step 1.1.4: 资料向量化入库
**关键点**:
- 使用`IngestV2Service`（已有）
- doc_type映射：
  ```python
  doc_type_map = {
      "company_profile": "tender_company_profile",
      "tech_doc": "tender_tech_doc",
      "case_study": "tender_case_study",
      "finance_doc": "tender_finance_doc",
      "cert_doc": "tender_cert_doc",
  }
  ```
- 确保`doc_type_mapper.py`中有这些映射

#### Step 1.1.5: 测试资料上传
- 前端上传企业资料
- 验证Milvus中有向量数据
- 验证PostgreSQL中有asset记录

---

### Phase 1.2: 检索功能集成（5步）

#### Step 1.2.1: 添加章节检索方法
**文件**: `backend/app/services/tender_service.py`

```python
async def retrieve_context_for_section(
    self,
    project_id: str,
    section_title: str,
    requirement_keywords: List[str],
    top_k: int = 80,
) -> Dict[str, Any]:
    """
    为章节检索相关企业资料
    
    Args:
        section_title: 章节标题
        requirement_keywords: 该章节的招标要求关键词
        top_k: 检索数量
    
    Returns:
        {
            "chunks": [...],  # 检索到的文本片段
            "total_chars": 1234,
            "avg_similarity": 0.85,
            "quality_score": 0.9
        }
    """
    from app.platform.retrieval.retriever import UnifiedRetriever
    
    # 构建query
    query = f"{section_title} {' '.join(requirement_keywords)}"
    
    # 检索
    retriever = UnifiedRetriever(self.pool)
    chunks = await retriever.retrieve(
        query=query,
        project_id=project_id,
        doc_types=["tender_company_profile", "tender_tech_doc", "tender_case_study"],
        top_k=top_k
    )
    
    # 评估质量
    quality = self._assess_retrieval_quality(chunks)
    
    return {
        "chunks": chunks,
        "total_chars": sum(len(c.text) for c in chunks),
        "avg_similarity": quality["avg_similarity"],
        "quality_score": quality["score"]
    }
```

#### Step 1.2.2: 构建检索query
**关键点**:
- query = 章节标题 + 招标要求关键词
- 例如: "项目经理资格 + 建造师证书 + 项目经验 + 类似项目"

#### Step 1.2.3: 从Milvus检索
- 使用`UnifiedRetriever`（已有）
- 指定doc_types为企业资料类型

#### Step 1.2.4: 评估检索质量
```python
def _assess_retrieval_quality(self, chunks: List[Any]) -> Dict[str, Any]:
    """
    评估检索质量
    
    返回:
        {
            "score": 0.0-1.0,  # 综合评分
            "avg_similarity": 0.0-1.0,
            "chunk_count": int,
            "total_chars": int,
            "is_sufficient": bool  # 是否足够生成
        }
    """
    if not chunks:
        return {"score": 0.0, "is_sufficient": False}
    
    avg_sim = sum(c.similarity for c in chunks) / len(chunks)
    total_chars = sum(len(c.text) for c in chunks)
    
    # 评分规则
    score = 0.0
    if len(chunks) >= 5: score += 0.3
    if avg_sim >= 0.7: score += 0.4
    if total_chars >= 500: score += 0.3
    
    return {
        "score": score,
        "avg_similarity": avg_sim,
        "chunk_count": len(chunks),
        "total_chars": total_chars,
        "is_sufficient": score >= 0.6
    }
```

#### Step 1.2.5: 测试检索功能
- 上传企业资料
- 调用检索接口
- 验证能检索到相关内容

---

### Phase 1.3: 改造生成逻辑（5步）

#### Step 1.3.1: 修改`_generate_section_content`
**文件**: `backend/app/services/tender_service.py`

```python
async def _generate_section_content(
    self,
    title: str,
    level: int,
    project_context: str,  # 原有的项目信息
    model_id: Optional[str] = None,
    # 新增参数
    project_id: Optional[str] = None,
    requirement_keywords: Optional[List[str]] = None,
) -> str:
    """为单个章节生成内容（增强版）"""
    
    # 1. 检索企业资料（如果提供了project_id）
    company_context = ""
    evidence_chunk_ids = []
    generation_mode = "template_based"  # 默认模板模式
    
    if project_id and requirement_keywords:
        retrieval_result = await self.retrieve_context_for_section(
            project_id, title, requirement_keywords
        )
        
        if retrieval_result["quality_score"] >= 0.6:
            # 检索质量足够，使用资料驱动模式
            generation_mode = "evidence_based"
            company_context = self._format_chunks_for_prompt(retrieval_result["chunks"])
            evidence_chunk_ids = [c.chunk_id for c in retrieval_result["chunks"]]
    
    # 2. 构建增强Prompt
    prompt = self._build_enhanced_prompt(
        title=title,
        level=level,
        project_context=project_context,
        company_context=company_context,
        mode=generation_mode
    )
    
    # 3. LLM生成
    content = await self._call_llm(prompt, model_id)
    
    # 4. 后处理
    content = self._postprocess_content(content)
    
    return content
```

#### Step 1.3.2: 在Prompt中注入企业资料
```python
def _build_enhanced_prompt(
    self,
    title: str,
    level: int,
    project_context: str,
    company_context: str,
    mode: str
) -> str:
    """构建增强Prompt"""
    
    min_words = {1: 1200, 2: 800, 3: 500, 4: 300}.get(level, 200)
    
    system = (
        "你是专业的投标文件撰写专家，擅长根据招标要求和企业实际情况生成规范、专业的投标书内容。"
    )
    
    user = f"""
【章节标题】{title}
【标题层级】第{level}级

【招标项目信息】
{project_context}

【企业资料】
{company_context if company_context else "（无企业资料，请生成通用内容）"}

【生成模式】{mode}
- evidence_based: 优先使用企业资料，突出企业优势
- template_based: 生成符合行业规范的通用内容框架

【输出要求】
1. 输出HTML格式的章节内容
2. 内容至少{min_words}字，分为3-6段
3. 如果有企业资料，必须基于资料撰写，突出企业真实优势
4. 如果无企业资料，生成合理的占位内容（标注【待补充】）
5. 不要输出章节标题，只输出正文内容
"""
    
    return {"system": system, "user": user}
```

#### Step 1.3.3: 根据检索质量选择生成模式
- quality_score >= 0.6 → evidence_based
- quality_score < 0.6 → template_based

#### Step 1.3.4: 记录evidence_chunk_ids
- 在生成结果中记录引用的资料chunk_id
- 存储到数据库（可能需要扩展tender_sections表）

#### Step 1.3.5: 测试生成内容
- 有资料：生成内容包含企业实际信息
- 无资料：生成通用框架内容

---

## 🏗️ Phase 2: 提取共性组件（25步）

### 关键文件结构

```
backend/app/works/common/
├── __init__.py
├── document_generator.py       # 抽象生成器基类
├── context_retriever.py        # 通用检索器
├── prompt_builder.py           # Prompt构建器
├── quality_assessor.py         # 质量评估器
└── types.py                    # 共享类型定义
```

### 核心抽象类设计

```python
# document_generator.py
class ResponseDocumentGenerator(ABC):
    """响应式文档生成器抽象基类"""
    
    @abstractmethod
    async def extract_section_requirements(
        self, section_title: str, all_requirements: Any
    ) -> Dict[str, Any]:
        """从全局要求中提取该章节的要求"""
        pass
    
    @abstractmethod
    def build_section_prompt(
        self, section: Dict, requirements: Dict, context: Dict, mode: str
    ) -> Dict[str, str]:
        """构建章节Prompt"""
        pass
    
    async def generate_section(
        self, section: Dict
    ) -> Dict[str, Any]:
        """生成单个章节（通用流程）"""
        # 1. 提取章节要求
        requirements = await self.extract_section_requirements(
            section["title"], self.all_requirements
        )
        
        # 2. 检索相关资料
        context = await self.retriever.retrieve(
            query=section["title"] + " " + requirements["keywords"],
            project_id=self.project_id,
            top_k=80
        )
        
        # 3. 评估检索质量
        quality = self.assessor.assess(context)
        mode = "evidence_based" if quality["is_sufficient"] else "template_based"
        
        # 4. 构建Prompt
        prompt = self.build_section_prompt(section, requirements, context, mode)
        
        # 5. LLM生成
        result = await self.llm.generate(prompt)
        
        # 6. 后处理
        content = self.postprocess(result, context)
        
        return {
            "content": content,
            "evidence_chunk_ids": context["chunk_ids"],
            "confidence": quality["score"],
            "mode": mode
        }
```

---

## 🎨 Phase 3: 统一Prompt模板（27步）

### 通用Prompt模板结构

```markdown
# prompts/common_section_generation.md

你是{document_type}撰写专家（{document_type_desc}）。

## 任务
为{document_type}章节"{section_title}"撰写完整、专业的内容。

## 背景信息
- **章节标题**: {section_title}
- **章节层级**: H{level}
- **{requirements_label}**: {requirements_text}

## 可用资料
【检索质量】检索到 {chunk_count} 个相关片段，总字数约 {total_chars} 字

【{evidence_label}】
{context_text}

## 生成模式
当前模式: {mode}
- evidence_based: 优先使用资料，突出真实优势
- template_based: 生成行业标准框架，标注待补充

## 撰写要求
1. **字数要求**: 至少 {min_words} 字，分为 {min_paragraphs}-{max_paragraphs} 段
2. **风格侧重**: {style_hint}
3. **对标要求**: {requirement_matching_instruction}
4. **证据使用**: {evidence_usage_instruction}
5. **输出格式**: {output_format}

## 输出
{output_instruction}
```

### 配置参数映射

**Tender配置**:
```python
{
    "document_type": "投标书",
    "document_type_desc": "招投标专家",
    "requirements_label": "招标要求",
    "evidence_label": "企业资料",
    "requirement_matching_instruction": "逐项响应招标要求，突出符合性和优势",
    "evidence_usage_instruction": "优先使用企业真实资料，突出案例和业绩",
    "output_format": "HTML",
}
```

**Declare配置**:
```python
{
    "document_type": "申报书",
    "document_type_desc": "申报文档专家",
    "requirements_label": "申报要求",
    "evidence_label": "用户资料",
    "requirement_matching_instruction": "严格对照申报标准，体现创新性和符合性",
    "evidence_usage_instruction": "基于用户资料，可合理扩展，突出优势亮点",
    "output_format": "Markdown（支持图片占位符{image:xxx}）",
}
```

---

## 🧪 Phase 4: 测试与优化（20步）

### 测试用例设计

**测试项目1**: 有充足企业资料
- 上传: 企业简介、技术方案、案例证明、财务报表、资质证书
- 预期: 生成内容详实、数据真实、confidence: high

**测试项目2**: 资料较少
- 上传: 仅企业简介
- 预期: 部分章节confidence: medium/low，有【待补充】占位

**测试项目3**: 无企业资料
- 上传: 仅招标文件
- 预期: 生成通用框架，confidence: low，大量【待补充】

### 质量评估指标

1. **内容真实性**: 生成的数据是否来自实际资料
2. **完整性**: 是否有空白章节或过短内容
3. **专业性**: 语言是否规范、逻辑是否清晰
4. **可用性**: 用户是否可以直接使用或仅需少量修改

---

## 📊 实施进度跟踪

### 已完成
- ✅ Phase 1.1.1: Tender前端UI
- ✅ Phase 1.1.2: 数据库迁移

### 进行中
- 🔄 Phase 1.1.3: Tender资料上传接口
- 🔄 Phase 1.1.4: 资料向量化入库
- 🔄 Phase 1.1.5: 测试资料上传

### 待开始
- ⏳ Phase 1.2: 检索功能集成（5步）
- ⏳ Phase 1.3: 改造生成逻辑（5步）
- ⏳ Phase 2: 提取共性组件（25步）
- ⏳ Phase 3: 统一Prompt模板（27步）
- ⏳ Phase 4: 测试与优化（20步）
- ⏳ Phase 5: 扩展性准备（12步）

---

## 🎯 关键决策点

### 1. 是否需要完全统一？
**建议**: 渐进式统一
- 先实现Tender的资料检索（Phase 1）
- 验证效果后再决定是否全面重构（Phase 2-3）

### 2. 性能考虑
- 检索top_k=80可能较慢，考虑分批检索
- 并行生成章节时注意LLM并发限制

### 3. 向后兼容
- 保留现有接口，新功能作为可选参数
- 渐进式迁移，避免破坏现有功能

---

## 📝 下一步行动

**立即执行**:
1. 完成Phase 1.1（Tender资料上传）
2. 完成Phase 1.2（检索功能）
3. 完成Phase 1.3（生成逻辑改造）
4. 测试Tender端到端流程

**评估后决定**:
- 如果效果显著 → 继续Phase 2-3（架构重构）
- 如果效果一般 → 调整策略，优化Prompt

---

**文档版本**: v1.0  
**创建日期**: 2026-01-02  
**预计完成**: 2-3周

