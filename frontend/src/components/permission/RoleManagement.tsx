/**
 * 角色管理组件
 */
import React, { useState, useEffect } from 'react';
import { roleApi, permissionApi } from '../../api/permission';
import { Role, RoleWithPermissions, Permission, RoleCreate, RoleUpdate } from '../../types/permission';

const RoleManagement: React.FC = () => {
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedRole, setSelectedRole] = useState<RoleWithPermissions | null>(null);
  const [showPermissionDialog, setShowPermissionDialog] = useState(false);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [createForm, setCreateForm] = useState<RoleCreate>({
    code: '',
    name: '',
    description: '',
    is_active: true,
  });

  // 加载角色列表
  const loadRoles = async () => {
    try {
      setLoading(true);
      const data = await roleApi.listRoles();
      setRoles(data);
    } catch (err: any) {
      setError(err.message || '加载角色列表失败');
    } finally {
      setLoading(false);
    }
  };

  // 加载权限列表
  const loadPermissions = async () => {
    try {
      const data = await permissionApi.listPermissions();
      setPermissions(data);
    } catch (err: any) {
      console.error('加载权限列表失败:', err);
    }
  };

  useEffect(() => {
    loadRoles();
    loadPermissions();
  }, []);

  // 查看角色权限
  const viewRolePermissions = async (role: Role) => {
    try {
      const data = await roleApi.getRole(role.id);
      setSelectedRole(data);
      setShowPermissionDialog(true);
    } catch (err: any) {
      setError(err.message || '加载角色权限失败');
    }
  };

  // 分配权限
  const assignPermission = async (permissionId: string) => {
    if (!selectedRole) return;

    try {
      await roleApi.assignPermissions({
        role_id: selectedRole.id,
        permission_ids: [permissionId],
      });
      
      // 重新加载角色权限
      const data = await roleApi.getRole(selectedRole.id);
      setSelectedRole(data);
    } catch (err: any) {
      setError(err.message || '分配权限失败');
    }
  };

  // 移除权限
  const removePermission = async (permissionId: string) => {
    if (!selectedRole) return;

    try {
      await roleApi.removePermissions({
        role_id: selectedRole.id,
        permission_ids: [permissionId],
      });
      
      // 重新加载角色权限
      const data = await roleApi.getRole(selectedRole.id);
      setSelectedRole(data);
    } catch (err: any) {
      setError(err.message || '移除权限失败');
    }
  };

  // 创建角色
  const handleCreateRole = async () => {
    try {
      await roleApi.createRole(createForm);
      setShowCreateDialog(false);
      setCreateForm({
        code: '',
        name: '',
        description: '',
        is_active: true,
      });
      await loadRoles();
    } catch (err: any) {
      setError(err.message || '创建角色失败');
    }
  };

  // 删除角色
  const handleDeleteRole = async (roleId: string) => {
    if (!confirm('确定要删除这个角色吗？')) return;

    try {
      await roleApi.deleteRole(roleId);
      await loadRoles();
    } catch (err: any) {
      setError(err.message || '删除角色失败');
    }
  };

  // 按模块分组权限
  const groupPermissionsByModule = (perms: Permission[]) => {
    const grouped: Record<string, Permission[]> = {};
    perms.forEach((perm) => {
      if (!grouped[perm.module]) {
        grouped[perm.module] = [];
      }
      grouped[perm.module].push(perm);
    });
    return grouped;
  };

  const moduleNames: Record<string, string> = {
    chat: '对话',
    kb: '知识库',
    tender: '招投标',
    declare: '申报书',
    recordings: '录音',
    system: '系统设置',
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

      {/* 顶部工具栏 */}
      <div style={{ marginBottom: '16px' }}>
        <button
          onClick={() => setShowCreateDialog(true)}
          style={{
            padding: '10px 20px',
            border: 'none',
            background: 'rgba(79, 70, 229, 0.2)',
            color: '#818cf8',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: 500,
          }}
        >
          + 创建角色
        </button>
      </div>

      {/* 角色列表 */}
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
                <th style={{ padding: '16px', textAlign: 'left', color: '#cbd5e1' }}>角色代码</th>
                <th style={{ padding: '16px', textAlign: 'left', color: '#cbd5e1' }}>角色名称</th>
                <th style={{ padding: '16px', textAlign: 'left', color: '#cbd5e1' }}>描述</th>
                <th style={{ padding: '16px', textAlign: 'left', color: '#cbd5e1' }}>类型</th>
                <th style={{ padding: '16px', textAlign: 'left', color: '#cbd5e1' }}>状态</th>
                <th style={{ padding: '16px', textAlign: 'center', color: '#cbd5e1' }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {roles.map((role) => (
                <tr
                  key={role.id}
                  style={{
                    borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
                  }}
                >
                  <td style={{ padding: '16px', color: '#e2e8f0', fontFamily: 'monospace' }}>
                    {role.code}
                  </td>
                  <td style={{ padding: '16px', color: '#e2e8f0', fontWeight: 500 }}>
                    {role.name}
                  </td>
                  <td style={{ padding: '16px', color: '#94a3b8', fontSize: '14px' }}>
                    {role.description || '-'}
                  </td>
                  <td style={{ padding: '16px' }}>
                    <span style={{
                      padding: '4px 12px',
                      background: role.is_system ? 'rgba(168, 85, 247, 0.2)' : 'rgba(59, 130, 246, 0.2)',
                      color: role.is_system ? '#a855f7' : '#3b82f6',
                      borderRadius: '12px',
                      fontSize: '13px',
                    }}>
                      {role.is_system ? '系统角色' : '自定义'}
                    </span>
                  </td>
                  <td style={{ padding: '16px' }}>
                    <span style={{
                      padding: '4px 12px',
                      background: role.is_active ? 'rgba(34, 197, 94, 0.2)' : 'rgba(156, 163, 175, 0.2)',
                      color: role.is_active ? '#22c55e' : '#9ca3af',
                      borderRadius: '12px',
                      fontSize: '13px',
                    }}>
                      {role.is_active ? '启用' : '禁用'}
                    </span>
                  </td>
                  <td style={{ padding: '16px', textAlign: 'center' }}>
                    <button
                      onClick={() => viewRolePermissions(role)}
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
                      分配权限
                    </button>
                    {!role.is_system && (
                      <button
                        onClick={() => handleDeleteRole(role.id)}
                        style={{
                          padding: '6px 12px',
                          border: '1px solid rgba(239, 68, 68, 0.3)',
                          background: 'rgba(239, 68, 68, 0.1)',
                          color: '#fca5a5',
                          borderRadius: '6px',
                          cursor: 'pointer',
                          fontSize: '13px',
                        }}
                      >
                        删除
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 创建角色对话框 */}
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
            <h2 style={{ margin: '0 0 24px 0', fontSize: '20px', color: '#f8fafc' }}>
              创建角色
            </h2>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', marginBottom: '8px', color: '#cbd5e1' }}>
                角色代码 *
              </label>
              <input
                type="text"
                value={createForm.code}
                onChange={(e) => setCreateForm({ ...createForm, code: e.target.value })}
                placeholder="例如: manager"
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  background: 'rgba(15, 23, 42, 0.5)',
                  border: '1px solid rgba(148, 163, 184, 0.3)',
                  borderRadius: '8px',
                  color: '#f8fafc',
                  fontSize: '14px',
                }}
              />
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', marginBottom: '8px', color: '#cbd5e1' }}>
                角色名称 *
              </label>
              <input
                type="text"
                value={createForm.name}
                onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                placeholder="例如: 部门经理"
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  background: 'rgba(15, 23, 42, 0.5)',
                  border: '1px solid rgba(148, 163, 184, 0.3)',
                  borderRadius: '8px',
                  color: '#f8fafc',
                  fontSize: '14px',
                }}
              />
            </div>

            <div style={{ marginBottom: '24px' }}>
              <label style={{ display: 'block', marginBottom: '8px', color: '#cbd5e1' }}>
                描述
              </label>
              <textarea
                value={createForm.description}
                onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                placeholder="角色描述..."
                rows={3}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  background: 'rgba(15, 23, 42, 0.5)',
                  border: '1px solid rgba(148, 163, 184, 0.3)',
                  borderRadius: '8px',
                  color: '#f8fafc',
                  fontSize: '14px',
                  resize: 'vertical',
                }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button
                onClick={() => {
                  setShowCreateDialog(false);
                  setCreateForm({
                    code: '',
                    name: '',
                    description: '',
                    is_active: true,
                  });
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
                onClick={handleCreateRole}
                disabled={!createForm.code || !createForm.name}
                style={{
                  padding: '10px 24px',
                  border: 'none',
                  background: createForm.code && createForm.name ? 'rgba(79, 70, 229, 0.8)' : 'rgba(79, 70, 229, 0.3)',
                  color: '#f8fafc',
                  borderRadius: '8px',
                  cursor: createForm.code && createForm.name ? 'pointer' : 'not-allowed',
                }}
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 权限分配对话框 */}
      {showPermissionDialog && selectedRole && (
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
            maxWidth: '800px',
            maxHeight: '80vh',
            overflow: 'auto',
          }}>
            <h2 style={{ margin: '0 0 24px 0', fontSize: '20px', color: '#f8fafc' }}>
              为角色 "{selectedRole.name}" 分配权限
            </h2>

            {/* 按模块分组显示权限 */}
            {Object.entries(groupPermissionsByModule(permissions)).map(([module, perms]) => (
              <div key={module} style={{ marginBottom: '24px' }}>
                <h3 style={{
                  fontSize: '16px',
                  color: '#cbd5e1',
                  marginBottom: '12px',
                  paddingBottom: '8px',
                  borderBottom: '1px solid rgba(148, 163, 184, 0.2)',
                }}>
                  {moduleNames[module] || module}
                </h3>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {perms.map((perm) => {
                    const hasPermission = selectedRole.permissions.some((p) => p.id === perm.id);
                    return (
                      <div
                        key={perm.id}
                        style={{
                          padding: '8px 16px',
                          background: hasPermission ? 'rgba(79, 70, 229, 0.2)' : 'rgba(30, 41, 59, 0.5)',
                          border: `1px solid ${hasPermission ? 'rgba(129, 140, 248, 0.3)' : 'rgba(148, 163, 184, 0.3)'}`,
                          borderRadius: '8px',
                          color: hasPermission ? '#818cf8' : '#94a3b8',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                        }}
                      >
                        <span style={{ fontSize: '13px' }}>{perm.name}</span>
                        {hasPermission ? (
                          <button
                            onClick={() => removePermission(perm.id)}
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
                        ) : (
                          <button
                            onClick={() => assignPermission(perm.id)}
                            style={{
                              padding: '2px 6px',
                              border: 'none',
                              background: 'rgba(34, 197, 94, 0.2)',
                              color: '#22c55e',
                              borderRadius: '4px',
                              cursor: 'pointer',
                              fontSize: '12px',
                            }}
                          >
                            +
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}

            {/* 关闭按钮 */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '24px' }}>
              <button
                onClick={() => {
                  setShowPermissionDialog(false);
                  setSelectedRole(null);
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
    </div>
  );
};

export default RoleManagement;

