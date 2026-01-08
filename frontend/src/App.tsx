import React, { useState } from "react";
import ChatLayout from "./components/ChatLayout";
import SystemSettings from "./components/SystemSettings";
import KnowledgeBaseManager from "./components/KnowledgeBaseManager";
import RecordingsList from "./components/RecordingsList";
import LoginPage from "./components/LoginPage";
import TenderWorkspace from "./components/TenderWorkspaceV2";
import DeclareWorkspace from "./components/DeclareWorkspaceV2";
import FormatTemplatesPage from "./components/FormatTemplatesPage";
import DebugPanel from "./components/DebugPanel";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { usePermission } from "./hooks/usePermission";

type Page = "chat" | "settings" | "kb" | "recordings" | "tender" | "declare" | "format-templates";

const MainApp: React.FC = () => {
  const { user, logout, isLoading } = useAuth();
  const { canAccessAdminMode, hasPermission, hasAnyPermission } = usePermission();
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
        {/* 知识库 - 需要 kb.view 权限 */}
        {hasPermission("kb.view") && (
          <button
            onClick={() => setCurrentPage("kb")}
            className={`nav-btn ${currentPage === "kb" ? "active" : ""}`}
          >
            📚 知识库
          </button>
        )}
        {/* 招投标 - 需要 tender.view 权限 */}
        {hasPermission("tender.view") && (
          <button
            onClick={() => setCurrentPage("tender")}
            className={`nav-btn ${currentPage === "tender" ? "active" : ""}`}
          >
            🧾 招投标
          </button>
        )}
        {/* 申报书 - 需要 declare.view 权限 */}
        {hasPermission("declare.view") && (
          <button
            onClick={() => setCurrentPage("declare")}
            className={`nav-btn ${currentPage === "declare" ? "active" : ""}`}
          >
            📝 申报书
          </button>
        )}
        {/* 我的录音 - 需要 recording.view 权限 */}
        {hasPermission("recording.view") && (
          <button
            onClick={() => setCurrentPage("recordings")}
            className={`nav-btn ${currentPage === "recordings" ? "active" : ""}`}
          >
            📼 我的录音
          </button>
        )}
        {/* 系统设置 - 需要管理员或员工权限 */}
        {canAccessAdminMode && (
          <button
            onClick={() => setCurrentPage("settings")}
            className={`nav-btn ${currentPage === "settings" ? "active" : ""}`}
          >
            ⚙️ 系统设置
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
        {currentPage === "chat" && <ChatLayout />}
        {currentPage === "kb" && <KnowledgeBaseManager />}
        {currentPage === "tender" && <TenderWorkspace />}
        {currentPage === "declare" && <DeclareWorkspace />}
        {currentPage === "format-templates" && <FormatTemplatesPage />}
        {currentPage === "recordings" && <RecordingsList />}
        {currentPage === "settings" && <SystemSettings />}
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
