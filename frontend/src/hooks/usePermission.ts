/**
 * 权限管理 Hook
 */
import { useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { UserRole } from '../types/auth';

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
}

export const usePermission = (): PermissionCheck => {
  const { user } = useAuth();

  const role: UserRole = user?.role || 'customer';
  const userId: string = user?.id || '';

  return {
    // 查看所有知识库（管理员）
    canViewAllKbs: role === 'admin',

    // 用户管理（管理员）
    canManageUsers: role === 'admin',

    // 创建知识库（所有人）
    canCreateKb: true,

    // 共享知识库（员工和管理员）
    canShareKb: role === 'admin' || role === 'employee',

    // 删除知识库
    canDeleteKb: (kbOwnerId: string) => {
      return role === 'admin' || userId === kbOwnerId;
    },

    // 编辑知识库
    canEditKb: (kbOwnerId: string) => {
      return role === 'admin' || userId === kbOwnerId;
    },

    // 访问知识库
    canAccessKb: (kbOwnerId: string, isPublic: boolean, isShared: boolean) => {
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

