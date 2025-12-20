/**
 * 格式模板管理组件
 * 用于创建、查看、编辑和删除格式模板
 */
import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../config/api';

interface FormatTemplate {
  id: string;
  name: string;
  description?: string;
  is_public: boolean;
  owner_id?: string;
  template_sha256?: string;
  template_spec_version?: string;
  template_spec_analyzed_at?: string;
  created_at: string;
  updated_at: string;
}

interface TemplateManagementProps {
  onClose?: () => void;
}

export default function TemplateManagement({ onClose }: TemplateManagementProps) {
  const [templates, setTemplates] = useState<FormatTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  
  // 新建模板表单
  const [newTemplateName, setNewTemplateName] = useState('');
  const [newTemplateDesc, setNewTemplateDesc] = useState('');
  const [newTemplateFile, setNewTemplateFile] = useState<File | null>(null);
  const [isPublic, setIsPublic] = useState(false);

  // 加载模板列表
  const loadTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get('/api/apps/tender/format-templates');
      setTemplates(data);
    } catch (err) {
      console.error('Failed to load templates:', err);
      alert(`加载模板失败: ${err}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  // 上传新模板
  const handleUploadTemplate = async () => {
    if (!newTemplateName.trim()) {
      alert('请输入模板名称');
      return;
    }
    if (!newTemplateFile) {
      alert('请选择 Word 文档文件');
      return;
    }
    
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('name', newTemplateName);
      if (newTemplateDesc) {
        formData.append('description', newTemplateDesc);
      }
      formData.append('is_public', isPublic.toString());
      formData.append('file', newTemplateFile);

      await api.post('/api/apps/tender/format-templates', formData);
      
      // 重置表单
      setNewTemplateName('');
      setNewTemplateDesc('');
      setNewTemplateFile(null);
      setIsPublic(false);
      
      // 重新加载列表
      await loadTemplates();
      alert('模板上传成功');
    } catch (err) {
      console.error('Failed to upload template:', err);
      alert(`上传失败: ${err}`);
    } finally {
      setUploading(false);
    }
  };

  // 删除模板
  const handleDeleteTemplate = async (templateId: string, templateName: string) => {
    if (!confirm(`确定要删除模板"${templateName}"吗？此操作不可恢复。`)) {
      return;
    }
    
    try {
      await api.delete(`/api/apps/tender/format-templates/${templateId}`);
      await loadTemplates();
      alert('删除成功');
    } catch (err) {
      console.error('Failed to delete template:', err);
      alert(`删除失败: ${err}`);
    }
  };

  // 下载模板文件
  const handleDownloadTemplate = async (templateId: string, templateName: string) => {
    try {
      const blob = await api.get(`/api/apps/tender/format-templates/${templateId}/file`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${templateName}.docx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download template:', err);
      alert(`下载失败: ${err}`);
    }
  };

  return (
    <div className="kb-detail" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 头部 */}
      <div className="header-bar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div className="header-title">📋 格式模板管理</div>
        {onClose && (
          <button onClick={onClose} className="link-button">
            关闭
          </button>
        )}
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '20px' }}>
        {/* 上传新模板区域 */}
        <section className="kb-upload-section" style={{ marginBottom: '24px' }}>
          <h4>📤 上传新模板</h4>
          <div className="kb-create-form">
            <input
              type="text"
              placeholder="模板名称 *"
              value={newTemplateName}
              onChange={e => setNewTemplateName(e.target.value)}
              disabled={uploading}
            />
            <textarea
              placeholder="模板描述（可选）"
              value={newTemplateDesc}
              onChange={e => setNewTemplateDesc(e.target.value)}
              style={{ minHeight: '60px' }}
              disabled={uploading}
            />
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
              <input
                type="file"
                accept=".docx,.doc"
                onChange={e => setNewTemplateFile(e.target.files?.[0] || null)}
                style={{ flex: 1 }}
                disabled={uploading}
              />
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#cbd5e1' }}>
                <input
                  type="checkbox"
                  checked={isPublic}
                  onChange={e => setIsPublic(e.target.checked)}
                  disabled={uploading}
                />
                <span>公开模板</span>
              </label>
            </div>
            <button onClick={handleUploadTemplate} disabled={uploading}>
              {uploading ? '上传中...' : '上传模板'}
            </button>
            {newTemplateFile && (
              <div className="sidebar-hint" style={{ marginTop: '8px' }}>
                已选择: {newTemplateFile.name}
              </div>
            )}
          </div>
        </section>

        {/* 模板列表 */}
        <section className="kb-doc-section">
          <h4>📚 模板库 ({templates.length})</h4>
          
          {loading ? (
            <div className="kb-empty">加载中...</div>
          ) : templates.length === 0 ? (
            <div className="kb-empty">暂无模板，请先上传一个 Word 模板文档</div>
          ) : (
            <div style={{ display: 'grid', gap: '16px' }}>
              {templates.map(template => (
                <div
                  key={template.id}
                  className="source-card"
                  style={{ padding: '16px' }}
                >
                  {/* 模板信息 */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '16px', fontWeight: 'bold', color: '#f1f5f9', marginBottom: '4px' }}>
                        {template.name}
                        {template.is_public && (
                          <span style={{ 
                            marginLeft: '8px', 
                            fontSize: '12px', 
                            padding: '2px 8px', 
                            background: 'rgba(96, 165, 250, 0.2)',
                            color: '#60a5fa',
                            borderRadius: '4px'
                          }}>
                            公开
                          </span>
                        )}
                      </div>
                      {template.description && (
                        <div className="kb-doc-meta" style={{ marginBottom: '8px' }}>
                          {template.description}
                        </div>
                      )}
                      <div className="kb-doc-meta" style={{ fontSize: '12px' }}>
                        <div>创建时间: {new Date(template.created_at).toLocaleString('zh-CN')}</div>
                        {template.template_spec_analyzed_at && (
                          <div>分析时间: {new Date(template.template_spec_analyzed_at).toLocaleString('zh-CN')}</div>
                        )}
                        {template.template_spec_version && (
                          <div>规格版本: {template.template_spec_version}</div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* 操作按钮 */}
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <button
                      onClick={() => handleDownloadTemplate(template.id, template.name)}
                      className="pill-button"
                      style={{ fontSize: '12px', padding: '4px 12px' }}
                    >
                      📥 下载
                    </button>
                    <button
                      onClick={() => handleDeleteTemplate(template.id, template.name)}
                      className="link-button"
                      style={{ fontSize: '12px', padding: '4px 12px', color: '#ef4444' }}
                    >
                      🗑️ 删除
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
