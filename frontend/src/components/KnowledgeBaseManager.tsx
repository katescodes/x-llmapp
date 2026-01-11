import React, { useCallback, useEffect, useState } from "react";
import {
  ImportResultItem,
  KnowledgeBase,
  KnowledgeBaseDocument,
  DocCategory,
  KbCategory
} from "../types";
import { api } from "../config/api";
import CategoryManager from "./CategoryManager";
import ShareButton from "./ShareButton";

const KnowledgeBaseManager: React.FC = () => {
  const [categories, setCategories] = useState<KbCategory[]>([]);
  const [showCategoryManager, setShowCategoryManager] = useState(false);
  const categoryLabels: Record<DocCategory, string> = {
    general_doc: "📄 普通文档",
    history_case: "📋 历史案例",
    reference_rule: "📘 规章制度",
    web_snapshot: "🌐 网页快照",
    tender_app: "📋 招投标文档",
    tender_notice: "📑 招标文件",
    bid_document: "📝 投标文件",
    format_template: "📋 格式模板",
    standard_spec: "📚 标准规范",
    technical_material: "🔧 技术资料",
    qualification_doc: "🏆 资质资料"
  };

  const getCategoryColor = (category: DocCategory): string => {
    const colors: Record<DocCategory, string> = {
      general_doc: "#10b981",
      history_case: "#3b82f6",
      reference_rule: "#8b5cf6",
      web_snapshot: "#f59e0b",
      tender_app: "#ef4444",
      tender_notice: "#f97316",
      bid_document: "#06b6d4",
      format_template: "#8b5cf6",
      standard_spec: "#14b8a6",
      technical_material: "#10b981",
      qualification_doc: "#f59e0b"
    };
    return colors[category] || "#6b7280";
  };
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [activeKb, setActiveKb] = useState<KnowledgeBase | null>(null);
  const [docs, setDocs] = useState<KnowledgeBaseDocument[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", category_id: "" });
  const [selectedFiles, setSelectedFiles] = useState<FileList | null>(null);
  const [kbCategory, setKbCategory] = useState<DocCategory>("general_doc");
  const [importing, setImporting] = useState(false);
  const [importProgress, setImportProgress] = useState(0);
  const [importResults, setImportResults] = useState<ImportResultItem[]>([]);

  const fetchCategories = useCallback(async () => {
    try {
      const data: KbCategory[] = await api.get('/api/kb-categories');
      setCategories(data);
    } catch (error) {
      console.error("加载分类失败", error);
    }
  }, []);

  const fetchKbs = useCallback(async () => {
    try {
      const data: KnowledgeBase[] = await api.get('/api/kb');
      setKbs(data);
      setActiveKb((prev) => {
        if (!prev) return null;
        const matched = data.find((kb) => kb.id === prev.id);
        if (!matched) {
          setDocs([]);
          return null;
        }
        return matched;
      });
    } catch (error) {
      console.error(error);
      alert("加载知识库列表失败，请检查后端日志。");
    }
  }, []);

  useEffect(() => {
    fetchCategories();
    fetchKbs();
  }, [fetchCategories, fetchKbs]);

  const loadDocs = async (kbId: string) => {
    setLoadingDocs(true);
    try {
      const data: KnowledgeBaseDocument[] = await api.get(`/api/kb/${kbId}/docs`);
      setDocs(data);
    } catch (error) {
      console.error(error);
      alert("加载文档列表失败。");
    } finally {
      setLoadingDocs(false);
    }
  };

  const handleSelectKb = (kb: KnowledgeBase) => {
    setActiveKb(kb);
    setImportResults([]);
    loadDocs(kb.id);
  };

  const handleCreateKb = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) {
      alert("知识库名称不能为空");
      return;
    }
    setCreating(true);
    try {
      const data: KnowledgeBase = await api.post('/api/kb', {
        name: form.name.trim(),
        description: form.description.trim(),
        category_id: form.category_id || null
      });
      setForm({ name: "", description: "", category_id: "" });
      await fetchKbs();
      setActiveKb(data);
      setDocs([]);
      loadDocs(data.id);
    } catch (error) {
      console.error(error);
      alert("创建知识库失败，请检查日志");
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteKb = async (kbId: string) => {
    if (!window.confirm("删除后将无法恢复，确定删除该知识库吗？")) return;
    try {
      await api.delete(`/api/kb/${kbId}`);
      if (activeKb?.id === kbId) {
        setActiveKb(null);
        setDocs([]);
      }
      fetchKbs();
    } catch (error) {
      console.error(error);
      alert("删除失败，请查看控制台输出");
    }
  };

  const handleDeleteDoc = async (docId: string) => {
    if (!activeKb) return;
    if (!window.confirm(`确认删除该文档吗？

此操作将同时删除：
✓ 文档的所有文本分块（chunks）
✓ 向量数据库中的向量记录
✓ 关联的招投标项目资产（如有）
✓ 相关的证据引用（如有）

⚠️ 此操作不可恢复！请确认是否继续？`)) return;
    try {
      await api.delete(`/api/kb/${activeKb.id}/docs/${docId}`);
      loadDocs(activeKb.id);
    } catch (error) {
      console.error(error);
      alert("删除文档失败");
    }
  };

  const handleImport = async () => {
    if (!activeKb) {
      alert("请先选择一个知识库");
      return;
    }
    if (!selectedFiles || selectedFiles.length === 0) {
      alert("请先选择需要上传的文件");
      return;
    }
    setImporting(true);
    setImportProgress(0);
    setImportResults([]);
    
    try {
      const formData = new FormData();
      Array.from(selectedFiles).forEach((file) => {
        formData.append("files", file);
      });
      formData.append("kb_category", kbCategory);
      
      // 使用统一的 api.upload 方法，支持上传进度
      const data = await api.upload(
        `/api/kb/${activeKb.id}/import`,
        formData,
        (progress) => setImportProgress(progress)
      );
      
      setImportResults(data.items || []);
      setSelectedFiles(null);
      loadDocs(activeKb.id);
    } catch (error) {
      console.error(error);
      alert(`导入失败：${error instanceof Error ? error.message : "请检查日志"}`);
    } finally {
      setImporting(false);
      setImportProgress(0);
    }
  };

  return (
    <div className="kb-page">
      <div className="kb-sidebar">
        <div className="kb-header">
          <h2>知识库列表</h2>
          <p>管理自定义文档并参与 RAG 检索</p>
        </div>
        <form className="kb-create-form" onSubmit={handleCreateKb}>
          <input
            type="text"
            placeholder="知识库名称"
            value={form.name}
            onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
          />
          <textarea
            placeholder="描述（可选）"
            value={form.description}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, description: e.target.value }))
            }
          />
          <select
            value={form.category_id}
            onChange={(e) => setForm((prev) => ({ ...prev, category_id: e.target.value }))}
            style={{
              padding: "8px",
              borderRadius: "8px",
              border: "1px solid rgba(148, 163, 184, 0.4)",
              background: "rgba(15, 23, 42, 0.7)",
              color: "#e5e7eb",
              fontSize: "13px"
            }}
          >
            <option value="">-- 无分类 --</option>
            {categories.map(cat => (
              <option key={cat.id} value={cat.id}>
                {cat.icon} {cat.display_name}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setShowCategoryManager(true)}
            style={{
              padding: "6px 12px",
              borderRadius: "8px",
              border: "1px solid rgba(148, 163, 184, 0.4)",
              background: "rgba(15, 23, 42, 0.7)",
              color: "#60a5fa",
              cursor: "pointer",
              fontSize: "12px"
            }}
          >
            ⚙️ 管理分类
          </button>
          <button type="submit" disabled={creating}>
            {creating ? "创建中…" : "创建知识库"}
          </button>
        </form>

        <div className="kb-list-panel">
          {kbs.length === 0 && (
            <div className="kb-empty">还没有知识库，先在上方创建一个吧。</div>
          )}
          {kbs.map((kb) => (
            <div
              key={kb.id}
              className={`kb-row ${activeKb?.id === kb.id ? "active" : ""}`}
              style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
            >
              <button
                style={{ flex: 1, border: 'none', background: 'transparent', cursor: 'pointer', textAlign: 'left' }}
                onClick={() => handleSelectKb(kb)}
              >
                <div className="kb-name">
                  {kb.category_icon && <span style={{ marginRight: '6px' }}>{kb.category_icon}</span>}
                  {kb.name}
                </div>
                <div className="kb-meta">
                  {kb.category_display_name && (
                    <span 
                      style={{
                        display: 'inline-block',
                        padding: '2px 6px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        background: kb.category_color || '#6b7280',
                        color: 'white',
                        marginRight: '8px',
                        fontWeight: '500'
                      }}
                    >
                      {kb.category_display_name}
                    </span>
                  )}
                  {kb.description || "暂无描述"} · 更新于 {new Date(kb.updated_at).toLocaleString()}
                </div>
              </button>
              <ShareButton
                resourceType="kb"
                resourceId={kb.id}
                resourceName={kb.name}
                isShared={kb.scope === 'organization'}
                onShareChange={() => fetchKbs()}
              />
            </div>
          ))}
        </div>
      </div>

      <div className="kb-detail">
        {!activeKb && (
          <div className="kb-empty-state">
            请选择左侧知识库查看详情，或新建一个知识库。
          </div>
        )}
        {activeKb && (
          <>
            <div className="kb-detail-header">
              <div>
                <h3>{activeKb.name}</h3>
                <p>{activeKb.description || "暂无描述"}</p>
                <small>
                  创建于 {new Date(activeKb.created_at).toLocaleString()}
                </small>
              </div>
              <button onClick={() => handleDeleteKb(activeKb.id)} className="pill-button">
                删除知识库
              </button>
            </div>

            <section className="kb-upload-section">
              <h4>导入文档</h4>
              <p style={{ marginBottom: 8 }}>
                <strong>支持格式：</strong>
                <br />
                📄 <span style={{ color: '#60a5fa' }}>文档</span>：TXT、MD、HTML、PDF、DOCX、CSV、JSON
                <br />
                🎙️ <span style={{ color: '#22c55e' }}>音频</span>：MP3、WAV、M4A、MP4、OGG、FLAC、WEBM、MPEG、MPGA
                <br />
                <small style={{ color: '#94a3b8', marginTop: 4, display: 'block' }}>
                  上传后自动解析 + 切分 + 向量化。音频文件使用本地 Whisper 模型转录（完全免费）
                </small>
              </p>
              <label className="kb-upload-category">
                <strong>文档类别：</strong>
                <span style={{ fontSize: '12px', color: '#666', marginLeft: '8px' }}>
                  （选择合适的分类有助于精准检索和决策支持）
                </span>
                <select 
                  value={kbCategory} 
                  onChange={(e) => setKbCategory(e.target.value as DocCategory)}
                  style={{ marginTop: '4px', width: '100%' }}
                >
                  <option value="general_doc">📄 普通文档 - 通用知识资料</option>
                  <option value="history_case">📋 历史案例 - 过往经验/案例记录</option>
                  <option value="reference_rule">📘 规章制度 - 政策/规范/教程</option>
                  <option value="web_snapshot">🌐 网页快照 - 从网络抓取的内容</option>
                </select>
              </label>
              <input
                type="file"
                multiple
                accept=".txt,.md,.markdown,.html,.htm,.pdf,.docx,.csv,.json,.mp3,.mp4,.mpeg,.mpga,.m4a,.wav,.webm,.ogg,.flac"
                onChange={(e) => setSelectedFiles(e.target.files)}
              />
              <button
                onClick={handleImport}
                disabled={importing}
                style={{ marginTop: 8 }}
              >
                {importing ? "导入中…" : "上传并导入"}
              </button>
              
              {/* 上传进度条 */}
              {importing && importProgress > 0 && (
                <div style={{ marginTop: 12 }}>
                  <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center',
                    marginBottom: 6 
                  }}>
                    <span style={{ fontSize: 12, color: '#94a3b8' }}>
                      {importProgress < 100 ? '上传中...' : '处理中...'}
                    </span>
                    <span style={{ fontSize: 12, color: '#60a5fa', fontWeight: 500 }}>
                      {importProgress}%
                    </span>
                  </div>
                  <div style={{
                    width: '100%',
                    height: 6,
                    backgroundColor: 'rgba(148, 163, 184, 0.2)',
                    borderRadius: 3,
                    overflow: 'hidden'
                  }}>
                    <div style={{
                      width: `${importProgress}%`,
                      height: '100%',
                      backgroundColor: importProgress < 100 ? '#60a5fa' : '#22c55e',
                      transition: 'width 0.3s ease, background-color 0.3s ease',
                      borderRadius: 3
                    }} />
                  </div>
                  {importProgress === 100 && (
                    <div style={{ 
                      fontSize: 11, 
                      color: '#94a3b8', 
                      marginTop: 4,
                      fontStyle: 'italic' 
                    }}>
                      文件已上传，正在进行向量化处理，请稍候...
                    </div>
                  )}
                </div>
              )}
              
              {importResults.length > 0 && (
                <div className="kb-import-results">
                  {importResults.map((item, idx) => (
                    <div key={`${item.filename}-${idx}`} className="kb-import-item">
                      <strong>{item.filename}</strong> - {item.status}
                      {item.chunks ? ` · ${item.chunks} 块` : ""}
                      {item.error ? ` · ${item.error}` : ""}
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="kb-doc-section">
              <h4>文档列表</h4>
              {loadingDocs && <div className="sidebar-hint">加载文档中…</div>}
              {!loadingDocs && docs.length === 0 && (
                <div className="kb-empty">尚未导入任何文档</div>
              )}
              <div className="kb-doc-grid">
                {docs.map((doc) => (
                  <div key={doc.id} className="kb-doc-card">
                    <div>
                      <div className="kb-doc-title">{doc.filename}</div>
                      <div className="kb-doc-meta">
                        <span 
                          style={{ 
                            display: 'inline-block',
                            padding: '2px 8px',
                            borderRadius: '4px',
                            fontSize: '12px',
                            fontWeight: 'bold',
                            color: 'white',
                            backgroundColor: getCategoryColor(doc.kb_category),
                            marginRight: '8px'
                          }}
                        >
                          {categoryLabels[doc.kb_category] || doc.kb_category}
                        </span>
                        状态：{doc.status}
                      </div>
                      <div className="kb-doc-meta">
                        更新时间：{new Date(doc.updated_at).toLocaleString()}
                      </div>
                      {doc.meta && doc.meta.chunks && (
                        <div className="kb-doc-meta">切片数：{doc.meta.chunks}</div>
                      )}
                    </div>
                    <button className="link-button" onClick={() => handleDeleteDoc(doc.id)}>
                      删除
                    </button>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
      </div>
      {showCategoryManager && (
        <CategoryManager
          onClose={() => setShowCategoryManager(false)}
          onCategoryChanged={() => {
            fetchCategories();
            fetchKbs();
          }}
        />
      )}
    </div>
  );
};

export default KnowledgeBaseManager;

