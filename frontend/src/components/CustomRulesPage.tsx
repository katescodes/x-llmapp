/**
 * 自定义规则管理页面
 * 
 * 功能：
 * 1. 创建自定义规则（用户输入规则要求，AI自动分析）
 * 2. 查看规则包列表
 * 3. 查看规则详情
 * 4. 删除规则包
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../config/api';

const API_BASE = API_BASE_URL;

// 获取 token 的辅助函数
const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

// 错误信息提取函数（处理各种错误格式）
const extractErrorMessage = (err: any): string => {
  if (err.response?.data) {
    const detail = err.response.data.detail;
    if (typeof detail === 'string') {
      return detail;
    } else if (detail && typeof detail === 'object') {
      // 处理结构化错误（如Pydantic验证错误）
      if (Array.isArray(detail)) {
        return detail.map((e: any) => e.msg || JSON.stringify(e)).join('; ');
      } else {
        return JSON.stringify(detail, null, 2);
      }
    } else if (err.response.data.message) {
      return err.response.data.message;
    }
  }
  if (err.message) {
    return err.message;
  }
  return '未知错误';
};

interface CustomRulePack {
  id: string;
  pack_name: string;
  pack_type: 'builtin' | 'custom';
  project_id?: string;
  priority: number;
  is_active: boolean;
  rule_count?: number;
  created_at?: string;
  updated_at?: string;
}

interface CustomRule {
  id: string;
  rule_pack_id: string;
  rule_key: string;
  rule_name: string;
  dimension: string;
  evaluator: 'deterministic' | 'semantic_llm';
  condition_json: any;
  severity: 'low' | 'medium' | 'high';
  is_hard: boolean;
  created_at?: string;
}

interface Props {
  projectId?: string;  // 改为可选，不选项目时查询所有规则包
  onBack?: () => void;
  embedded?: boolean;
}

export default function CustomRulesPage({ projectId, onBack, embedded = false }: Props) {
  const [rulePacks, setRulePacks] = useState<CustomRulePack[]>([]);
  const [selectedPack, setSelectedPack] = useState<CustomRulePack | null>(null);
  const [rules, setRules] = useState<CustomRule[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);

  // 创建表单状态
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [packName, setPackName] = useState('');
  const [ruleRequirements, setRuleRequirements] = useState('');

  // 加载规则包列表（加载所有共享规则包，不限制项目）
  const loadRulePacks = async () => {
    setLoading(true);
    try {
      // 不传project_id，加载所有共享规则包
      const res = await axios.get(`${API_BASE}/api/custom-rules/rule-packs`, {
        headers: getAuthHeaders(),
      });
      setRulePacks(res.data || []);
    } catch (err: any) {
      console.error('加载规则包失败:', err);
      const errorMsg = extractErrorMessage(err);
      alert(`加载规则包失败：\n${errorMsg}`);
    } finally {
      setLoading(false);
    }
  };

  // 加载规则详情
  const loadRules = async (packId: string) => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/api/custom-rules/rule-packs/${packId}/rules`, {
        headers: getAuthHeaders(),
      });
      setRules(res.data || []);
    } catch (err: any) {
      console.error('加载规则失败:', err);
      const errorMsg = extractErrorMessage(err);
      alert(`加载规则失败：\n${errorMsg}`);
    } finally {
      setLoading(false);
    }
  };

  // 创建规则包
  const handleCreate = async () => {
    if (!packName.trim()) {
      alert('请输入规则包名称');
      return;
    }
    if (!ruleRequirements.trim()) {
      alert('请输入规则要求');
      return;
    }

    setCreating(true);
    try {
      const res = await axios.post(
        `${API_BASE}/api/custom-rules/rule-packs`,
        {
          project_id: null,  // 规则包是共享的，不属于特定项目
          pack_name: packName,
          rule_requirements: ruleRequirements,
        },
        { headers: getAuthHeaders() }
      );

      alert('规则包创建成功！');
      setPackName('');
      setRuleRequirements('');
      setShowCreateForm(false);

      // 重新加载列表
      await loadRulePacks();

      // 自动选中新创建的规则包
      const newPack = res.data;
      setSelectedPack(newPack);
      await loadRules(newPack.id);
    } catch (err: any) {
      console.error('创建规则包失败:', err);
      const errorMsg = extractErrorMessage(err);
      alert(`创建规则包失败：\n${errorMsg}`);
    } finally {
      setCreating(false);
    }
  };

  // 删除规则包
  const handleDelete = async (packId: string, packName: string) => {
    if (!confirm(`确定要删除规则包"${packName}"吗？此操作不可恢复。`)) {
      return;
    }

    try {
      await axios.delete(`${API_BASE}/api/custom-rules/rule-packs/${packId}`, {
        headers: getAuthHeaders(),
      });

      alert('规则包已删除');
      
      // 如果删除的是当前选中的规则包，清空选中状态
      if (selectedPack?.id === packId) {
        setSelectedPack(null);
        setRules([]);
      }

      // 重新加载列表
      await loadRulePacks();
    } catch (err: any) {
      console.error('删除规则包失败:', err);
      const errorMsg = extractErrorMessage(err);
      alert(`删除规则包失败：\n${errorMsg}`);
    }
  };

  // 选择规则包
  const handleSelectPack = async (pack: CustomRulePack) => {
    setSelectedPack(pack);
    await loadRules(pack.id);
  };

  // 初始加载
  useEffect(() => {
    loadRulePacks();
  }, [projectId]);

  // 维度映射
  const dimensionMap: Record<string, string> = {
    qualification: '资格审查',
    technical: '技术规格',
    business: '商务条款',
    price: '价格/报价',
    doc_structure: '文档结构',
    schedule_quality: '进度/质量',
    other: '其他',
  };

  // 严重程度映射
  const severityMap: Record<string, { label: string; color: string }> = {
    low: { label: '低', color: '#52c41a' },
    medium: { label: '中', color: '#faad14' },
    high: { label: '高', color: '#ff4d4f' },
  };

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
            📋 自定义规则管理
          </h2>
        </div>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          className="kb-create-form"
          style={{ width: 'auto', marginBottom: 0 }}
        >
          {showCreateForm ? '取消' : '+ 创建规则包'}
        </button>
      </div>

      {/* 创建表单 */}
      {showCreateForm && (
        <div className="source-card" style={{ marginBottom: '20px', padding: '20px' }}>
          <h3 style={{ marginTop: 0, marginBottom: '16px', color: '#ffffff' }}>创建自定义规则包</h3>
          
          <div className="kb-create-form">
            <label className="sidebar-label">规则包名称：</label>
            <input
              type="text"
              value={packName}
              onChange={(e) => setPackName(e.target.value)}
              placeholder="例如：特殊资格要求"
              className="sidebar-select"
              style={{ marginBottom: '12px' }}
            />

            <label className="sidebar-label">规则要求（AI 将自动分析）：</label>
            <textarea
              value={ruleRequirements}
              onChange={(e) => setRuleRequirements(e.target.value)}
              placeholder="请输入规则要求，例如：&#10;1. 投标人必须具有有效的营业执照，且注册资本不低于500万元&#10;2. 投标人必须提供近三年的财务审计报告&#10;3. 投标报价不得高于预算的110%&#10;&#10;系统将自动分析并生成结构化规则"
              className="sidebar-select"
              rows={8}
              style={{ 
                marginBottom: '12px',
                fontFamily: 'monospace',
                whiteSpace: 'pre-wrap',
              }}
            />

            <div className="kb-doc-meta" style={{ marginBottom: '12px' }}>
              💡 提示：请尽量清晰地描述每条规则的要求，系统会使用 AI 自动分析并生成结构化规则。
            </div>

            <button
              onClick={handleCreate}
              className="kb-create-form"
              style={{ width: 'auto', marginBottom: 0 }}
              disabled={creating}
            >
              {creating ? '创建中...' : '创建规则包'}
            </button>
          </div>
        </div>
      )}

      {/* 主内容区域 */}
      <div style={{ display: 'flex', gap: '20px', flex: 1, overflow: 'hidden' }}>
        {/* 左侧：规则包列表 */}
        <div style={{ width: '300px', display: 'flex', flexDirection: 'column' }}>
          <h3 style={{ marginTop: 0, marginBottom: '12px', color: '#ffffff' }}>
            规则包列表 ({rulePacks.length})
          </h3>
          
          <div style={{ flex: 1, overflow: 'auto' }}>
            {loading && rulePacks.length === 0 ? (
              <div className="kb-doc-meta">加载中...</div>
            ) : rulePacks.length === 0 ? (
              <div className="kb-doc-meta">暂无规则包，点击右上角创建</div>
            ) : (
              rulePacks.map((pack) => (
                <div
                  key={pack.id}
                  className="source-card"
                  style={{
                    marginBottom: '8px',
                    padding: '12px',
                    cursor: 'pointer',
                    border: selectedPack?.id === pack.id ? '2px solid #1890ff' : '1px solid #4a5568',
                    background: selectedPack?.id === pack.id ? 'rgba(24, 144, 255, 0.1)' : '#2d3748',
                  }}
                  onClick={() => handleSelectPack(pack)}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, marginBottom: '4px', color: '#ffffff' }}>
                        {pack.pack_name}
                      </div>
                      <div style={{ fontSize: '12px', color: '#a0aec0' }}>
                        {pack.rule_count || 0} 条规则
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(pack.id, pack.pack_name);
                      }}
                      className="sidebar-btn"
                      style={{
                        width: 'auto',
                        padding: '4px 8px',
                        fontSize: '12px',
                        marginBottom: 0,
                        background: '#e53e3e',
                      }}
                    >
                      删除
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* 右侧：规则详情 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          {selectedPack ? (
            <>
              <h3 style={{ marginTop: 0, marginBottom: '12px', color: '#ffffff' }}>
                规则详情 - {selectedPack.pack_name}
              </h3>

              <div style={{ flex: 1, overflow: 'auto' }}>
                {loading ? (
                  <div className="kb-doc-meta">加载中...</div>
                ) : rules.length === 0 ? (
                  <div className="kb-doc-meta">该规则包暂无规则</div>
                ) : (
                  <div>
                    {rules.map((rule, index) => (
                      <div
                        key={rule.id}
                        className="source-card"
                        style={{ marginBottom: '12px', padding: '16px' }}
                      >
                        {/* 规则头部 */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px' }}>
                          <div style={{ flex: 1 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                              <span style={{ fontSize: '16px', fontWeight: 600, color: '#ffffff' }}>
                                {index + 1}. {rule.rule_name}
                              </span>
                              {rule.is_hard && (
                                <span
                                  style={{
                                    padding: '2px 8px',
                                    background: '#e53e3e',
                                    borderRadius: '4px',
                                    fontSize: '12px',
                                    fontWeight: 600,
                                  }}
                                >
                                  废标项
                                </span>
                              )}
                            </div>
                            <div style={{ fontSize: '12px', color: '#a0aec0' }}>
                              规则ID: {rule.rule_key}
                            </div>
                          </div>
                        </div>

                        {/* 规则信息 */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                          <div>
                            <div style={{ fontSize: '12px', color: '#a0aec0', marginBottom: '4px' }}>维度</div>
                            <div style={{ fontSize: '14px', color: '#ffffff' }}>
                              {dimensionMap[rule.dimension] || rule.dimension}
                            </div>
                          </div>
                          <div>
                            <div style={{ fontSize: '12px', color: '#a0aec0', marginBottom: '4px' }}>严重程度</div>
                            <div>
                              <span
                                style={{
                                  padding: '2px 8px',
                                  background: severityMap[rule.severity]?.color || '#718096',
                                  borderRadius: '4px',
                                  fontSize: '12px',
                                  fontWeight: 600,
                                }}
                              >
                                {severityMap[rule.severity]?.label || rule.severity}
                              </span>
                            </div>
                          </div>
                          <div>
                            <div style={{ fontSize: '12px', color: '#a0aec0', marginBottom: '4px' }}>执行器</div>
                            <div style={{ fontSize: '14px', color: '#ffffff' }}>
                              {rule.evaluator === 'deterministic' ? '确定性' : 'LLM语义'}
                            </div>
                          </div>
                          <div>
                            <div style={{ fontSize: '12px', color: '#a0aec0', marginBottom: '4px' }}>类型</div>
                            <div style={{ fontSize: '14px', color: '#ffffff' }}>
                              {rule.is_hard ? '硬性要求' : '扣分项'}
                            </div>
                          </div>
                        </div>

                        {/* 条件详情 */}
                        <div>
                          <div style={{ fontSize: '12px', color: '#a0aec0', marginBottom: '4px' }}>条件配置</div>
                          <div
                            style={{
                              background: '#1a202c',
                              padding: '12px',
                              borderRadius: '4px',
                              fontSize: '12px',
                              fontFamily: 'monospace',
                              color: '#e2e8f0',
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-all',
                            }}
                          >
                            {JSON.stringify(rule.condition_json, null, 2)}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="kb-doc-meta">
              请从左侧选择一个规则包查看详情
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

