/**
 * 格式模板管理页面
 * 包含列表、详情、解析预览等功能
 */
import React, { useState, useEffect } from 'react';
import { api, API_BASE_URL } from '../config/api';
import { FormatTemplate } from '../types/tender';
import RichTocPreview from './template/RichTocPreview';
import { templateSpecToTemplateStyle, templateSpecToTocItems } from './template/templatePreviewUtils';
import ShareButton from './ShareButton';
import '../styles.css';

type Props = {
  embedded?: boolean;
  onBack?: () => void;
};

export default function FormatTemplatesPage({ embedded, onBack }: Props) {
  const [templates, setTemplates] = useState<FormatTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  
  // 视图状态：'list' | 'detail'
  const [view, setView] = useState<'list' | 'detail'>('list');
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  
  // 创建模板
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTemplateName, setNewTemplateName] = useState('');
  const [newTemplateDesc, setNewTemplateDesc] = useState('');
  const [newTemplateFile, setNewTemplateFile] = useState<File | null>(null);
  const [isPublic, setIsPublic] = useState(false);
  const [creating, setCreating] = useState(false);

  // 详情页状态
  const [template, setTemplate] = useState<FormatTemplate | null>(null);
  const [spec, setSpec] = useState<any>(null);
  const [summary, setSummary] = useState<any>(null);
  const [parseSummary, setParseSummary] = useState<any>(null);
  const [templateAnalysis, setTemplateAnalysis] = useState<any>(null); // 新增：模板分析结果
  const [activeTab, setActiveTab] = useState<'preview' | 'docPreview' | 'spec' | 'diagnostics' | 'analysis'>('preview');
  const [previewNonce, setPreviewNonce] = useState<number>(Date.now());
  const [docPreviewUrl, setDocPreviewUrl] = useState<string | null>(null);
  const [docPreviewFormat, setDocPreviewFormat] = useState<'pdf' | 'docx' | null>(null);
  const [docPreviewLoading, setDocPreviewLoading] = useState(false);
  const [docPreviewError, setDocPreviewError] = useState<string | null>(null);

  // 编辑状态
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [editDesc, setEditDesc] = useState('');

  // 替换文件
  const [replacingFile, setReplacingFile] = useState(false);
  const [newFile, setNewFile] = useState<File | null>(null);

  // 重新分析
  const [reanalyzing, setReanalyzing] = useState(false);

  // 加载模板列表
  const loadTemplates = async () => {
    setLoading(true);
    try {
      const data = await api.get('/api/apps/tender/format-templates');
      setTemplates(data);
    } catch (err) {
      console.error('Failed to load templates:', err);
      alert(`加载失败: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTemplates();
  }, []);

  // 加载详情
  useEffect(() => {
    if (view === 'detail' && selectedTemplateId) {
      loadTemplateDetail(selectedTemplateId);
    }
  }, [view, selectedTemplateId]);

  const loadTemplateDetail = async (templateId: string) => {
    try {
      console.log('[加载详情] 开始加载模板详情:', templateId);
      const [templateData, specData, summaryData, parseSummaryData, analysisData] = await Promise.all([
        api.get(`/api/apps/tender/format-templates/${templateId}`),
        api.get(`/api/apps/tender/format-templates/${templateId}/spec`).catch((e) => { console.warn('[spec] 加载失败:', e); return null; }),
        api.get(`/api/apps/tender/format-templates/${templateId}/analysis-summary`).catch((e) => { console.warn('[analysis-summary] 加载失败:', e); return null; }),
        api.get(`/api/apps/tender/format-templates/${templateId}/parse-summary`).catch((e) => { console.warn('[parse-summary] 加载失败:', e); return null; }),
        api.get(`/api/apps/tender/templates/${templateId}/analysis`).catch((e) => { console.error('[analysis] 加载失败:', e); return null; }), // 新增：加载模板分析
      ]);
      
      console.log('[加载详情] analysisData:', analysisData);
      console.log('[加载详情] analysisData type:', typeof analysisData);
      console.log('[加载详情] has analysis_summary?', analysisData?.analysis_summary);
      
      setTemplate(templateData);
      setSpec(specData);
      setSummary(summaryData);
      setParseSummary(parseSummaryData);
      setTemplateAnalysis(analysisData); // 新增：设置分析结果
      setEditName(templateData.name);
      setEditDesc(templateData.description || '');
    } catch (err) {
      console.error('Failed to load template detail:', err);
      alert(`加载详情失败: ${err}`);
    }
  };

  const getToken = () =>
    localStorage.getItem('auth_token') ||
    localStorage.getItem('access_token') ||
    localStorage.getItem('token') ||
    '';

  const cleanupDocPreviewUrl = (u: string | null) => {
    try {
      if (u) URL.revokeObjectURL(u);
    } catch {
      // ignore
    }
  };

  const fetchDocPreview = async (templateId: string, want: 'pdf' | 'docx' = 'pdf') => {
    setDocPreviewLoading(true);
    setDocPreviewError(null);
    try {
      cleanupDocPreviewUrl(docPreviewUrl);
      setDocPreviewUrl(null);
      setDocPreviewFormat(null);

      const token = getToken();
      const url = `${API_BASE_URL}/api/apps/tender/format-templates/${templateId}/preview?format=${want}&ts=${Date.now()}`;
      const res = await fetch(url, {
        method: 'GET',
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      if (res.status === 401) throw new Error('未授权，请重新登录');
      if (res.status === 403) throw new Error('权限不足');
      if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);

      const ct = (res.headers.get('content-type') || '').toLowerCase();
      const blob = await res.blob();
      const objUrl = URL.createObjectURL(blob);

      setDocPreviewUrl(objUrl);
      setDocPreviewFormat(ct.includes('application/pdf') ? 'pdf' : 'docx');
      setActiveTab('docPreview');
    } catch (e: any) {
      setDocPreviewError(String(e?.message || e || '预览加载失败'));
      // 失败时也切换到docPreview标签页，显示错误信息
      setActiveTab('docPreview');
    } finally {
      setDocPreviewLoading(false);
    }
  };

  useEffect(() => {
    return () => {
      cleanupDocPreviewUrl(docPreviewUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    // 模板切换时清理旧的 objectUrl，避免内存泄漏
    cleanupDocPreviewUrl(docPreviewUrl);
    setDocPreviewUrl(null);
    setDocPreviewFormat(null);
    setDocPreviewError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTemplateId]);

  // 创建模板
  const handleCreate = async () => {
    if (!newTemplateName.trim()) {
      alert('请输入模板名称');
      return;
    }
    if (!newTemplateFile) {
      alert('请选择模板文件');
      return;
    }

    setCreating(true);
    try {
      const formData = new FormData();
      formData.append('name', newTemplateName);
      if (newTemplateDesc) formData.append('description', newTemplateDesc);
      formData.append('is_public', isPublic.toString());
      formData.append('file', newTemplateFile);

      await api.post('/api/apps/tender/format-templates', formData);
      setShowCreateModal(false);
      setNewTemplateName('');
      setNewTemplateDesc('');
      setNewTemplateFile(null);
      setIsPublic(false);
      await loadTemplates();
      alert('模板创建成功，正在解析中...');
    } catch (err) {
      alert(`创建失败: ${err}`);
    } finally {
      setCreating(false);
    }
  };

  // 删除模板
  const handleDelete = async (templateToDelete: FormatTemplate) => {
    if (!confirm(`确定要删除模板"${templateToDelete.name}"吗？`)) return;

    try {
      await api.delete(`/api/apps/tender/format-templates/${templateToDelete.id}`);
      await loadTemplates();
      // 如果删除的是当前查看的模板，返回列表
      if (templateToDelete.id === selectedTemplateId) {
        setView('list');
        setSelectedTemplateId(null);
      }
      alert('删除成功');
    } catch (err) {
      alert(`删除失败: ${err}`);
    }
  };

  // 更新元数据
  const handleSaveEdit = async () => {
    if (!template) return;
    try {
      const updated = await api.put(`/api/apps/tender/format-templates/${template.id}`, {
        name: editName,
        description: editDesc,
      });
      setTemplate(updated);
      setEditing(false);
      await loadTemplates();
      alert('更新成功');
    } catch (err) {
      alert(`更新失败: ${err}`);
    }
  };

  // 替换文件并重新分析
  const handleReplaceFile = async () => {
    if (!template || !newFile) {
      alert('请选择文件');
      return;
    }

    setReplacingFile(true);
    try {
      const formData = new FormData();
      formData.append('file', newFile);

      await api.request(`/api/apps/tender/format-templates/${template.id}/file`, {
        method: 'PUT',
        body: formData,
      });

      setNewFile(null);
      await loadTemplateDetail(template.id);
      alert('文件替换成功，正在重新分析...');
    } catch (err) {
      alert(`替换失败: ${err}`);
    } finally {
      setReplacingFile(false);
    }
  };

  // 强制重新分析
  const handleForceAnalyze = async () => {
    if (!template || !newFile) {
      alert('请先选择文件');
      return;
    }

    try {
      const formData = new FormData();
      formData.append('file', newFile);
      formData.append('force', 'true');

      await api.post(`/api/apps/tender/format-templates/${template.id}/analyze?force=true`, formData);

      setNewFile(null);
      await loadTemplateDetail(template.id);
      alert('重新分析完成');
    } catch (err) {
      alert(`分析失败: ${err}`);
    }
  };

  // 触发“确定性解析”（header/footer 图片 + section/variants + headingLevels）
  const handleDeterministicParse = async () => {
    if (!template) return;
    try {
      await api.request(`/api/apps/tender/format-templates/${template.id}/parse?force=true`, { method: 'POST' });
      const ps = await api.get(`/api/apps/tender/format-templates/${template.id}/parse-summary`).catch(() => null);
      setParseSummary(ps);
      // 解析后刷新预览（pdf 优先）
      await fetchDocPreview(template.id, 'pdf');
    } catch (err) {
      alert(`解析失败: ${err}`);
    }
  };

  const handleRefreshDocPreview = async () => {
    if (!template) return;
    setPreviewNonce(Date.now());
    await fetchDocPreview(template.id, 'pdf');
  };

  // 重新分析模板
  const handleReanalyze = async () => {
    if (!template) return;
    
    if (!confirm('确定要重新分析此模板吗？这将使用LLM重新解析模板结构，可能需要10-30秒。')) {
      return;
    }

    setReanalyzing(true);
    const startTime = Date.now();
    
    try {
      console.log('[模板分析] 开始分析...');
      await api.post(`/api/apps/tender/templates/${template.id}/reanalyze`);
      
      const duration = ((Date.now() - startTime) / 1000).toFixed(1);
      console.log(`[模板分析] 分析完成，耗时 ${duration}s`);
      
      // 重新加载详情
      await loadTemplateDetail(template.id);
      
      // 使用更明显的提示
      const message = `✅ 模板分析完成！\n\n耗时: ${duration}秒\n请查看"模板分析"标签页的结果。`;
      alert(message);
      
      // 自动切换到分析标签页
      setActiveTab('analysis');
    } catch (err) {
      console.error('[模板分析] 分析失败:', err);
      const message = `❌ 模板分析失败\n\n错误: ${err}\n\n请检查：\n1. 模板文件是否完整\n2. LLM 服务是否正常\n3. 网络连接是否稳定`;
      alert(message);
    } finally {
      setReanalyzing(false);
    }
  };

  // 解析状态显示
  const getAnalysisStatus = (t: FormatTemplate) => {
    if (!t.template_spec_analyzed_at) {
      return <span style={{ color: '#ffc107' }}>待解析</span>;
    }
    return <span style={{ color: '#28a745' }}>已解析</span>;
  };

  // 渲染列表视图
  if (view === 'list') {
    const inner = (
      <div style={{ padding: embedded ? 0 : '20px' }}>
        {embedded && (
          <div className="header-bar" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <button className="link-button" onClick={onBack}>
              ← 返回
            </button>
            <div className="header-title">格式模板管理</div>
            <div style={{ width: 60 }} />
          </div>
        )}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <div>
                <h2 style={{ margin: 0, color: '#e2e8f0' }}>格式模板管理</h2>
                <p style={{ margin: '4px 0 0', color: '#a0aec0' }}>
                  管理投标文档格式模板，支持 AI 解析和样式预览
                </p>
              </div>
              <button className="sidebar-btn primary" onClick={() => setShowCreateModal(true)}>
                ➕ 新建模板
              </button>
            </div>

            {loading ? (
              <div className="kb-empty">加载中...</div>
            ) : templates.length === 0 ? (
              <div className="kb-empty">
                暂无模板，点击"新建模板"开始创建
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
                {templates.map(t => (
                  <div
                    key={t.id}
                    className="kb-row"
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      padding: '16px',
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                    }}
                    onClick={() => {
                      setSelectedTemplateId(t.id);
                      setView('detail');
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px' }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="kb-name" style={{ marginBottom: '4px' }}>{t.name}</div>
                        {t.description && (
                          <div className="kb-meta">{t.description}</div>
                        )}
                      </div>
                      <div style={{ marginLeft: '8px' }}>
                        {getAnalysisStatus(t)}
                      </div>
                    </div>

                    <div style={{ fontSize: '12px', color: '#a0aec0', marginTop: 'auto' }}>
                      <div>更新: {t.updated_at ? new Date(t.updated_at).toLocaleDateString() : 'N/A'}</div>
                      {t.is_public && (
                        <div style={{ color: '#4299e1', marginTop: '4px' }}>🌐 公开</div>
                      )}
                    </div>

                    <div style={{ display: 'flex', gap: '8px', marginTop: '12px', alignItems: 'center' }}>
                      <ShareButton
                        resourceType="template"
                        resourceId={t.id}
                        resourceName={t.name}
                        isShared={t.scope === 'organization'}
                        onShareChange={() => loadTemplates()}
                      />
                      <button
                        className="sidebar-btn"
                        style={{ flex: 1, fontSize: '12px' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedTemplateId(t.id);
                          setView('detail');
                        }}
                      >
                        查看详情
                      </button>
                      <button
                        className="sidebar-btn"
                        style={{ fontSize: '12px', background: '#dc3545' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(t);
                        }}
                      >
                        删除
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
      </div>
    );

    if (embedded) {
      return (
        <div className="kb-detail" style={{ height: "100%", overflow: "auto", padding: "16px" }}>
          {inner}

        {/* 创建模板模态框 */}
        {showCreateModal && (
          <div className="modal-overlay" onClick={() => !creating && setShowCreateModal(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '600px' }}>
              <h3 style={{ margin: '0 0 24px 0', color: '#e2e8f0', fontSize: '20px', fontWeight: 600 }}>新建格式模板</h3>

              <div style={{ marginBottom: '20px' }}>
                <label className="label-text" style={{ display: 'block', marginBottom: '8px', color: '#cbd5e1', fontSize: '14px' }}>
                  模板名称 <span style={{ color: '#ef4444' }}>*</span>
                </label>
                <input
                  type="text"
                  value={newTemplateName}
                  onChange={(e) => setNewTemplateName(e.target.value)}
                  placeholder="例如：水务自动化投标书模板"
                  className="sidebar-input"
                  style={{ 
                    width: '100%',
                    padding: '10px 12px',
                    fontSize: '14px',
                    marginBottom: 0,
                    boxSizing: 'border-box'
                  }}
                />
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label className="label-text" style={{ display: 'block', marginBottom: '8px', color: '#cbd5e1', fontSize: '14px' }}>
                  描述
                </label>
                <textarea
                  value={newTemplateDesc}
                  onChange={(e) => setNewTemplateDesc(e.target.value)}
                  placeholder="可选，描述模板的用途和特点"
                  className="sidebar-input"
                  style={{ 
                    width: '100%',
                    minHeight: '80px',
                    padding: '10px 12px',
                    fontSize: '14px',
                    marginBottom: 0,
                    boxSizing: 'border-box',
                    resize: 'vertical'
                  }}
                />
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label className="label-text" style={{ display: 'block', marginBottom: '8px', color: '#cbd5e1', fontSize: '14px' }}>
                  模板文件 <span style={{ color: '#ef4444' }}>*</span> (.docx)
                </label>
                <input
                  type="file"
                  accept=".docx,.doc"
                  onChange={(e) => setNewTemplateFile(e.target.files?.[0] || null)}
                  style={{ 
                    width: '100%',
                    padding: '10px 12px',
                    background: '#2d3748',
                    border: '1px solid #4a5568',
                    borderRadius: '6px',
                    color: '#e2e8f0',
                    fontSize: '14px',
                    cursor: 'pointer',
                    boxSizing: 'border-box'
                  }}
                />
                {newTemplateFile && (
                  <div style={{ marginTop: '8px', fontSize: '12px', color: '#94a3b8' }}>
                    已选择: {newTemplateFile.name}
                  </div>
                )}
              </div>

              <div style={{ marginBottom: '24px', padding: '12px', background: '#1e293b', borderRadius: '6px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#e2e8f0', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={isPublic}
                    onChange={(e) => setIsPublic(e.target.checked)}
                    style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                  />
                  <span style={{ fontSize: '14px' }}>设为公开（所有用户可见）</span>
                </label>
              </div>

              <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', borderTop: '1px solid #374151', paddingTop: '16px' }}>
                <button 
                  className="sidebar-btn" 
                  onClick={() => setShowCreateModal(false)} 
                  disabled={creating}
                  style={{ 
                    padding: '10px 20px',
                    fontSize: '14px',
                    minWidth: '80px'
                  }}
                >
                  取消
                </button>
                <button 
                  className="sidebar-btn primary" 
                  onClick={handleCreate} 
                  disabled={creating || !newTemplateName.trim() || !newTemplateFile}
                  style={{ 
                    padding: '10px 20px',
                    fontSize: '14px',
                    minWidth: '80px'
                  }}
                >
                  {creating ? '创建中...' : '创建'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
      );
    }

    return (
      <div className="app-root">
        <div className="sidebar" style={{ width: '100%', maxWidth: 'none' }}>
          {inner}
        </div>

        {/* 创建模板模态框 */}
        {showCreateModal && (
          <div className="modal-overlay" onClick={() => !creating && setShowCreateModal(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '600px' }}>
              <h3 style={{ margin: '0 0 24px 0', color: '#e2e8f0', fontSize: '20px', fontWeight: 600 }}>新建格式模板</h3>

              <div style={{ marginBottom: '20px' }}>
                <label className="label-text" style={{ display: 'block', marginBottom: '8px', color: '#cbd5e1', fontSize: '14px' }}>
                  模板名称 <span style={{ color: '#ef4444' }}>*</span>
                </label>
                <input
                  type="text"
                  value={newTemplateName}
                  onChange={(e) => setNewTemplateName(e.target.value)}
                  placeholder="例如：水务自动化投标书模板"
                  className="sidebar-input"
                  style={{ 
                    width: '100%',
                    padding: '10px 12px',
                    fontSize: '14px',
                    marginBottom: 0,
                    boxSizing: 'border-box'
                  }}
                />
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label className="label-text" style={{ display: 'block', marginBottom: '8px', color: '#cbd5e1', fontSize: '14px' }}>
                  描述
                </label>
                <textarea
                  value={newTemplateDesc}
                  onChange={(e) => setNewTemplateDesc(e.target.value)}
                  placeholder="可选，描述模板的用途和特点"
                  className="sidebar-input"
                  style={{ 
                    width: '100%',
                    minHeight: '80px',
                    padding: '10px 12px',
                    fontSize: '14px',
                    marginBottom: 0,
                    boxSizing: 'border-box',
                    resize: 'vertical'
                  }}
                />
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label className="label-text" style={{ display: 'block', marginBottom: '8px', color: '#cbd5e1', fontSize: '14px' }}>
                  模板文件 <span style={{ color: '#ef4444' }}>*</span> (.docx)
                </label>
                <input
                  type="file"
                  accept=".docx,.doc"
                  onChange={(e) => setNewTemplateFile(e.target.files?.[0] || null)}
                  style={{ 
                    width: '100%',
                    padding: '10px 12px',
                    background: '#2d3748',
                    border: '1px solid #4a5568',
                    borderRadius: '6px',
                    color: '#e2e8f0',
                    fontSize: '14px',
                    cursor: 'pointer',
                    boxSizing: 'border-box'
                  }}
                />
                {newTemplateFile && (
                  <div style={{ marginTop: '8px', fontSize: '12px', color: '#94a3b8' }}>
                    已选择: {newTemplateFile.name}
                  </div>
                )}
              </div>

              <div style={{ marginBottom: '24px', padding: '12px', background: '#1e293b', borderRadius: '6px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#e2e8f0', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={isPublic}
                    onChange={(e) => setIsPublic(e.target.checked)}
                    style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                  />
                  <span style={{ fontSize: '14px' }}>设为公开（所有用户可见）</span>
                </label>
              </div>

              <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', borderTop: '1px solid #374151', paddingTop: '16px' }}>
                <button 
                  className="sidebar-btn" 
                  onClick={() => setShowCreateModal(false)} 
                  disabled={creating}
                  style={{ 
                    padding: '10px 20px',
                    fontSize: '14px',
                    minWidth: '80px'
                  }}
                >
                  取消
                </button>
                <button 
                  className="sidebar-btn primary" 
                  onClick={handleCreate} 
                  disabled={creating || !newTemplateName.trim() || !newTemplateFile}
                  style={{ 
                    padding: '10px 20px',
                    fontSize: '14px',
                    minWidth: '80px'
                  }}
                >
                  {creating ? '创建中...' : '创建'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // 渲染详情视图
  if (!template) {
    return (
      <div className="app-root">
        <div className="kb-detail" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="kb-empty">加载中...</div>
        </div>
      </div>
    );
  }

  const detailInner = (
    <div style={{ padding: embedded ? 0 : '20px' }}>
      {embedded && (
        <div className="header-bar" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <button className="link-button" onClick={onBack}>
            ← 返回
          </button>
          <div className="header-title">格式模板管理</div>
          <div style={{ width: 60 }} />
        </div>
      )}
          {/* 头部 */}
          <div style={{ marginBottom: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px' }}>
              <button className="sidebar-btn" onClick={() => {
                setView('list');
                setSelectedTemplateId(null);
              }}>
                ← 返回列表
              </button>
              <div style={{ display: 'flex', gap: '8px' }}>
                {!editing ? (
                  <button className="sidebar-btn" onClick={() => setEditing(true)}>
                    ✏️ 编辑
                  </button>
                ) : (
                  <>
                    <button className="sidebar-btn" onClick={() => setEditing(false)}>
                      取消
                    </button>
                    <button className="sidebar-btn primary" onClick={handleSaveEdit}>
                      保存
                    </button>
                  </>
                )}
              </div>
            </div>

            {editing ? (
              <>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="sidebar-input"
                  style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '8px' }}
                />
                <textarea
                  value={editDesc}
                  onChange={(e) => setEditDesc(e.target.value)}
                  className="sidebar-input"
                  style={{ minHeight: '60px' }}
                />
              </>
            ) : (
              <>
                <h2 style={{ margin: 0, color: '#e2e8f0' }}>{template.name}</h2>
                {template.description && (
                  <p style={{ margin: '4px 0 0', color: '#a0aec0' }}>{template.description}</p>
                )}
              </>
            )}

            <div style={{ fontSize: '12px', color: '#a0aec0', marginTop: '12px', display: 'flex', gap: '16px' }}>
              <span>更新时间: {template.updated_at ? new Date(template.updated_at).toLocaleString() : 'N/A'}</span>
              {template.template_spec_analyzed_at && (
                <span>分析时间: {new Date(template.template_spec_analyzed_at).toLocaleString()}</span>
              )}
            </div>
          </div>

          {/* 操作区 */}
          <div style={{ marginBottom: '20px', padding: '16px', background: '#1a202c', borderRadius: '8px' }}>
            <h4 style={{ margin: '0 0 12px 0', color: '#e2e8f0' }}>文件操作</h4>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'end' }}>
              <div style={{ flex: 1 }}>
                <label className="label-text">选择新文件 (.docx)</label>
                <input
                  type="file"
                  accept=".docx,.doc"
                  onChange={(e) => setNewFile(e.target.files?.[0] || null)}
                  style={{ width: '100%', padding: '8px', background: '#2d3748', border: '1px solid #4a5568', borderRadius: '4px', color: '#e2e8f0' }}
                />
              </div>
              <button
                className="sidebar-btn primary"
                onClick={handleReplaceFile}
                disabled={!newFile || replacingFile}
              >
                {replacingFile ? '替换中...' : '替换文件'}
              </button>
              <button
                className="sidebar-btn"
                onClick={handleForceAnalyze}
                disabled={!newFile}
              >
                强制重新分析
              </button>
            </div>
          </div>

          {/* Tab 切换 */}
          <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', borderBottom: '1px solid #4a5568', flexWrap: 'wrap' }}>
            <button
              className={`sidebar-btn ${activeTab === 'preview' ? 'primary' : ''}`}
              style={{ borderRadius: '4px 4px 0 0' }}
              onClick={() => setActiveTab('preview')}
            >
              样式预览
            </button>
            <button
              className={`sidebar-btn ${activeTab === 'docPreview' ? 'primary' : ''}`}
              style={{ borderRadius: '4px 4px 0 0' }}
              onClick={() => {
                setActiveTab('docPreview');
                if (template?.id && !docPreviewUrl && !docPreviewLoading) {
                  fetchDocPreview(template.id, 'pdf');
                }
              }}
            >
              文档预览(PDF)
            </button>
            <button
              className={`sidebar-btn ${activeTab === 'analysis' ? 'primary' : ''}`}
              style={{ borderRadius: '4px 4px 0 0' }}
              onClick={() => setActiveTab('analysis')}
            >
              🤖 模板分析
            </button>
            <button
              className={`sidebar-btn ${activeTab === 'spec' ? 'primary' : ''}`}
              style={{ borderRadius: '4px 4px 0 0' }}
              onClick={() => setActiveTab('spec')}
            >
              解析结构
            </button>
            <button
              className={`sidebar-btn ${activeTab === 'diagnostics' ? 'primary' : ''}`}
              style={{ borderRadius: '4px 4px 0 0' }}
              onClick={() => setActiveTab('diagnostics')}
            >
              AI 诊断
            </button>
          </div>

          {/* Tab 内容 */}
          <div style={{ padding: '16px', background: '#1a202c', borderRadius: '8px', minHeight: '400px' }}>
            {activeTab === 'preview' && (
              <div>
                <h3 style={{ marginTop: 0, color: '#e2e8f0' }}>样式预览（前端渲染）</h3>
                {spec ? (
                  <div style={{ width: '100%', minHeight: 520 }}>
                    <RichTocPreview
                      items={templateSpecToTocItems(spec)}
                      templateStyle={templateSpecToTemplateStyle(spec)}
                      style={{ minHeight: '500px' }}
                    />
                  </div>
                ) : (
                  <div className="kb-empty">模板尚未解析，请上传文件并分析</div>
                )}
              </div>
            )}

            {activeTab === 'docPreview' && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                  <h3 style={{ marginTop: 0, marginBottom: 0, color: '#e2e8f0' }}>文档预览（后端生成，PDF 优先）</h3>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <button className="sidebar-btn" onClick={handleDeterministicParse} disabled={!template || docPreviewLoading}>
                      重新解析
                    </button>
                    <button className="sidebar-btn primary" onClick={handleRefreshDocPreview} disabled={!template || docPreviewLoading}>
                      {docPreviewLoading ? '生成中...' : '刷新预览'}
                    </button>
                    <button
                      className="sidebar-btn"
                      onClick={() => template?.id && fetchDocPreview(template.id, 'docx')}
                      disabled={!template || docPreviewLoading}
                    >
                      下载预览DOCX
                    </button>
                  </div>
                </div>

                {/* 确定性解析摘要 */}
                <div style={{ marginTop: 12, marginBottom: 12, padding: '12px', background: '#2d3748', borderRadius: 8, color: '#e2e8f0' }}>
                  <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                    <div>
                      <strong>parse_status:</strong> {parseSummary?.parse_status || template?.parse_status || 'PENDING'}
                    </div>
                    {parseSummary?.parse_updated_at && (
                      <div>
                        <strong>updated_at:</strong> {new Date(parseSummary.parse_updated_at).toLocaleString()}
                      </div>
                    )}
                    {parseSummary?.parse_result?.confidence != null && (
                      <div>
                        <strong>confidence:</strong> {(Number(parseSummary.parse_result.confidence) * 100).toFixed(0)}%
                      </div>
                    )}
                  </div>
                  {parseSummary?.parse_error && (
                    <div style={{ marginTop: 8, color: '#fecaca' }}>
                      <strong>parse_error:</strong> {String(parseSummary.parse_error)}
                    </div>
                  )}

                  {parseSummary?.parse_result && (
                    <div style={{ marginTop: 10, fontSize: 12, color: '#cbd5e1' }}>
                      <div style={{ marginBottom: 6 }}>
                        <strong>variants:</strong>{' '}
                        {Array.isArray(parseSummary.parse_result.variants) ? parseSummary.parse_result.variants.join(', ') : 'N/A'}
                      </div>
                      <div style={{ marginBottom: 6 }}>
                        <strong>heading 1-5:</strong>{' '}
                        {(() => {
                          const hl = parseSummary?.parse_result?.heading_levels || {};
                          const parts = [1, 2, 3, 4, 5].map((i) => `${i}:${hl[String(i)] ? 'Y' : 'N'}`);
                          return parts.join('  ');
                        })()}
                      </div>
                      <div>
                        <strong>header/footer images:</strong>
                        <pre style={{ marginTop: 6, background: '#1a202c', padding: 10, borderRadius: 6, overflow: 'auto' }}>
                          {JSON.stringify(parseSummary.parse_result.header_footer_images || {}, null, 2)}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>

                {docPreviewError && (
                  <div style={{ padding: '10px 12px', background: '#7f1d1d', color: '#fff', borderRadius: 6, marginBottom: 12 }}>
                    {docPreviewError}
                  </div>
                )}

                {/* 预览区域 */}
                {docPreviewUrl ? (
                  docPreviewFormat === 'pdf' ? (
                    <iframe
                      key={previewNonce}
                      src={docPreviewUrl}
                      style={{ width: '100%', height: '70vh', border: '1px solid #4a5568', borderRadius: 8, background: '#0f172a' }}
                      title="format-template-preview"
                    />
                  ) : (
                    <div className="kb-empty">
                      本次生成未能产出 PDF（已回退为 DOCX）。请点击上方“下载预览DOCX”查看，或检查后端 LibreOffice 是否可用。
                    </div>
                  )
                ) : (
                  <div className="kb-empty">{docPreviewLoading ? '生成预览中...' : '点击“刷新预览”生成预览文件'}</div>
                )}
              </div>
            )}

            {activeTab === 'spec' && (
              <div>
                <h3 style={{ marginTop: 0, color: '#e2e8f0' }}>📋 解析结构</h3>
                {parseSummary ? (
                  <div style={{ fontSize: '14px', color: '#e2e8f0' }}>
                    {/* 标题级别映射 */}
                    {parseSummary.heading_levels && parseSummary.heading_levels.length > 0 && (
                      <div style={{ marginBottom: '20px', padding: '16px', background: '#2d3748', borderRadius: '8px' }}>
                        <h4 style={{ margin: '0 0 12px 0', color: '#60a5fa' }}>🎯 标题级别映射</h4>
                        <div style={{ display: 'grid', gap: '8px' }}>
                          {parseSummary.heading_levels.map((hl: any, idx: number) => (
                            <div key={idx} style={{ padding: '8px 12px', background: '#1e293b', borderRadius: '4px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontWeight: 'bold', color: '#fbbf24' }}>{hl.level.toUpperCase()}</span>
                              <span style={{ color: '#94a3b8' }}>→</span>
                              <span style={{ color: '#e2e8f0' }}>{hl.style}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 文档结构统计 */}
                    {parseSummary.sections && parseSummary.sections.length > 0 && (
                      <div style={{ marginBottom: '20px', padding: '16px', background: '#2d3748', borderRadius: '8px' }}>
                        <h4 style={{ margin: '0 0 12px 0', color: '#60a5fa' }}>📊 文档结构</h4>
                        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                          {parseSummary.sections.map((sec: any, idx: number) => (
                            <div key={idx} style={{ padding: '12px 16px', background: '#1e293b', borderRadius: '6px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span style={{ fontSize: '20px' }}>{sec.type === 'paragraph' ? '📝' : '📋'}</span>
                              <span style={{ fontWeight: 'bold', color: '#e2e8f0' }}>{sec.label}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 样式变体列表 */}
                    {parseSummary.variants && parseSummary.variants.length > 0 && (
                      <div style={{ marginBottom: '20px', padding: '16px', background: '#2d3748', borderRadius: '8px' }}>
                        <h4 style={{ margin: '0 0 12px 0', color: '#60a5fa' }}>🎨 样式变体 (前20个)</h4>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '8px' }}>
                          {parseSummary.variants.map((variant: any, idx: number) => (
                            <div key={idx} style={{ padding: '8px 12px', background: '#1e293b', borderRadius: '4px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ color: '#e2e8f0', fontSize: '13px' }}>{variant.name}</span>
                              {variant.has_numbering && (
                                <span style={{ fontSize: '11px', padding: '2px 6px', background: '#1e40af', borderRadius: '3px', color: '#93c5fd' }}>编号</span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 模板使用说明 */}
                    {parseSummary.template_instructions && parseSummary.template_instructions.has_instructions && (
                      <div style={{ marginBottom: '20px', padding: '16px', background: '#2d3748', borderRadius: '8px' }}>
                        <h4 style={{ margin: '0 0 12px 0', color: '#60a5fa' }}>📋 模板使用说明</h4>
                        <div style={{ padding: '12px', background: '#1e293b', borderRadius: '6px', whiteSpace: 'pre-wrap', fontSize: '13px', lineHeight: '1.6', color: '#cbd5e1' }}>
                          {parseSummary.template_instructions.instructions_text}
                        </div>
                        <div style={{ marginTop: '8px', fontSize: '12px', color: '#64748b' }}>
                          📦 共 {parseSummary.template_instructions.instructions_count} 个说明块
                        </div>
                      </div>
                    )}

                    {/* 页眉页脚规格 */}
                    {parseSummary.header_footer_spec && parseSummary.header_footer_spec.paper_sizes && (
                      <div style={{ marginBottom: '20px', padding: '16px', background: '#2d3748', borderRadius: '8px' }}>
                        <h4 style={{ margin: '0 0 12px 0', color: '#60a5fa' }}>🖼️ 页眉页脚规格</h4>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                          <thead>
                            <tr style={{ borderBottom: '1px solid #475569' }}>
                              <th style={{ padding: '8px', textAlign: 'left', color: '#94a3b8' }}>纸张类型</th>
                              <th style={{ padding: '8px', textAlign: 'left', color: '#94a3b8' }}>页眉尺寸</th>
                              <th style={{ padding: '8px', textAlign: 'left', color: '#94a3b8' }}>页脚尺寸</th>
                            </tr>
                          </thead>
                          <tbody>
                            {Object.entries(parseSummary.header_footer_spec.paper_sizes).map(([key, value]: [string, any]) => (
                              <tr key={key} style={{ borderBottom: '1px solid #334155' }}>
                                <td style={{ padding: '8px', color: '#e2e8f0' }}>
                                  {key === 'A4_portrait' && 'A4竖版'}
                                  {key === 'A4_landscape' && 'A4横版'}
                                  {key === 'A3_landscape' && 'A3横版'}
                                </td>
                                <td style={{ padding: '8px', color: '#cbd5e1' }}>
                                  {value.header ? `${value.header.height} × ${value.header.width}` : '-'}
                                </td>
                                <td style={{ padding: '8px', color: '#cbd5e1' }}>
                                  {value.footer ? `${value.footer.height} × ${value.footer.width}` : '-'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {parseSummary.header_footer_spec.text_indent && (
                          <div style={{ marginTop: '12px', padding: '8px', background: '#1e293b', borderRadius: '4px', fontSize: '12px', color: '#cbd5e1' }}>
                            <strong>文本缩进:</strong> {parseSummary.header_footer_spec.text_indent}
                          </div>
                        )}
                        {parseSummary.header_footer_spec.layout_notes && parseSummary.header_footer_spec.layout_notes.length > 0 && (
                          <div style={{ marginTop: '12px', padding: '8px', background: '#1e293b', borderRadius: '4px', fontSize: '12px', color: '#cbd5e1' }}>
                            <strong>布局说明:</strong>
                            <ul style={{ margin: '4px 0 0 20px', padding: 0 }}>
                              {parseSummary.header_footer_spec.layout_notes.map((note: string, idx: number) => (
                                <li key={idx} style={{ marginBottom: '4px' }}>{note}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}

                    {/* 域代码使用说明 */}
                    {parseSummary.field_code_usage && parseSummary.field_code_usage.uses_field_codes && (
                      <div style={{ marginBottom: '20px', padding: '16px', background: '#2d3748', borderRadius: '8px' }}>
                        <h4 style={{ margin: '0 0 12px 0', color: '#60a5fa' }}>⚙️ 域代码和样式</h4>
                        <div style={{ display: 'grid', gap: '8px' }}>
                          {parseSummary.field_code_usage.field_type && (
                            <div style={{ padding: '8px', background: '#1e293b', borderRadius: '4px', fontSize: '13px', color: '#cbd5e1' }}>
                              <strong>域类型:</strong> <span style={{ color: '#fbbf24' }}>{parseSummary.field_code_usage.field_type}</span>
                            </div>
                          )}
                          {parseSummary.field_code_usage.auto_update && (
                            <div style={{ padding: '8px', background: '#1e293b', borderRadius: '4px', fontSize: '13px', color: '#cbd5e1' }}>
                              <strong>自动更新:</strong> {parseSummary.field_code_usage.auto_update}
                            </div>
                          )}
                          {parseSummary.field_code_usage.plain_text_sections && parseSummary.field_code_usage.plain_text_sections.length > 0 && (
                            <div style={{ padding: '8px', background: '#1e293b', borderRadius: '4px', fontSize: '13px', color: '#cbd5e1' }}>
                              <strong>纯文字区段:</strong> {parseSummary.field_code_usage.plain_text_sections.join('、')}
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* 封面结构 */}
                    {parseSummary.cover_structure && parseSummary.cover_structure.has_cover && (
                      <div style={{ marginBottom: '20px', padding: '16px', background: '#2d3748', borderRadius: '8px' }}>
                        <h4 style={{ margin: '0 0 12px 0', color: '#60a5fa' }}>📄 封面结构</h4>
                        <div style={{ padding: '12px', background: '#1e293b', borderRadius: '6px' }}>
                          <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', lineHeight: '2', color: '#cbd5e1' }}>
                            {parseSummary.cover_structure.cover_elements.map((element: string, idx: number) => (
                              <li key={idx}>{element}</li>
                            ))}
                          </ul>
                        </div>
                        <div style={{ marginTop: '8px', fontSize: '12px', color: '#64748b' }}>
                          📦 共 {parseSummary.cover_structure.cover_blocks_count} 个封面块
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ padding: '40px', textAlign: 'center', color: '#94a3b8' }}>
                    <div style={{ fontSize: '48px', marginBottom: '16px' }}>📋</div>
                    <p style={{ fontSize: '16px', marginBottom: '8px' }}>暂无解析结构</p>
                    <p style={{ fontSize: '14px', color: '#64748b' }}>模板分析完成后将显示详细的结构信息</p>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'analysis' && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <h3 style={{ margin: 0, color: '#e2e8f0' }}>🤖 模板分析结果（LLM 理解）</h3>
                  <button
                    className="sidebar-btn primary"
                    onClick={handleReanalyze}
                    disabled={!template || reanalyzing}
                    style={{ fontSize: '14px' }}
                  >
                    {reanalyzing ? '🔄 分析中...' : '🔄 重新解析'}
                  </button>
                </div>
                {templateAnalysis ? (
                  <div style={{ fontSize: '14px', color: '#e2e8f0' }}>
                    {/* 分析摘要 */}
                    {templateAnalysis.analysis_summary && (
                      <div style={{ marginBottom: '20px', padding: '16px', background: '#2d3748', borderRadius: '8px' }}>
                        <h4 style={{ margin: '0 0 12px 0', color: '#60a5fa' }}>📊 分析摘要</h4>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
                          <div>
                            <strong>置信度:</strong>{' '}
                            <span style={{ 
                              color: templateAnalysis.analysis_summary.confidence >= 0.8 ? '#10b981' : 
                                     templateAnalysis.analysis_summary.confidence >= 0.6 ? '#fbbf24' : '#ef4444' 
                            }}>
                              {(templateAnalysis.analysis_summary.confidence * 100).toFixed(0)}%
                            </span>
                          </div>
                          <div>
                            <strong>Anchors:</strong> {templateAnalysis.analysis_summary.anchorsCount || 0}
                          </div>
                          <div>
                            <strong>保留块:</strong> {templateAnalysis.analysis_summary.keepBlocksCount || 0}
                          </div>
                          <div>
                            <strong>删除块:</strong> {templateAnalysis.analysis_summary.deleteBlocksCount || 0}
                          </div>
                          <div>
                            <strong>内容标记:</strong>{' '}
                            {templateAnalysis.analysis_summary.hasContentMarker ? '✅ 有' : '❌ 无'}
                          </div>
                        </div>

                        {/* 警告信息 */}
                        {templateAnalysis.warnings && templateAnalysis.warnings.length > 0 && (
                          <div style={{ marginTop: '12px', padding: '12px', background: '#78350f', borderRadius: '6px' }}>
                            <strong style={{ color: '#fbbf24' }}>⚠️ 警告:</strong>
                            <ul style={{ margin: '8px 0 0', paddingLeft: '20px' }}>
                              {templateAnalysis.warnings.map((w: string, i: number) => (
                                <li key={i} style={{ color: '#fef3c7' }}>{w}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Role Mapping */}
                    {templateAnalysis.full_analysis?.roleMapping && (
                      <div style={{ marginBottom: '20px', padding: '16px', background: '#2d3748', borderRadius: '8px' }}>
                        <h4 style={{ margin: '0 0 12px 0', color: '#60a5fa' }}>🎨 样式映射（Role Mapping）</h4>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '8px' }}>
                          {Object.entries(templateAnalysis.full_analysis.roleMapping).map(([role, styleName]) => (
                            <div key={role} style={{ padding: '8px', background: '#1e293b', borderRadius: '4px' }}>
                              <strong style={{ color: '#94a3b8' }}>{role}:</strong>
                              <div style={{ color: '#e2e8f0', fontSize: '13px', marginTop: '4px' }}>{String(styleName)}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Apply Assets - Anchors */}
                    {templateAnalysis.full_analysis?.applyAssets?.anchors && (
                      <div style={{ marginBottom: '20px', padding: '16px', background: '#2d3748', borderRadius: '8px' }}>
                        <h4 style={{ margin: '0 0 12px 0', color: '#60a5fa' }}>⚓ 内容锚点（Anchors）</h4>
                        {templateAnalysis.full_analysis.applyAssets.anchors.map((anchor: any, idx: number) => (
                          <div key={idx} style={{ marginBottom: '12px', padding: '12px', background: '#1e293b', borderRadius: '6px' }}>
                            <div style={{ marginBottom: '8px' }}>
                              <strong style={{ color: '#10b981' }}>ID:</strong> {anchor.id}
                            </div>
                            {anchor.blockId && (
                              <div style={{ marginBottom: '4px', fontSize: '12px', color: '#94a3b8' }}>
                                Block ID: {anchor.blockId}
                              </div>
                            )}
                            {anchor.description && (
                              <div style={{ fontSize: '13px', color: '#cbd5e1', fontStyle: 'italic' }}>
                                {anchor.description}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Apply Assets - Keep Plan */}
                    {templateAnalysis.full_analysis?.applyAssets?.keepPlan && (
                      <div style={{ marginBottom: '20px', padding: '16px', background: '#2d3748', borderRadius: '8px' }}>
                        <h4 style={{ margin: '0 0 12px 0', color: '#60a5fa' }}>✅ 保留计划（Keep Plan）</h4>
                        <div style={{ fontSize: '13px', color: '#cbd5e1' }}>
                          <strong>策略:</strong> {templateAnalysis.full_analysis.applyAssets.keepPlan.strategy || 'N/A'}
                        </div>
                        {templateAnalysis.full_analysis.applyAssets.keepPlan.blockIds && (
                          <div style={{ marginTop: '8px' }}>
                            <strong style={{ fontSize: '13px' }}>Block IDs:</strong>
                            <div style={{ 
                              marginTop: '6px', 
                              maxHeight: '150px', 
                              overflow: 'auto', 
                              padding: '8px', 
                              background: '#1e293b', 
                              borderRadius: '4px',
                              fontSize: '12px',
                              fontFamily: 'monospace'
                            }}>
                              {Array.isArray(templateAnalysis.full_analysis.applyAssets.keepPlan.blockIds) ?
                                templateAnalysis.full_analysis.applyAssets.keepPlan.blockIds.join(', ') :
                                JSON.stringify(templateAnalysis.full_analysis.applyAssets.keepPlan.blockIds, null, 2)
                              }
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Apply Assets - Policy */}
                    {templateAnalysis.full_analysis?.applyAssets?.policy && (
                      <div style={{ marginBottom: '20px', padding: '16px', background: '#2d3748', borderRadius: '8px' }}>
                        <h4 style={{ margin: '0 0 12px 0', color: '#60a5fa' }}>📋 应用策略（Policy）</h4>
                        <pre style={{ 
                          margin: 0, 
                          padding: '12px', 
                          background: '#1e293b', 
                          borderRadius: '6px', 
                          overflow: 'auto',
                          fontSize: '12px',
                          color: '#e2e8f0'
                        }}>
                          {JSON.stringify(templateAnalysis.full_analysis.applyAssets.policy, null, 2)}
                        </pre>
                      </div>
                    )}

                    {/* Style Profile */}
                    {templateAnalysis.full_analysis?.styleProfile && (
                      <div style={{ marginBottom: '20px', padding: '16px', background: '#2d3748', borderRadius: '8px' }}>
                        <h4 style={{ margin: '0 0 12px 0', color: '#60a5fa' }}>🎭 样式配置（Style Profile）</h4>
                        <details>
                          <summary style={{ cursor: 'pointer', color: '#94a3b8', marginBottom: '8px' }}>
                            点击展开/收起详细配置
                          </summary>
                          <pre style={{ 
                            margin: '8px 0 0', 
                            padding: '12px', 
                            background: '#1e293b', 
                            borderRadius: '6px', 
                            overflow: 'auto',
                            fontSize: '11px',
                            maxHeight: '400px',
                            color: '#e2e8f0'
                          }}>
                            {JSON.stringify(templateAnalysis.full_analysis.styleProfile, null, 2)}
                          </pre>
                        </details>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="kb-empty">
                    <div style={{ marginBottom: '12px', fontSize: '18px', fontWeight: 'bold' }}>📋 模板尚未进行 LLM 分析</div>
                    <div style={{ fontSize: '14px', color: '#94a3b8', marginBottom: '20px', lineHeight: '1.6' }}>
                      LLM 分析可以：<br/>
                      • 自动识别模板结构和样式<br/>
                      • 提取页眉页脚和特殊布局<br/>
                      • 生成智能套用方案<br/><br/>
                      <strong style={{ color: '#60a5fa' }}>点击下方按钮开始分析（需要 10-30 秒）</strong>
                    </div>
                    <button
                      className="sidebar-btn primary"
                      onClick={handleReanalyze}
                      disabled={!template || reanalyzing}
                      style={{ 
                        fontSize: '16px', 
                        padding: '12px 24px',
                        fontWeight: 'bold',
                        boxShadow: reanalyzing ? 'none' : '0 4px 12px rgba(96, 165, 250, 0.3)'
                      }}
                    >
                      {reanalyzing ? '🔄 分析中，请稍候...' : '🚀 开始 LLM 分析'}
                    </button>
                    {reanalyzing && (
                      <div style={{ marginTop: '16px', fontSize: '13px', color: '#fbbf24' }}>
                        ⏳ 正在调用 LLM 分析模板结构，请耐心等待...
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'diagnostics' && (
              <div>
                <h3 style={{ marginTop: 0, color: '#e2e8f0' }}>AI 解析诊断</h3>
                {summary && summary.analyzed ? (
                  <div style={{ fontSize: '14px', color: '#e2e8f0' }}>
                    <div style={{ marginBottom: '16px', padding: '12px', background: '#2d3748', borderRadius: '4px' }}>
                      <strong>置信度:</strong> <span style={{ color: summary.confidence >= 0.7 ? '#28a745' : '#ffc107' }}>{(summary.confidence * 100).toFixed(1)}%</span>
                    </div>

                    {summary.warnings && summary.warnings.length > 0 && (
                      <div style={{ marginBottom: '16px' }}>
                        <strong>警告:</strong>
                        <div style={{ marginTop: '8px' }}>
                          {summary.warnings.map((warning: string, idx: number) => (
                            <div key={idx} style={{ padding: '8px', background: '#fff3cd', color: '#856404', borderRadius: '4px', marginBottom: '4px' }}>
                              {warning}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div style={{ marginBottom: '16px' }}>
                      <strong>分析信息:</strong>
                      <div style={{ marginTop: '8px', fontSize: '12px', color: '#a0aec0' }}>
                        <div>模型: {summary.llm_model || 'N/A'}</div>
                        <div>耗时: {summary.analysis_duration_ms ? `${summary.analysis_duration_ms}ms` : 'N/A'}</div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="kb-empty">
                    {summary?.analyzed === false ? summary.message || '模板尚未解析' : '加载诊断信息失败'}
                  </div>
                )}
              </div>
            )}
          </div>
    </div>
  );

  if (embedded) {
    return (
      <div className="kb-detail" style={{ height: "100%", overflow: "auto", padding: "16px" }}>
        {detailInner}
      </div>
    );
  }

  return (
    <div className="app-root">
      <div className="sidebar" style={{ width: '100%', maxWidth: 'none' }}>
        {detailInner}
      </div>
    </div>
  );
}
