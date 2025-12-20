/**
 * 导入向导组件
 * 用于将录音导入到知识库
 */
import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useAuthFetch } from '../hooks/usePermission';
import { Recording, ImportRecordingRequest } from '../types/recording';
import { KnowledgeBase } from '../types';
import '../styles/import-wizard.css';

interface ImportWizardProps {
  recording: Recording;
  onClose: () => void;
  onSuccess: () => void;
}

const ImportWizard: React.FC<ImportWizardProps> = ({ recording, onClose, onSuccess }) => {
  const { token } = useAuth();
  const authFetch = useAuthFetch();
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || window.location.origin;

  const [step, setStep] = useState<'selectKb' | 'metadata'>('selectKb');
  const [kbList, setKbList] = useState<KnowledgeBase[]>([]);
  const [selectedKbId, setSelectedKbId] = useState<string | null>(null);
  const [newKbName, setNewKbName] = useState('');
  const [isCreatingNew, setIsCreatingNew] = useState(false);
  const [loadingKbs, setLoadingKbs] = useState(false);

  const [formData, setFormData] = useState({
    title: recording.title,
    category: recording.category || 'history_case',
    tags: recording.tags || [],
    notes: recording.notes || '',
  });

  const [tagInput, setTagInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // 加载知识库列表
  useEffect(() => {
    const loadKnowledgeBases = async () => {
      setLoadingKbs(true);
      try {
        console.log('Loading knowledge bases from:', `${apiBaseUrl}/api/kb`);
        const response = await authFetch(`${apiBaseUrl}/api/kb`);
        console.log('KB API response status:', response.status);
        if (response.ok) {
          const data = await response.json();
          console.log('KB data received:', data);
          setKbList(data || []);
          // 如果有知识库，默认选中第一个
          if (data && data.length > 0) {
            setSelectedKbId(data[0].id);
            console.log('Selected KB:', data[0].id, data[0].name);
          } else {
            console.log('No knowledge bases found');
          }
        } else {
          console.error('Failed to load KB list, status:', response.status);
        }
      } catch (error) {
        console.error('Failed to load knowledge bases:', error);
      } finally {
        setLoadingKbs(false);
      }
    };

    loadKnowledgeBases();
  }, [authFetch, apiBaseUrl]);

  // 处理导入
  const handleImport = async () => {
    if (!isCreatingNew && !selectedKbId) {
      setError('请选择一个知识库');
      return;
    }

    if (isCreatingNew && !newKbName.trim()) {
      setError('请输入新知识库名称');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const importRequest: ImportRecordingRequest = {
        kb_id: isCreatingNew ? undefined : selectedKbId || undefined,
        new_kb_name: isCreatingNew ? newKbName : undefined,
        title: formData.title,
        category: formData.category,
        tags: formData.tags.length > 0 ? formData.tags : undefined,
        notes: formData.notes || undefined,
      };

      const response = await authFetch(
        `${apiBaseUrl}/api/recordings/${recording.id}/import`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(importRequest),
        }
      );

      if (response.ok) {
        onSuccess();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || '导入失败');
      }
    } catch (error: any) {
      console.error('Import error:', error);
      setError(error.message || '导入失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  // 添加标签
  const addTag = () => {
    if (tagInput.trim() && !formData.tags.includes(tagInput.trim())) {
      setFormData({
        ...formData,
        tags: [...formData.tags, tagInput.trim()],
      });
      setTagInput('');
    }
  };

  // 删除标签
  const removeTag = (tag: string) => {
    setFormData({
      ...formData,
      tags: formData.tags.filter((t) => t !== tag),
    });
  };

  return (
    <div className="import-wizard-overlay" onClick={onClose}>
      <div className="import-wizard-modal" onClick={(e) => e.stopPropagation()}>
        <div className="wizard-header">
          <h3>📥 导入录音到知识库</h3>
          <button className="close-btn" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="wizard-body">
          {/* 步骤 1: 选择知识库 */}
          {step === 'selectKb' && (
            <div className="wizard-step">
              <h4>选择目标知识库</h4>

              {loadingKbs ? (
                <div style={{ textAlign: 'center', padding: '20px' }}>加载知识库列表...</div>
              ) : (
                <>
                  <div className="kb-list">
                    {kbList.length > 0 && (
                      <>
                        {kbList.map((kb) => (
                          <label key={kb.id} className="kb-option">
                            <input
                              type="radio"
                              name="kb"
                              value={kb.id}
                              checked={selectedKbId === kb.id && !isCreatingNew}
                              onChange={() => {
                                setSelectedKbId(kb.id);
                                setIsCreatingNew(false);
                                setError('');
                              }}
                            />
                            <div className="kb-info">
                              <div className="kb-name">{kb.name}</div>
                              {kb.description && <div className="kb-desc">{kb.description}</div>}
                            </div>
                          </label>
                        ))}
                      </>
                    )}

                    <label className="kb-option new-kb">
                      <input
                        type="radio"
                        name="kb"
                        value="new"
                        checked={isCreatingNew}
                        onChange={() => {
                          setIsCreatingNew(true);
                          setSelectedKbId(null);
                          setError('');
                        }}
                      />
                      <div className="kb-info">
                        <div className="kb-name">+ 新建知识库</div>
                      </div>
                    </label>

                    {isCreatingNew && (
                      <div className="new-kb-form">
                        <input
                          type="text"
                          placeholder="知识库名称"
                          value={newKbName}
                          onChange={(e) => setNewKbName(e.target.value)}
                        />
                      </div>
                    )}
                  </div>

                  <div className="wizard-actions">
                    <button className="btn-secondary" onClick={onClose}>
                      取消
                    </button>
                    <button className="btn-primary" onClick={() => setStep('metadata')}>
                      下一步
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {/* 步骤 2: 元数据 */}
          {step === 'metadata' && (
            <div className="wizard-step">
              <h4>完善信息</h4>

              <div className="form-group">
                <label>标题</label>
                <input
                  type="text"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label>分类</label>
                <select
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                >
                  <option value="general_doc">📄 普通文档</option>
                  <option value="history_case">📋 历史案例</option>
                  <option value="reference_rule">📘 规章制度</option>
                </select>
              </div>

              <div className="form-group">
                <label>标签</label>
                <div className="tags-input">
                  {formData.tags.map((tag) => (
                    <span key={tag} className="tag">
                      {tag}
                      <button onClick={() => removeTag(tag)}>×</button>
                    </span>
                  ))}
                  <input
                    type="text"
                    placeholder="添加标签"
                    value={tagInput}
                    onChange={(e) => setTagInput(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        addTag();
                      }
                    }}
                  />
                  <button type="button" onClick={addTag} className="add-tag-btn">
                    +
                  </button>
                </div>
              </div>

              <div className="form-group">
                <label>备注</label>
                <textarea
                  value={formData.notes}
                  onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                  placeholder="可选的备注信息"
                  rows={3}
                />
              </div>

              {error && <div className="error-message">⚠️ {error}</div>}

              <div className="wizard-actions">
                <button className="btn-secondary" onClick={() => setStep('selectKb')}>
                  上一步
                </button>
                <button
                  className="btn-primary"
                  onClick={handleImport}
                  disabled={loading}
                >
                  {loading ? '导入中...' : '确定导入'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ImportWizard;

