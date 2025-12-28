/**
 * 权限项管理组件
 */
import React, { useState, useEffect } from 'react';
import { permissionApi } from '../../api/permission';
import { Permission } from '../../types/permission';

const PermissionManagement: React.FC = () => {
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [filterModule, setFilterModule] = useState<string>('');

  // 加载权限列表
  const loadPermissions = async () => {
    try {
      setLoading(true);
      const data = await permissionApi.listPermissions(filterModule || undefined);
      setPermissions(data);
    } catch (err: any) {
      setError(err.message || '加载权限列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPermissions();
  }, [filterModule]);

  // 模块列表
  const modules = [
    { value: '', label: '全部' },
    { value: 'chat', label: '对话' },
    { value: 'kb', label: '知识库' },
    { value: 'tender', label: '招投标' },
    { value: 'declare', label: '申报书' },
    { value: 'recordings', label: '录音' },
    { value: 'system', label: '系统设置' },
  ];

  const moduleNames: Record<string, string> = {
    chat: '对话',
    kb: '知识库',
    tender: '招投标',
    declare: '申报书',
    recordings: '录音',
    system: '系统设置',
  };

  const resourceTypeNames: Record<string, string> = {
    menu: '菜单',
    api: 'API',
    button: '按钮',
    data: '数据',
  };

  // 按模块分组
  const groupByModule = (perms: Permission[]) => {
    const grouped: Record<string, Permission[]> = {};
    perms.forEach((perm) => {
      if (!grouped[perm.module]) {
        grouped[perm.module] = [];
      }
      grouped[perm.module].push(perm);
    });
    return grouped;
  };

  const groupedPermissions = groupByModule(permissions);

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

      {/* 过滤器 */}
      <div style={{ marginBottom: '16px', display: 'flex', gap: '12px', alignItems: 'center' }}>
        <span style={{ color: '#cbd5e1' }}>模块筛选：</span>
        {modules.map((mod) => (
          <button
            key={mod.value}
            onClick={() => setFilterModule(mod.value)}
            style={{
              padding: '8px 16px',
              border: '1px solid rgba(148, 163, 184, 0.3)',
              background: filterModule === mod.value ? 'rgba(79, 70, 229, 0.2)' : 'rgba(30, 41, 59, 0.5)',
              color: filterModule === mod.value ? '#818cf8' : '#94a3b8',
              borderRadius: '8px',
              cursor: 'pointer',
              fontSize: '14px',
            }}
          >
            {mod.label}
          </button>
        ))}
      </div>

      {/* 权限列表 */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
          加载中...
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {Object.entries(groupedPermissions).map(([module, perms]) => (
            <div
              key={module}
              style={{
                background: 'rgba(30, 41, 59, 0.5)',
                borderRadius: '12px',
                padding: '24px',
              }}
            >
              <h3 style={{
                margin: '0 0 16px 0',
                fontSize: '18px',
                color: '#f8fafc',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
              }}>
                <span style={{
                  padding: '6px 16px',
                  background: 'rgba(79, 70, 229, 0.2)',
                  color: '#818cf8',
                  borderRadius: '8px',
                  fontSize: '14px',
                  fontWeight: 500,
                }}>
                  {moduleNames[module] || module}
                </span>
                <span style={{ color: '#94a3b8', fontSize: '14px', fontWeight: 400 }}>
                  共 {perms.length} 项权限
                </span>
              </h3>

              <div style={{ display: 'grid', gap: '12px' }}>
                {perms
                  .sort((a, b) => a.display_order - b.display_order)
                  .map((perm) => (
                    <div
                      key={perm.id}
                      style={{
                        padding: '16px',
                        background: 'rgba(15, 23, 42, 0.5)',
                        border: '1px solid rgba(148, 163, 184, 0.2)',
                        borderRadius: '8px',
                        display: 'grid',
                        gridTemplateColumns: 'auto 1fr auto auto',
                        gap: '16px',
                        alignItems: 'center',
                      }}
                    >
                      {/* 权限代码 */}
                      <div style={{
                        fontFamily: 'monospace',
                        color: '#818cf8',
                        fontSize: '13px',
                        minWidth: '200px',
                      }}>
                        {perm.code}
                      </div>

                      {/* 权限名称和描述 */}
                      <div>
                        <div style={{
                          color: '#e2e8f0',
                          fontWeight: 500,
                          marginBottom: '4px',
                        }}>
                          {perm.name}
                        </div>
                        {perm.description && (
                          <div style={{
                            color: '#94a3b8',
                            fontSize: '13px',
                          }}>
                            {perm.description}
                          </div>
                        )}
                      </div>

                      {/* 资源类型 */}
                      <div>
                        {perm.resource_type && (
                          <span style={{
                            padding: '4px 12px',
                            background: 'rgba(59, 130, 246, 0.2)',
                            color: '#3b82f6',
                            borderRadius: '12px',
                            fontSize: '12px',
                          }}>
                            {resourceTypeNames[perm.resource_type] || perm.resource_type}
                          </span>
                        )}
                      </div>

                      {/* 状态 */}
                      <div>
                        <span style={{
                          padding: '4px 12px',
                          background: perm.is_active ? 'rgba(34, 197, 94, 0.2)' : 'rgba(156, 163, 175, 0.2)',
                          color: perm.is_active ? '#22c55e' : '#9ca3af',
                          borderRadius: '12px',
                          fontSize: '12px',
                        }}>
                          {perm.is_active ? '启用' : '禁用'}
                        </span>
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 空状态 */}
      {!loading && permissions.length === 0 && (
        <div style={{
          textAlign: 'center',
          padding: '60px 20px',
          color: '#94a3b8',
        }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>🔑</div>
          <div style={{ fontSize: '16px' }}>暂无权限项</div>
        </div>
      )}
    </div>
  );
};

export default PermissionManagement;

