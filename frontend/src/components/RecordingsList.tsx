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

  // 手动转写
  const handleTranscribe = async (recordingId: string) => {
    if (!confirm('确定要转写这条录音吗？转写可能需要一些时间。')) return;

    setTranscribingId(recordingId);
    try {
      // 创建一个带超时的 fetch 请求（5分钟超时）
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5 * 60 * 1000);

      const response = await authFetch(`${apiBaseUrl}/api/recordings/${recordingId}/transcribe`, {
        method: 'POST',
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        const data = await response.json();
        alert(`转写成功！字数：${data.word_count}`);
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
                    <button
                      className="action-btn play"
                      onClick={() => setPlayingAudio(recording.id)}
                    >
                      ▶️ 播放
                    </button>
                  )}
                  {(!recording.transcript || recording.word_count === 0) && recording.keep_audio && (
                    <button
                      className="action-btn transcribe"
                      onClick={() => handleTranscribe(recording.id)}
                      disabled={transcribingId === recording.id}
                    >
                      {transcribingId === recording.id ? '🔄 转写中...' : '📝 转写'}
                    </button>
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
                  {recording.import_status === 'pending' && recording.transcript && recording.word_count > 0 && (
                    <button
                      className="action-btn import"
                      onClick={() => openImportWizard(recording)}
                    >
                      📥 导入知识库
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
    </div>
  );
};

export default RecordingsList;

