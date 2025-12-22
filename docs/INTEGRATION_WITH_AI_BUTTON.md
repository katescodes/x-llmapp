# "AI生成申报书"功能 - 实现对应关系

## 📍 前端按钮位置

**文件**: `frontend/src/components/DeclareWorkspace.tsx`

**位置**: 第 891-918 行

```tsx
{/* Step5: 生成申报书 */}
{activeStep === 5 && (
  <section className="kb-upload-section">
    <h4>🤖 AI 生成申报书</h4>
    <div className="sidebar-hint" style={{ marginBottom: '20px' }}>
      AI 将完整生成申报书内容，包括所有未填充的章节。
    </div>

    <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
      {/* 👇 这个按钮触发 AI 生成 */}
      <button
        onClick={handleGenerateDocument}  // 👈 关键函数
        disabled={generating || directory.length === 0}
        className="kb-create-form"
      >
        {generating ? '生成中...' : '🤖 AI 生成申报书'}
      </button>

      {/* 👇 这个按钮导出 DOCX */}
      <button
        onClick={handleExport}  // 👈 关键函数
        disabled={exporting || !docMeta}
      >
        {exporting ? '导出中...' : '📥 导出 DOCX'}
      </button>
    </div>
  </section>
)}
```

## 🔗 完整调用链路

### 1. 前端调用

```tsx
// frontend/src/components/DeclareWorkspace.tsx: 390-426

const handleGenerateDocument = async () => {
  // 调用 API 生成文档
  const run = await declareApi.generateDocument(currentProject.project_id, { sync: 1 });
  
  if (run.status === 'success') {
    setDocMeta({ generated: true, run_id: run.run_id });
    showToast('success', '申报书生成完成，可导出！');
  }
};

const handleExport = async () => {
  // 调用 API 导出 DOCX
  const blob = await declareApi.exportDocx(currentProject.project_id);
  const filename = `${currentProject.name}-申报书.docx`;
  declareApi.downloadBlob(blob, filename);
};
```

### 2. 后端路由

**文件**: `backend/app/routers/declare.py`

#### 生成文档路由

```python
# 第 255-279 行

@router.post("/projects/{project_id}/document/generate", response_model=RunOut)
def generate_document(
    project_id: str,
    bg: BackgroundTasks,
    req: Request,
    sync: int = 0,
    user=Depends(get_current_user_sync),
):
    """生成申报书文档"""
    dao = _get_dao()
    service = _get_service(req)  # 获取 DeclareService
    
    # 创建 run
    run_id = dao.create_run(project_id, "document")
    
    if sync == 1:
        # 同步执行
        service.generate_document(project_id, run_id)  # 👈 调用服务层
        run = dao.get_run(run_id)
        return run
    else:
        # 异步执行
        bg.add_task(service.generate_document, project_id, run_id)
        run = dao.get_run(run_id)
        return run
```

#### 导出 DOCX 路由

```python
# 第 282-301 行

@router.get("/projects/{project_id}/export/docx")
def export_docx(project_id: str, user=Depends(get_current_user_sync)):
    """导出 DOCX"""
    dao = _get_dao()
    document = dao.get_latest_document(project_id)  # 获取已生成的文档
    
    if not document:
        raise HTTPException(status_code=404, detail="No document found")
    
    storage_path = document.get("storage_path")
    filename = document.get("filename")
    
    if not storage_path or not os.path.exists(storage_path):
        raise HTTPException(status_code=404, detail="Document file not found")
    
    return FileResponse(
        path=storage_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
```

### 3. 服务层 - 当前实现

**文件**: `backend/app/services/declare_service.py`

```python
# 第 334-364 行

def generate_document(
    self,
    project_id: str,
    run_id: Optional[str] = None,
):
    """生成申报书文档（同步入口）"""
    from app.services.export.declare_docx_exporter import DeclareDocxExporter
    
    try:
        exporter = DeclareDocxExporter(self.dao)
        result = exporter.export(project_id)  # 👈 调用 DeclareDocxExporter
        
        # 更新 run 状态
        if run_id:
            self.dao.update_run(
                run_id,
                "success",
                progress=1.0,
                message="Document generated",
                result_json=result,
            )
        
        logger.info(f"[DeclareService] generate_document success")
        
    except Exception as e:
        logger.error(f"[DeclareService] generate_document failed: {e}")
        if run_id:
            self.dao.update_run(run_id, "failed", progress=0.0, message=str(e))
        raise
```

### 4. 导出器 - 当前实现（需要改造）

**文件**: `backend/app/services/export/declare_docx_exporter.py`

```python
# 第 15-142 行

class DeclareDocxExporter:
    """申报书 DOCX 导出器"""
    
    def export(
        self,
        project_id: str,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """导出申报书为 DOCX"""
        
        # 1. 获取项目信息
        project = self.dao.get_project(project_id)
        
        # 2. 获取目录节点
        nodes = self.dao.get_active_directory_nodes(project_id)
        
        # 3. 获取章节内容
        sections = self.dao.get_active_sections(project_id)
        sections_by_node_id = {s.get("node_id"): s for s in sections}
        
        # 4. 创建 Word 文档
        doc = Document()
        doc.add_heading(project_name, level=0)
        
        # 5. 遍历目录节点
        for node in self._build_tree(nodes):
            # 添加标题
            doc.add_heading(node["title"], level=node["level"])
            
            # 👇 添加正文（当前逻辑：直接写入已有内容）
            section = sections_by_node_id.get(node["id"])
            if section:
                content = section.get("content", "")
                if content:
                    doc.add_paragraph(content)  # 👈 这里需要改造
            # 👆
        
        # 6. 保存文档
        doc.save(storage_path)
        
        # 7. 创建文档记录
        document_id = self.dao.create_document(...)
        
        return {"document_id": document_id, "storage_path": storage_path}
```

## 🔧 需要改造的地方

### ⭐ 关键改造点：DeclareDocxExporter.export()

**改造前**：只写入已有内容，空内容就留空

```python
# 当前代码（第 81-96 行）
section = sections_by_node_id.get(node["id"])
if section:
    content = section.get("content", "")
    if content:
        doc.add_paragraph(content)  # 有内容就写，没有就空着
```

**改造后**：集成自动生成逻辑

```python
# 改造后的代码（应用我们实现的功能）

# 1. 在文件顶部导入
from app.services.export.docx_exporter import (
    AutoWriteCfg,
    build_project_context_string,
    _is_empty_or_placeholder,
    generate_section_text_by_title,
)
import re

# 2. 在 export() 方法中初始化配置
def export(self, project_id: str, output_dir: Optional[str] = None, 
           auto_generate: bool = True) -> Dict[str, Any]:  # 👈 添加参数
    """导出申报书为 DOCX"""
    
    # ... 前面代码不变 ...
    
    # 👇 新增：准备自动生成配置
    cfg = AutoWriteCfg(
        min_words_h1=1200,
        min_words_h2=800,
        min_words_h3=500,
        min_words_h4=300,
        max_tokens=1600,
        multi_round=True,
    )
    
    # 自动构建项目上下文
    project_context = build_project_context_string(project)
    
    # 内容缓存
    content_cache = {}
    # 👆
    
    # ... 创建文档代码不变 ...
    
    # 遍历目录节点（改造这里）
    for node in self._build_tree(nodes):
        # 添加标题
        doc.add_heading(node["title"], level=node["level"])
        
        # 👇 改造：添加正文（支持自动生成）
        section = sections_by_node_id.get(node["id"])
        content = section.get("content", "") if section else ""
        
        # 判断是否需要自动生成
        if auto_generate and _is_empty_or_placeholder(content):
            try:
                logger.info(f"自动生成内容: title={node['title']}, level={node['level']}")
                
                # 调用我们实现的生成函数
                generated_text = await generate_section_text_by_title(
                    title=node["title"],
                    level=node["level"],
                    project_context=project_context,
                    cfg=cfg,
                    cache=content_cache,
                )
                
                # 按空行分段写入 docx
                paragraphs = [
                    p.strip() 
                    for p in re.split(r"\n{2,}", generated_text) 
                    if p.strip()
                ]
                
                for para in paragraphs:
                    doc.add_paragraph(para)
                
                logger.info(f"自动生成完成: {len(paragraphs)} 个段落")
                
            except Exception as e:
                logger.error(f"自动生成失败: {e}")
                doc.add_paragraph(f"【自动生成内容失败：{str(e)}】")
        
        # 已有内容直接写入（不覆盖）
        elif content and not _is_empty_or_placeholder(content):
            doc.add_paragraph(content)
        # 👆
    
    # ... 后面保存文档代码不变 ...
```

### 3. 修改服务层调用（支持异步）

**文件**: `backend/app/services/declare_service.py`

```python
# 改造 generate_document 方法为异步

async def generate_document(  # 👈 改为 async
    self,
    project_id: str,
    run_id: Optional[str] = None,
    auto_generate: bool = True,  # 👈 添加参数
):
    """生成申报书文档（同步入口）"""
    from app.services.export.declare_docx_exporter import DeclareDocxExporter
    
    try:
        exporter = DeclareDocxExporter(self.dao)
        result = await exporter.export(  # 👈 改为 await
            project_id, 
            auto_generate=auto_generate
        )
        
        # ... 更新 run 状态代码不变 ...
```

### 4. 修改路由层（支持异步）

**文件**: `backend/app/routers/declare.py`

```python
# 改造路由为异步

@router.post("/projects/{project_id}/document/generate", response_model=RunOut)
async def generate_document(  # 👈 改为 async
    project_id: str,
    bg: BackgroundTasks,
    req: Request,
    sync: int = 0,
    auto_generate: bool = True,  # 👈 添加参数
    user=Depends(get_current_user_sync),
):
    """生成申报书文档"""
    dao = _get_dao()
    service = _get_service(req)
    
    run_id = dao.create_run(project_id, "document")
    
    if sync == 1:
        # 同步执行
        await service.generate_document(  # 👈 改为 await
            project_id, run_id, auto_generate=auto_generate
        )
        run = dao.get_run(run_id)
        return run
    else:
        # 异步执行
        bg.add_task(
            service.generate_document, 
            project_id, run_id, auto_generate
        )
        run = dao.get_run(run_id)
        return run
```

## 📋 改造清单

| 序号 | 文件 | 改动内容 | 状态 |
|------|------|----------|------|
| 1 | `declare_docx_exporter.py` | 导入自动生成函数，改造 `export()` 方法 | 🔴 待改造 |
| 2 | `declare_service.py` | `generate_document()` 改为异步 | 🔴 待改造 |
| 3 | `routers/declare.py` | `generate_document` 路由改为异步 | 🔴 待改造 |
| 4 | 前端（可选） | 添加"启用 AI 生成"开关 | 🟡 可选 |

## 🚀 快速改造步骤

### 步骤 1：改造 DeclareDocxExporter

在 `backend/app/services/export/declare_docx_exporter.py` 开头添加导入：

```python
from app.services.export.docx_exporter import (
    AutoWriteCfg,
    build_project_context_string,
    _is_empty_or_placeholder,
    generate_section_text_by_title,
)
import re
import asyncio
```

修改 `export()` 方法签名和内部逻辑（参考上面的"改造后代码"）。

### 步骤 2：改造 DeclareService

将 `generate_document()` 改为异步函数。

### 步骤 3：改造路由

将路由函数改为异步。

### 步骤 4：测试

```bash
# 前端点击"AI生成申报书"按钮
# 预期：生成的 docx 中每个章节都有内容，不再是空白
```

## ✅ 完成后的效果

1. **前端点击"🤖 AI 生成申报书"按钮**
2. **后端执行流程**：
   - 加载项目数据和目录节点
   - 遍历每个节点
   - 判断内容是否为空或占位符
   - 如果为空，调用 LLM 多轮生成（1000-2500字）
   - 分段写入 docx
   - 保存文档到数据库
3. **前端显示"申报书生成完成，可导出"**
4. **点击"📥 导出 DOCX"下载文件**
5. **打开 docx，每个章节都有充实的内容！**

## 📝 注意事项

1. **异步改造**：整个调用链需要改为异步（async/await）
2. **LLM 配置**：确保系统已配置可用的 LLM 模型
3. **超时处理**：多轮生成可能需要较长时间（10-30秒/节点）
4. **错误处理**：单个节点失败不影响其他节点
5. **用户体验**：考虑添加进度条显示生成进度

---

**结论**：我们实现的自动生成功能完全可以集成到现有的"AI生成申报书"按钮，只需要在 `DeclareDocxExporter` 中添加判断和调用逻辑即可！


