/**
 * 登录注册页面
 */
import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import '../styles/auth.css';

const LoginPage: React.FC = () => {
  const { login, register } = useAuth();
  const [isLogin, setIsLogin] = useState(true);
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    email: '',
    display_name: '',
    company: '',
    phone: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isLogin) {
        await login(formData.username, formData.password);
      } else {
        await register({
          username: formData.username,
          password: formData.password,
          email: formData.email || undefined,
          display_name: formData.display_name || undefined,
          company: formData.company || undefined,
          phone: formData.phone || undefined,
          role: 'customer',
        });
      }
    } catch (err: any) {
      setError(err.message || '操作失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '16px' }}>
            <img 
              src="/logo.png?v=2" 
              alt="亿林亿智" 
              style={{ height: '60px', marginRight: '12px' }}
            />
            <h1 style={{ margin: 0, fontSize: '32px', fontWeight: 'bold' }}>亿林亿智</h1>
          </div>
          <p>智能知识问答系统</p>
        </div>

        <div className="auth-tabs">
          <button
            className={`auth-tab ${isLogin ? 'active' : ''}`}
            onClick={() => {
              setIsLogin(true);
              setError('');
            }}
          >
            登录
          </button>
          <button
            className={`auth-tab ${!isLogin ? 'active' : ''}`}
            onClick={() => {
              setIsLogin(false);
              setError('');
            }}
          >
            注册
          </button>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          {error && (
            <div className="auth-error">
              ⚠️ {error}
            </div>
          )}

          <div className="form-group">
            <label htmlFor="username">用户名 *</label>
            <input
              type="text"
              id="username"
              name="username"
              value={formData.username}
              onChange={handleChange}
              placeholder="请输入用户名"
              required
              minLength={3}
              maxLength={50}
              autoComplete="username"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">密码 *</label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="请输入密码"
              required
              minLength={6}
              maxLength={100}
              autoComplete={isLogin ? 'current-password' : 'new-password'}
            />
          </div>

          {!isLogin && (
            <>
              <div className="form-group">
                <label htmlFor="display_name">显示名称</label>
                <input
                  type="text"
                  id="display_name"
                  name="display_name"
                  value={formData.display_name}
                  onChange={handleChange}
                  placeholder="您的昵称或真实姓名"
                  maxLength={100}
                />
              </div>

              <div className="form-group">
                <label htmlFor="email">邮箱</label>
                <input
                  type="email"
                  id="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="your@email.com"
                  maxLength={100}
                />
              </div>

              <div className="form-group">
                <label htmlFor="company">公司</label>
                <input
                  type="text"
                  id="company"
                  name="company"
                  value={formData.company}
                  onChange={handleChange}
                  placeholder="您的公司名称"
                  maxLength={100}
                />
              </div>

              <div className="form-group">
                <label htmlFor="phone">手机号</label>
                <input
                  type="tel"
                  id="phone"
                  name="phone"
                  value={formData.phone}
                  onChange={handleChange}
                  placeholder="联系电话"
                  maxLength={20}
                />
              </div>
            </>
          )}

          <button
            type="submit"
            className="auth-submit-btn"
            disabled={loading}
          >
            {loading ? (
              <span>处理中...</span>
            ) : (
              <span>{isLogin ? '登录' : '注册'}</span>
            )}
          </button>
        </form>

        {isLogin && (
          <div className="auth-footer">
            <p>默认管理员账号：admin / admin123</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default LoginPage;

