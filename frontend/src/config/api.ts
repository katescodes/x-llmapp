// 生产模式：直接使用当前页面地址（nginx会代理 /api/ 到backend）
// 开发模式：使用环境变量或默认地址
const envApiBase = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_BASE;

// 如果有配置环境变量则使用环境变量
// 否则在开发和生产模式都使用当前origin（依赖nginx代理）
export const API_BASE_URL = envApiBase || window.location.origin;

// ==================== 统一 API 请求方法 ====================

function getToken(): string {
  // 优先使用 auth_token（系统标准），兼容其他可能的 key
  return localStorage.getItem('auth_token') || 
         localStorage.getItem('access_token') || 
         localStorage.getItem('token') || 
         '';
}

interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
}

async function request(path: string, options: RequestOptions = {}): Promise<any> {
  const token = getToken();
  const headers: Record<string, string> = { ...(options.headers as any) };

  // 如果是 FormData，不设置 Content-Type（让浏览器自动设置 boundary）
  const isFormData = options.body instanceof FormData;
  if (!isFormData && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  // 自动添加 Authorization header
  if (token && !options.skipAuth) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // 确保路径以 / 开头
  const url = path.startsWith('/') ? path : `/${path}`;
  
  const res = await fetch(`${API_BASE_URL}${url}`, { 
    ...options, 
    headers 
  });

  // 统一处理认证错误
  if (res.status === 401) {
    // 可选：清除 token 并跳转登录
    localStorage.removeItem('auth_token');
    throw new Error('未授权，请重新登录');
  }
  
  if (res.status === 403) {
    throw new Error('权限不足');
  }

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }

  // 204 No Content - 不尝试解析响应体
  if (res.status === 204) {
    return null;
  }

  // 根据 Content-Type 返回不同格式
  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return res.json();
  }
  if (
      contentType.includes('application/octet-stream') ||
      contentType.includes('application/vnd.openxmlformats') ||
      contentType.includes('application/pdf') ||
      contentType.startsWith('image/')
  ) {
    return res.blob();
  }
  return res.text();
}

// 导出便捷方法
export const api = {
  get: (path: string, options?: RequestOptions) => 
    request(path, { ...options, method: 'GET' }),
  
  post: (path: string, body?: any, options?: RequestOptions) => 
    request(path, { 
      ...options, 
      method: 'POST', 
      body: body instanceof FormData ? body : JSON.stringify(body) 
    }),
  
  put: (path: string, body?: any, options?: RequestOptions) => 
    request(path, { 
      ...options, 
      method: 'PUT', 
      body: JSON.stringify(body) 
    }),
  
  delete: (path: string, options?: RequestOptions) => 
    request(path, { ...options, method: 'DELETE' }),

  // 原始 request 方法（供特殊需求使用）
  request,
};
