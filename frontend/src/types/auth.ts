/**
 * 认证相关类型定义
 */

export type UserRole = 'admin' | 'employee' | 'customer';

export interface User {
  id: string;
  username: string;
  email?: string;
  role: UserRole;
  display_name?: string;
  phone?: string;
  department?: string;
  company?: string;
  avatar_url?: string;
  is_active: boolean;
  last_login_at?: string;
  created_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
  expires_in: number;
}

export interface RegisterRequest {
  username: string;
  password: string;
  email?: string;
  display_name?: string;
  phone?: string;
  company?: string;
  role?: UserRole;
}

export interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => void;
  updateUser: (user: User) => void;
}

