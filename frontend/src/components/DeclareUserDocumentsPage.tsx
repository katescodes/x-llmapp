/**
 * 申报书用户文档管理页面
 * 样式与招投标的UserDocumentsPage一致
 * 
 * 功能：
 * 1. 管理文档分类（申报通知、用户文档、图片等）
 * 2. 上传文档（支持PDF、Word、图片、Excel等）
 * 3. 查看和管理文档列表
 * 4. 删除文档
 */

import React, { useState, useEffect } from 'react';
import * as declareApi from '../api/declareApiProvider';

interface DeclareAsset {
  asset_id: string;
  project_id: string;
  kind: 'notice' | 'user_doc';
  asset_type: 'document' | 'image' | 'image_description';
  filename: string;
  storage_path?: string;
  file_size?: number;
  mime_type?: string;
  created_at?: string;
  metadata?: any;
}

interface Props {
  projectId: string;
  onBack?: () => void;
}

export default function DeclareUserDocumentsPage({ projectId, onBack }: Props) {
  const [assets, setAssets] = useState<DeclareAsset[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<'all' | 'notice' | 'user_doc' | 'image'>('all');
  const [selectedDocument, setSelectedDocument] = useState<DeclareAsset | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  // 上传文档表单状态
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [uploadKind, setUploadKind] = useState<'notice' | 'user_doc'>('notice');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

  // 加载文档列表
  const loadDocuments = async () => {
    setLoading(true);
    try {
      const result = await declareApi.listAssets(projectId);
      setAssets(result.assets || []);
    } catch (err: any) {
      console.error('加载文档失败:', err);
      alert('加载文档失败: ' + (err.message || '未知错误'));
    } finally {
      setLoading(false);
    }
  };

  // 上传文档
  const handleUploadDocuments = async () => {
    if (selectedFiles.length === 0) {
      alert('请选择文件');
      return;
    }

    setUploading(true);
    try {
      // 判断kind：如果是图片，使用'image'，否则使用当前选择的kind
      const finalKind = selectedFiles.some(f => f.type.startsWith('image/')) ? 'image' : uploadKind;
      
      await declareApi.uploadAssets(
        projectId,
        finalKind,
        selectedFiles
      );

      alert('文档上传成功！');
      setSelectedFiles([]);
      setShowUploadForm(false);

      await loadDocuments();
    } catch (err: any) {
      console.error('上传文档失败:', err);
      alert('上传文档失败: ' + (err.message || '未知错误'));
    } finally {
      setUploading(false);
    }
  };

  // 删除文档（暂不支持API）
  const handleDeleteDocument = async (assetId: string, filename: string) => {
    alert('删除功能暂未开放，请联系管理员');
    // TODO: 等待后端API实现后启用
    // if (!confirm(`确定要删除文档"${filename}"吗？此操作不可恢复。`)) {
    //   return;
    // }
    // try {
    //   await declareApi.deleteAsset(projectId, assetId);
    //   alert('文档已删除');
    //   if (selectedDocument?.asset_id === assetId) {
    //     setSelectedDocument(null);
    //   }
    //   await loadDocuments();
    // } catch (err: any) {
    //   console.error('删除文档失败:', err);
    //   alert('删除文档失败: ' + (err.message || '未知错误'));
    // }
  };

  // 选择文档
  const handleSelectDocument = (doc: DeclareAsset) => {
    setSelectedDocument(doc);
  };

  // 格式化文件大小
  const formatFileSize = (bytes?: number) => {
    if (!bytes) return '-';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  // 获取分类名称
  const getCategoryName = (kind: string, asset_type?: string) => {
    if (kind === 'notice') return '📄 申报通知';
    if (asset_type === 'image') return '🖼️ 图片资料';
    return '📋 用户文档';
  };

  // 获取分类图标
  const getCategoryIcon = (kind: string, asset_type?: string) => {
    if (kind === 'notice') return '📄';
    if (asset_type === 'image') return '🖼️';
    return '📝';
  };

  // 过滤文档
  const filteredDocuments = assets.filter(doc => {
    if (selectedCategory === 'all') return true;
    if (selectedCategory === 'notice') return doc.kind === 'notice';
    if (selectedCategory === 'image') return doc.asset_type === 'image';
    if (selectedCategory === 'user_doc') return doc.kind === 'user_doc' && doc.asset_type !== 'image';
    return true;
  });

  // 初始加载
  useEffect(() => {
    loadDocuments();
  }, [projectId]);

  return (
    <div style={{ padding: '20px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 头部 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {onBack && (
            <button
              onClick={onBack}
              className="sidebar-btn"
              style={{ 
                width: 'auto', 
                marginBottom: 0,
                padding: '10px 20px'
              }}
            >
              ← 返回
            </button>
          )}
          <h2 style={{ margin: 0, color: '#ffffff', fontSize: '20px', fontWeight: 600 }}>
            📁 申报书文档管理
          </h2>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => {
              setShowUploadForm(!showUploadForm);
              setUploadKind('user_doc');
            }}
            className="kb-create-form"
            style={{ 
              width: 'auto', 
              marginBottom: 0, 
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' 
            }}
          >
            {showUploadForm ? '取消' : '+ 上传文档'}
          </button>
        </div>
      </div>

      {/* 上传文档表单 */}
      {showUploadForm && (
        <div className="source-card" style={{ marginBottom: '20px', padding: '20px' }}>
          <h3 style={{ margin: '0 0 16px 0', color: '#ffffff', fontSize: '16px' }}>上传文档</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <select
              value={uploadKind}
              onChange={e => setUploadKind(e.target.value as 'notice' | 'user_doc')}
              style={{ 
                padding: '10px', 
                borderRadius: '6px', 
                border: '1px solid #444', 
                background: '#2a2a2a', 
                color: '#fff' 
              }}
            >
              <option value="notice">📄 申报通知</option>
              <option value="user_doc">📋 用户文档</option>
            </select>
            
            <input
              type="file"
              multiple
              onChange={e => setSelectedFiles(Array.from(e.target.files || []))}
              style={{ 
                padding: '10px', 
                borderRadius: '6px', 
                border: '1px solid #444', 
                background: '#2a2a2a', 
                color: '#fff' 
              }}
              accept=".pdf,.doc,.docx,.txt,.xls,.xlsx,.jpg,.jpeg,.png,.gif,.bmp,.webp"
            />
            
            {selectedFiles.length > 0 && (
              <div style={{ color: '#888', fontSize: '12px' }}>
                已选择 {selectedFiles.length} 个文件
                {selectedFiles.map((f, idx) => (
                  <div key={idx} style={{ marginTop: '4px' }}>
                    • {f.name} ({formatFileSize(f.size)})
                  </div>
                ))}
              </div>
            )}
            
            <button
              onClick={handleUploadDocuments}
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
            onClick={() => {
              setSelectedCategory('all');
              setSelectedDocument(null);
            }}
            className={`kb-row ${selectedCategory === 'all' ? 'active' : ''}`}
            style={{ cursor: 'pointer' }}
          >
            <div style={{ flex: 1 }}>
              <div className="kb-name">📋 全部文档</div>
              <div className="kb-meta">{assets.length} 个文档</div>
            </div>
          </div>
          
          <div style={{ fontSize: '12px', color: '#888', padding: '8px 12px' }}>分类列表</div>
          
          <div
            onClick={() => {
              setSelectedCategory('notice');
              setSelectedDocument(null);
            }}
            className={`kb-row ${selectedCategory === 'notice' ? 'active' : ''}`}
            style={{ cursor: 'pointer' }}
          >
            <div style={{ flex: 1 }}>
              <div className="kb-name">📄 申报通知</div>
              <div className="kb-meta">
                {assets.filter(a => a.kind === 'notice').length} 个文档
              </div>
            </div>
          </div>
          
          <div
            onClick={() => {
              setSelectedCategory('user_doc');
              setSelectedDocument(null);
            }}
            className={`kb-row ${selectedCategory === 'user_doc' ? 'active' : ''}`}
            style={{ cursor: 'pointer' }}
          >
            <div style={{ flex: 1 }}>
              <div className="kb-name">📋 用户文档</div>
              <div className="kb-meta">
                {assets.filter(a => a.kind === 'user_doc' && a.asset_type !== 'image').length} 个文档
              </div>
            </div>
          </div>
          
          <div
            onClick={() => {
              setSelectedCategory('image');
              setSelectedDocument(null);
            }}
            className={`kb-row ${selectedCategory === 'image' ? 'active' : ''}`}
            style={{ cursor: 'pointer' }}
          >
            <div style={{ flex: 1 }}>
              <div className="kb-name">🖼️ 图片资料</div>
              <div className="kb-meta">
                {assets.filter(a => a.asset_type === 'image').length} 个图片
              </div>
            </div>
          </div>
        </div>

        {/* 中间：文档列表 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ fontSize: '14px', color: '#888', marginBottom: '12px' }}>
            {selectedCategory === 'all' ? '全部文档' : 
             selectedCategory === 'notice' ? '申报通知' :
             selectedCategory === 'image' ? '图片资料' : '用户文档'}
            （共 {filteredDocuments.length} 个）
          </div>
          
          <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {loading ? (
              <div className="kb-doc-meta">加载中...</div>
            ) : filteredDocuments.length === 0 ? (
              <div className="kb-doc-meta">暂无文档，请上传文档</div>
            ) : (
              filteredDocuments.map(doc => (
                <div
                  key={doc.asset_id}
                  onClick={() => handleSelectDocument(doc)}
                  className={`source-card ${selectedDocument?.asset_id === doc.asset_id ? 'active' : ''}`}
                  style={{ cursor: 'pointer', padding: '16px' }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                        <span style={{ fontSize: '16px' }}>
                          {getCategoryIcon(doc.kind, doc.asset_type)}
                        </span>
                        <span style={{ color: '#fff', fontWeight: '500' }}>{doc.filename}</span>
                      </div>
                      <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>
                        分类: {getCategoryName(doc.kind, doc.asset_type)}
                      </div>
                      <div style={{ fontSize: '12px', color: '#888' }}>
                        大小: {formatFileSize(doc.file_size)}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '4px' }}>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteDocument(doc.asset_id, doc.filename);
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
                  <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>文件名</div>
                  <div style={{ color: '#fff' }}>{selectedDocument.filename}</div>
                </div>
                
                <div>
                  <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>分类</div>
                  <div style={{ color: '#fff' }}>{getCategoryName(selectedDocument.kind, selectedDocument.asset_type)}</div>
                </div>
                
                <div>
                  <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>类型</div>
                  <div style={{ color: '#fff' }}>
                    {selectedDocument.asset_type === 'image' ? '图片' : '文档'}
                  </div>
                </div>
                
                <div>
                  <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>文件大小</div>
                  <div style={{ color: '#fff' }}>{formatFileSize(selectedDocument.file_size)}</div>
                </div>
                
                {selectedDocument.mime_type && (
                  <div>
                    <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>MIME类型</div>
                    <div style={{ color: '#fff', fontSize: '13px' }}>{selectedDocument.mime_type}</div>
                  </div>
                )}
                
                {selectedDocument.metadata && Object.keys(selectedDocument.metadata).length > 0 && (
                  <div>
                    <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>元数据</div>
                    <div style={{ 
                      color: '#fff', 
                      fontSize: '13px', 
                      background: '#2a2a2a', 
                      padding: '12px', 
                      borderRadius: '6px',
                      whiteSpace: 'pre-wrap',
                      maxHeight: '200px',
                      overflow: 'auto'
                    }}>
                      {JSON.stringify(selectedDocument.metadata, null, 2)}
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

