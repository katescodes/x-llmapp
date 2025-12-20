import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  ChatMessage,
  ChatMode,
  ChatRequestPayload,
  ChatResponsePayload,
  ChatSessionDetail,
  ChatSessionSummary,
  KnowledgeBase,
  LLMProfile,
  Source,
  DetailLevel,
  ChatSection
} from "../types";
import HeaderBar from "./HeaderBar";
import MessageList from "./MessageList";
import MessageInput from "./MessageInput";
import SourcePanel from "./SourcePanel";
// VoiceRecorder moved to RecordingsList page
import { API_BASE_URL } from "../config/api";

const MAX_HISTORY_TURNS = 8;

const formatTime = (iso: string) => {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
};

const extractErrorMessage = async (
  resp: Response,
  fallback: string
): Promise<string> => {
  try {
    const body = await resp.text();
    if (!body) {
      return `${fallback} (HTTP ${resp.status})`;
    }
    try {
      const parsed = JSON.parse(body);
      if (parsed && typeof parsed === "object") {
        return (
          (parsed as any).detail ||
          (parsed as any).message ||
          JSON.stringify(parsed)
        );
      }
      if (typeof parsed === "string") {
        return parsed;
      }
    } catch {
      return body;
    }
    return body;
  } catch (err) {
    console.warn("读取错误响应失败", err);
    return `${fallback} (HTTP ${resp.status})`;
  }
};

const ChatLayout: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [sourcesCollapsed, setSourcesCollapsed] = useState(false);
  const [pending, setPending] = useState(false);
  const [searchWarning, setSearchWarning] = useState<string | null>(null);

  const [llmOptions, setLlmOptions] = useState<LLMProfile[]>([]);
  const [selectedLLM, setSelectedLLM] = useState<string | undefined>();
  const [activeLLMName, setActiveLLMName] = useState<string | undefined>();

  const [sessionId, setSessionId] = useState<string | undefined>();
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [sessionLoading, setSessionLoading] = useState(false);

  const [kbList, setKbList] = useState<KnowledgeBase[]>([]);
  const [selectedKbIds, setSelectedKbIds] = useState<string[]>([]);
  const [kbLoading, setKbLoading] = useState(false);
  const [enableWeb, setEnableWeb] = useState(false);
  const [chatMode, setChatMode] = useState<ChatMode>("normal");
  // 编排器相关（编排器已默认启用，不再需要开关）
  const [detailLevel, setDetailLevel] = useState<DetailLevel>("normal");
  // Removed voice recording from chat - now in RecordingsList

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messageListRef = useRef<HTMLDivElement>(null);
  const apiBaseUrl = API_BASE_URL;

  const scrollToBottom = () => {
    // 只滚动消息列表容器，不要滚动整个页面
    const el = messageListRef.current;
    if (!el) return;
    requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
    });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const fetchSessions = useCallback(async () => {
    try {
      const resp = await fetch(`${apiBaseUrl}/api/history/sessions?page=1&page_size=50`);
      if (resp.ok) {
        const data: ChatSessionSummary[] = await resp.json();
        setSessions(data);
      }
    } catch (error) {
      console.warn("加载会话列表失败", error);
    }
  }, [apiBaseUrl]);

  const fetchKbs = useCallback(async () => {
    setKbLoading(true);
    try {
      const resp = await fetch(`${apiBaseUrl}/api/kb`);
      if (!resp.ok) throw new Error("获取知识库失败");
      const data: KnowledgeBase[] = await resp.json();
      setKbList(data);
      setSelectedKbIds((prev) => prev.filter((id) => data.some((kb) => kb.id === id)));
    } catch (error) {
      console.warn("加载知识库列表失败", error);
    } finally {
      setKbLoading(false);
    }
  }, [apiBaseUrl]);

  useEffect(() => {
    const fetchLLMs = async () => {
      try {
        const resp = await fetch(`${apiBaseUrl}/api/llms`);
        if (!resp.ok) {
          throw new Error("加载 LLM 列表失败");
        }
        const data: LLMProfile[] = await resp.json();
        setLlmOptions(data);

        const defaultProfile =
          data.find((p) => p.is_default) || (data.length > 0 ? data[0] : null);
        if (defaultProfile) {
          setSelectedLLM(defaultProfile.key);
          setActiveLLMName(defaultProfile.name);
        }
      } catch (err) {
        console.error(err);
        setLlmOptions([
          {
            key: "local",
            name: "本地模型",
            description: "默认本地模型（加载失败兜底）",
            is_default: true
          }
        ]);
        setSelectedLLM("local");
        setActiveLLMName("本地模型");
      }
    };

    fetchLLMs();
    fetchSessions();
    fetchKbs();
  }, [apiBaseUrl, fetchKbs, fetchSessions]);

  const appendAssistantText = (messageId: string, chunk: string) => {
    if (!chunk) return;
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === messageId
          ? {
              ...msg,
              content: `${msg.content || ""}${chunk}`
            }
          : msg
      )
    );
  };

  const finalizeAssistantMessage = (
    messageId: string,
    content: string,
    nextSources?: Source[],
    sections?: ChatSection[],
    followups?: string[]
  ) => {
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === messageId
          ? {
              ...msg,
              content,
              sources: nextSources ?? msg.sources,
              sections: sections ?? msg.sections,
              followups: followups ?? msg.followups
            }
          : msg
      )
    );
  };

  const applyResponseMeta = (
    data: ChatResponsePayload,
    assistantMessageId: string
  ) => {
    finalizeAssistantMessage(
      assistantMessageId,
      data.answer,
      data.sources || [],
      data.sections,
      data.followups
    );
    setSources(data.sources || []);
    const usedModel = data.used_model;
    const resolvedModelName = usedModel?.name || data.llm_name;
    const resolvedModelId = usedModel?.id || data.llm_key;
    if (resolvedModelName) {
      setActiveLLMName(resolvedModelName);
    }
    if (resolvedModelId) {
      setSelectedLLM(resolvedModelId);
    }
    setSessionId(data.session_id);
    if (data.search_usage_warning) {
      setSearchWarning(data.search_usage_warning);
    } else {
      setSearchWarning(null);
    }
    fetchSessions();
  };

  const handleSend = async (text: string, attachmentIds?: string[]) => {
    const trimmed = text.trim();
    if (!trimmed || pending) return;

    const timestamp = new Date().toISOString();
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: trimmed,
      createdAt: timestamp
    };
    const assistantMessageId = `assistant-${Date.now()}`;
    const assistantPlaceholder: ChatMessage = {
      id: assistantMessageId,
      role: "assistant",
      content: "",
      createdAt: timestamp,
      sources: []
    };

    // 历史消息由后端从数据库session中加载，前端不再传递
    // 这样可以统一管理上下文，支持更复杂的摘要和裁剪策略
    const historyPayload: { role: "user" | "assistant" | "system"; content: string }[] = [];

    const payload: ChatRequestPayload = {
      message: trimmed,
      history: historyPayload,  // 空数组，完全依赖后端管理上下文
      llm_key: selectedLLM,
      session_id: sessionId,
      mode: chatMode,  // 回答模式："normal"(标准) | "decision"(方案) | "history_decision"(历史案例)
      enable_web: enableWeb,
      selected_kb_ids: selectedKbIds.length ? selectedKbIds : undefined,
      attachment_ids: attachmentIds,  // 添加附件ID
      // 编排器相关（编排器已默认启用）
      enable_orchestrator: true,  // 编排器默认启用
      detail_level: detailLevel  // 详尽度："brief"(精简) | "normal"(标准) | "detailed"(详细)
    };

    // Debug: 显示选中的知识库和附件
    if (selectedKbIds.length > 0) {
      console.log(`[知识库检索] 已选择 ${selectedKbIds.length} 个知识库:`, selectedKbIds);
    } else {
      console.log('[知识库检索] 未选择知识库，将不使用本地知识库');
    }
    if (attachmentIds && attachmentIds.length > 0) {
      console.log(`[附件] 已上传 ${attachmentIds.length} 个附件:`, attachmentIds);
    }
    
    // Debug: 显示请求参数（特别是 mode 和 detail_level，确保不混淆）
    console.log('[请求参数]', {
      mode: payload.mode,  // 应该是 "normal" | "decision" | "history_decision"
      detail_level: payload.detail_level,  // 应该是 "brief" | "normal" | "detailed"
      enable_orchestrator: payload.enable_orchestrator
    });

    setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);
    setPending(true);
    setSearchWarning(null);
    setSources([]);

    const runStandardRequest = async () => {
      const resp = await fetch(`${apiBaseUrl}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!resp.ok) {
        const errText = await extractErrorMessage(resp, "请求失败");
        throw new Error(errText);
      }
      const data: ChatResponsePayload = await resp.json();
      applyResponseMeta(data, assistantMessageId);
    };

    const runStreamingRequest = async () => {
      const resp = await fetch(`${apiBaseUrl}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!resp.ok || !resp.body) {
        const errText = await extractErrorMessage(resp, "流式接口请求失败");
        throw new Error(errText);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let finished = false;

      const processEventBlock = (block: string) => {
        if (!block.trim()) return;
        const lines = block.split("\n");
        let eventType = "message";
        const dataLines: string[] = [];
        for (const rawLine of lines) {
          const line = rawLine.trim();
          if (!line) continue;
          if (line.startsWith("event:")) {
            eventType = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            dataLines.push(line.slice(5).trimStart());
          }
        }
        const dataPayload = dataLines.join("\n");
        let parsed: any = {};
        if (dataPayload) {
          try {
            parsed = JSON.parse(dataPayload);
          } catch {
            parsed = { text: dataPayload };
          }
        }
        if (eventType === "delta") {
          appendAssistantText(assistantMessageId, parsed?.text || "");
        } else if (eventType === "result") {
          applyResponseMeta(parsed as ChatResponsePayload, assistantMessageId);
          finished = true;
        } else if (eventType === "error") {
          throw new Error(parsed?.detail || "流式输出失败");
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx = buffer.indexOf("\n\n");
        while (idx !== -1) {
          const chunk = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          processEventBlock(chunk);
          idx = buffer.indexOf("\n\n");
        }
      }
      if (buffer.trim()) {
        processEventBlock(buffer);
      }
      if (!finished) {
        throw new Error("流式响应未返回完整结果");
      }
    };

    try {
      await runStreamingRequest();
    } catch (streamErr) {
      console.warn("流式输出失败，回退普通请求", streamErr);
      try {
        await runStandardRequest();
      } catch (err) {
        console.error(err);
        const message =
          err instanceof Error
            ? err.message
            : "调用后端接口失败，请检查后端服务是否已启动。";
        finalizeAssistantMessage(assistantMessageId, message);
      }
    } finally {
      setPending(false);
    }
  };

  const handleLoadSession = async (id: string) => {
    setSessionLoading(true);
    try {
      const resp = await fetch(`${apiBaseUrl}/api/history/sessions/${id}`);
      if (!resp.ok) throw new Error("加载会话失败");
      const data: ChatSessionDetail = await resp.json();
      setSessionId(data.id);
      const restoredKbIds =
        (data.meta?.last_kb_ids as string[] | undefined) ??
        data.default_kb_ids ??
        [];
      setSelectedKbIds(restoredKbIds);
      if (typeof data.meta?.last_enable_web === "boolean") {
        setEnableWeb(data.meta.last_enable_web);
      }
      const lastModel = data.meta?.last_model;
      if (lastModel?.id) {
        setSelectedLLM(lastModel.id);
      } else if (data.model_id) {
        setSelectedLLM(data.model_id);
      }
      if (lastModel?.name) {
        setActiveLLMName(lastModel.name);
      } else if (lastModel?.id) {
        const match = llmOptions.find((opt) => opt.key === lastModel.id);
        if (match) {
          setActiveLLMName(match.name);
        }
      } else if (data.model_id) {
        const match = llmOptions.find((opt) => opt.key === data.model_id);
        if (match) {
          setActiveLLMName(match.name);
        }
      }
      const mapped = data.messages.map((msg) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        createdAt: msg.created_at,
        metadata: msg.metadata,
        sources: (msg.metadata?.sources as Source[]) || []
      }));
      setMessages(mapped);
      const lastAnswer = [...mapped].reverse().find((m) => m.role === "assistant");
      setSources(lastAnswer?.sources || []);
    } catch (error) {
      console.error(error);
      alert("加载会话失败，请查看控制台");
    } finally {
      setSessionLoading(false);
    }
  };

  const handleDeleteSession = async (id: string) => {
    if (!window.confirm("确认删除该会话？")) return;
    try {
      const resp = await fetch(`${apiBaseUrl}/api/history/sessions/${id}`, {
        method: "DELETE"
      });
      if (!resp.ok) throw new Error("删除会话失败");
      if (sessionId === id) {
        handleStartNew();
      }
      fetchSessions();
    } catch (error) {
      console.error(error);
      alert("删除会话失败");
    }
  };

  const handleStartNew = () => {
    setSessionId(undefined);
    setMessages([]);
    setSources([]);
    setSearchWarning(null);
    const currentModelName =
      llmOptions.find((opt) => opt.key === selectedLLM)?.name || activeLLMName;
    if (currentModelName) {
      setActiveLLMName(currentModelName);
    }
  };

  const toggleKbSelection = (kbId: string) => {
    setSelectedKbIds((prev) =>
      prev.includes(kbId) ? prev.filter((id) => id !== kbId) : [...prev, kbId]
    );
  };

  const handleModelChange = (value: string) => {
    setSelectedLLM(value);
    const match = llmOptions.find((opt) => opt.key === value);
    if (match) {
      setActiveLLMName(match.name);
    }
  };

  const manualMode = !enableWeb && selectedKbIds.length === 0;
  const bannerMessage =
    searchWarning || (manualMode ? "未启用检索，将直接由模型回答。" : null);

  return (
    <div className="app-root">
      {/* 左侧侧栏 */}
      <div className="sidebar">
        {/* 固定头部 */}
        <div className="sidebar-header">
          <div className="sidebar-title">亿林GPT · Search</div>
          <div className="sidebar-subtitle">本地大模型 + 联网搜索 + RAG</div>
        </div>

        {/* 可滚动内容区 */}
        <div className="sidebar-scroll">
          <div className="sidebar-label">当前 LLM：</div>
        <select
          value={selectedLLM}
          onChange={(e) => handleModelChange(e.target.value)}
          className="sidebar-select"
        >
          {llmOptions.length === 0 && (
            <option value="">加载模型列表中…</option>
          )}
          {llmOptions.map((llm) => (
            <option key={llm.key} value={llm.key}>
              {llm.name}
            </option>
          ))}
        </select>

        <div className="sidebar-section">
          <div className="sidebar-label">回答模式</div>
          <select
            value={chatMode}
            onChange={(e) => setChatMode(e.target.value as ChatMode)}
            className="sidebar-select"
          >
            <option value="normal">💬 标准模式 - 知识查询</option>
            <option value="decision">🎯 方案建议 - 结构化决策分析</option>
            <option value="history_decision">📋 历史案例决策 - 从经验中学习</option>
          </select>
          <div className="sidebar-hint">
            {chatMode === "normal" && "标准问答模式，适合快速查询知识"}
            {chatMode === "decision" && "输出结构化方案对比、风险分析和执行步骤"}
            {chatMode === "history_decision" && "从历史案例中学习，提供行动指南、风险预警和延伸建议"}
          </div>
        </div>

        <div className="sidebar-section">
          <label className="checkbox-option">
            <input
              type="checkbox"
              checked={enableWeb}
              onChange={(e) => setEnableWeb(e.target.checked)}
            />
            <span>启用联网搜索</span>
          </label>
          <div className="sidebar-hint">勾选后会通过 Google CSE 抓取网页并入库。</div>
        </div>

        {/* 答案详尽度配置（编排器已默认启用，直接显示）*/}
        <div className="sidebar-section">
          <div className="sidebar-label">答案详尽度：</div>
            <div style={{ display: "flex", gap: "8px", marginTop: "8px" }}>
              <label
                className={`pill-button ${detailLevel === "brief" ? "active" : ""}`}
                style={{
                  cursor: "pointer",
                  backgroundColor: detailLevel === "brief" ? "#3b82f6" : "#f3f4f6",
                  color: detailLevel === "brief" ? "#ffffff" : "#111827",
                }}
              >
                <input
                  type="radio"
                  name="detail-level"
                  value="brief"
                  checked={detailLevel === "brief"}
                  onChange={(e) => setDetailLevel(e.target.value as DetailLevel)}
                  style={{ display: "none" }}
                />
                精简
              </label>
              <label
                className={`pill-button ${detailLevel === "normal" ? "active" : ""}`}
                style={{
                  cursor: "pointer",
                  backgroundColor: detailLevel === "normal" ? "#3b82f6" : "#f3f4f6",
                  color: detailLevel === "normal" ? "#ffffff" : "#111827",
                }}
              >
                <input
                  type="radio"
                  name="detail-level"
                  value="normal"
                  checked={detailLevel === "normal"}
                  onChange={(e) => setDetailLevel(e.target.value as DetailLevel)}
                  style={{ display: "none" }}
                />
                标准
              </label>
              <label
                className={`pill-button ${detailLevel === "detailed" ? "active" : ""}`}
                style={{
                  cursor: "pointer",
                  backgroundColor: detailLevel === "detailed" ? "#3b82f6" : "#f3f4f6",
                  color: detailLevel === "detailed" ? "#ffffff" : "#111827",
                }}
              >
                <input
                  type="radio"
                  name="detail-level"
                  value="detailed"
                  checked={detailLevel === "detailed"}
                  onChange={(e) => setDetailLevel(e.target.value as DetailLevel)}
                  style={{ display: "none" }}
                />
                详细
              </label>
            </div>
          <div className="sidebar-hint">
            也可在问题中直接说明（如"简短说明"/"详细展开"）
          </div>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-label">检索知识库（可多选）：</div>
          <div className="kb-chip-container">
            {kbLoading && <div className="sidebar-hint">加载知识库中…</div>}
            {!kbLoading && kbList.length === 0 && (
              <div className="sidebar-hint">暂无知识库，可前往“知识库”页面创建</div>
            )}
            {kbList.map((kb) => (
              <label key={kb.id} className="kb-item">
                <input
                  type="checkbox"
                  checked={selectedKbIds.includes(kb.id)}
                  onChange={() => toggleKbSelection(kb.id)}
                />
                <span>{kb.name}</span>
              </label>
            ))}
          </div>
          {selectedKbIds.length === 0 && (
            <div className="sidebar-hint">未选择知识库时不会使用本地知识库检索。</div>
          )}
          {selectedKbIds.length > 0 && (
            <button
              className="link-button"
              onClick={() => setSelectedKbIds([])}
            >
              清空选择（当前 {selectedKbIds.length} 个）
            </button>
          )}
        </div>

        <div className="sidebar-section">
          <div className="sidebar-label">历史会话</div>
          <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
            <button className="pill-button" onClick={handleStartNew}>
              ＋ 新建
            </button>
            <button className="pill-button" onClick={fetchSessions}>
              刷新
            </button>
          </div>
          <div className="session-list">
            {sessionLoading && <div className="sidebar-hint">加载会话中…</div>}
            {!sessionLoading && sessions.length === 0 && (
              <div className="sidebar-hint">暂无会话记录</div>
            )}
            {sessions.map((session) => (
              <div
                key={session.id}
                className={`session-item ${
                  session.id === sessionId ? "active" : ""
                }`}
                onClick={() => handleLoadSession(session.id)}
              >
                <div>
                  <div className="session-title">
                    {session.title || "未命名会话"}
                  </div>
                  <div className="session-meta">
                    {formatTime(session.updated_at)}
                  </div>
                </div>
                <button
                  className="session-delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteSession(session.id);
                  }}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>

          {/* 固定底部 */}
          <div className="sidebar-footer">
            <div>后端: FastAPI + RAG</div>
            <div>Milvus Lite: data/milvus.db</div>
          </div>
        </div>
      </div>

      {/* 中间 + 右侧 */}
      <div className="main-panel">
        <HeaderBar pending={pending} activeLLMName={activeLLMName} />

        <div className="content-panel">
          <div className="chat-panel">
            {bannerMessage && (
              <div className="warning-banner">{bannerMessage}</div>
            )}
            <div ref={messageListRef} className="chat-messages">
              <MessageList messages={messages} messagesEndRef={messagesEndRef} />
            </div>
            <div className="input-panel">
              <MessageInput onSend={handleSend} pending={pending} apiBaseUrl={apiBaseUrl} />
            </div>
          </div>

          <div
            className={`source-panel-container ${
              sourcesCollapsed ? "collapsed" : ""
            }`}
          >
            <SourcePanel
              sources={sources}
              collapsed={sourcesCollapsed}
              onToggle={() => setSourcesCollapsed((prev) => !prev)}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatLayout;
