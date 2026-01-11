import React, { useEffect, useState } from 'react';
import { api } from '../config/api';
import './OrganizationPage.css';

interface OrganizationInfo {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

interface MemberInfo {
  id: string;
  username: string;
  display_name: string | null;
  email: string | null;
  role: string;
}

interface AvailableUser {
  id: string;
  username: string;
  display_name: string | null;
  email: string | null;
  role: string;
}

interface SharedResourcesStats {
  format_templates: number;
  rule_packs: number;
  knowledge_bases: number;
  user_documents: number;
}

interface OrganizationStats {
  total_members: number;
  members_by_role: Record<string, number>;
  shared_resources: SharedResourcesStats;
}

interface OrganizationData {
  info: OrganizationInfo;
  stats: OrganizationStats;
}

const OrganizationPage: React.FC = () => {
  const [organizations, setOrganizations] = useState<OrganizationInfo[]>([]);
  const [selectedOrg, setSelectedOrg] = useState<OrganizationInfo | null>(null);
  const [orgData, setOrgData] = useState<OrganizationData | null>(null);
  const [members, setMembers] = useState<MemberInfo[]>([]);
  const [availableUsers, setAvailableUsers] = useState<AvailableUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [editMode, setEditMode] = useState(false);
  const [editedName, setEditedName] = useState('');
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showAddUserDialog, setShowAddUserDialog] = useState(false);
  const [newOrgName, setNewOrgName] = useState('');

  useEffect(() => {
    loadOrganizations();
  }, []);

  const loadOrganizations = async () => {
    try {
      setLoading(true);
      const data = await api.get('/api/organizations/');
      setOrganizations(data);
      
      // 默认选择第一个企业
      if (data.length > 0 && !selectedOrg) {
        setSelectedOrg(data[0]);
        loadOrganizationData(data[0].id);
      }
    } catch (error) {
      console.error('加载企业列表失败:', error);
      alert('加载企业列表失败');
    } finally {
      setLoading(false);
    }
  };

  const loadOrganizationData = async (orgId: string) => {
    try {
      const response = await api.get(`/api/organizations/${orgId}/detail`);
      setOrgData(response);
      setEditedName(response.info.name);
      await loadMembers(orgId);
    } catch (error) {
      console.error('加载企业信息失败:', error);
    }
  };

  const loadMembers = async (orgId: string) => {
    try {
      const response = await api.get(`/api/organizations/${orgId}/members`);
      setMembers(response);
    } catch (error) {
      console.error('加载成员列表失败:', error);
    }
  };

  const handleSelectOrg = (org: OrganizationInfo) => {
    setSelectedOrg(org);
    setEditMode(false);
    // 先清空数据，避免显示上一个企业的数据
    setOrgData(null);
    setMembers([]);
    // 然后加载新数据
    loadOrganizationData(org.id);
  };

  const handleCreateOrg = async () => {
    if (!newOrgName.trim()) {
      alert('请输入企业名称');
      return;
    }

    try {
      await api.post('/api/organizations/', { name: newOrgName });
      setShowCreateDialog(false);
      setNewOrgName('');
      await loadOrganizations();
      alert('企业创建成功');
    } catch (error: any) {
      console.error('创建企业失败:', error);
      alert(`创建失败: ${error.message}`);
    }
  };

  const handleSaveOrgName = async () => {
    if (!selectedOrg) return;
    
    try {
      await api.put(`/api/organizations/${selectedOrg.id}`, { name: editedName });
      await loadOrganizations();
      setEditMode(false);
      alert('企业名称更新成功');
    } catch (error: any) {
      console.error('更新企业名称失败:', error);
      alert(`更新失败: ${error.message}`);
    }
  };

  const handleDeleteOrg = async (org: OrganizationInfo) => {
    if (!confirm(`确定要删除企业"${org.name}"吗？删除后该企业下的所有用户将解除关联。`)) {
      return;
    }

    try {
      await api.delete(`/api/organizations/${org.id}`);
      await loadOrganizations();
      
      if (selectedOrg?.id === org.id) {
        setSelectedOrg(null);
        setOrgData(null);
        setMembers([]);
      }
      
      alert('企业删除成功');
    } catch (error: any) {
      console.error('删除企业失败:', error);
      alert(`删除失败: ${error.message}`);
    }
  };

  const loadAvailableUsers = async (orgId: string) => {
    try {
      const data = await api.get(`/api/organizations/${orgId}/available-users`);
      setAvailableUsers(data);
    } catch (error) {
      console.error('加载可用用户列表失败:', error);
    }
  };

  const handleShowAddUser = async () => {
    if (!selectedOrg) return;
    await loadAvailableUsers(selectedOrg.id);
    setShowAddUserDialog(true);
  };

  const handleAddUser = async (userId: string) => {
    if (!selectedOrg) return;

    try {
      await api.post(`/api/organizations/${selectedOrg.id}/members/${userId}`, {});
      await loadMembers(selectedOrg.id);
      await loadAvailableUsers(selectedOrg.id);
      alert('用户添加成功');
    } catch (error: any) {
      console.error('添加用户失败:', error);
      alert(`添加失败: ${error.message}`);
    }
  };

  const handleRemoveUser = async (userId: string) => {
    if (!selectedOrg) return;
    if (!confirm('确定要将该用户从企业中移除吗？')) return;

    try {
      await api.delete(`/api/organizations/${selectedOrg.id}/members/${userId}`);
      await loadMembers(selectedOrg.id);
      alert('用户移除成功');
    } catch (error: any) {
      console.error('移除用户失败:', error);
      alert(`移除失败: ${error.message}`);
    }
  };

  const getRoleName = (role: string): string => {
    const roleNames: Record<string, string> = {
      admin: '管理员',
      employee: '员工',
      customer: '客户'
    };
    return roleNames[role] || role;
  };

  if (loading) {
    return <div className="org-page-loading">加载中...</div>;
  }

  return (
    <div className="org-page-container">
      <div style={{ display: 'flex', gap: '20px', height: '100%' }}>
        {/* 左侧企业列表 */}
        <div style={{
          width: '300px',
          background: 'rgba(30, 41, 59, 0.5)',
          borderRadius: '12px',
          padding: '20px',
          overflowY: 'auto'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ margin: 0, color: '#f8fafc' }}>企业列表</h3>
            <button
              onClick={() => setShowCreateDialog(true)}
              style={{
                padding: '6px 12px',
                background: 'linear-gradient(135deg, #4f46e5, #22c55e)',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '13px'
              }}
            >
              ➕ 新建
            </button>
          </div>

          {organizations.length === 0 ? (
            <div style={{ textAlign: 'center', color: '#94a3b8', padding: '20px' }}>
              暂无企业
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {organizations.map((org) => (
                <div
                  key={org.id}
                  style={{
                    padding: '12px',
                    background: selectedOrg?.id === org.id ? 'rgba(79, 70, 229, 0.2)' : 'rgba(15, 23, 42, 0.5)',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    border: selectedOrg?.id === org.id ? '1px solid rgba(129, 140, 248, 0.3)' : '1px solid transparent',
                    transition: 'all 0.2s',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                  }}
                  onClick={() => handleSelectOrg(org)}
                >
                  <div>
                    <div style={{ color: '#e2e8f0', fontWeight: 500 }}>{org.name}</div>
                    <div style={{ color: '#94a3b8', fontSize: '12px', marginTop: '4px' }}>
                      {new Date(org.created_at).toLocaleDateString('zh-CN')}
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteOrg(org);
                    }}
                    style={{
                      padding: '4px 8px',
                      background: 'rgba(239, 68, 68, 0.2)',
                      color: '#ef4444',
                      border: '1px solid rgba(239, 68, 68, 0.3)',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '12px'
                    }}
                  >
                    删除
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 右侧企业详情 */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {!selectedOrg ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
              请选择一个企业查看详情
            </div>
          ) : !orgData ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
              加载中...
            </div>
          ) : (
            <>
              <h1>企业详情</h1>

              {/* 企业基本信息 */}
              <section className="org-info-section">
                <h2>企业信息</h2>
                <div className="org-info-card">
                  <div className="org-info-row">
                    <label>企业ID:</label>
                    <span>{orgData.info.id}</span>
                  </div>
                  <div className="org-info-row">
                    <label>企业名称:</label>
                    {editMode ? (
                      <div className="edit-name-group">
                        <input
                          type="text"
                          value={editedName}
                          onChange={(e) => setEditedName(e.target.value)}
                          className="edit-name-input"
                        />
                        <button onClick={handleSaveOrgName} className="btn-save">保存</button>
                        <button onClick={() => {
                          setEditMode(false);
                          setEditedName(orgData.info.name);
                        }} className="btn-cancel">取消</button>
                      </div>
                    ) : (
                      <div className="name-display-group">
                        <span>{orgData.info.name}</span>
                        <button onClick={() => setEditMode(true)} className="btn-edit">编辑</button>
                      </div>
                    )}
                  </div>
                  <div className="org-info-row">
                    <label>创建时间:</label>
                    <span>{new Date(orgData.info.created_at).toLocaleString('zh-CN')}</span>
                  </div>
                </div>
              </section>

              {/* 成员统计 */}
              <section className="org-stats-section">
                <h2>成员统计</h2>
                <div className="stats-grid">
                  <div className="stat-card">
                    <div className="stat-value">{orgData.stats.total_members}</div>
                    <div className="stat-label">总成员数</div>
                  </div>
                  {Object.entries(orgData.stats.members_by_role).map(([role, count]) => (
                    <div key={role} className="stat-card">
                      <div className="stat-value">{count}</div>
                      <div className="stat-label">{getRoleName(role)}</div>
                    </div>
                  ))}
                </div>
              </section>

              {/* 共享资源统计 */}
              <section className="org-stats-section">
                <h2>共享资源统计</h2>
                <div className="stats-grid">
                  <div className="stat-card">
                    <div className="stat-value">{orgData.stats.shared_resources.format_templates}</div>
                    <div className="stat-label">格式模板</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-value">{orgData.stats.shared_resources.rule_packs}</div>
                    <div className="stat-label">规则包</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-value">{orgData.stats.shared_resources.knowledge_bases}</div>
                    <div className="stat-label">知识库</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-value">{orgData.stats.shared_resources.user_documents}</div>
                    <div className="stat-label">用户文档</div>
                  </div>
                </div>
              </section>

              {/* 成员列表 */}
              <section className="org-members-section">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <h2 style={{ margin: 0 }}>成员列表 ({members.length})</h2>
                  <button
                    onClick={handleShowAddUser}
                    style={{
                      padding: '8px 16px',
                      background: 'linear-gradient(135deg, #4f46e5, #22c55e)',
                      color: '#fff',
                      border: 'none',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      fontSize: '14px'
                    }}
                  >
                    ➕ 添加用户
                  </button>
                </div>
                <div className="members-table-container">
                  <table className="members-table">
                    <thead>
                      <tr>
                        <th>用户名</th>
                        <th>显示名称</th>
                        <th>邮箱</th>
                        <th>角色</th>
                        <th>操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {members.map((member) => (
                        <tr key={member.id}>
                          <td>{member.username}</td>
                          <td>{member.display_name || '-'}</td>
                          <td>{member.email || '-'}</td>
                          <td>
                            <span className={`role-badge role-${member.role}`}>
                              {getRoleName(member.role)}
                            </span>
                          </td>
                          <td>
                            <button
                              onClick={() => handleRemoveUser(member.id)}
                              style={{
                                padding: '4px 12px',
                                background: 'rgba(239, 68, 68, 0.2)',
                                color: '#ef4444',
                                border: '1px solid rgba(239, 68, 68, 0.3)',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontSize: '12px'
                              }}
                            >
                              移除
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          )}
        </div>
      </div>

      {/* 创建企业对话框 */}
      {showCreateDialog && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.7)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
        }}>
          <div style={{
            background: '#1e293b',
            borderRadius: '16px',
            padding: '32px',
            width: '90%',
            maxWidth: '500px',
          }}>
            <h2 style={{
              margin: '0 0 24px 0',
              fontSize: '20px',
              color: '#f8fafc',
            }}>
              创建新企业
            </h2>

            <div style={{ marginBottom: '24px' }}>
              <label style={{
                display: 'block',
                fontSize: '14px',
                color: '#cbd5e1',
                marginBottom: '8px',
              }}>
                企业名称：
              </label>
              <input
                type="text"
                value={newOrgName}
                onChange={(e) => setNewOrgName(e.target.value)}
                placeholder="请输入企业名称"
                style={{
                  width: '100%',
                  padding: '10px',
                  background: 'rgba(30, 41, 59, 0.5)',
                  border: '1px solid rgba(148, 163, 184, 0.3)',
                  borderRadius: '8px',
                  color: '#e2e8f0',
                  fontSize: '14px',
                }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button
                onClick={() => {
                  setShowCreateDialog(false);
                  setNewOrgName('');
                }}
                style={{
                  padding: '10px 24px',
                  border: '1px solid rgba(148, 163, 184, 0.3)',
                  background: 'rgba(30, 41, 59, 0.5)',
                  color: '#e2e8f0',
                  borderRadius: '8px',
                  cursor: 'pointer',
                }}
              >
                取消
              </button>
              <button
                onClick={handleCreateOrg}
                style={{
                  padding: '10px 24px',
                  border: 'none',
                  background: 'linear-gradient(135deg, #4f46e5, #22c55e)',
                  color: '#fff',
                  borderRadius: '8px',
                  cursor: 'pointer',
                }}
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 添加用户对话框 */}
      {showAddUserDialog && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.7)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
        }}>
          <div style={{
            background: '#1e293b',
            borderRadius: '16px',
            padding: '32px',
            width: '90%',
            maxWidth: '600px',
            maxHeight: '80vh',
            overflowY: 'auto',
          }}>
            <h2 style={{
              margin: '0 0 24px 0',
              fontSize: '20px',
              color: '#f8fafc',
            }}>
              添加用户到企业
            </h2>

            <div style={{ marginBottom: '24px' }}>
              {availableUsers.length === 0 ? (
                <div style={{ textAlign: 'center', color: '#94a3b8', padding: '20px' }}>
                  暂无可添加的用户
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {availableUsers.map((user) => (
                    <div
                      key={user.id}
                      style={{
                        padding: '12px',
                        background: 'rgba(30, 41, 59, 0.5)',
                        borderRadius: '8px',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                      }}
                    >
                      <div>
                        <div style={{ color: '#e2e8f0', fontWeight: 500 }}>
                          {user.username}
                          {user.display_name && ` (${user.display_name})`}
                        </div>
                        <div style={{ color: '#94a3b8', fontSize: '12px', marginTop: '4px' }}>
                          {user.email || '无邮箱'} | {getRoleName(user.role)}
                        </div>
                      </div>
                      <button
                        onClick={() => handleAddUser(user.id)}
                        style={{
                          padding: '6px 16px',
                          background: 'linear-gradient(135deg, #4f46e5, #22c55e)',
                          color: '#fff',
                          border: 'none',
                          borderRadius: '6px',
                          cursor: 'pointer',
                          fontSize: '13px',
                        }}
                      >
                        添加
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowAddUserDialog(false)}
                style={{
                  padding: '10px 24px',
                  border: '1px solid rgba(148, 163, 184, 0.3)',
                  background: 'rgba(30, 41, 59, 0.5)',
                  color: '#e2e8f0',
                  borderRadius: '8px',
                  cursor: 'pointer',
                }}
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

export default OrganizationPage;
