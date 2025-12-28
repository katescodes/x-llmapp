import React, { useState } from "react";
import ChatLayout from "./components/ChatLayout";
import SystemSettings from "./components/SystemSettings";
import KnowledgeBaseManager from "./components/KnowledgeBaseManager";
import RecordingsList from "./components/RecordingsList";
import LoginPage from "./components/LoginPage";
import TenderWorkspace from "./components/TenderWorkspace";
import DeclareWorkspace from "./components/DeclareWorkspace";
import FormatTemplatesPage from "./components/FormatTemplatesPage";
import PermissionManagementPage from "./components/PermissionManagementPage";
import DebugPanel from "./components/DebugPanel";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { usePermission } from "./hooks/usePermission";

type Page = "chat" | "settings" | "kb" | "recordings" | "tender" | "declare" | "format-templates" | "permissions";

const MainApp: React.FC = () => {
  const { user, logout, isLoading } = useAuth();
  const { canAccessAdminMode } = usePermission();
  const [currentPage, setCurrentPage] = useState<Page>("chat");

  // 监听从招投标工作台跳转到格式模板的事件
  React.useEffect(() => {
    const handleNavigateToTemplates = () => {
      setCurrentPage("format-templates");
    };
    window.addEventListener('navigate-to-templates', handleNavigateToTemplates);
    return () => {
      window.removeEventListener('navigate-to-templates', handleNavigateToTemplates);
    };
  }, []);

  // 加载中
  if (isLoading) {
    return (
      <div style={{
        height: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)",
        color: "#f8fafc"
      }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "48px", marginBottom: "16px" }}>🤖</div>
          <div>加载中...</div>
        </div>
      </div>
    );
  }

  // 未登录：显示登录页面
  if (!user) {
    return <LoginPage />;
  }

  const pageContainerStyle = (visible: boolean): React.CSSProperties => ({
    display: visible ? "block" : "none",
    height: "100%",
  });

  // 已登录：显示主应用
  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
      {/* 顶部导航 */}
      <nav className="app-nav">
        <div className="nav-buttons">
        <button
          onClick={() => setCurrentPage("chat")}
          className={`nav-btn ${currentPage === "chat" ? "active" : ""}`}
        >
          💬 对话
        </button>
        <button
          onClick={() => setCurrentPage("kb")}
          className={`nav-btn ${currentPage === "kb" ? "active" : ""}`}
        >
          📚 知识库
        </button>
        <button
          onClick={() => setCurrentPage("tender")}
          className={`nav-btn ${currentPage === "tender" ? "active" : ""}`}
        >
          🧾 招投标
        </button>
        <button
          onClick={() => setCurrentPage("declare")}
          className={`nav-btn ${currentPage === "declare" ? "active" : ""}`}
        >
          📝 申报书
        </button>
        <button
          onClick={() => setCurrentPage("recordings")}
          className={`nav-btn ${currentPage === "recordings" ? "active" : ""}`}
        >
          📼 我的录音
        </button>
        <button
          onClick={() => setCurrentPage("settings")}
          className={`nav-btn ${currentPage === "settings" ? "active" : ""}`}
        >
          ⚙️ 系统设置
        </button>
        {/* 权限管理入口（仅管理员可见） */}
        {user.role === 'admin' && (
          <button
            onClick={() => setCurrentPage("permissions")}
            className={`nav-btn ${currentPage === "permissions" ? "active" : ""}`}
          >
            🔐 权限管理
          </button>
        )}
        </div>
        
        {/* 用户信息和退出 */}
        <div className="nav-user-section">
          <div className="nav-user-info">
            <div className="nav-user-avatar">
              {user.display_name?.charAt(0).toUpperCase() || user.username?.charAt(0).toUpperCase() || "U"}
            </div>
            <span className="nav-user-name">
              {user.display_name || user.username}
              <span className={`badge ${
                user.role === 'admin' ? 'badge-error' : 
                user.role === 'employee' ? 'badge-info' : 
                'badge-success'
              }`} style={{ marginLeft: '8px' }}>
                {user.role === 'admin' ? '管理员' : 
                 user.role === 'employee' ? '员工' : '客户'}
              </span>
            </span>
          </div>
          <button onClick={logout} className="nav-logout-btn">
            退出登录
          </button>
        </div>
      </nav>

      {/* 页面内容 */}
      <div style={{ flex: 1, overflow: "hidden", minHeight: 0 }}>
        <div
          style={pageContainerStyle(currentPage === "chat")}
          aria-hidden={currentPage !== "chat"}
        >
          <ChatLayout />
        </div>
        <div
          style={pageContainerStyle(currentPage === "kb")}
          aria-hidden={currentPage !== "kb"}
        >
          <KnowledgeBaseManager />
        </div>
        <div
          style={pageContainerStyle(currentPage === "tender")}
          aria-hidden={currentPage !== "tender"}
        >
          <TenderWorkspace />
        </div>
        <div
          style={pageContainerStyle(currentPage === "declare")}
          aria-hidden={currentPage !== "declare"}
        >
          <DeclareWorkspace />
        </div>
        <div
          style={pageContainerStyle(currentPage === "format-templates")}
          aria-hidden={currentPage !== "format-templates"}
        >
          <FormatTemplatesPage />
        </div>
        <div
          style={pageContainerStyle(currentPage === "recordings")}
          aria-hidden={currentPage !== "recordings"}
        >
          <RecordingsList />
        </div>
        <div
          style={pageContainerStyle(currentPage === "settings")}
          aria-hidden={currentPage !== "settings"}
        >
          <SystemSettings />
        </div>
        <div
          style={pageContainerStyle(currentPage === "permissions")}
          aria-hidden={currentPage !== "permissions"}
        >
          <PermissionManagementPage />
        </div>
      </div>
      
      {/* Debug 面板（仅开发模式） */}
      <DebugPanel />
    </div>
  );
};

// 根组件：包装 AuthProvider
const App: React.FC = () => {
  return (
    <AuthProvider>
      <MainApp />
    </AuthProvider>
  );
};

export default App;
