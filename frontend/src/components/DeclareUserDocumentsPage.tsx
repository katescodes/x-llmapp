/**
 * 申报书用户文档管理页面
 * 
 * 功能：
 * 1. 表格形式展示文档列表
 * 2. 支持批量选择和批量删除
 * 3. 上传时自动去重（相同文件名的文档）
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
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  // 批量选择
  const [selectedAssetIds, setSelectedAssetIds] = useState<Set<string>>(new Set());
  const [selectAll, setSelectAll] = useState(false);

  // 上传文档表单状态
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [uploadKind, setUploadKind] = useState<'notice' | 'user_doc'>('user_doc');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

  // 加载文档列表
  const loadDocuments = async () => {
    setLoading(true);
    try {
      const result = await declareApi.listAssets(projectId);
      const assetsList = Array.isArray(result) ? result : result.assets || [];
      setAssets(assetsList);
    } catch (err: any) {
      console.error('加载文档失败:', err);
      alert('加载文档失败: ' + (err.message || '未知错误'));
    } finally {
      setLoading(false);
    }
  };

  // 文件去重检查
  const checkDuplicateFiles = (files: File[]): { unique: File[], duplicates: string[] } => {
    const existingFilenames = new Set(assets.map(a => a.filename));
    const unique: File[] = [];
    const duplicates: string[] = [];

    files.forEach(file => {
      if (existingFilenames.has(file.name)) {
        duplicates.push(file.name);
      } else {
        unique.push(file);
        existingFilenames.add(file.name); // 防止本次上传中的重复
      }
    });

    return { unique, duplicates };
  };

  // 上传文档
  const handleUploadDocuments = async () => {
    if (selectedFiles.length === 0) {
      alert('请选择文件');
      return;
    }

    // 去重检查
    const { unique, duplicates } = checkDuplicateFiles(selectedFiles);
    
    if (duplicates.length > 0) {
      const msg = `以下文件已存在，将被跳过：\n${duplicates.join('\n')}\n\n是否继续上传其余${unique.length}个文件？`;
      if (unique.length === 0) {
        alert('所选文件均已存在，无需重复上传');
        return;
      }
      if (!confirm(msg)) {
        return;
      }
    }

    if (unique.length === 0) {
      return;
    }

    setUploading(true);
    try {
      console.log('[DeclareUserDocs] 开始上传（去重后）:', {
        projectId,
        uploadKind,
        totalFiles: selectedFiles.length,
        uniqueFiles: unique.length,
        duplicates: duplicates.length
      });
      
      const result = await declareApi.uploadAssets(
        projectId,
        uploadKind,
        unique // 只上传去重后的文件
      );
      
      console.log('[DeclareUserDocs] 上传成功:', result);

      const successMsg = `成功上传 ${unique.length} 个文件` + 
        (duplicates.length > 0 ? `\n跳过 ${duplicates.length} 个重复文件` : '');
      alert(successMsg);
      
      setSelectedFiles([]);
      setShowUploadForm(false);
      await loadDocuments();
    } catch (err: any) {
      console.error('[DeclareUserDocs] 上传文档失败:', err);
      alert('上传文档失败: ' + (err.message || '未知错误'));
    } finally {
      setUploading(false);
    }
  };

  // 切换单个选择
  const toggleSelectAsset = (assetId: string) => {
    const newSelected = new Set(selectedAssetIds);
    if (newSelected.has(assetId)) {
      newSelected.delete(assetId);
    } else {
      newSelected.add(assetId);
    }
    setSelectedAssetIds(newSelected);
    setSelectAll(newSelected.size === filteredDocuments.length && filteredDocuments.length > 0);
  };

  // 切换全选
  const toggleSelectAll = () => {
    if (selectAll) {
      setSelectedAssetIds(new Set());
      setSelectAll(false);
    } else {
      const allIds = new Set(filteredDocuments.map(d => d.asset_id));
      setSelectedAssetIds(allIds);
      setSelectAll(true);
    }
  };

  // 批量删除
  const handleBatchDelete = async () => {
    if (selectedAssetIds.size === 0) {
      alert('请选择要删除的文档');
      return;
    }

    if (!confirm(`确定要删除选中的 ${selectedAssetIds.size} 个文档吗？此操作不可恢复。`)) {
      return;
    }

    try {
      // 逐个删除
      const deletePromises = Array.from(selectedAssetIds).map(assetId =>
        declareApi.deleteAsset(projectId, assetId)
      );
      
      await Promise.all(deletePromises);
      
      alert(`成功删除 ${selectedAssetIds.size} 个文档`);
      setSelectedAssetIds(new Set());
      setSelectAll(false);
      await loadDocuments();
    } catch (err: any) {
      console.error('批量删除失败:', err);
      alert('批量删除失败: ' + (err.message || '未知错误'));
    }
  };

  // 删除单个文档
  const handleDeleteDocument = async (assetId: string, filename: string) => {
    if (!confirm(`确定要删除文档"${filename}"吗？此操作不可恢复。`)) {
      return;
    }
    try {
      await declareApi.deleteAsset(projectId, assetId);
      alert('文档已删除');
      setSelectedAssetIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(assetId);
        return newSet;
      });
      await loadDocuments();
    } catch (err: any) {
      console.error('删除文档失败:', err);
      alert('删除文档失败: ' + (err.message || '未知错误'));
    }
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
    if (kind === 'notice') return '申报通知';
    if (asset_type === 'image') return '图片资料';
    if (asset_type === 'image_description') return '图片说明';
    return '用户文档';
  };

  // 获取分类图标
  const getCategoryIcon = (kind: string, asset_type?: string) => {
    if (kind === 'notice') return '📄';
    if (asset_type === 'image') return '🖼️';
    if (asset_type === 'image_description') return '📊';
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

  // 当过滤条件变化时，清空选择
  useEffect(() => {
    setSelectedAssetIds(new Set());
    setSelectAll(false);
  }, [selectedCategory]);

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
          {selectedAssetIds.size > 0 && (
            <button
              onClick={handleBatchDelete}
              className="kb-create-form"
              style={{ 
                width: 'auto', 
                marginBottom: 0, 
                background: 'linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%)' 
              }}
            >
              🗑️ 批量删除 ({selectedAssetIds.size})
            </button>
          )}
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
              style={{ padding: '10px', borderRadius: '6px', border: '1px solid #444', background: '#2a2a2a', color: '#fff' }}
            >
              <option value="notice">📄 申报通知</option>
              <option value="user_doc">📋 用户文档（含图片、Excel）</option>
            </select>
            <input
              type="file"
              multiple
              onChange={e => setSelectedFiles(Array.from(e.target.files || []))}
              style={{ padding: '10px', borderRadius: '6px', border: '1px solid #444', background: '#2a2a2a', color: '#fff' }}
              accept=".pdf,.doc,.docx,.txt,.md,.jpg,.jpeg,.png,.gif,.bmp,.webp,.xls,.xlsx,.ppt,.pptx"
            />
            {selectedFiles.length > 0 && (
              <div style={{ color: '#888', fontSize: '12px' }}>
                已选择 {selectedFiles.length} 个文件
                <div style={{ marginTop: '8px', maxHeight: '120px', overflow: 'auto' }}>
                  {selectedFiles.map((f, idx) => {
                    const isDuplicate = assets.some(a => a.filename === f.name);
                    return (
                      <div key={idx} style={{ 
                        marginTop: '4px',
                        color: isDuplicate ? '#ff6b6b' : '#888'
                      }}>
                        {isDuplicate && '⚠️ '} {f.name} ({formatFileSize(f.size)})
                        {isDuplicate && ' - 文件已存在，将被跳过'}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
            <button
              onClick={handleUploadDocuments}
              disabled={uploading || selectedFiles.length === 0}
              className="kb-create-form"
              style={{ width: 'auto' }}
            >
              {uploading ? '上传中...' : '上传文档'}
            </button>
          </div>
        </div>
      )}

      {/* 分类标签 */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', flexWrap: 'wrap' }}>
        <button
          onClick={() => setSelectedCategory('all')}
          style={{
            padding: '8px 16px',
            borderRadius: '6px',
            border: selectedCategory === 'all' ? '2px solid #667eea' : '1px solid #444',
            background: selectedCategory === 'all' ? 'rgba(102, 126, 234, 0.2)' : '#2a2a2a',
            color: '#fff',
            cursor: 'pointer',
            fontSize: '13px'
          }}
        >
          📋 全部文档 ({assets.length})
        </button>
        <button
          onClick={() => setSelectedCategory('notice')}
          style={{
            padding: '8px 16px',
            borderRadius: '6px',
            border: selectedCategory === 'notice' ? '2px solid #667eea' : '1px solid #444',
            background: selectedCategory === 'notice' ? 'rgba(102, 126, 234, 0.2)' : '#2a2a2a',
            color: '#fff',
            cursor: 'pointer',
            fontSize: '13px'
          }}
        >
          📄 申报通知 ({assets.filter(a => a.kind === 'notice').length})
        </button>
        <button
          onClick={() => setSelectedCategory('user_doc')}
          style={{
            padding: '8px 16px',
            borderRadius: '6px',
            border: selectedCategory === 'user_doc' ? '2px solid #667eea' : '1px solid #444',
            background: selectedCategory === 'user_doc' ? 'rgba(102, 126, 234, 0.2)' : '#2a2a2a',
            color: '#fff',
            cursor: 'pointer',
            fontSize: '13px'
          }}
        >
          📝 用户文档 ({assets.filter(a => a.kind === 'user_doc' && a.asset_type !== 'image').length})
        </button>
        <button
          onClick={() => setSelectedCategory('image')}
          style={{
            padding: '8px 16px',
            borderRadius: '6px',
            border: selectedCategory === 'image' ? '2px solid #667eea' : '1px solid #444',
            background: selectedCategory === 'image' ? 'rgba(102, 126, 234, 0.2)' : '#2a2a2a',
            color: '#fff',
            cursor: 'pointer',
            fontSize: '13px'
          }}
        >
          🖼️ 图片资料 ({assets.filter(a => a.asset_type === 'image').length})
        </button>
      </div>

      {/* 表格 */}
      <div style={{ flex: 1, overflow: 'auto', background: '#1a1a1a', borderRadius: '8px', border: '1px solid #333' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead style={{ background: '#2a2a2a', position: 'sticky', top: 0, zIndex: 1 }}>
            <tr>
              <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #444', width: '40px' }}>
                <input
                  type="checkbox"
                  checked={selectAll}
                  onChange={toggleSelectAll}
                  style={{ cursor: 'pointer' }}
                />
              </th>
              <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #444', color: '#888', fontSize: '13px', fontWeight: 600 }}>
                文件名
              </th>
              <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #444', color: '#888', fontSize: '13px', fontWeight: 600, width: '120px' }}>
                分类
              </th>
              <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #444', color: '#888', fontSize: '13px', fontWeight: 600, width: '100px' }}>
                大小
              </th>
              <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #444', color: '#888', fontSize: '13px', fontWeight: 600, width: '160px' }}>
                上传时间
              </th>
              <th style={{ padding: '12px', textAlign: 'center', borderBottom: '1px solid #444', color: '#888', fontSize: '13px', fontWeight: 600, width: '80px' }}>
                操作
              </th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} style={{ padding: '40px', textAlign: 'center', color: '#888' }}>
                  加载中...
                </td>
              </tr>
            ) : filteredDocuments.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ padding: '40px', textAlign: 'center', color: '#888' }}>
                  暂无文档，请上传文档
                </td>
              </tr>
            ) : (
              filteredDocuments.map(doc => (
                <tr
                  key={doc.asset_id}
                  style={{
                    background: selectedAssetIds.has(doc.asset_id) ? 'rgba(102, 126, 234, 0.1)' : 'transparent',
                    borderBottom: '1px solid #2a2a2a'
                  }}
                  onMouseEnter={e => {
                    if (!selectedAssetIds.has(doc.asset_id)) {
                      e.currentTarget.style.background = 'rgba(255, 255, 255, 0.02)';
                    }
                  }}
                  onMouseLeave={e => {
                    if (!selectedAssetIds.has(doc.asset_id)) {
                      e.currentTarget.style.background = 'transparent';
                    }
                  }}
                >
                  <td style={{ padding: '12px' }}>
                    <input
                      type="checkbox"
                      checked={selectedAssetIds.has(doc.asset_id)}
                      onChange={() => toggleSelectAsset(doc.asset_id)}
                      style={{ cursor: 'pointer' }}
                    />
                  </td>
                  <td style={{ padding: '12px', color: '#fff', fontSize: '13px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '16px' }}>{getCategoryIcon(doc.kind, doc.asset_type)}</span>
                      <span>{doc.filename}</span>
                    </div>
                  </td>
                  <td style={{ padding: '12px', color: '#aaa', fontSize: '12px' }}>
                    {getCategoryName(doc.kind, doc.asset_type)}
                  </td>
                  <td style={{ padding: '12px', color: '#aaa', fontSize: '12px' }}>
                    {formatFileSize(doc.file_size)}
                  </td>
                  <td style={{ padding: '12px', color: '#aaa', fontSize: '12px' }}>
                    {doc.created_at ? new Date(doc.created_at).toLocaleString('zh-CN', {
                      year: 'numeric',
                      month: '2-digit',
                      day: '2-digit',
                      hour: '2-digit',
                      minute: '2-digit'
                    }) : '-'}
                  </td>
                  <td style={{ padding: '12px', textAlign: 'center' }}>
                    <button
                      onClick={() => handleDeleteDocument(doc.asset_id, doc.filename)}
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
                      🗑️ 删除
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* 底部统计 */}
      {filteredDocuments.length > 0 && (
        <div style={{ marginTop: '16px', padding: '12px', background: '#2a2a2a', borderRadius: '6px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ color: '#888', fontSize: '13px' }}>
            共 {filteredDocuments.length} 个文档
            {selectedAssetIds.size > 0 && ` · 已选择 ${selectedAssetIds.size} 个`}
          </div>
          <div style={{ color: '#888', fontSize: '13px' }}>
            总大小: {formatFileSize(filteredDocuments.reduce((sum, doc) => sum + (doc.file_size || 0), 0))}
          </div>
        </div>
      )}
    </div>
  );
}
