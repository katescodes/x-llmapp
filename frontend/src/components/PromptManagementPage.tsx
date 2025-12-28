import React, { useState, useEffect } from "react";
import { useAuthFetch } from "../hooks/usePermission";

const API_BASE = "/api/apps/tender/prompts";

interface PromptModule {
  id: string;
  name: string;
  description: string;
  icon: string;
}

interface PromptTemplate {
  id: string;
  module: string;
  name: string;
  description: string;
  content: string;
  version: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface HistoryItem {
  id: string;
  version: number;
  change_note: string;
  changed_at: string;
}

export default function PromptManagementPage() {
  const authFetch = useAuthFetch();
  const [modules, setModules] = useState<PromptModule[]>([]);
  const [selectedModule, setSelectedModule] = useState<string>("");
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [selectedPrompt, setSelectedPrompt] = useState<PromptTemplate | null>(null);
  const [editingContent, setEditingContent] = useState<string>("");
  const [isEditing, setIsEditing] = useState(false);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [changeNote, setChangeNote] = useState("");
  const [loading, setLoading] = useState(false);

  // 加载模块列表
  useEffect(() => {
    loadModules();
  }, []);

  // 加载模块的Prompt列表
  useEffect(() => {
    if (selectedModule) {
      loadPrompts(selectedModule);
    }
  }, [selectedModule]);

  const loadModules = async () => {
    try {
      const resp = await authFetch(`${API_BASE}/modules`);
      const data = await resp.json();
      if (data.ok) {
        setModules(data.modules);
        if (data.modules.length > 0) {
          setSelectedModule(data.modules[0].id);
        }
      }
    } catch (err) {
      console.error("Failed to load modules:", err);
      alert("加载模块列表失败");
    }
  };

  const loadPrompts = async (module: string) => {
    try {
      const resp = await authFetch(`${API_BASE}/?module=${module}`);
      const data = await resp.json();
      if (data.ok) {
        setPrompts(data.prompts);
        if (data.prompts.length > 0) {
          selectPrompt(data.prompts[0]);
        } else {
          setSelectedPrompt(null);
        }
      }
    } catch (err) {
      console.error("Failed to load prompts:", err);
      alert("加载Prompt列表失败");
    }
  };

  const selectPrompt = (prompt: PromptTemplate) => {
    setSelectedPrompt(prompt);
    setEditingContent(prompt.content);
    setIsEditing(false);
    setShowHistory(false);
  };

  const handleSave = async () => {
    if (!selectedPrompt || !changeNote.trim()) {
      alert("请填写变更说明");
      return;
    }

    setLoading(true);
    const currentPromptId = selectedPrompt.id; // 保存当前选中的Prompt ID
    try {
      const resp = await authFetch(`${API_BASE}/${selectedPrompt.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: editingContent,
          change_note: changeNote,
        }),
      });
      const data = await resp.json();

      if (data.ok) {
        alert(`保存成功！版本：v${data.version}`);
        setIsEditing(false);
        setChangeNote("");
        // 重新加载Prompt列表
        await loadPrompts(selectedModule);
        // 重新选择刚才编辑的Prompt（保持用户的上下文）
        const updatedPromptResp = await authFetch(`${API_BASE}/${currentPromptId}`);
        const updatedPromptData = await updatedPromptResp.json();
        if (updatedPromptData.ok) {
          selectPrompt(updatedPromptData.prompt);
        }
      }
    } catch (err: any) {
      console.error("Failed to save prompt:", err);
      alert(`保存失败：${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const loadHistory = async (promptId: string) => {
    try {
      const resp = await authFetch(`${API_BASE}/${promptId}/history`);
      const data = await resp.json();
      if (data.ok) {
        setHistory(data.history);
        setShowHistory(true);
      }
    } catch (err) {
      console.error("Failed to load history:", err);
      alert("加载历史记录失败");
    }
  };

  const viewVersion = async (promptId: string, version: number) => {
    try {
      const resp = await authFetch(`${API_BASE}/${promptId}/history/${version}`);
      const data = await resp.json();
      if (data.ok) {
        const versionData = data.version_data;
        if (confirm(`查看版本 v${version} (${versionData.changed_at})\n变更说明: ${versionData.change_note}\n\n是否加载此版本内容到编辑器？`)) {
          setEditingContent(versionData.content);
          setIsEditing(true);
          setShowHistory(false);
        }
      }
    } catch (err) {
      console.error("Failed to load version:", err);
      alert("加载版本失败");
    }
  };

  const currentModule = modules.find(m => m.id === selectedModule);

  return (
    <div style={{ padding: "20px", maxWidth: "1400px", margin: "0 auto" }}>
      <h1>📝 Prompt 模板管理</h1>
      <p style={{ color: "#666", marginBottom: "20px" }}>
        在线编辑和管理各个模块的提示词模板，修改后立即生效，无需重新部署程序
      </p>

      {/* 模块选择 */}
      <div style={{ marginBottom: "20px", display: "flex", gap: "10px" }}>
        {modules.map((mod) => (
          <button
            key={mod.id}
            onClick={() => setSelectedModule(mod.id)}
            style={{
              padding: "10px 20px",
              border: selectedModule === mod.id ? "2px solid #1890ff" : "1px solid #d9d9d9",
              background: selectedModule === mod.id ? "#e6f7ff" : "#fff",
              borderRadius: "4px",
              cursor: "pointer",
              fontSize: "14px",
            }}
          >
            {mod.icon} {mod.name}
          </button>
        ))}
      </div>

      {currentModule && (
        <div style={{ marginBottom: "20px", padding: "15px", background: "#f5f5f5", borderRadius: "4px" }}>
          <strong>{currentModule.icon} {currentModule.name}</strong>
          <div style={{ color: "#666", marginTop: "5px" }}>
            {currentModule.description}
            {prompts.length > 0 && (
              <span style={{ marginLeft: "10px", color: "#1890ff", fontWeight: 600 }}>
                · {prompts.length} 个版本
              </span>
            )}
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "250px 1fr", gap: "20px" }}>
        {/* 左侧：Prompt列表 */}
        <div>
          <h3>版本列表</h3>
          {prompts.length === 0 ? (
            <div style={{ color: "#999", padding: "20px", textAlign: "center" }}>
              暂无Prompt模板
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {prompts.map((p) => (
                <div
                  key={p.id}
                  onClick={() => selectPrompt(p)}
                  style={{
                    padding: "12px",
                    border: selectedPrompt?.id === p.id ? "2px solid #1890ff" : "1px solid #d9d9d9",
                    borderRadius: "4px",
                    cursor: "pointer",
                    background: selectedPrompt?.id === p.id ? "#e6f7ff" : "#fff",
                  }}
                >
                  <div style={{ fontWeight: 600 }}>{p.name}</div>
                  <div style={{ fontSize: "12px", color: "#666", marginTop: "4px" }}>
                    版本: v{p.version} | {p.is_active ? "✓ 激活" : "未激活"}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 右侧：Prompt编辑器 */}
        <div>
          {selectedPrompt ? (
            <>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                <h3>{selectedPrompt.name} (v{selectedPrompt.version})</h3>
                <div style={{ display: "flex", gap: "10px" }}>
                  <button
                    onClick={() => {
                      loadPrompts(selectedModule);
                      alert("已刷新Prompt列表");
                    }}
                    style={{ padding: "8px 16px", cursor: "pointer", background: "#f0f0f0", border: "1px solid #d9d9d9", borderRadius: "4px" }}
                    title="从数据库重新加载最新数据"
                  >
                    🔄 刷新
                  </button>
                  <button
                    onClick={() => loadHistory(selectedPrompt.id)}
                    style={{ padding: "8px 16px", cursor: "pointer" }}
                  >
                    📜 查看历史
                  </button>
                  {!isEditing ? (
                    <button
                      onClick={() => setIsEditing(true)}
                      style={{ padding: "8px 16px", background: "#1890ff", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer" }}
                    >
                      ✏️ 编辑
                    </button>
                  ) : (
                    <>
                      <button
                        onClick={() => { setIsEditing(false); setEditingContent(selectedPrompt.content); }}
                        style={{ padding: "8px 16px", cursor: "pointer" }}
                      >
                        取消
                      </button>
                      <button
                        onClick={handleSave}
                        disabled={loading}
                        style={{ padding: "8px 16px", background: "#52c41a", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer" }}
                      >
                        {loading ? "保存中..." : "💾 保存"}
                      </button>
                    </>
                  )}
                </div>
              </div>

              {isEditing && (
                <div style={{ marginBottom: "10px" }}>
                  <input
                    type="text"
                    placeholder="变更说明（必填）"
                    value={changeNote}
                    onChange={(e) => setChangeNote(e.target.value)}
                    style={{ width: "100%", padding: "8px", border: "1px solid #d9d9d9", borderRadius: "4px" }}
                  />
                </div>
              )}

              {showHistory ? (
                <div style={{ border: "1px solid #d9d9d9", borderRadius: "4px", padding: "20px", background: "#fff" }}>
                  <h4>变更历史</h4>
                  {history.length === 0 ? (
                    <div style={{ color: "#999", textAlign: "center", padding: "20px" }}>暂无历史记录</div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                      {history.map((h) => (
                        <div
                          key={h.id}
                          style={{ padding: "12px", border: "1px solid #e8e8e8", borderRadius: "4px", cursor: "pointer" }}
                          onClick={() => viewVersion(selectedPrompt.id, h.version)}
                        >
                          <div style={{ fontWeight: 600 }}>版本 v{h.version}</div>
                          <div style={{ fontSize: "12px", color: "#666", marginTop: "4px" }}>
                            {h.change_note}
                          </div>
                          <div style={{ fontSize: "12px", color: "#999", marginTop: "4px" }}>
                            {new Date(h.changed_at).toLocaleString("zh-CN")}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <textarea
                  value={editingContent}
                  onChange={(e) => setEditingContent(e.target.value)}
                  disabled={!isEditing}
                  style={{
                    width: "100%",
                    height: "600px",
                    padding: "12px",
                    border: "1px solid #d9d9d9",
                    borderRadius: "4px",
                    fontFamily: "Consolas, Monaco, monospace",
                    fontSize: "13px",
                    lineHeight: "1.6",
                    background: isEditing ? "#fff" : "#f5f5f5",
                    resize: "vertical",
                  }}
                />
              )}

              <div style={{ marginTop: "10px", padding: "10px", background: "#fffbe6", border: "1px solid #ffe58f", borderRadius: "4px", fontSize: "12px" }}>
                <strong>💡 提示：</strong>
                <ul style={{ margin: "5px 0", paddingLeft: "20px" }}>
                  <li>修改保存后，下次点击"开始提取/开始识别"等按钮时会自动使用最新版本</li>
                  <li>支持Markdown格式，可以使用标题、列表、代码块等</li>
                  <li>每次保存会自动创建新版本，可通过"查看历史"恢复旧版本</li>
                  <li>建议修改前先填写详细的变更说明，便于后续追溯</li>
                </ul>
              </div>
            </>
          ) : (
            <div style={{ textAlign: "center", color: "#999", padding: "60px" }}>
              请选择一个Prompt模板
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

