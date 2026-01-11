/**
 * 用户管理组件
 */
import React, { useState, useEffect } from 'react';
import { api } from '../../config/api';
import { userRoleApi, roleApi } from '../../api/permission';
import { User } from '../../types/auth';
import { Role, UserRole } from '../../types/permission';

interface Organization {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

const UserManagement: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [userRoles, setUserRoles] = useState<UserRole[]>([]);
  const [showRoleDialog, setShowRoleDialog] = useState(false);
  const [showOrgDialog, setShowOrgDialog] = useState(false);
  const [selectedOrgId, setSelectedOrgId] = useState<string>('');

  // 加载用户列表
  const loadUsers = async () => {
    try {
      setLoading(true);
      const data = await api.get('/api/auth/users');
      setUsers(data);
    } catch (err: any) {
      setError(err.message || '加载用户列表失败');
    } finally {
      setLoading(false);
    }
  };

  // 加载角色列表
  const loadRoles = async () => {
    try {
      const data = await roleApi.listRoles();
      setRoles(data);
    } catch (err: any) {
      console.error('加载角色列表失败:', err);
    }
  };

  // 加载企业列表
  const loadOrganizations = async () => {
    try {
      const data = await api.get('/api/organizations/');
      setOrganizations(data);
    } catch (err: any) {
      console.error('加载企业列表失败:', err);
    }
  };

  useEffect(() => {
    loadUsers();
    loadRoles();
    loadOrganizations();
  }, []);

  // 查看用户角色
  const viewUserRoles = async (user: User) => {
    try {
      setSelectedUser(user);
      const data = await userRoleApi.getUserRoles(user.id);
      setUserRoles(data);
      setShowRoleDialog(true);
    } catch (err: any) {
      setError(err.message || '加载用户角色失败');
    }
  };

  // 分配角色
  const assignRole = async (roleId: string) => {
    if (!selectedUser) return;

    try {
      await userRoleApi.assignRoles({
        user_id: selectedUser.id,
        role_ids: [roleId],
      });
      
      // 重新加载用户角色
      const data = await userRoleApi.getUserRoles(selectedUser.id);
      setUserRoles(data);
    } catch (err: any) {
      setError(err.message || '分配角色失败');
    }
  };

  // 移除角色
  const removeRole = async (roleId: string) => {
    if (!selectedUser) return;

    try {
      await userRoleApi.removeRoles({
        user_id: selectedUser.id,
        role_ids: [roleId],
      });
      
      // 重新加载用户角色
      const data = await userRoleApi.getUserRoles(selectedUser.id);
      setUserRoles(data);
    } catch (err: any) {
      setError(err.message || '移除角色失败');
    }
  };

  // 启用/禁用用户
  const toggleUserStatus = async (userId: string, isActive: boolean) => {
    try {
      await api.patch(`/api/auth/users/${userId}`, { is_active: !isActive });
      await loadUsers();
    } catch (err: any) {
      setError(err.message || '更新用户状态失败');
    }
  };

  // 显示企业编辑对话框
  const showEditOrganization = (user: User) => {
    setSelectedUser(user);
    setSelectedOrgId(user.organization_id || '');
    setShowOrgDialog(true);
  };

  // 更新用户企业
  const updateUserOrganization = async () => {
    if (!selectedUser) return;

    try {
      await api.patch(`/api/auth/users/${selectedUser.id}`, {
        organization_id: selectedOrgId || null
      });
      setShowOrgDialog(false);
      setSelectedUser(null);
      setSelectedOrgId('');
      await loadUsers();
    } catch (err: any) {
      setError(err.message || '更新用户企业失败');
    }
  };

  const getRoleBadgeColor = (roleCode: string) => {
    switch (roleCode) {
      case 'admin':
        return '#ef4444';
      case 'manager':
        return '#f59e0b';
      case 'employee':
        return '#3b82f6';
      default:
        return '#22c55e';
    }
  };

  const getRoleLabel = (roleCode: string) => {
    switch (roleCode) {
      case 'admin':
        return '管理员';
      case 'manager':
        return '经理';
      case 'employee':
        return '员工';
      default:
        return '客户';
    }
  };

  return (
    <div>
      {/* 错误提示 */}
      {error && (
        <div style={{
          padding: '12px 16px',
          background: 'rgba(239, 68, 68, 0.1)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          borderRadius: '8px',
          color: '#fca5a5',
          marginBottom: '16px',
        }}>
          {error}
          <button
            onClick={() => setError('')}
            style={{
              marginLeft: '12px',
              padding: '4px 8px',
              border: 'none',
              background: 'rgba(239, 68, 68, 0.2)',
              color: '#fca5a5',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
          >
            关闭
          </button>
        </div>
      )}

      {/* 用户列表 */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
          加载中...
        </div>
      ) : (
        <div style={{
          background: 'rgba(30, 41, 59, 0.5)',
          borderRadius: '12px',
          overflow: 'hidden',
        }}>
          <table style={{
            width: '100%',
            borderCollapse: 'collapse',
          }}>
            <thead>
              <tr style={{
                background: 'rgba(15, 23, 42, 0.5)',
                borderBottom: '1px solid rgba(148, 163, 184, 0.2)',
              }}>
                <th style={{ padding: '16px', textAlign: 'left', color: '#cbd5e1' }}>用户名</th>
                <th style={{ padding: '16px', textAlign: 'left', color: '#cbd5e1' }}>显示名称</th>
                <th style={{ padding: '16px', textAlign: 'left', color: '#cbd5e1' }}>邮箱</th>
                <th style={{ padding: '16px', textAlign: 'left', color: '#cbd5e1' }}>企业</th>
                <th style={{ padding: '16px', textAlign: 'left', color: '#cbd5e1' }}>角色</th>
                <th style={{ padding: '16px', textAlign: 'left', color: '#cbd5e1' }}>状态</th>
                <th style={{ padding: '16px', textAlign: 'left', color: '#cbd5e1' }}>创建时间</th>
                <th style={{ padding: '16px', textAlign: 'center', color: '#cbd5e1' }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr
                  key={user.id}
                  style={{
                    borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
                  }}
                >
                  <td style={{ padding: '16px', color: '#e2e8f0' }}>{user.username}</td>
                  <td style={{ padding: '16px', color: '#e2e8f0' }}>{user.display_name || '-'}</td>
                  <td style={{ padding: '16px', color: '#94a3b8' }}>{user.email || '-'}</td>
                  <td style={{ padding: '16px', color: '#94a3b8' }}>
                    {user.organization_names && user.organization_names.length > 0 ? (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {user.organization_names.map((name, idx) => (
                          <span
                            key={idx}
                            style={{
                              padding: '2px 8px',
                              background: 'rgba(34, 197, 94, 0.2)',
                              color: '#22c55e',
                              borderRadius: '4px',
                              fontSize: '12px',
                            }}
                          >
                            {name}
                          </span>
                        ))}
                      </div>
                    ) : '-'}
                  </td>
                  <td style={{ padding: '16px' }}>
                    <span style={{
                      padding: '4px 12px',
                      background: `${getRoleBadgeColor(user.role)}20`,
                      color: getRoleBadgeColor(user.role),
                      borderRadius: '12px',
                      fontSize: '13px',
                    }}>
                      {getRoleLabel(user.role)}
                    </span>
                  </td>
                  <td style={{ padding: '16px' }}>
                    <span style={{
                      padding: '4px 12px',
                      background: user.is_active ? 'rgba(34, 197, 94, 0.2)' : 'rgba(156, 163, 175, 0.2)',
                      color: user.is_active ? '#22c55e' : '#9ca3af',
                      borderRadius: '12px',
                      fontSize: '13px',
                    }}>
                      {user.is_active ? '启用' : '禁用'}
                    </span>
                  </td>
                  <td style={{ padding: '16px', color: '#94a3b8', fontSize: '14px' }}>
                    {new Date(user.created_at).toLocaleDateString('zh-CN')}
                  </td>
                  <td style={{ padding: '16px', textAlign: 'center' }}>
                    <button
                      onClick={() => viewUserRoles(user)}
                      style={{
                        padding: '6px 12px',
                        border: '1px solid rgba(129, 140, 248, 0.3)',
                        background: 'rgba(79, 70, 229, 0.1)',
                        color: '#818cf8',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        fontSize: '13px',
                        marginRight: '8px',
                      }}
                    >
                      分配角色
                    </button>
                    <button
                      onClick={() => showEditOrganization(user)}
                      style={{
                        padding: '6px 12px',
                        border: '1px solid rgba(34, 197, 94, 0.3)',
                        background: 'rgba(34, 197, 94, 0.1)',
                        color: '#22c55e',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        fontSize: '13px',
                        marginRight: '8px',
                      }}
                    >
                      编辑企业
                    </button>
                    <button
                      onClick={() => toggleUserStatus(user.id, user.is_active)}
                      style={{
                        padding: '6px 12px',
                        border: '1px solid rgba(148, 163, 184, 0.3)',
                        background: 'rgba(148, 163, 184, 0.1)',
                        color: '#94a3b8',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        fontSize: '13px',
                      }}
                    >
                      {user.is_active ? '禁用' : '启用'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 角色分配对话框 */}
      {showRoleDialog && selectedUser && (
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
            overflow: 'auto',
          }}>
            <h2 style={{
              margin: '0 0 24px 0',
              fontSize: '20px',
              color: '#f8fafc',
            }}>
              为用户 "{selectedUser.username}" 分配角色
            </h2>

            {/* 当前角色 */}
            <div style={{ marginBottom: '24px' }}>
              <h3 style={{ fontSize: '16px', color: '#cbd5e1', marginBottom: '12px' }}>
                当前角色：
              </h3>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {userRoles.length === 0 ? (
                  <span style={{ color: '#94a3b8' }}>未分配角色</span>
                ) : (
                  userRoles.map((ur) => (
                    <div
                      key={ur.id}
                      style={{
                        padding: '8px 16px',
                        background: 'rgba(79, 70, 229, 0.2)',
                        border: '1px solid rgba(129, 140, 248, 0.3)',
                        borderRadius: '8px',
                        color: '#818cf8',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                      }}
                    >
                      <span>{ur.role_name}</span>
                      <button
                        onClick={() => removeRole(ur.role_id)}
                        style={{
                          padding: '2px 6px',
                          border: 'none',
                          background: 'rgba(239, 68, 68, 0.2)',
                          color: '#ef4444',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          fontSize: '12px',
                        }}
                      >
                        ×
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* 可分配角色 */}
            <div style={{ marginBottom: '24px' }}>
              <h3 style={{ fontSize: '16px', color: '#cbd5e1', marginBottom: '12px' }}>
                添加角色：
              </h3>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {roles
                  .filter((role) => !userRoles.some((ur) => ur.role_id === role.id))
                  .map((role) => (
                    <button
                      key={role.id}
                      onClick={() => assignRole(role.id)}
                      style={{
                        padding: '8px 16px',
                        border: '1px solid rgba(148, 163, 184, 0.3)',
                        background: 'rgba(30, 41, 59, 0.5)',
                        color: '#e2e8f0',
                        borderRadius: '8px',
                        cursor: 'pointer',
                      }}
                    >
                      + {role.name}
                    </button>
                  ))}
              </div>
            </div>

            {/* 关闭按钮 */}
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                onClick={() => {
                  setShowRoleDialog(false);
                  setSelectedUser(null);
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
                关闭
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 企业编辑对话框 */}
      {showOrgDialog && selectedUser && (
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
              为用户 "{selectedUser.username}" 设置企业
            </h2>

            <div style={{ marginBottom: '24px' }}>
              <label style={{
                display: 'block',
                fontSize: '14px',
                color: '#cbd5e1',
                marginBottom: '8px',
              }}>
                选择企业：
              </label>
              <select
                value={selectedOrgId}
                onChange={(e) => setSelectedOrgId(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px',
                  background: 'rgba(30, 41, 59, 0.5)',
                  border: '1px solid rgba(148, 163, 184, 0.3)',
                  borderRadius: '8px',
                  color: '#e2e8f0',
                  fontSize: '14px',
                }}
              >
                <option value="">无企业</option>
                {organizations.map((org) => (
                  <option key={org.id} value={org.id}>
                    {org.name}
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button
                onClick={() => {
                  setShowOrgDialog(false);
                  setSelectedUser(null);
                  setSelectedOrgId('');
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
                onClick={updateUserOrganization}
                style={{
                  padding: '10px 24px',
                  border: 'none',
                  background: 'linear-gradient(135deg, #4f46e5, #22c55e)',
                  color: '#fff',
                  borderRadius: '8px',
                  cursor: 'pointer',
                }}
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserManagement;

