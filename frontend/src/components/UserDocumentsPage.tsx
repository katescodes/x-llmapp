/**
 * 用户文档管理页面
 * 
 * 功能：
 * 1. 管理文档分类（技术资料、资质文件等）
 * 2. 上传文档（支持PDF、Word、图片等）
 * 3. 查看和管理文档列表
 * 4. 删除文档
 * 5. AI分析文档（提取关键信息）
 * 6. 共享文档到企业
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../config/api';
import ShareButton from './ShareButton';

const API_BASE = API_BASE_URL;

// 获取 token 的辅助函数
const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

interface UserDocCategory {
  id: string;
  project_id: string;
  category_name: string;
  category_desc?: string;
  display_order: number;
  doc_count?: number;
  created_at?: string;
  updated_at?: string;
}

interface UserDocument {
  id: string;
  project_id: string;
  category_id?: string;
  category_name?: string;
  doc_name: string;
  filename: string;
  file_type: string;
  mime_type?: string;
  file_size?: number;
  storage_path?: string;
  kb_doc_id?: string;
  doc_tags: string[];
  description?: string;
  is_analyzed: boolean;
  analysis_json: any;
  owner_id?: string;
  scope?: string;
  organization_id?: string;
  created_at?: string;
  updated_at?: string;
}

interface Props {
  projectId?: string;  // 改为可选，不选项目时查询所有文档
  onBack?: () => void;
  embedded?: boolean;
}

export default function UserDocumentsPage({ projectId, onBack, embedded = false }: Props) {
  const [categories, setCategories] = useState<UserDocCategory[]>([]);
  const [documents, setDocuments] = useState<UserDocument[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<UserDocCategory | null>(null);
  const [selectedDocument, setSelectedDocument] = useState<UserDocument | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  // 创建分类表单状态
  const [showCreateCategoryForm, setShowCreateCategoryForm] = useState(false);
  const [categoryName, setCategoryName] = useState('');
  const [categoryDesc, setCategoryDesc] = useState('');

  // 上传文档表单状态
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [docName, setDocName] = useState('');
  const [docDescription, setDocDescription] = useState('');
  const [docTags, setDocTags] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadCategoryId, setUploadCategoryId] = useState<string>('');

  // 加载分类列表
  const loadCategories = async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (projectId) {
        params.project_id = projectId;
      }
      const res = await axios.get(`${API_BASE}/api/user-documents/categories`, {
        params,
        headers: getAuthHeaders(),
      });
      setCategories(res.data || []);
    } catch (err: any) {
      console.error('加载分类失败:', err);
      alert(err.response?.data?.detail || '加载分类失败');
    } finally {
      setLoading(false);
    }
  };

  // 加载文档列表
  const loadDocuments = async (categoryId?: string) => {
    setLoading(true);
    try {
      const params: any = {};
      if (projectId) {
        params.project_id = projectId;
      }
      if (categoryId) {
        params.category_id = categoryId;
      }
      const res = await axios.get(`${API_BASE}/api/user-documents/documents`, {
        params,
        headers: getAuthHeaders(),
      });
      setDocuments(res.data || []);
    } catch (err: any) {
      console.error('加载文档失败:', err);
      alert(err.response?.data?.detail || '加载文档失败');
    } finally {
      setLoading(false);
    }
  };

  // 创建分类
  const handleCreateCategory = async () => {
    if (!categoryName.trim()) {
      alert('请输入分类名称');
      return;
    }

    try {
      await axios.post(
        `${API_BASE}/api/user-documents/categories`,
        {
          project_id: projectId || null,  // NULL表示共享分类
          category_name: categoryName,
          category_desc: categoryDesc,
          display_order: categories.length,
        },
        { headers: getAuthHeaders() }
      );

      alert('分类创建成功！');
      setCategoryName('');
      setCategoryDesc('');
      setShowCreateCategoryForm(false);
      await loadCategories();
    } catch (err: any) {
      console.error('创建分类失败:', err);
      alert(err.response?.data?.detail || '创建分类失败');
    }
  };

  // 删除分类
  const handleDeleteCategory = async (categoryId: string, categoryName: string) => {
    if (!confirm(`确定要删除分类"${categoryName}"吗？该分类下的文档不会被删除，但会被移至"未分类"。`)) {
      return;
    }

    try {
      await axios.delete(`${API_BASE}/api/user-documents/categories/${categoryId}`, {
        headers: getAuthHeaders(),
      });

      alert('分类已删除');
      
      if (selectedCategory?.id === categoryId) {
        setSelectedCategory(null);
      }

      await loadCategories();
      await loadDocuments();
    } catch (err: any) {
      console.error('删除分类失败:', err);
      alert(err.response?.data?.detail || '删除分类失败');
    }
  };

  // 上传文档
  const handleUploadDocument = async () => {
    if (!docName.trim()) {
      alert('请输入文档名称');
      return;
    }
    if (!selectedFile) {
      alert('请选择文件');
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('project_id', projectId || '');  // 空字符串表示共享文档（后端会处理为NULL）
      formData.append('doc_name', docName);
      formData.append('file', selectedFile);
      if (uploadCategoryId) {
        formData.append('category_id', uploadCategoryId);
      }
      if (docDescription) {
        formData.append('description', docDescription);
      }
      if (docTags) {
        // 将逗号分隔的标签转换为JSON数组
        const tagsArray = docTags.split(',').map(t => t.trim()).filter(t => t);
        formData.append('doc_tags', JSON.stringify(tagsArray));
      }

      await axios.post(`${API_BASE}/api/user-documents/documents`, formData, {
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'multipart/form-data',
        },
      });

      alert('文档上传成功！');
      setDocName('');
      setDocDescription('');
      setDocTags('');
      setSelectedFile(null);
      setUploadCategoryId('');
      setShowUploadForm(false);

      await loadDocuments(selectedCategory?.id);
      await loadCategories(); // 刷新分类以更新文档数量
    } catch (err: any) {
      console.error('上传文档失败:', err);
      alert(err.response?.data?.detail || '上传文档失败');
    } finally {
      setUploading(false);
    }
  };

  // 删除文档
  const handleDeleteDocument = async (docId: string, docName: string) => {
    if (!confirm(`确定要删除文档"${docName}"吗？此操作不可恢复。`)) {
      return;
    }

    try {
      await axios.delete(`${API_BASE}/api/user-documents/documents/${docId}`, {
        headers: getAuthHeaders(),
      });

      alert('文档已删除');
      
      if (selectedDocument?.id === docId) {
        setSelectedDocument(null);
      }

      await loadDocuments(selectedCategory?.id);
      await loadCategories(); // 刷新分类以更新文档数量
    } catch (err: any) {
      console.error('删除文档失败:', err);
      alert(err.response?.data?.detail || '删除文档失败');
    }
  };

  // 分析文档
  const handleAnalyzeDocument = async (docId: string) => {
    if (!confirm('确定要使用AI分析这个文档吗？这可能需要一些时间。')) {
      return;
    }

    setLoading(true);
    try {
      await axios.post(
        `${API_BASE}/api/user-documents/documents/${docId}/analyze`,
        {},
        { headers: getAuthHeaders() }
      );

      alert('文档分析完成！');
      await loadDocuments(selectedCategory?.id);
    } catch (err: any) {
      console.error('分析文档失败:', err);
      alert(err.response?.data?.detail || '分析文档失败');
    } finally {
      setLoading(false);
    }
  };

  // 选择分类
  const handleSelectCategory = async (category: UserDocCategory | null) => {
    setSelectedCategory(category);
    setSelectedDocument(null);
    await loadDocuments(category?.id);
  };

  // 选择文档
  const handleSelectDocument = (doc: UserDocument) => {
    setSelectedDocument(doc);
  };

  // 格式化文件大小
  const formatFileSize = (bytes?: number) => {
    if (!bytes) return '-';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  // 初始加载
  useEffect(() => {
    loadCategories();
    loadDocuments();
  }, [projectId]);

  return (
    <div style={{ padding: embedded ? 0 : '20px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 头部 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {onBack && (
            <button
              onClick={onBack}
              className="sidebar-btn"
              style={{ width: 'auto', marginBottom: 0 }}
            >
              ← 返回
            </button>
          )}
          <h2 style={{ margin: 0, color: '#ffffff', fontSize: '20px', fontWeight: 600 }}>
            📁 用户文档管理
          </h2>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => setShowCreateCategoryForm(!showCreateCategoryForm)}
            className="kb-create-form"
            style={{ width: 'auto', marginBottom: 0 }}
          >
            {showCreateCategoryForm ? '取消' : '+ 新建分类'}
          </button>
          <button
            onClick={() => {
              setShowUploadForm(!showUploadForm);
              setUploadCategoryId(selectedCategory?.id || '');
            }}
            className="kb-create-form"
            style={{ width: 'auto', marginBottom: 0, background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}
          >
            {showUploadForm ? '取消' : '+ 上传文档'}
          </button>
        </div>
      </div>

      {/* 项目提示 */}
      {!projectId && (
        <div style={{ 
          padding: '12px 16px', 
          background: '#fff3cd', 
          borderRadius: '6px', 
          color: '#856404',
          marginBottom: '16px',
          fontSize: '14px'
        }}>
          💡 提示：当前未选择项目，显示所有文档。创建分类和上传文档需要先选择项目。
        </div>
      )}

      {/* 创建分类表单 */}
      {showCreateCategoryForm && (
        <div className="source-card" style={{ marginBottom: '20px', padding: '20px' }}>
          <h3 style={{ margin: '0 0 16px 0', color: '#ffffff', fontSize: '16px' }}>新建分类</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <input
              type="text"
              placeholder="分类名称（如：技术资料、资质文件）"
              value={categoryName}
              onChange={e => setCategoryName(e.target.value)}
              style={{ padding: '10px', borderRadius: '6px', border: '1px solid #444', background: '#2a2a2a', color: '#fff' }}
            />
            <textarea
              placeholder="分类描述（可选）"
              value={categoryDesc}
              onChange={e => setCategoryDesc(e.target.value)}
              style={{ padding: '10px', borderRadius: '6px', border: '1px solid #444', background: '#2a2a2a', color: '#fff', minHeight: '60px' }}
            />
            <button
              onClick={handleCreateCategory}
              className="kb-create-form"
              style={{ width: 'auto' }}
            >
              创建分类
            </button>
          </div>
        </div>
      )}

      {/* 上传文档表单 */}
      {showUploadForm && (
        <div className="source-card" style={{ marginBottom: '20px', padding: '20px' }}>
          <h3 style={{ margin: '0 0 16px 0', color: '#ffffff', fontSize: '16px' }}>上传文档</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <input
              type="text"
              placeholder="文档名称"
              value={docName}
              onChange={e => setDocName(e.target.value)}
              style={{ padding: '10px', borderRadius: '6px', border: '1px solid #444', background: '#2a2a2a', color: '#fff' }}
            />
            <select
              value={uploadCategoryId}
              onChange={e => setUploadCategoryId(e.target.value)}
              style={{ padding: '10px', borderRadius: '6px', border: '1px solid #444', background: '#2a2a2a', color: '#fff' }}
            >
              <option value="">未分类</option>
              {categories.map(cat => (
                <option key={cat.id} value={cat.id}>
                  {cat.category_name}
                </option>
              ))}
            </select>
            <textarea
              placeholder="文档描述（可选）"
              value={docDescription}
              onChange={e => setDocDescription(e.target.value)}
              style={{ padding: '10px', borderRadius: '6px', border: '1px solid #444', background: '#2a2a2a', color: '#fff', minHeight: '60px' }}
            />
            <input
              type="text"
              placeholder="文档标签（逗号分隔，如：ISO认证,2024年）"
              value={docTags}
              onChange={e => setDocTags(e.target.value)}
              style={{ padding: '10px', borderRadius: '6px', border: '1px solid #444', background: '#2a2a2a', color: '#fff' }}
            />
            <input
              type="file"
              onChange={e => setSelectedFile(e.target.files?.[0] || null)}
              style={{ padding: '10px', borderRadius: '6px', border: '1px solid #444', background: '#2a2a2a', color: '#fff' }}
              accept=".pdf,.doc,.docx,.txt,.md,.jpg,.jpeg,.png,.gif,.bmp,.webp,.xls,.xlsx,.ppt,.pptx"
            />
            {selectedFile && (
              <div style={{ color: '#888', fontSize: '12px' }}>
                已选择: {selectedFile.name} ({formatFileSize(selectedFile.size)})
              </div>
            )}
            <button
              onClick={handleUploadDocument}
              disabled={uploading}
              className="kb-create-form"
              style={{ width: 'auto' }}
            >
              {uploading ? '上传中...' : '上传文档'}
            </button>
          </div>
        </div>
      )}

      {/* 主内容区域 */}
      <div style={{ flex: 1, display: 'flex', gap: '20px', overflow: 'hidden' }}>
        {/* 左侧：分类列表 */}
        <div style={{ width: '250px', display: 'flex', flexDirection: 'column', gap: '8px', overflow: 'auto' }}>
          <div
            onClick={() => handleSelectCategory(null)}
            className={`kb-row ${!selectedCategory ? 'active' : ''}`}
            style={{ cursor: 'pointer' }}
          >
            <div style={{ flex: 1 }}>
              <div className="kb-name">📋 全部文档</div>
              <div className="kb-meta">{documents.length} 个文档</div>
            </div>
          </div>
          
          <div style={{ fontSize: '12px', color: '#888', padding: '8px 12px' }}>分类列表</div>
          
          {categories.map(cat => (
            <div
              key={cat.id}
              onClick={() => handleSelectCategory(cat)}
              className={`kb-row ${selectedCategory?.id === cat.id ? 'active' : ''}`}
              style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
            >
              <div style={{ flex: 1 }}>
                <div className="kb-name">{cat.category_name}</div>
                <div className="kb-meta">{cat.doc_count || 0} 个文档</div>
                {cat.category_desc && (
                  <div className="sidebar-hint" style={{ marginTop: '4px' }}>{cat.category_desc}</div>
                )}
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeleteCategory(cat.id, cat.category_name);
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#ff6b6b',
                  cursor: 'pointer',
                  fontSize: '14px',
                  padding: '4px 8px',
                }}
                title="删除分类"
              >
                🗑️
              </button>
            </div>
          ))}
        </div>

        {/* 中间：文档列表 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ fontSize: '14px', color: '#888', marginBottom: '12px' }}>
            {selectedCategory ? `分类：${selectedCategory.category_name}` : '全部文档'}
            （共 {documents.length} 个）
          </div>
          
          <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {loading ? (
              <div className="kb-doc-meta">加载中...</div>
            ) : documents.length === 0 ? (
              <div className="kb-doc-meta">暂无文档，请上传文档</div>
            ) : (
              documents.map(doc => (
                <div
                  key={doc.id}
                  onClick={() => handleSelectDocument(doc)}
                  className={`source-card ${selectedDocument?.id === doc.id ? 'active' : ''}`}
                  style={{ cursor: 'pointer', padding: '16px' }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                        <span style={{ fontSize: '16px' }}>
                          {doc.file_type === 'image' ? '🖼️' : doc.file_type === 'pdf' ? '📄' : '📝'}
                        </span>
                        <span style={{ color: '#fff', fontWeight: '500' }}>{doc.doc_name}</span>
                        {doc.is_analyzed && (
                          <span style={{ fontSize: '12px', background: '#4caf50', color: '#fff', padding: '2px 6px', borderRadius: '4px' }}>
                            已分析
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>
                        文件: {doc.filename} ({formatFileSize(doc.file_size)})
                      </div>
                      {doc.category_name && (
                        <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>
                          分类: {doc.category_name}
                        </div>
                      )}
                      {doc.doc_tags && doc.doc_tags.length > 0 && (
                        <div style={{ display: 'flex', gap: '4px', marginTop: '8px', flexWrap: 'wrap' }}>
                          {doc.doc_tags.map((tag, idx) => (
                            <span
                              key={idx}
                              style={{
                                fontSize: '11px',
                                background: '#444',
                                color: '#aaa',
                                padding: '2px 6px',
                                borderRadius: '3px',
                              }}
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    <div style={{ display: 'flex', gap: '4px', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        {!doc.is_analyzed && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleAnalyzeDocument(doc.id);
                            }}
                            style={{
                              background: 'none',
                              border: '1px solid #667eea',
                              color: '#667eea',
                              cursor: 'pointer',
                              fontSize: '12px',
                              padding: '4px 8px',
                              borderRadius: '4px',
                            }}
                            title="AI分析"
                          >
                            🔍 分析
                          </button>
                        )}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteDocument(doc.id, doc.doc_name);
                          }}
                          style={{
                            background: 'none',
                            border: 'none',
                            color: '#ff6b6b',
                            cursor: 'pointer',
                            fontSize: '14px',
                            padding: '4px 8px',
                          }}
                          title="删除文档"
                        >
                          🗑️
                        </button>
                      </div>
                      <ShareButton
                        resourceType="document"
                        resourceId={doc.id}
                        resourceName={doc.doc_name}
                        isShared={doc.scope === 'organization'}
                        onShareChange={() => loadDocuments(selectedCategory?.id)}
                      />
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* 右侧：文档详情 */}
        {selectedDocument && (
          <div style={{ width: '350px', display: 'flex', flexDirection: 'column', gap: '12px', overflow: 'auto' }}>
            <div className="source-card" style={{ padding: '20px' }}>
              <h3 style={{ margin: '0 0 16px 0', color: '#ffffff', fontSize: '16px' }}>文档详情</h3>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div>
                  <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>文档名称</div>
                  <div style={{ color: '#fff' }}>{selectedDocument.doc_name}</div>
                </div>
                
                <div>
                  <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>文件名</div>
                  <div style={{ color: '#fff', fontSize: '13px' }}>{selectedDocument.filename}</div>
                </div>
                
                <div>
                  <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>文件类型</div>
                  <div style={{ color: '#fff' }}>{selectedDocument.file_type.toUpperCase()}</div>
                </div>
                
                <div>
                  <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>文件大小</div>
                  <div style={{ color: '#fff' }}>{formatFileSize(selectedDocument.file_size)}</div>
                </div>
                
                {selectedDocument.description && (
                  <div>
                    <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>描述</div>
                    <div style={{ color: '#fff', fontSize: '13px' }}>{selectedDocument.description}</div>
                  </div>
                )}
                
                {selectedDocument.doc_tags && selectedDocument.doc_tags.length > 0 && (
                  <div>
                    <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>标签</div>
                    <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                      {selectedDocument.doc_tags.map((tag, idx) => (
                        <span
                          key={idx}
                          style={{
                            fontSize: '11px',
                            background: '#444',
                            color: '#aaa',
                            padding: '2px 6px',
                            borderRadius: '3px',
                          }}
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                
                {selectedDocument.is_analyzed && selectedDocument.analysis_json && (
                  <div>
                    <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>AI分析结果</div>
                    <div style={{ 
                      color: '#fff', 
                      fontSize: '13px', 
                      background: '#2a2a2a', 
                      padding: '12px', 
                      borderRadius: '6px',
                      whiteSpace: 'pre-wrap'
                    }}>
                      {JSON.stringify(selectedDocument.analysis_json, null, 2)}
                    </div>
                  </div>
                )}
                
                <div>
                  <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>上传时间</div>
                  <div style={{ color: '#fff', fontSize: '13px' }}>
                    {selectedDocument.created_at ? new Date(selectedDocument.created_at).toLocaleString('zh-CN') : '-'}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

