/**
 * 录音列表组件
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useAuthFetch } from '../hooks/usePermission';
import { Recording, RecordingStatus } from '../types/recording';
import ImportWizard from './ImportWizard';
import VoiceRecorder from './VoiceRecorder';
import '../styles/recordings.css';

const RecordingsList: React.FC = () => {
  const { token } = useAuth();
  const authFetch = useAuthFetch();
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || window.location.origin;

  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [filteredRecordings, setFilteredRecordings] = useState<Recording[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [selectedRecording, setSelectedRecording] = useState<Recording | null>(null);
  const [showImportWizard, setShowImportWizard] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [viewingRecording, setViewingRecording] = useState<Recording | null>(null);
  const [viewingSummary, setViewingSummary] = useState<Recording | null>(null);
  const [playingAudio, setPlayingAudio] = useState<string | null>(null);
  const [transcribingId, setTranscribingId] = useState<string | null>(null);
  
  // 转写增强选项
  const [showTranscribeDialog, setShowTranscribeDialog] = useState(false);
  const [transcribeRecordingId, setTranscribeRecordingId] = useState<string | null>(null);
  const [enhanceEnabled, setEnhanceEnabled] = useState(false);
  const [enhancementType, setEnhancementType] = useState('punctuation');
  
  // 导入音频文件
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(false);

  // 加载录音列表
  const loadRecordings = useCallback(async () => {
    if (!token) return;

    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: '20',
      });

      if (statusFilter && statusFilter !== 'all') {
        params.append('status', statusFilter);
      }

      if (searchQuery) {
        params.append('search', searchQuery);
      }

      const response = await authFetch(`${apiBaseUrl}/api/recordings?${params}`);

      if (response.ok) {
        const data = await response.json();
        setRecordings(data.items);
        setFilteredRecordings(data.items);
        setTotalPages(data.total_pages);
      } else {
        console.error('Failed to load recordings');
      }
    } catch (error) {
      console.error('Error loading recordings:', error);
    } finally {
      setLoading(false);
    }
    // 移除 authFetch 和 apiBaseUrl 避免无限循环
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, page, statusFilter, searchQuery]);

  useEffect(() => {
    loadRecordings();
  }, [loadRecordings]);

  // 格式化时长
  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // 生成摘要（通过LLM）
  const generateSummary = async (recording: Recording) => {
    try {
      const response = await authFetch(`${apiBaseUrl}/api/recordings/${recording.id}/summary`, {
        method: 'POST',
      });
      if (response.ok) {
        const data = await response.json();
        setViewingSummary({ ...recording, notes: data.summary });
      } else {
        alert('生成摘要失败');
      }
    } catch (error) {
      console.error('生成摘要失败:', error);
      alert('生成摘要失败');
    }
  };

  // 打开转写对话框
  const openTranscribeDialog = (recordingId: string) => {
    setTranscribeRecordingId(recordingId);
    setShowTranscribeDialog(true);
  };

  // 手动转写
  const handleTranscribe = async () => {
    if (!transcribeRecordingId) return;

    setShowTranscribeDialog(false);
    setTranscribingId(transcribeRecordingId);
    
    try {
      // 创建一个带超时的 fetch 请求（5分钟超时）
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5 * 60 * 1000);

      const response = await authFetch(`${apiBaseUrl}/api/recordings/${transcribeRecordingId}/transcribe`, {
        method: 'POST',
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          enhance: enhanceEnabled,
          enhancement_type: enhancementType,
          model_id: null // 使用默认模型
        }),
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        const data = await response.json();
        alert(`转写成功！字数：${data.word_count}${enhanceEnabled ? '\n已应用LLM增强' : ''}`);
        loadRecordings();
      } else {
        const errorData = await response.json();
        alert(`转写失败：${errorData.detail || '未知错误'}`);
      }
    } catch (error: any) {
      console.error('转写失败:', error);
      if (error.name === 'AbortError') {
        alert('转写超时，请检查录音文件大小或稍后重试');
      } else {
        alert('转写失败，请重试');
      }
    } finally {
      setTranscribingId(null);
      setTranscribeRecordingId(null);
    }
  };

  // 格式化文件大小
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // 格式化日期
  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) return '今天 ' + date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    if (days === 1) return '昨天 ' + date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    if (days < 7) return `${days}天前`;
    return date.toLocaleDateString('zh-CN');
  };

  // 状态徽章
  const getStatusBadge = (status: RecordingStatus) => {
    const config = {
      pending: { icon: '⚠️', label: '未入库', color: '#f59e0b' },
      importing: { icon: '⏳', label: '导入中', color: '#3b82f6' },
      imported: { icon: '✅', label: '已入库', color: '#22c55e' },
      failed: { icon: '❌', label: '失败', color: '#ef4444' },
    };

    const { icon, label, color } = config[status] || config.pending;

    return (
      <span
        className="status-badge"
        style={{
          backgroundColor: `${color}20`,
          color,
          border: `1px solid ${color}40`,
        }}
      >
        {icon} {label}
      </span>
    );
  };

  // 删除录音
  const handleDelete = async (recordingId: string) => {
    if (!confirm('确定要删除这条录音吗？')) return;

    try {
      const response = await authFetch(`${apiBaseUrl}/api/recordings/${recordingId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        loadRecordings();
      } else {
        alert('删除失败');
      }
    } catch (error) {
      console.error('Error deleting recording:', error);
      alert('删除失败');
    }
  };

  // 打开导入向导
  const openImportWizard = (recording: Recording) => {
    setSelectedRecording(recording);
    setShowImportWizard(true);
  };

  // 导入成功后的回调
  const handleImportSuccess = () => {
    setShowImportWizard(false);
    setSelectedRecording(null);
    loadRecordings();
  };

  // 录音完成回调
  const handleRecordingComplete = (recordingData: any) => {
    setIsRecording(false);
    // 刷新录音列表
    loadRecordings();
    // 可以选择自动打开导入向导
    // setSelectedRecording(recordingData);
    // setShowImportWizard(true);
  };

  // 下载录音文件
  const handleDownload = async (recordingId: string, title: string, audioFormat: string) => {
    try {
      const response = await authFetch(`${apiBaseUrl}/api/recordings/${recordingId}/download`);
      
      if (response.ok) {
        // 获取文件名（从响应头或使用默认值）
        const contentDisposition = response.headers.get('content-disposition');
        let filename = `${title}.${audioFormat || 'webm'}`;
        
        if (contentDisposition) {
          const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
          if (filenameMatch && filenameMatch[1]) {
            filename = filenameMatch[1].replace(/['"]/g, '');
          }
        }
        
        // 下载文件
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        
        // 延迟清理，确保下载开始
        setTimeout(() => {
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);
        }, 100);
        
        console.log(`下载成功: ${filename}`);
      } else {
        const errorText = await response.text();
        console.error('下载失败:', response.status, errorText);
        alert(`下载失败: ${response.status} - ${errorText || '未知错误'}`);
      }
    } catch (error) {
      console.error('下载失败:', error);
      alert(`下载失败: ${error instanceof Error ? error.message : '网络错误'}`);
    }
  };

  // 上传音频文件
  const handleUploadAudio = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // 检查文件类型
    const allowedTypes = ['audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/m4a', 'audio/ogg', 'audio/webm', 'audio/flac', 'audio/aac'];
    const fileExt = file.name.split('.').pop()?.toLowerCase();
    const allowedExts = ['mp3', 'wav', 'm4a', 'ogg', 'webm', 'flac', 'aac'];
    
    if (!allowedExts.includes(fileExt || '')) {
      alert('不支持的音频格式，支持的格式: mp3, wav, m4a, ogg, webm, flac, aac');
      event.target.value = ''; // 清空input
      return;
    }

    // 检查文件大小（100MB限制）
    if (file.size > 100 * 1024 * 1024) {
      alert('文件过大，最大支持100MB');
      event.target.value = '';
      return;
    }

    setUploadingFile(true);
    
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await authFetch(`${apiBaseUrl}/api/recordings/upload`, {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        alert(`${data.message}\n\n文件名: ${file.name}\n大小: ${formatFileSize(data.file_size)}`);
        setShowImportDialog(false);
        loadRecordings();
      } else {
        const errorData = await response.json();
        alert(`上传失败：${errorData.detail || '未知错误'}`);
      }
    } catch (error) {
      console.error('上传失败:', error);
      alert('上传失败，请重试');
    } finally {
      setUploadingFile(false);
      event.target.value = ''; // 清空input
    }
  };

  return (
    <div className="recordings-container">
      {/* 录音界面 */}
      {isRecording ? (
        <div style={{ padding: '20px' }}>
          <div style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2>🎙️ 新录音</h2>
            <button
              onClick={() => setIsRecording(false)}
              style={{
                padding: '8px 16px',
                background: 'rgba(239, 68, 68, 0.2)',
                color: '#ef4444',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                borderRadius: '6px',
                cursor: 'pointer'
              }}
            >
              ✕ 关闭
            </button>
          </div>
          <VoiceRecorder
            onComplete={handleRecordingComplete}
            onCancel={() => setIsRecording(false)}
          />
        </div>
      ) : (
        <>
          <div className="recordings-header">
            <div>
              <h2>📼 我的录音</h2>
              <div className="recordings-stats">
                共 {filteredRecordings.length} 条录音
              </div>
            </div>
            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                onClick={() => setShowImportDialog(true)}
                style={{
                  padding: '10px 20px',
                  background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontSize: '16px',
                  fontWeight: '600',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                📁 导入音频
              </button>
              <button
                onClick={() => setIsRecording(true)}
                style={{
                  padding: '10px 20px',
                  background: 'linear-gradient(135deg, #22c55e, #16a34a)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontSize: '16px',
                  fontWeight: '600',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                🎤 新录音
              </button>
            </div>
          </div>

          {/* 筛选和搜索 */}
          <div className="recordings-toolbar">
        <div className="filter-buttons">
          <button
            className={`filter-btn ${statusFilter === 'all' ? 'active' : ''}`}
            onClick={() => setStatusFilter('all')}
          >
            全部
          </button>
          <button
            className={`filter-btn ${statusFilter === 'pending' ? 'active' : ''}`}
            onClick={() => setStatusFilter('pending')}
          >
            未入库
          </button>
          <button
            className={`filter-btn ${statusFilter === 'imported' ? 'active' : ''}`}
            onClick={() => setStatusFilter('imported')}
          >
            已入库
          </button>
        </div>

        <div className="search-box">
          <input
            type="text"
            placeholder="搜索录音..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
          </div>

          {/* 录音列表 */}
          {loading ? (
            <div className="loading">加载中...</div>
          ) : filteredRecordings.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">🎙️</div>
              <p>还没有录音，去对话界面开始录音吧！</p>
            </div>
          ) : (
            <>
              <div className="recordings-list">
            {filteredRecordings.map((recording) => (
              <div key={recording.id} className="recording-card">
                <div className="recording-header">
                  <h3 className="recording-title">🎙️ {recording.title}</h3>
                  {getStatusBadge(recording.import_status)}
                </div>

                <div className="recording-meta">
                  <span>{formatDate(recording.created_at)}</span>
                  <span>•</span>
                  <span>{formatDuration(recording.duration)}</span>
                  <span>•</span>
                  <span>{formatFileSize(recording.file_size)}</span>
                  <span>•</span>
                  <span>{recording.word_count} 字</span>
                </div>

                {recording.kb_name && (
                  <div className="recording-kb">
                    ✅ 已入库: <strong>{recording.kb_name}</strong>
                  </div>
                )}

                {recording.tags && recording.tags.length > 0 && (
                  <div className="recording-tags">
                    {recording.tags.map((tag) => (
                      <span key={tag} className="tag">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}

                <div className="recording-actions">
                  {recording.keep_audio && (
                    <>
                      <button
                        className="action-btn play"
                        onClick={() => setPlayingAudio(recording.id)}
                      >
                        ▶️ 播放
                      </button>
                      <button
                        className="action-btn download"
                        onClick={() => handleDownload(recording.id, recording.title, recording.audio_format)}
                      >
                        💾 导出
                      </button>
                      <button
                        className="action-btn transcribe"
                        onClick={() => openTranscribeDialog(recording.id)}
                        disabled={transcribingId === recording.id}
                      >
                        {transcribingId === recording.id 
                          ? '🔄 转写中...' 
                          : (recording.transcript && recording.word_count > 0 ? '🔄 再次转写' : '📝 转写')}
                      </button>
                    </>
                  )}
                  {recording.transcript && recording.word_count > 0 && (
                    <>
                      <button
                        className="action-btn view"
                        onClick={() => setViewingRecording(recording)}
                      >
                        📄 全文
                      </button>
                      <button
                        className="action-btn summary"
                        onClick={() => generateSummary(recording)}
                      >
                        📝 摘要
                      </button>
                    </>
                  )}
                  {recording.transcript && recording.word_count > 0 && (
                    <button
                      className="action-btn import"
                      onClick={() => openImportWizard(recording)}
                    >
                      {recording.import_status === 'imported' ? '🔄 重新导入' : '📥 导入知识库'}
                    </button>
                  )}
                  <button
                    className="action-btn delete"
                    onClick={() => handleDelete(recording.id)}
                  >
                    🗑️ 删除
                  </button>
                </div>
              </div>
            ))}
              </div>

              {/* 分页 */}
              {totalPages > 1 && (
                <div className="pagination">
                  <button
                    disabled={page === 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    上一页
                  </button>
                  <span>
                    第 {page} / {totalPages} 页
                  </span>
                  <button
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  >
                    下一页
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}

      {/* 导入向导对话框 */}
      {showImportWizard && selectedRecording && (
        <ImportWizard
          recording={selectedRecording}
          onClose={() => setShowImportWizard(false)}
          onSuccess={handleImportSuccess}
        />
      )}

      {/* 查看全文对话框 */}
      {viewingRecording && (
        <div className="modal-overlay" onClick={() => setViewingRecording(null)}>
          <div className="modal-content full-text-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>📄 {viewingRecording.title}</h3>
              <button className="close-btn" onClick={() => setViewingRecording(null)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="full-text-meta">
                <span>录音时长: {formatDuration(viewingRecording.duration)}</span>
                <span>•</span>
                <span>字数: {viewingRecording.word_count}</span>
                <span>•</span>
                <span>录制时间: {formatDate(viewingRecording.created_at)}</span>
              </div>
              <div className="full-text-content">
                {viewingRecording.transcript}
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setViewingRecording(null)}>
                关闭
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 查看摘要对话框 */}
      {viewingSummary && (
        <div className="modal-overlay" onClick={() => setViewingSummary(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>📝 摘要 - {viewingSummary.title}</h3>
              <button className="close-btn" onClick={() => setViewingSummary(null)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="full-text-content">
                {viewingSummary.notes || '正在生成摘要...'}
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setViewingSummary(null)}>
                关闭
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 播放音频对话框 */}
      {playingAudio && (
        <div className="modal-overlay" onClick={() => setPlayingAudio(null)}>
          <div className="modal-content audio-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>🎵 播放录音</h3>
              <button className="close-btn" onClick={() => setPlayingAudio(null)}>✕</button>
            </div>
            <div className="modal-body">
              <audio 
                controls 
                autoPlay 
                src={`${apiBaseUrl}/api/recordings/${playingAudio}/audio?token=${token}`}
                style={{ width: '100%' }}
              />
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setPlayingAudio(null)}>
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* 转写设置对话框 */}
      {showTranscribeDialog && (
        <div className="modal-overlay" onClick={() => setShowTranscribeDialog(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '500px' }}>
            <div className="modal-header">
              <h3>🎙️ 转写设置</h3>
              <button className="close-btn" onClick={() => setShowTranscribeDialog(false)}>✕</button>
            </div>
            <div className="modal-body" style={{ padding: '20px' }}>
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={enhanceEnabled}
                    onChange={(e) => setEnhanceEnabled(e.target.checked)}
                    style={{ marginRight: '10px', width: '18px', height: '18px' }}
                  />
                  <span style={{ fontSize: '15px', fontWeight: '500' }}>启用LLM文本增强</span>
                </label>
                <p style={{ 
                  marginTop: '8px', 
                  marginLeft: '28px', 
                  fontSize: '13px', 
                  color: '#94a3b8',
                  lineHeight: '1.5'
                }}>
                  使用AI智能添加标点符号和段落划分，提升可读性
                </p>
              </div>
              
              {enhanceEnabled && (
                <div style={{ 
                  marginTop: '20px', 
                  padding: '15px', 
                  background: 'rgba(148, 163, 184, 0.1)', 
                  borderRadius: '8px',
                  border: '1px solid rgba(148, 163, 184, 0.2)'
                }}>
                  <label style={{ display: 'block', marginBottom: '10px', fontSize: '14px', fontWeight: '500' }}>
                    增强模式：
                  </label>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    <label style={{ display: 'flex', alignItems: 'flex-start', cursor: 'pointer' }}>
                      <input
                        type="radio"
                        value="punctuation"
                        checked={enhancementType === 'punctuation'}
                        onChange={(e) => setEnhancementType(e.target.value)}
                        style={{ marginRight: '10px', marginTop: '3px' }}
                      />
                      <div>
                        <div style={{ fontSize: '14px', fontWeight: '500' }}>标点和段落</div>
                        <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '2px' }}>
                          添加标点符号和段落，保持口语风格
                        </div>
                      </div>
                    </label>
                    
                    <label style={{ display: 'flex', alignItems: 'flex-start', cursor: 'pointer' }}>
                      <input
                        type="radio"
                        value="formal"
                        checked={enhancementType === 'formal'}
                        onChange={(e) => setEnhancementType(e.target.value)}
                        style={{ marginRight: '10px', marginTop: '3px' }}
                      />
                      <div>
                        <div style={{ fontSize: '14px', fontWeight: '500' }}>正式书面语</div>
                        <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '2px' }}>
                          去除口语词，转换为正式文档
                        </div>
                      </div>
                    </label>
                    
                    <label style={{ display: 'flex', alignItems: 'flex-start', cursor: 'pointer' }}>
                      <input
                        type="radio"
                        value="meeting"
                        checked={enhancementType === 'meeting'}
                        onChange={(e) => setEnhancementType(e.target.value)}
                        style={{ marginRight: '10px', marginTop: '3px' }}
                      />
                      <div>
                        <div style={{ fontSize: '14px', fontWeight: '500' }}>会议纪要</div>
                        <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '2px' }}>
                          整理为结构化会议纪要格式
                        </div>
                      </div>
                    </label>
                  </div>
                </div>
              )}
              
              <div style={{ 
                marginTop: '20px', 
                padding: '12px', 
                background: 'rgba(34, 197, 94, 0.1)', 
                borderRadius: '6px',
                fontSize: '12px',
                color: '#94a3b8'
              }}>
                💡 提示：转写可能需要几分钟，请耐心等待
              </div>
            </div>
            <div className="modal-footer">
              <button 
                className="btn-secondary" 
                onClick={() => setShowTranscribeDialog(false)}
              >
                取消
              </button>
              <button 
                className="btn-primary" 
                onClick={handleTranscribe}
                disabled={transcribingId !== null}
              >
                开始转写
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 导入音频文件对话框 */}
      {showImportDialog && (
        <div className="modal-overlay" onClick={() => setShowImportDialog(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '500px' }}>
            <div className="modal-header">
              <h3>📁 导入音频文件</h3>
              <button className="close-btn" onClick={() => setShowImportDialog(false)}>✕</button>
            </div>
            <div className="modal-body" style={{ padding: '30px' }}>
              <div style={{
                border: '2px dashed rgba(148, 163, 184, 0.3)',
                borderRadius: '12px',
                padding: '40px',
                textAlign: 'center',
                background: 'rgba(148, 163, 184, 0.05)',
                cursor: 'pointer',
                transition: 'all 0.3s ease'
              }}
              onDragOver={(e) => {
                e.preventDefault();
                e.currentTarget.style.borderColor = '#3b82f6';
                e.currentTarget.style.background = 'rgba(59, 130, 246, 0.1)';
              }}
              onDragLeave={(e) => {
                e.currentTarget.style.borderColor = 'rgba(148, 163, 184, 0.3)';
                e.currentTarget.style.background = 'rgba(148, 163, 184, 0.05)';
              }}
              onDrop={(e) => {
                e.preventDefault();
                e.currentTarget.style.borderColor = 'rgba(148, 163, 184, 0.3)';
                e.currentTarget.style.background = 'rgba(148, 163, 184, 0.05)';
                
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                  const input = document.getElementById('audio-file-input') as HTMLInputElement;
                  if (input) {
                    // 创建新的DataTransfer对象来设置input的files
                    const dataTransfer = new DataTransfer();
                    dataTransfer.items.add(files[0]);
                    input.files = dataTransfer.files;
                    
                    // 触发change事件
                    const event = new Event('change', { bubbles: true });
                    input.dispatchEvent(event);
                  }
                }
              }}
              onClick={() => document.getElementById('audio-file-input')?.click()}>
                {uploadingFile ? (
                  <>
                    <div style={{ fontSize: '48px', marginBottom: '15px' }}>⏳</div>
                    <div style={{ fontSize: '16px', fontWeight: '500', marginBottom: '10px' }}>
                      上传中...
                    </div>
                  </>
                ) : (
                  <>
                    <div style={{ fontSize: '48px', marginBottom: '15px' }}>📁</div>
                    <div style={{ fontSize: '16px', fontWeight: '500', marginBottom: '10px' }}>
                      点击选择或拖拽音频文件
                    </div>
                    <div style={{ fontSize: '13px', color: '#94a3b8', marginBottom: '15px' }}>
                      支持格式: MP3, WAV, M4A, OGG, WebM, FLAC, AAC
                    </div>
                    <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                      文件大小限制: 100MB
                    </div>
                  </>
                )}
              </div>
              <input
                id="audio-file-input"
                type="file"
                accept=".mp3,.wav,.m4a,.ogg,.webm,.flac,.aac,audio/*"
                onChange={handleUploadAudio}
                style={{ display: 'none' }}
                disabled={uploadingFile}
              />
              
              <div style={{ 
                marginTop: '20px', 
                padding: '15px', 
                background: 'rgba(59, 130, 246, 0.1)', 
                borderRadius: '8px',
                fontSize: '13px',
                color: '#94a3b8',
                lineHeight: '1.6'
              }}>
                <div style={{ fontWeight: '500', marginBottom: '8px', color: '#3b82f6' }}>
                  📝 使用说明：
                </div>
                <div>1. 上传成功后，音频文件会保存到"我的录音"列表</div>
                <div>2. 点击"转写"按钮进行语音识别</div>
                <div>3. 转写完成后可以播放音频、查看全文或导入知识库</div>
              </div>
            </div>
            <div className="modal-footer">
              <button 
                className="btn-secondary" 
                onClick={() => setShowImportDialog(false)}
                disabled={uploadingFile}
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RecordingsList;

