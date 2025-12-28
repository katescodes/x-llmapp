/**
 * 权限管理API
 */
import { api } from '../config/api';
import {
  Permission,
  Role,
  RoleWithPermissions,
  UserRole,
  UserPermissions,
  PermissionCheckResponse,
  PermissionStats,
  RolePermissionAssign,
  UserRoleAssign,
  PermissionCreate,
  PermissionUpdate,
  RoleCreate,
  RoleUpdate,
  DataPermission,
} from '../types/permission';

// ==================== 权限项管理 ====================
export const permissionApi = {
  // 获取权限项列表
  listPermissions: (module?: string, activeOnly: boolean = true): Promise<Permission[]> => {
    const params = new URLSearchParams();
    if (module) params.append('module', module);
    params.append('active_only', activeOnly.toString());
    return api.get(`/api/permissions/items?${params.toString()}`);
  },

  // 获取权限树
  getPermissionsTree: (module?: string): Promise<Permission[]> => {
    const params = module ? `?module=${module}` : '';
    return api.get(`/api/permissions/items/tree${params}`);
  },

  // 获取单个权限
  getPermission: (permId: string): Promise<Permission> => {
    return api.get(`/api/permissions/items/${permId}`);
  },

  // 创建权限
  createPermission: (data: PermissionCreate): Promise<Permission> => {
    return api.post('/api/permissions/items', data);
  },

  // 更新权限
  updatePermission: (permId: string, data: PermissionUpdate): Promise<Permission> => {
    return api.put(`/api/permissions/items/${permId}`, data);
  },
};

// ==================== 角色管理 ====================
export const roleApi = {
  // 获取角色列表
  listRoles: (activeOnly: boolean = true): Promise<Role[]> => {
    const params = `?active_only=${activeOnly}`;
    return api.get(`/api/permissions/roles${params}`);
  },

  // 获取角色详情（含权限）
  getRole: (roleId: string): Promise<RoleWithPermissions> => {
    return api.get(`/api/permissions/roles/${roleId}`);
  },

  // 创建角色
  createRole: (data: RoleCreate): Promise<Role> => {
    return api.post('/api/permissions/roles', data);
  },

  // 更新角色
  updateRole: (roleId: string, data: RoleUpdate): Promise<Role> => {
    return api.put(`/api/permissions/roles/${roleId}`, data);
  },

  // 删除角色
  deleteRole: (roleId: string): Promise<void> => {
    return api.delete(`/api/permissions/roles/${roleId}`);
  },

  // 获取角色的权限列表
  getRolePermissions: (roleId: string): Promise<Permission[]> => {
    return api.get(`/api/permissions/roles/${roleId}/permissions`);
  },

  // 为角色分配权限
  assignPermissions: (data: RolePermissionAssign): Promise<{ message: string }> => {
    return api.post('/api/permissions/roles/assign-permissions', data);
  },

  // 移除角色的权限
  removePermissions: (data: RolePermissionAssign): Promise<{ message: string }> => {
    return api.post('/api/permissions/roles/remove-permissions', data);
  },
};

// ==================== 用户-角色管理 ====================
export const userRoleApi = {
  // 获取用户的角色列表
  getUserRoles: (userId: string): Promise<UserRole[]> => {
    return api.get(`/api/permissions/users/${userId}/roles`);
  },

  // 为用户分配角色
  assignRoles: (data: UserRoleAssign): Promise<{ message: string }> => {
    return api.post('/api/permissions/users/assign-roles', data);
  },

  // 移除用户的角色
  removeRoles: (data: UserRoleAssign): Promise<{ message: string }> => {
    return api.post('/api/permissions/users/remove-roles', data);
  },

  // 获取用户的所有权限
  getUserPermissions: (userId: string): Promise<UserPermissions> => {
    return api.get(`/api/permissions/users/${userId}/all-permissions`);
  },

  // 获取当前用户的权限
  getMyPermissions: (): Promise<UserPermissions> => {
    return api.get('/api/permissions/me/permissions');
  },

  // 检查用户权限
  checkPermissions: (userId: string, permissionCodes: string[]): Promise<PermissionCheckResponse> => {
    return api.post(`/api/permissions/users/${userId}/check`, permissionCodes);
  },
};

// ==================== 数据权限管理 ====================
export const dataPermissionApi = {
  // 获取用户的数据权限
  getDataPermission: (userId: string, resourceType: string): Promise<DataPermission> => {
    return api.get(`/api/permissions/users/${userId}/data-permissions/${resourceType}`);
  },

  // 设置用户的数据权限
  setDataPermission: (userId: string, data: any): Promise<DataPermission> => {
    return api.post(`/api/permissions/users/${userId}/data-permissions`, data);
  },
};

// ==================== 统计信息 ====================
export const permissionStatsApi = {
  // 获取权限统计
  getStats: (): Promise<PermissionStats> => {
    return api.get('/api/permissions/stats');
  },
};

