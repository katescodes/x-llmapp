/**
 * 权限管理相关类型定义
 */

// 权限项
export interface Permission {
  id: string;
  code: string;
  name: string;
  description?: string;
  module: string;
  parent_code?: string;
  resource_type?: string;
  display_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  children?: Permission[]; // 用于树形结构
}

// 角色
export interface Role {
  id: string;
  code: string;
  name: string;
  description?: string;
  is_system: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// 角色及其权限
export interface RoleWithPermissions extends Role {
  permissions: Permission[];
}

// 用户角色
export interface UserRole {
  id: string;
  user_id: string;
  role_id: string;
  role_code: string;
  role_name: string;
  granted_by?: string;
  granted_at: string;
  expires_at?: string;
}

// 数据权限范围
export type DataScope = 'all' | 'dept' | 'self' | 'custom';

// 数据权限
export interface DataPermission {
  id: string;
  user_id: string;
  resource_type: string;
  data_scope: DataScope;
  custom_scope_json?: any;
  created_at: string;
  updated_at: string;
}

// 用户所有权限
export interface UserPermissions {
  user_id: string;
  username: string;
  roles: Role[];
  permissions: Permission[];
  data_scope?: DataScope;
}

// 权限检查响应
export interface PermissionCheckResponse {
  user_id: string;
  permissions: Record<string, boolean>;
}

// 权限统计
export interface PermissionStats {
  total_permissions: number;
  total_roles: number;
  total_user_roles: number;
  active_permissions: number;
  active_roles: number;
}

// API请求类型
export interface RolePermissionAssign {
  role_id: string;
  permission_ids: string[];
}

export interface UserRoleAssign {
  user_id: string;
  role_ids: string[];
  expires_at?: string;
}

export interface PermissionCreate {
  code: string;
  name: string;
  description?: string;
  module: string;
  parent_code?: string;
  resource_type?: string;
  display_order?: number;
  is_active?: boolean;
}

export interface PermissionUpdate {
  name?: string;
  description?: string;
  display_order?: number;
  is_active?: boolean;
}

export interface RoleCreate {
  code: string;
  name: string;
  description?: string;
  is_active?: boolean;
}

export interface RoleUpdate {
  name?: string;
  description?: string;
  is_active?: boolean;
}

