/**
 * 权限管理主界面
 */
import React, { useState } from 'react';
import UserManagement from './permission/UserManagement';
import RoleManagement from './permission/RoleManagement';
import PermissionManagement from './permission/PermissionManagement';

type TabType = 'users' | 'roles' | 'permissions';

const PermissionManagementPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('users');

  const tabStyle = (tab: TabType): React.CSSProperties => ({
    padding: '12px 24px',
    border: 'none',
    background: activeTab === tab ? 'rgba(79, 70, 229, 0.2)' : 'transparent',
    color: activeTab === tab ? '#818cf8' : '#94a3b8',
    borderRadius: '8px',
    cursor: 'pointer',
    fontSize: '15px',
    fontWeight: activeTab === tab ? 600 : 400,
    transition: 'all 0.2s',
  });

  return (
    <div style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
      color: '#f8fafc',
    }}>
      {/* 标题栏 */}
      <div style={{
        padding: '20px 32px',
        borderBottom: '1px solid rgba(148, 163, 184, 0.2)',
      }}>
        <h1 style={{
          margin: 0,
          fontSize: '24px',
          fontWeight: 600,
          color: '#f8fafc',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
        }}>
          <span>🔐</span>
          <span>权限管理</span>
        </h1>
        <p style={{
          margin: '8px 0 0 0',
          fontSize: '14px',
          color: '#94a3b8',
        }}>
          管理系统用户、角色和权限
        </p>
      </div>

      {/* 标签栏 */}
      <div style={{
        padding: '16px 32px',
        borderBottom: '1px solid rgba(148, 163, 184, 0.2)',
        display: 'flex',
        gap: '8px',
      }}>
        <button style={tabStyle('users')} onClick={() => setActiveTab('users')}>
          👥 用户管理
        </button>
        <button style={tabStyle('roles')} onClick={() => setActiveTab('roles')}>
          👔 角色管理
        </button>
        <button style={tabStyle('permissions')} onClick={() => setActiveTab('permissions')}>
          🔑 权限项管理
        </button>
      </div>

      {/* 内容区域 */}
      <div style={{
        flex: 1,
        overflow: 'auto',
        padding: '24px 32px',
      }}>
        {activeTab === 'users' && <UserManagement />}
        {activeTab === 'roles' && <RoleManagement />}
        {activeTab === 'permissions' && <PermissionManagement />}
      </div>
    </div>
  );
};

export default PermissionManagementPage;

