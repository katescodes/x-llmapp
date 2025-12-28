/**
 * 权限管理 Hook
 */
import { useCallback, useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { UserRole } from '../types/auth';
import { userRoleApi } from '../api/permission';
import { UserPermissions } from '../types/permission';

export interface PermissionCheck {
  canViewAllKbs: boolean;
  canManageUsers: boolean;
  canCreateKb: boolean;
  canShareKb: boolean;
  canDeleteKb: (kbOwnerId: string) => boolean;
  canEditKb: (kbOwnerId: string) => boolean;
  canAccessKb: (kbOwnerId: string, isPublic: boolean, isShared: boolean) => boolean;
  canAccessAdminMode: boolean;
  isAdmin: boolean;
  isEmployee: boolean;
  isCustomer: boolean;
  hasPermission: (permissionCode: string) => boolean;
  hasAnyPermission: (permissionCodes: string[]) => boolean;
  hasAllPermissions: (permissionCodes: string[]) => boolean;
  permissions: string[]; // 用户拥有的权限代码列表
}

export const usePermission = (): PermissionCheck => {
  const { user } = useAuth();
  const [userPermissions, setUserPermissions] = useState<UserPermissions | null>(null);

  const role: UserRole = user?.role || 'customer';
  const userId: string = user?.id || '';

  // 加载用户权限
  useEffect(() => {
    const loadPermissions = async () => {
      if (user) {
        try {
          const perms = await userRoleApi.getMyPermissions();
          setUserPermissions(perms);
        } catch (err) {
          console.error('加载用户权限失败:', err);
        }
      }
    };

    loadPermissions();
  }, [user]);

  // 获取权限代码列表
  const permissionCodes = userPermissions?.permissions.map((p) => p.code) || [];

  // 检查是否拥有某个权限
  const hasPermission = useCallback(
    (permissionCode: string): boolean => {
      return permissionCodes.includes(permissionCode);
    },
    [permissionCodes]
  );

  // 检查是否拥有任一权限
  const hasAnyPermission = useCallback(
    (codes: string[]): boolean => {
      return codes.some((code) => permissionCodes.includes(code));
    },
    [permissionCodes]
  );

  // 检查是否拥有所有权限
  const hasAllPermissions = useCallback(
    (codes: string[]): boolean => {
      return codes.every((code) => permissionCodes.includes(code));
    },
    [permissionCodes]
  );

  return {
    // 查看所有知识库（管理员或有all数据权限）
    canViewAllKbs: role === 'admin' || (userPermissions?.data_scope === 'all'),

    // 用户管理（有用户管理权限）
    canManageUsers: hasPermission('permission.user.view'),

    // 创建知识库
    canCreateKb: hasPermission('kb.create'),

    // 共享知识库
    canShareKb: hasPermission('kb.share'),

    // 删除知识库
    canDeleteKb: (kbOwnerId: string) => {
      if (!hasPermission('kb.delete')) return false;
      return role === 'admin' || userId === kbOwnerId;
    },

    // 编辑知识库
    canEditKb: (kbOwnerId: string) => {
      if (!hasPermission('kb.edit')) return false;
      return role === 'admin' || userId === kbOwnerId;
    },

    // 访问知识库
    canAccessKb: (kbOwnerId: string, isPublic: boolean, isShared: boolean) => {
      if (!hasPermission('kb.view')) return false;
      // 管理员可以访问所有
      if (role === 'admin') return true;
      // 所有者可以访问
      if (userId === kbOwnerId) return true;
      // 公开的可以访问
      if (isPublic) return true;
      // 共享给自己的可以访问
      if (isShared) return true;
      // 其他情况不能访问
      return false;
    },

    // 访问管理模式
    canAccessAdminMode: role === 'admin' || role === 'employee',

    // 角色判断
    isAdmin: role === 'admin',
    isEmployee: role === 'employee',
    isCustomer: role === 'customer',

    // 权限检查方法
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
    permissions: permissionCodes,
  };
};

/**
 * API 请求工具：自动添加认证 Token
 */
export const useAuthFetch = () => {
  const { token } = useAuth();
  
  // 使用 useCallback 避免每次渲染都创建新函数
  const authFetch = useCallback(async (url: string, options: RequestInit = {}) => {
    const headers: HeadersInit = {
      ...options.headers,
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    return fetch(url, {
      ...options,
      headers,
    });
  }, [token]); // 只在 token 变化时重新创建

  return authFetch;
};

