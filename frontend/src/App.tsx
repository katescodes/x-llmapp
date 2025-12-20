import React, { useState } from "react";
import ChatLayout from "./components/ChatLayout";
import SystemSettings from "./components/SystemSettings";
import KnowledgeBaseManager from "./components/KnowledgeBaseManager";
import RecordingsList from "./components/RecordingsList";
import LoginPage from "./components/LoginPage";
import TenderWorkspace from "./components/TenderWorkspace";
import DeclareWorkspace from "./components/DeclareWorkspace";
import FormatTemplatesPage from "./components/FormatTemplatesPage";
import DebugPanel from "./components/DebugPanel";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { usePermission } from "./hooks/usePermission";

type Page = "chat" | "settings" | "kb" | "recordings" | "tender" | "declare" | "format-templates";

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
      <nav style={{
        padding: "8px 20px",
        borderBottom: "1px solid rgba(148, 163, 184, 0.2)",
        background: "rgba(15, 23, 42, 0.9)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between"
      }}>
        <div style={{ display: "flex", gap: "16px" }}>
        <button
          onClick={() => setCurrentPage("chat")}
          style={{
            padding: "8px 16px",
            border: "none",
            background: currentPage === "chat" ? "rgba(79, 70, 229, 0.2)" : "transparent",
            color: "#e5e7eb",
            borderRadius: "6px",
            cursor: "pointer"
          }}
        >
          💬 对话
        </button>
        <button
          onClick={() => setCurrentPage("kb")}
          style={{
            padding: "8px 16px",
            border: "none",
            background: currentPage === "kb" ? "rgba(79, 70, 229, 0.2)" : "transparent",
            color: "#e5e7eb",
            borderRadius: "6px",
            cursor: "pointer"
          }}
        >
          📚 知识库
        </button>
        <button
          onClick={() => setCurrentPage("tender")}
          style={{
            padding: "8px 16px",
            border: "none",
            background: currentPage === "tender" ? "rgba(79, 70, 229, 0.2)" : "transparent",
            color: "#e5e7eb",
            borderRadius: "6px",
            cursor: "pointer"
          }}
        >
          🧾 招投标
        </button>
        <button
          onClick={() => setCurrentPage("declare")}
          style={{
            padding: "8px 16px",
            border: "none",
            background: currentPage === "declare" ? "rgba(79, 70, 229, 0.2)" : "transparent",
            color: "#e5e7eb",
            borderRadius: "6px",
            cursor: "pointer"
          }}
        >
          📝 申报书
        </button>
        <button
          onClick={() => setCurrentPage("recordings")}
          style={{
            padding: "8px 16px",
            border: "none",
            background: currentPage === "recordings" ? "rgba(79, 70, 229, 0.2)" : "transparent",
            color: "#e5e7eb",
            borderRadius: "6px",
            cursor: "pointer"
          }}
        >
          📼 我的录音
        </button>
        <button
          onClick={() => setCurrentPage("settings")}
          style={{
            padding: "8px 16px",
            border: "none",
            background: currentPage === "settings" ? "rgba(79, 70, 229, 0.2)" : "transparent",
            color: "#e5e7eb",
            borderRadius: "6px",
            cursor: "pointer"
          }}
        >
          ⚙️ 系统设置
        </button>
        </div>
        
        {/* 用户信息和退出 */}
        <div style={{ 
          display: "flex", 
          alignItems: "center", 
          gap: "16px",
          color: "#e5e7eb",
          fontSize: "14px"
        }}>
          <span>
            👤 {user.display_name || user.username}
            <span style={{ 
              marginLeft: "8px",
              padding: "2px 8px",
              background: user.role === 'admin' ? "rgba(239, 68, 68, 0.2)" : 
                          user.role === 'employee' ? "rgba(59, 130, 246, 0.2)" : 
                          "rgba(34, 197, 94, 0.2)",
              borderRadius: "4px",
              fontSize: "12px"
            }}>
              {user.role === 'admin' ? '管理员' : 
               user.role === 'employee' ? '员工' : '客户'}
            </span>
          </span>
          <button
            onClick={logout}
            style={{
              padding: "6px 12px",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              background: "rgba(239, 68, 68, 0.1)",
              color: "#fca5a5",
              borderRadius: "6px",
              cursor: "pointer",
              fontSize: "13px"
            }}
          >
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
