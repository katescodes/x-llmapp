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
  timeout?: number; // 超时时间（毫秒），默认5分钟
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
  
  // 设置超时（默认5分钟，AI生成需要较长时间）
  const timeout = options.timeout || 300000; // 5分钟
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);
  
  try {
    const res = await fetch(`${API_BASE_URL}${url}`, { 
      ...options, 
      headers,
      signal: controller.signal
    });
    
    clearTimeout(timeoutId);

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
  } catch (error: any) {
    clearTimeout(timeoutId);
    
    // 处理超时错误
    if (error.name === 'AbortError') {
      throw new Error(`请求超时（${timeout / 1000}秒），请稍后重试`);
    }
    
    // 重新抛出其他错误
    throw error;
  }
}

// 导出便捷方法
export const api = {
  baseURL: API_BASE_URL,  // 导出 baseURL 供外部使用
  
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
  
  patch: (path: string, body?: any, options?: RequestOptions) => 
    request(path, { 
      ...options, 
      method: 'PATCH', 
      body: JSON.stringify(body) 
    }),
  
  delete: (path: string, options?: RequestOptions) => 
    request(path, { ...options, method: 'DELETE' }),

  // 文件上传方法（支持进度回调）
  upload: (path: string, formData: FormData, onProgress?: (progress: number) => void): Promise<any> => {
    return new Promise((resolve, reject) => {
      const token = getToken();
      const xhr = new XMLHttpRequest();
      
      // 上传进度
      if (onProgress) {
        xhr.upload.addEventListener("progress", (e) => {
          if (e.lengthComputable) {
            const percentComplete = Math.round((e.loaded / e.total) * 100);
            onProgress(percentComplete);
          }
        });
      }
      
      // 请求完成
      xhr.addEventListener("load", () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const data = JSON.parse(xhr.responseText);
            resolve(data);
          } catch (err) {
            reject(new Error("解析响应失败"));
          }
        } else if (xhr.status === 401) {
          localStorage.removeItem('auth_token');
          reject(new Error('未授权，请重新登录'));
        } else if (xhr.status === 403) {
          reject(new Error('权限不足'));
        } else {
          reject(new Error(`上传失败 (HTTP ${xhr.status})`));
        }
      });
      
      // 请求失败
      xhr.addEventListener("error", () => {
        reject(new Error("网络错误"));
      });
      
      // 请求中止
      xhr.addEventListener("abort", () => {
        reject(new Error("请求被中止"));
      });
      
      // 确保路径以 / 开头
      const url = path.startsWith('/') ? path : `/${path}`;
      xhr.open("POST", `${API_BASE_URL}${url}`);
      
      // 添加 Authorization header
      if (token) {
        xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      }
      
      xhr.send(formData);
    });
  },

  // 原始 request 方法（供特殊需求使用）
  request,
};
