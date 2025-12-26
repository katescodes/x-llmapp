import React, { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import {
  LLMModel,
  LLMModelCreate,
  LLMModelUpdate,
  AppSettings,
  EmbeddingConfig,
  EmbeddingProvider,
  EmbeddingProviderCreate,
  SearchConfig,
  RetrievalConfig
} from "../types";
import { API_BASE_URL } from "../config/api";
import { useAuth } from "../contexts/AuthContext";
import { useAuthFetch } from "../hooks/usePermission";

// ASR配置类型
interface ASRConfig {
  id: string;
  name: string;
  api_url: string;
  api_key?: string;
  model_name: string;
  response_format: string;
  is_active: boolean;
  is_default: boolean;
  extra_params?: Record<string, any>;
  usage_count: number;
  last_test_at?: string;
  last_test_status?: 'success' | 'failed';
  last_test_message?: string;
  created_at: string;
  updated_at?: string;
}

interface ASRConfigCreate {
  name: string;
  api_url: string;
  api_key?: string;
  model_name: string;
  response_format: string;
  is_active: boolean;
  is_default: boolean;
  extra_params?: Record<string, any>;
}

type CurlParseResult = {
  url?: URL;
  apiKey?: string;
  optionsDelta: Record<string, any>;
  path?: string;
};

const stripQuotes = (value: string) => {
  if (!value) return value;
  const trimmed = value.trim();
  if (
    (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
    (trimmed.startsWith("'") && trimmed.endsWith("'"))
  ) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
};

const parseCurl = (command: string): CurlParseResult => {
  const cleaned = command
    .replace(/\\\r?\n/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const tokenMatches =
    cleaned.match(/"[^"\\]*(?:\\.[^"\\]*)*"|'[^'\\]*(?:\\.[^'\\]*)*'|\S+/g) ??
    [];
  let method: string | undefined;
  let urlStr: string | undefined;
  const headers: Record<string, string> = {};
  const dataParts: string[] = [];

  const getTokenValue = (index: number) => {
    const token = tokenMatches[index];
    return token ? stripQuotes(token) : "";
  };

  for (let i = 0; i < tokenMatches.length; i += 1) {
    const token = tokenMatches[i];
    const lower = token.toLowerCase();
    if (lower === "curl") continue;

    if (lower === "-x" || lower === "--request") {
      method = getTokenValue(i + 1)?.toUpperCase();
      i += 1;
      continue;
    }

    if (lower === "-h" || lower === "--header") {
      const headerRaw = getTokenValue(i + 1);
      const [key, ...rest] = headerRaw.split(":");
      if (key) headers[key.trim()] = rest.join(":").trim();
      i += 1;
      continue;
    }

    if (
      lower === "-d" ||
      lower === "--data" ||
      lower === "--data-raw" ||
      lower === "--data-binary" ||
      lower === "--data-urlencode"
    ) {
      dataParts.push(getTokenValue(i + 1));
      i += 1;
      continue;
    }

    if (lower === "--url") {
      urlStr = getTokenValue(i + 1);
      i += 1;
      continue;
    }

    if (!lower.startsWith("-") && !urlStr) {
      urlStr = stripQuotes(token);
    }
  }

  let parsedUrl: URL | undefined;
  if (urlStr && /^https?:\/\//i.test(urlStr)) parsedUrl = new URL(urlStr);

  let apiKey: string | undefined;
  Object.entries(headers).forEach(([key, value]) => {
    if (key.toLowerCase() === "authorization") {
      const match = value.match(/Bearer\s+(.+)/i);
      if (match) apiKey = match[1].trim();
    }
  });

  const dataPayload = dataParts.filter(Boolean).join("&");
  let bodyJson: any;
  if (dataPayload) {
    try {
      bodyJson = JSON.parse(dataPayload);
    } catch {
      bodyJson = dataPayload;
    }
  }

  const optionsDelta: Record<string, any> = {};
  if (parsedUrl) optionsDelta.path = `${parsedUrl.pathname}${parsedUrl.search}`;
  if (method) optionsDelta.method = method;
  if (Object.keys(headers).length) optionsDelta.headers = headers;
  if (bodyJson) optionsDelta.bodyTemplate = bodyJson;

  return {
    url: parsedUrl,
    apiKey,
    optionsDelta,
    path: optionsDelta.path,
  };
};

interface LLMSettingsProps {}

// Prompt相关类型
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

const SystemSettings: React.FC<LLMSettingsProps> = () => {
  const { token } = useAuth();
  const authFetch = useAuthFetch();
  
  // Tab state
  const [currentTab, setCurrentTab] = useState<'llm' | 'embedding' | 'app' | 'asr' | 'prompts'>('llm');
  
  // LLM states
  const [models, setModels] = useState<LLMModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingModel, setEditingModel] = useState<LLMModel | null>(null);
  const [formData, setFormData] = useState<LLMModelCreate>({
    name: "",
    base_url: "",
    endpoint_path: "/v1/chat/completions",
    model: "",
    api_key: "",
    temperature: 0.7,
    max_tokens: 2048,
    timeout_ms: 30000,
  });
  const [curlInput, setCurlInput] = useState("");
  const [showCurlHelper, setShowCurlHelper] = useState(false);
  const [appSettings, setAppSettings] = useState<AppSettings | null>(null);
  const [embeddingProviders, setEmbeddingProviders] = useState<EmbeddingProvider[]>([]);
  
  // ASR states
  const [asrConfigs, setAsrConfigs] = useState<ASRConfig[]>([]);
  const [asrLoading, setAsrLoading] = useState(false);
  const [showAsrForm, setShowAsrForm] = useState(false);
  const [editingAsrConfig, setEditingAsrConfig] = useState<ASRConfig | null>(null);
  const [asrFormData, setAsrFormData] = useState<ASRConfigCreate>({
    name: "",
    api_url: "",
    api_key: "",
    model_name: "whisper",
    response_format: "verbose_json",
    is_active: true,
    is_default: false,
    extra_params: {},
  });
  const [asrCurlInput, setAsrCurlInput] = useState("");
  const [showAsrCurlHelper, setShowAsrCurlHelper] = useState(false);
  const [testingAsrConfig, setTestingAsrConfig] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<any>(null);
  
  // Prompt states
  const [promptModules, setPromptModules] = useState<PromptModule[]>([]);
  const [selectedModule, setSelectedModule] = useState<string>("");
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [selectedPrompt, setSelectedPrompt] = useState<PromptTemplate | null>(null);
  const [editingContent, setEditingContent] = useState<string>("");
  const [isEditingPrompt, setIsEditingPrompt] = useState(false);
  const [promptHistory, setPromptHistory] = useState<HistoryItem[]>([]);
  const [showPromptHistory, setShowPromptHistory] = useState(false);
  const [changeNote, setChangeNote] = useState("");
  const [promptLoading, setPromptLoading] = useState(false);
  const [showEmbeddingModal, setShowEmbeddingModal] = useState(false);
  const [editingEmbedding, setEditingEmbedding] = useState<EmbeddingProvider | null>(null);
  const [embeddingFormData, setEmbeddingFormData] = useState<EmbeddingProviderCreate>({
    name: "",
    base_url: "",
    endpoint_path: "/v1/embeddings",
    model: "",
    api_key: "",
    timeout_ms: 30000,
    batch_size: 16,
    output_dense: true,
    output_sparse: true,
    sparse_format: "indices_values",
  });
  const [embeddingCurlInput, setEmbeddingCurlInput] = useState("");
  const [showEmbeddingCurlHelper, setShowEmbeddingCurlHelper] = useState(false);
  const [savingEmbedding, setSavingEmbedding] = useState(false);
  const [searchForm, setSearchForm] = useState<SearchConfig | null>(null);
  const [googleKeyDraft, setGoogleKeyDraft] = useState({ apiKey: "", cx: "" });
  const [savingSearch, setSavingSearch] = useState(false);
  const [testingSearch, setTestingSearch] = useState(false);
  const [retrievalForm, setRetrievalForm] = useState<RetrievalConfig | null>(null);
  const [savingRetrieval, setSavingRetrieval] = useState(false);

  const apiBaseUrl = API_BASE_URL;

  // 加载模型列表
  // ===== ASR配置管理函数 =====
  
  const loadAsrConfigs = async () => {
    if (!token) return;
    
    try {
      setAsrLoading(true);
      const response = await authFetch(`${apiBaseUrl}/api/asr-configs`);
      if (response.ok) {
        const data = await response.json();
        setAsrConfigs(data.items || []);
      }
    } catch (error) {
      console.error("加载ASR配置失败:", error);
    } finally {
      setAsrLoading(false);
    }
  };

  const createAsrConfig = async () => {
    if (!token) return;
    
    try {
      const response = await authFetch(`${apiBaseUrl}/api/asr-configs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(asrFormData),
      });
      
      if (response.ok) {
        alert('ASR配置创建成功');
        setShowAsrForm(false);
        resetAsrForm();
        loadAsrConfigs();
      } else {
        const error = await response.json();
        alert(`创建失败: ${error.detail || '未知错误'}`);
      }
    } catch (error: any) {
      console.error('创建ASR配置失败:', error);
      alert(`创建失败: ${error.message}`);
    }
  };

  const updateAsrConfig = async () => {
    if (!token || !editingAsrConfig) return;
    
    try {
      const response = await authFetch(
        `${apiBaseUrl}/api/asr-configs/${editingAsrConfig.id}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(asrFormData),
        }
      );
      
      if (response.ok) {
        alert('ASR配置更新成功');
        setShowAsrForm(false);
        setEditingAsrConfig(null);
        resetAsrForm();
        loadAsrConfigs();
      } else {
        const error = await response.json();
        alert(`更新失败: ${error.detail || '未知错误'}`);
      }
    } catch (error: any) {
      console.error('更新ASR配置失败:', error);
      alert(`更新失败: ${error.message}`);
    }
  };

  const deleteAsrConfig = async (id: string) => {
    if (!token || !confirm('确定要删除这个ASR配置吗？')) return;
    
    try {
      const response = await authFetch(`${apiBaseUrl}/api/asr-configs/${id}`, {
        method: 'DELETE',
      });
      
      if (response.ok) {
        alert('删除成功');
        loadAsrConfigs();
      } else {
        const error = await response.json();
        alert(`删除失败: ${error.detail || '未知错误'}`);
      }
    } catch (error: any) {
      console.error('删除ASR配置失败:', error);
      alert(`删除失败: ${error.message}`);
    }
  };

  const testAsrConfig = async (id: string) => {
    if (!token) return;
    
    try {
      setTestingAsrConfig(id);
      setTestResult(null);
      
      const response = await authFetch(`${apiBaseUrl}/api/asr-configs/${id}/test`, {
        method: 'POST',
      });
      
      if (response.ok) {
        const result = await response.json();
        setTestResult(result);
        loadAsrConfigs(); // 刷新列表以更新测试状态
      } else {
        const error = await response.json();
        setTestResult({
          success: false,
          message: error.detail || '测试失败',
        });
      }
    } catch (error: any) {
      console.error('测试ASR配置失败:', error);
      setTestResult({
        success: false,
        message: error.message || '测试失败',
      });
    } finally {
      setTestingAsrConfig(null);
    }
  };

  const importAsrFromCurl = async () => {
    if (!token || !asrCurlInput.trim()) {
      alert('请输入curl命令');
      return;
    }
    
    try {
      const response = await authFetch(`${apiBaseUrl}/api/asr-configs/import/curl`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ curl_command: asrCurlInput }),
      });
      
      if (response.ok) {
        alert('从curl导入成功');
        setAsrCurlInput('');
        setShowAsrCurlHelper(false);
        loadAsrConfigs();
      } else {
        const error = await response.json();
        alert(`导入失败: ${error.detail || '未知错误'}`);
      }
    } catch (error: any) {
      console.error('导入ASR配置失败:', error);
      alert(`导入失败: ${error.message}`);
    }
  };

  const resetAsrForm = () => {
    setAsrFormData({
      name: "",
      api_url: "",
      api_key: "",
      model_name: "whisper",
      response_format: "verbose_json",
      is_active: true,
      is_default: false,
      extra_params: {},
    });
  };

  const openEditAsrConfig = (config: ASRConfig) => {
    setEditingAsrConfig(config);
    setAsrFormData({
      name: config.name,
      api_url: config.api_url,
      api_key: config.api_key || "",
      model_name: config.model_name,
      response_format: config.response_format,
      is_active: config.is_active,
      is_default: config.is_default,
      extra_params: config.extra_params || {},
    });
    setShowAsrForm(true);
  };
  
  // ===== Prompt管理函数 =====
  
  const loadPromptModules = async () => {
    try {
      const resp = await fetch(`/api/apps/tender/prompts/modules`);
      const data = await resp.json();
      if (data.ok) {
        setPromptModules(data.modules);
        if (data.modules.length > 0) {
          setSelectedModule(data.modules[0].id);
        }
      }
    } catch (err) {
      console.error("Failed to load modules:", err);
    }
  };

  const loadPrompts = async (module: string) => {
    try {
      const resp = await fetch(`/api/apps/tender/prompts/?module=${module}`);
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
    }
  };

  const selectPrompt = (prompt: PromptTemplate) => {
    setSelectedPrompt(prompt);
    setEditingContent(prompt.content);
    setIsEditingPrompt(false);
    setShowPromptHistory(false);
  };

  const handlePromptSave = async () => {
    if (!selectedPrompt || !changeNote.trim()) {
      alert("请填写变更说明");
      return;
    }

    setPromptLoading(true);
    try {
      const resp = await fetch(`/api/apps/tender/prompts/${selectedPrompt.id}`, {
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
        setIsEditingPrompt(false);
        setChangeNote("");
        loadPrompts(selectedModule);
      }
    } catch (err: any) {
      console.error("Failed to save prompt:", err);
      alert(`保存失败：${err.message}`);
    } finally {
      setPromptLoading(false);
    }
  };

  const loadPromptHistory = async (promptId: string) => {
    try {
      const resp = await fetch(`/api/apps/tender/prompts/${promptId}/history`);
      const data = await resp.json();
      if (data.ok) {
        setPromptHistory(data.history);
        setShowPromptHistory(true);
      }
    } catch (err) {
      console.error("Failed to load history:", err);
    }
  };

  const viewPromptVersion = async (promptId: string, version: number) => {
    try {
      const resp = await fetch(`/api/apps/tender/prompts/${promptId}/history/${version}`);
      const data = await resp.json();
      if (data.ok) {
        const versionData = data.version_data;
        if (confirm(`查看版本 v${version} (${versionData.changed_at})\n变更说明: ${versionData.change_note}\n\n是否加载此版本内容到编辑器？`)) {
          setEditingContent(versionData.content);
          setIsEditingPrompt(true);
          setShowPromptHistory(false);
        }
      }
    } catch (err) {
      console.error("Failed to load version:", err);
    }
  };
  
  // ===== LLM模型管理函数 =====

  const loadModels = async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/api/settings/llm-models`);
      if (response.ok) {
        const data = await response.json();
        setModels(data);
      }
    } catch (error) {
      console.error("加载模型列表失败:", error);
    } finally {
      setLoading(false);
    }
  };

  const loadEmbeddingProviders = async () => {
    try {
      const resp = await fetch(`${apiBaseUrl}/api/settings/embedding-providers`);
      if (resp.ok) {
        const data = await resp.json();
        setEmbeddingProviders(data);
      }
    } catch (error) {
      console.error("加载 Embedding 服务失败:", error);
    }
  };

  const loadAppSettings = async () => {
    try {
      const resp = await fetch(`${apiBaseUrl}/api/settings/app`);
      if (resp.ok) {
        const data = await resp.json();
        setAppSettings(data);
        const searchCfg = {
          ...(data.search || {
            provider: "cse",
            mode: "smart",
            warn: 100,
            limit: 500,
            max_urls: 5,
            results_per_query: 5,
          }),
          google_cse_api_key: "",
          google_cse_cx: "",
          has_google_key: data.search?.has_google_key,
        };
        setSearchForm(searchCfg);
        setRetrievalForm(data.retrieval);
        return;
      }
      throw new Error(await resp.text());
    } catch (error) {
      console.error("加载应用设置失败:", error);
      setSearchForm({
        provider: "cse",
        mode: "smart",
        google_cse_api_key: "",
        google_cse_cx: "",
        has_google_key: false,
        warn: 100,
        limit: 500,
        max_urls: 5,
        results_per_query: 5,
      });
    }
  };

  const handleTestGoogleSearch = async () => {
    if (testingSearch) return;
    setTestingSearch(true);
    try {
      const payload: Record<string, string> = {};
      if (googleKeyDraft.apiKey) {
        payload.google_cse_api_key = googleKeyDraft.apiKey;
      }
      if (googleKeyDraft.cx) {
        payload.google_cse_cx = googleKeyDraft.cx;
      }
      const resp = await fetch(`${apiBaseUrl}/api/settings/search/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || !data?.ok) {
        throw new Error(data?.detail || data?.error || "测试失败");
      }
      alert("Google CSE 连接正常 ✅");
    } catch (error: any) {
      alert(`测试失败：${error?.message || error}`);
    } finally {
      setTestingSearch(false);
    }
  };

  useEffect(() => {
    loadModels();
    loadEmbeddingProviders();
    loadAppSettings();
    if (token && currentTab === 'asr') {
      loadAsrConfigs();
    }
    if (currentTab === 'prompts') {
      loadPromptModules();
    }
  }, [apiBaseUrl, token, currentTab]);
  
  useEffect(() => {
    if (selectedModule) {
      loadPrompts(selectedModule);
    }
  }, [selectedModule]);

  useEffect(() => {
    if (showCreateForm) {
      const original = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => {
        document.body.style.overflow = original;
      };
    }
  }, [showCreateForm]);

  // 重置表单
  const resetForm = () => {
    setFormData({
      name: "",
      base_url: "",
      endpoint_path: "/v1/chat/completions",
      model: "",
      api_key: "",
      temperature: 0.7,
      max_tokens: 2048,
      timeout_ms: 30000,
    });
    setEditingModel(null);
    setShowCreateForm(false);
  };

  const submitModel = async (payload: LLMModelCreate, editingId?: string | null) => {
    try {
      const url = editingId
        ? `${apiBaseUrl}/api/settings/llm-models/${editingId}`
        : `${apiBaseUrl}/api/settings/llm-models`;
      const method = editingId ? "PUT" : "POST";

      const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        await loadModels();
        if (!editingId) {
          resetForm();
        }
        alert(editingId ? "模型更新成功" : "模型创建成功");
        return true;
      } else {
        const error = await response.json();
        alert(`操作失败: ${error.detail || "未知错误"}`);
        return false;
      }
    } catch (error) {
      console.error("提交失败:", error);
      alert("操作失败，请检查网络连接");
      return false;
    }
  };

  // 提交表单
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await submitModel(formData, editingModel?.id);
  };

  // 删除模型
  const handleDelete = async (modelId: string) => {
    if (!confirm("确定要删除这个模型吗？")) return;

    try {
      const response = await fetch(`${apiBaseUrl}/api/settings/llm-models/${modelId}`, {
        method: "DELETE",
      });

      if (response.ok) {
        await loadModels();
        alert("模型删除成功");
      } else {
        let error: any = {};
        try {
          error = await response.json();
        } catch (e) {
          /* ignore */
        }
        alert(`删除失败: ${error.detail || "未知错误"}`);
      }
    } catch (error) {
      console.error("删除失败:", error);
      alert("删除失败，请检查网络连接");
    }
  };

  const parseCurlCommand = async () => {
    if (!curlInput.trim()) {
      alert("请粘贴 curl 命令");
      return;
    }
    try {
      const parsed = parseCurl(curlInput);

      let newData = { ...formData };
      if (parsed.url) {
        newData = {
          ...newData,
          base_url: parsed.url.origin,
          endpoint_path: parsed.path || parsed.url.pathname || newData.endpoint_path,
        };
      }

      if (parsed.apiKey) {
        newData = {
          ...newData,
          api_key: parsed.apiKey,
        };
      }

      const body = parsed.optionsDelta.bodyTemplate;
      if (body && typeof body === "object") {
        newData = {
          ...newData,
          model: body.model || newData.model,
          temperature:
            typeof body.temperature === "number" ? body.temperature : newData.temperature,
          max_tokens:
            typeof body.max_tokens === "number" ? body.max_tokens : newData.max_tokens,
        };
      }

      if (!newData.name.trim()) {
        const hostname = parsed.url?.hostname?.replace(/[^a-z0-9-]/gi, "") || "curl-model";
        newData = {
          ...newData,
          name: `${hostname}-${Date.now().toString(36)}`,
        };
      }

      if (!newData.model.trim()) {
        alert("无法从 curl 中解析出模型名称，请手动填写。");
        setFormData(newData);
        return;
      }

      const baseUrlTrimmed = newData.base_url.trim();
      const endpointPathTrimmed = newData.endpoint_path?.trim() || "/v1/chat/completions";
      newData = {
        ...newData,
        base_url: baseUrlTrimmed,
        endpoint_path: endpointPathTrimmed,
      };

      if (!baseUrlTrimmed || !endpointPathTrimmed) {
        alert("curl 中缺少完整的 URL，请确认命令格式。");
        setFormData(newData);
        return;
      }

      setFormData(newData);
      const ok = await submitModel(newData);
      if (ok) {
        alert("已根据 curl 解析并保存模型。");
      }
    } catch (err) {
      console.error(err);
      alert("解析 curl 命令失败，请确认格式。");
    }
  };

  // 设置默认模型
  const handleSetDefault = async (modelId: string) => {
    try {
      const response = await fetch(`${apiBaseUrl}/api/settings/llm-models/${modelId}/set-default`, {
        method: "POST",
      });

      if (response.ok) {
        await loadModels();
        alert("默认模型设置成功");
      } else {
        const error = await response.json();
        alert(`设置失败: ${error.detail || "未知错误"}`);
      }
    } catch (error) {
      console.error("设置默认模型失败:", error);
      alert("设置失败，请检查网络连接");
    }
  };

  const handleTestConnection = async (modelId: string) => {
    try {
      const response = await fetch(
        `${apiBaseUrl}/api/settings/llm-models/${modelId}/test`,
        { method: "POST" }
      );
      const data = await response.json();
      if (response.ok && data.ok) {
        alert("连接正常 ✅");
      } else {
        const message = data.error || data.detail || "测试失败";
        alert(`连接失败: ${message}`);
      }
    } catch (error) {
      console.error("测试连接失败:", error);
      alert("测试失败，请检查网络连接");
    }
  };

  const resetEmbeddingForm = () => {
    setEmbeddingFormData({
      name: "",
      base_url: "",
      endpoint_path: "/v1/embeddings",
      model: "",
      api_key: "",
      timeout_ms: 30000,
      batch_size: 16,
      output_dense: true,
      output_sparse: true,
      sparse_format: "indices_values",
    });
    setEditingEmbedding(null);
    setShowEmbeddingModal(false);
  };

  const submitEmbeddingProvider = async (
    payload: EmbeddingProviderCreate,
    editingId?: string | null
  ) => {
    try {
      const url = editingId
        ? `${apiBaseUrl}/api/settings/embedding-providers/${editingId}`
        : `${apiBaseUrl}/api/settings/embedding-providers`;
      const method = editingId ? "PUT" : "POST";
      const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "未知错误");
      }
      await loadEmbeddingProviders();
      resetEmbeddingForm();
      alert(editingId ? "Embedding 服务更新成功" : "Embedding 服务创建成功");
      return true;
    } catch (error: any) {
      console.error("Embedding 提交失败:", error);
      alert(error?.message || "操作失败");
      return false;
    }
  };

  const handleEmbeddingSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await submitEmbeddingProvider(embeddingFormData, editingEmbedding?.id);
  };

  const handleEmbeddingDelete = async (providerId: string) => {
    if (!confirm("确定要删除这个 Embedding 服务吗？")) return;
    try {
      const resp = await fetch(
        `${apiBaseUrl}/api/settings/embedding-providers/${providerId}`,
        { method: "DELETE" }
      );
      if (!resp.ok) {
        const error = await resp.json();
        throw new Error(error.detail || "删除失败");
      }
      await loadEmbeddingProviders();
      alert("删除成功");
    } catch (error: any) {
      console.error("删除失败:", error);
      alert(error?.message || "删除失败");
    }
  };

  const handleEmbeddingSetDefault = async (providerId: string) => {
    try {
      const resp = await fetch(
        `${apiBaseUrl}/api/settings/embedding-providers/${providerId}/set-default`,
        { method: "POST" }
      );
      if (!resp.ok) {
        const error = await resp.json();
        throw new Error(error.detail || "设置默认失败");
      }
      await loadEmbeddingProviders();
      alert("默认 Embedding 已更新");
    } catch (error: any) {
      alert(error?.message || "设置默认失败");
    }
  };

  const handleEmbeddingTest = async (providerId: string) => {
    try {
      const resp = await fetch(
        `${apiBaseUrl}/api/settings/embedding-providers/${providerId}/test`,
        { method: "POST" }
      );
      const data = await resp.json();
      if (resp.ok && data.ok) {
        alert("连接正常 ✅");
      } else {
        throw new Error(data.detail || data.error || "测试失败");
      }
    } catch (error: any) {
      alert(`连接失败: ${error?.message || error}`);
    }
  };

  const handleEmbeddingEdit = (provider: EmbeddingProvider) => {
    setEditingEmbedding(provider);
    setEmbeddingFormData({
      name: provider.name,
      base_url: provider.base_url,
      endpoint_path: provider.endpoint_path,
      model: provider.model,
      api_key: "",
      timeout_ms: provider.timeout_ms,
      batch_size: provider.batch_size,
      output_dense: provider.output_dense,
      output_sparse: provider.output_sparse,
      dense_dim: provider.dense_dim ?? undefined,
      sparse_format: provider.sparse_format,
    });
    setShowEmbeddingModal(true);
  };

  const parseEmbeddingCurlCommand = async () => {
    if (!embeddingCurlInput.trim()) {
      alert("请粘贴 curl 命令");
      return;
    }
    try {
      const parsed = parseCurl(embeddingCurlInput);
      let newData = { ...embeddingFormData };
      if (parsed.url) {
        newData = {
          ...newData,
          base_url: parsed.url.origin,
          endpoint_path: parsed.path || parsed.url.pathname || newData.endpoint_path,
        };
      }
      if (parsed.apiKey) {
        newData = { ...newData, api_key: parsed.apiKey };
      }
      const body = parsed.optionsDelta.bodyTemplate;
      if (body && typeof body === "object") {
        if (body.model) newData = { ...newData, model: body.model };
        if (typeof body.output_dense === "boolean") {
          newData = { ...newData, output_dense: body.output_dense };
        }
        if (typeof body.output_sparse === "boolean") {
          newData = { ...newData, output_sparse: body.output_sparse };
        }
      }
      if (!newData.name.trim()) {
        const hostname = parsed.url?.hostname?.replace(/[^a-z0-9-]/gi, "") || "embedding";
        newData = { ...newData, name: `${hostname}-${Date.now().toString(36)}` };
      }
      if (!newData.model.trim()) {
        alert("无法从 curl 中解析出模型名称，请手动填写。");
        setEmbeddingFormData(newData);
        return;
      }
      const base = newData.base_url.trim();
      const path = newData.endpoint_path?.trim() || "/v1/embeddings";
      if (!base || !path) {
        alert("curl 中缺少完整的 URL，请确认命令格式。");
        setEmbeddingFormData({ ...newData, base_url: base, endpoint_path: path });
        return;
      }
      setEmbeddingFormData({ ...newData, base_url: base, endpoint_path: path });
      setShowEmbeddingModal(true);
      alert("已根据 curl 预填表单，请检查后保存。");
    } catch (err) {
      console.error(err);
      alert("解析 curl 命令失败，请确认格式。");
    }
  };

  // 开始编辑
  const handleEdit = (model: LLMModel) => {
    setEditingModel(model);
    setFormData({
      name: model.name,
      base_url: model.base_url,
      endpoint_path: model.endpoint_path,
      model: model.model,
      api_key: "", // 不显示现有token
      temperature: model.temperature,
      max_tokens: model.max_tokens,
      top_p: model.top_p,
      presence_penalty: model.presence_penalty,
      frequency_penalty: model.frequency_penalty,
      timeout_ms: model.timeout_ms,
      extra_headers: model.extra_headers,
    });
    setShowCreateForm(true);
  };

  if (loading) {
    return (
      <div style={{ padding: "20px", textAlign: "center", color: "#e5e7eb" }}>
        加载中...
      </div>
    );
  }

  return (
    <div style={{ padding: "20px", color: "#e5e7eb", height: "100%", overflow: "auto" }}>
      <h2 style={{ margin: 0, marginBottom: "20px" }}>⚙️ 系统设置</h2>
      
      {/* 标签页导航 */}
      <div style={{
        display: "flex",
        gap: "8px",
        marginBottom: "24px",
        borderBottom: "2px solid rgba(148, 163, 184, 0.2)",
        paddingBottom: "8px"
      }}>
        <button
          onClick={() => setCurrentTab('llm')}
          style={{
            padding: "10px 20px",
            background: currentTab === 'llm' ? "rgba(79, 70, 229, 0.2)" : "transparent",
            color: currentTab === 'llm' ? "#22c55e" : "#94a3b8",
            border: "none",
            borderBottom: currentTab === 'llm' ? "2px solid #22c55e" : "none",
            borderRadius: "6px 6px 0 0",
            cursor: "pointer",
            fontSize: "14px",
            fontWeight: currentTab === 'llm' ? "600" : "normal",
            transition: "all 0.2s"
          }}
        >
          🤖 LLM模型
        </button>
        <button
          onClick={() => setCurrentTab('embedding')}
          style={{
            padding: "10px 20px",
            background: currentTab === 'embedding' ? "rgba(79, 70, 229, 0.2)" : "transparent",
            color: currentTab === 'embedding' ? "#22c55e" : "#94a3b8",
            border: "none",
            borderBottom: currentTab === 'embedding' ? "2px solid #22c55e" : "none",
            borderRadius: "6px 6px 0 0",
            cursor: "pointer",
            fontSize: "14px",
            fontWeight: currentTab === 'embedding' ? "600" : "normal",
            transition: "all 0.2s"
          }}
        >
          🔌 向量模型
        </button>
        <button
          onClick={() => setCurrentTab('app')}
          style={{
            padding: "10px 20px",
            background: currentTab === 'app' ? "rgba(79, 70, 229, 0.2)" : "transparent",
            color: currentTab === 'app' ? "#22c55e" : "#94a3b8",
            border: "none",
            borderBottom: currentTab === 'app' ? "2px solid #22c55e" : "none",
            borderRadius: "6px 6px 0 0",
            cursor: "pointer",
            fontSize: "14px",
            fontWeight: currentTab === 'app' ? "600" : "normal",
            transition: "all 0.2s"
          }}
        >
          📱 应用设置
        </button>
        <button
          onClick={() => setCurrentTab('asr')}
          style={{
            padding: "10px 20px",
            background: currentTab === 'asr' ? "rgba(79, 70, 229, 0.2)" : "transparent",
            color: currentTab === 'asr' ? "#22c55e" : "#94a3b8",
            border: "none",
            borderBottom: currentTab === 'asr' ? "2px solid #22c55e" : "none",
            borderRadius: "6px 6px 0 0",
            cursor: "pointer",
            fontSize: "14px",
            fontWeight: currentTab === 'asr' ? "600" : "normal",
            transition: "all 0.2s"
          }}
        >
          🎤 语音转文本
        </button>
        <button
          onClick={() => setCurrentTab('prompts')}
          style={{
            padding: "10px 20px",
            background: currentTab === 'prompts' ? "rgba(79, 70, 229, 0.2)" : "transparent",
            color: currentTab === 'prompts' ? "#22c55e" : "#94a3b8",
            border: "none",
            borderBottom: currentTab === 'prompts' ? "2px solid #22c55e" : "none",
            borderRadius: "6px 6px 0 0",
            cursor: "pointer",
            fontSize: "14px",
            fontWeight: currentTab === 'prompts' ? "600" : "normal",
            transition: "all 0.2s"
          }}
        >
          📝 Prompt管理
        </button>
      </div>

      {/* LLM模型配置标签页 */}
      {currentTab === 'llm' && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px", gap: "12px" }}>
            <h3 style={{ margin: 0 }}>LLM模型配置</h3>
            <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
              <button
                onClick={() => setShowCreateForm(true)}
                style={{
                  padding: "8px 16px",
                  background: "linear-gradient(135deg, #4f46e5, #22c55e)",
                  color: "white",
                  border: "none",
                  borderRadius: "6px",
                  cursor: "pointer",
                }}
              >
                ➕ 新增模型
              </button>
            </div>
          </div>

      <div
        style={{
          background: "rgba(15,23,42,0.8)",
          padding: "12px",
          borderRadius: "8px",
          marginBottom: "16px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
          <div style={{ fontSize: 13, color: "#9ca3af" }}>粘贴上游 curl 命令快速填充</div>
          <button
            onClick={() => setShowCurlHelper((prev) => !prev)}
            style={{
              padding: "4px 10px",
              borderRadius: "6px",
              border: "1px solid rgba(148,163,184,0.4)",
              background: "transparent",
              color: "#e5e7eb",
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            {showCurlHelper ? "收起" : "展开"}
          </button>
        </div>
        {showCurlHelper && (
          <div>
            <textarea
              value={curlInput}
              onChange={(e) => setCurlInput(e.target.value)}
              placeholder={`例如：\ncurl https://api.openai.com/v1/chat/completions \\\n  -H "Authorization: Bearer sk-xxxx" \\\n  -H "Content-Type: application/json" \\\n  -d '{ "model": "gpt-4o-mini" }'`}
              style={{
                width: "100%",
                minHeight: "100px",
                borderRadius: "8px",
                border: "1px solid rgba(148,163,184,0.3)",
                background: "rgba(15, 23, 42, 0.9)",
                color: "#e5e7eb",
                fontSize: 13,
                padding: "8px",
                marginBottom: "8px",
              }}
            />
            <button
              onClick={parseCurlCommand}
              style={{
                padding: "6px 14px",
                borderRadius: "6px",
                border: "none",
                background: "linear-gradient(135deg, #4f46e5, #22c55e)",
                color: "#fff",
                cursor: "pointer",
                fontSize: 13,
              }}
            >
              从 curl 解析
            </button>
          </div>
        )}
      </div>

      {/* LLM 模型列表 */}
      <div style={{ marginBottom: "20px" }}>
        <table style={{
          width: "100%",
          borderCollapse: "collapse",
          background: "rgba(15, 23, 42, 0.9)",
          borderRadius: "8px",
          overflow: "hidden"
        }}>
          <thead>
            <tr style={{ background: "rgba(79, 70, 229, 0.1)" }}>
              <th style={{ padding: "12px", textAlign: "left", borderBottom: "1px solid rgba(148, 163, 184, 0.2)" }}>名称</th>
              <th style={{ padding: "12px", textAlign: "left", borderBottom: "1px solid rgba(148, 163, 184, 0.2)" }}>Base URL</th>
              <th style={{ padding: "12px", textAlign: "left", borderBottom: "1px solid rgba(148, 163, 184, 0.2)" }}>Model</th>
              <th style={{ padding: "12px", textAlign: "left", borderBottom: "1px solid rgba(148, 163, 184, 0.2)" }}>参数</th>
              <th style={{ padding: "12px", textAlign: "left", borderBottom: "1px solid rgba(148, 163, 184, 0.2)" }}>Token</th>
              <th style={{ padding: "12px", textAlign: "left", borderBottom: "1px solid rgba(148, 163, 184, 0.2)" }}>默认</th>
              <th style={{ padding: "12px", textAlign: "left", borderBottom: "1px solid rgba(148, 163, 184, 0.2)" }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {models.map((model) => (
              <tr key={model.id} style={{ borderBottom: "1px solid rgba(148, 163, 184, 0.1)" }}>
                <td style={{ padding: "12px" }}>{model.name}</td>
                <td style={{ padding: "12px", fontSize: "12px", color: "#9ca3af" }}>
                  {model.base_url}{model.endpoint_path}
                </td>
                <td style={{ padding: "12px" }}>{model.model}</td>
                <td style={{ padding: "12px", fontSize: "12px" }}>
                  T:{model.temperature}, Max:{model.max_tokens}
                </td>
                <td style={{ padding: "12px", fontSize: "12px", color: model.has_token ? "#22c55e" : "#ef4444" }}>
                  {model.has_token ? model.token_hint : "未设置"}
                </td>
                <td style={{ padding: "12px" }}>
                  {model.is_default && <span style={{ color: "#22c55e" }}>✓</span>}
                </td>
                <td style={{ padding: "12px" }}>
                  <button
                    onClick={() => handleEdit(model)}
                    style={{
                      padding: "4px 8px",
                      marginRight: "4px",
                      background: "rgba(59, 130, 246, 0.2)",
                      color: "#60a5fa",
                      border: "none",
                      borderRadius: "4px",
                      cursor: "pointer"
                    }}
                  >
                    编辑
                  </button>
                  <button
                    onClick={() => handleTestConnection(model.id)}
                    style={{
                      padding: "4px 8px",
                      marginRight: "4px",
                      background: "rgba(14, 165, 233, 0.2)",
                      color: "#38bdf8",
                      border: "none",
                      borderRadius: "4px",
                      cursor: "pointer"
                    }}
                  >
                    测试
                  </button>
                  {!model.is_default && (
                    <button
                      onClick={() => handleSetDefault(model.id)}
                      style={{
                        padding: "4px 8px",
                        marginRight: "4px",
                        background: "rgba(34, 197, 94, 0.2)",
                        color: "#22c55e",
                        border: "none",
                        borderRadius: "4px",
                        cursor: "pointer"
                      }}
                    >
                      设为默认
                    </button>
                  )}
                  <button
                    onClick={() => handleDelete(model.id)}
                    style={{
                      padding: "4px 8px",
                      background: "rgba(239, 68, 68, 0.2)",
                      color: "#ef4444",
                      border: "none",
                      borderRadius: "4px",
                      cursor: "pointer"
                    }}
                  >
                    删除
                  </button>
                </td>
              </tr>
            ))}
            {models.length === 0 && (
              <tr>
                <td colSpan={7} style={{ padding: "40px", textAlign: "center", color: "#9ca3af" }}>
                  暂无模型配置，请点击"新增模型"开始配置
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Retrieval 配置 */}
      <div
        style={{
          background: "rgba(15,23,42,0.9)",
          padding: "16px",
          borderRadius: "10px",
          marginBottom: "20px",
          border: "1px solid rgba(148,163,184,0.2)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ margin: 0 }}>Retrieval / Ranker</h3>
          <button
            disabled={savingRetrieval || !retrievalForm}
            onClick={async () => {
              if (!retrievalForm) return;
              setSavingRetrieval(true);
              try {
                const resp = await fetch(`${apiBaseUrl}/api/settings/app`, {
                  method: "PUT",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ retrieval: retrievalForm }),
                });
                if (!resp.ok) {
                  const err = await resp.text();
                  throw new Error(err);
                }
                await loadAppSettings();
                alert("Retrieval 配置已保存");
              } catch (error: any) {
                alert(`保存失败: ${error?.message || error}`);
              } finally {
                setSavingRetrieval(false);
              }
            }}
            style={{
              padding: "6px 14px",
              background: "linear-gradient(135deg, #4f46e5, #22c55e)",
              borderRadius: 6,
              border: "none",
              color: "#fff",
              cursor: savingRetrieval ? "not-allowed" : "pointer",
            }}
          >
            {savingRetrieval ? "保存中..." : "保存配置"}
          </button>
        </div>
        {retrievalForm ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))",
              gap: "12px",
              marginTop: "12px",
            }}
          >
            <label style={{ fontSize: 12 }}>
              Dense TopK
              <input
                type="number"
                min={1}
                value={retrievalForm.topk_dense}
                onChange={(e) =>
                  setRetrievalForm({ ...retrievalForm, topk_dense: Number(e.target.value) })
                }
                style={{
                  width: "100%",
                  padding: "8px",
                  borderRadius: 6,
                  border: "1px solid rgba(148,163,184,0.3)",
                  background: "rgba(15,23,42,0.9)",
                  color: "#e5e7eb",
                }}
              />
            </label>
            <label style={{ fontSize: 12 }}>
              Sparse TopK
              <input
                type="number"
                min={1}
                value={retrievalForm.topk_sparse}
                onChange={(e) =>
                  setRetrievalForm({ ...retrievalForm, topk_sparse: Number(e.target.value) })
                }
                style={{
                  width: "100%",
                  padding: "8px",
                  borderRadius: 6,
                  border: "1px solid rgba(148,163,184,0.3)",
                  background: "rgba(15,23,42,0.9)",
                  color: "#e5e7eb",
                }}
              />
            </label>
            <label style={{ fontSize: 12 }}>
              最终返回 TopK
              <input
                type="number"
                min={1}
                value={retrievalForm.topk_final}
                onChange={(e) =>
                  setRetrievalForm({ ...retrievalForm, topk_final: Number(e.target.value) })
                }
                style={{
                  width: "100%",
                  padding: "8px",
                  borderRadius: 6,
                  border: "1px solid rgba(148,163,184,0.3)",
                  background: "rgba(15,23,42,0.9)",
                  color: "#e5e7eb",
                }}
              />
            </label>
            <label style={{ fontSize: 12 }}>
              最少参考条数
              <input
                type="number"
                min={1}
                value={retrievalForm.min_sources}
                onChange={(e) =>
                  setRetrievalForm({
                    ...retrievalForm,
                    min_sources: Number(e.target.value),
                  })
                }
                style={{
                  width: "100%",
                  padding: "8px",
                  borderRadius: 6,
                  border: "1px solid rgba(148,163,184,0.3)",
                  background: "rgba(15,23,42,0.9)",
                  color: "#e5e7eb",
                }}
              />
            </label>
            <label style={{ fontSize: 12 }}>
              Ranker
              <select
                value={retrievalForm.ranker}
                onChange={(e) => setRetrievalForm({ ...retrievalForm, ranker: e.target.value as any })}
                style={{
                  width: "100%",
                  padding: "8px",
                  borderRadius: 6,
                  border: "1px solid rgba(148,163,184,0.3)",
                  background: "rgba(15,23,42,0.9)",
                  color: "#e5e7eb",
                }}
              >
                <option value="rrf">Reciprocal Rank Fusion</option>
                <option value="weighted">Weighted</option>
              </select>
            </label>
            {retrievalForm.ranker === "rrf" ? (
              <label style={{ fontSize: 12 }}>
                RRF K
                <input
                  type="number"
                  min={1}
                  value={retrievalForm.rrf_k}
                  onChange={(e) =>
                    setRetrievalForm({ ...retrievalForm, rrf_k: Number(e.target.value) })
                  }
                  style={{
                    width: "100%",
                    padding: "8px",
                    borderRadius: 6,
                    border: "1px solid rgba(148,163,184,0.3)",
                    background: "rgba(15,23,42,0.9)",
                    color: "#e5e7eb",
                  }}
                />
              </label>
            ) : (
              <>
                <label style={{ fontSize: 12 }}>
                  Dense 权重
                  <input
                    type="number"
                    step={0.05}
                    min={0}
                    max={1}
                    value={retrievalForm.weight_dense}
                    onChange={(e) =>
                      setRetrievalForm({
                        ...retrievalForm,
                        weight_dense: Number(e.target.value),
                      })
                    }
                    style={{
                      width: "100%",
                      padding: "8px",
                      borderRadius: 6,
                      border: "1px solid rgba(148,163,184,0.3)",
                      background: "rgba(15,23,42,0.9)",
                      color: "#e5e7eb",
                    }}
                  />
                </label>
                <label style={{ fontSize: 12 }}>
                  Sparse 权重
                  <input
                    type="number"
                    step={0.05}
                    min={0}
                    max={1}
                    value={retrievalForm.weight_sparse}
                    onChange={(e) =>
                      setRetrievalForm({
                        ...retrievalForm,
                        weight_sparse: Number(e.target.value),
                      })
                    }
                    style={{
                      width: "100%",
                      padding: "8px",
                      borderRadius: 6,
                      border: "1px solid rgba(148,163,184,0.3)",
                      background: "rgba(15,23,42,0.9)",
                      color: "#e5e7eb",
                    }}
                  />
                </label>
              </>
            )}
          </div>
        ) : (
          <div style={{ marginTop: 12, fontSize: 12, color: "#9ca3af" }}>加载中...</div>
        )}
      </div>
        </div>
      )}

      {/* Embedding配置标签页 */}
      {currentTab === 'embedding' && (
        <div>
          {/* Embedding 服务 */}
          <div
            style={{
              background: "rgba(15,23,42,0.9)",
              padding: "16px",
              borderRadius: "10px",
              marginBottom: "20px",
              border: "1px solid rgba(148,163,184,0.2)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0 }}>Embedding 服务（HTTP/HTTPS）</h3>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            <button
              onClick={() => setShowEmbeddingCurlHelper((prev) => !prev)}
              style={{
                padding: "6px 12px",
                borderRadius: 6,
                border: "1px solid rgba(148,163,184,0.3)",
                background: "transparent",
                color: "#e5e7eb",
                cursor: "pointer",
              }}
            >
              {showEmbeddingCurlHelper ? "收起 curl 解析" : "从 curl 解析"}
            </button>
            <button
              onClick={() => {
                setShowEmbeddingModal(true);
                setEditingEmbedding(null);
                resetEmbeddingForm();
                setShowEmbeddingModal(true);
              }}
              style={{
                padding: "6px 14px",
                background: "linear-gradient(135deg, #4f46e5, #22c55e)",
                borderRadius: 6,
                border: "none",
                color: "#fff",
                cursor: "pointer",
              }}
            >
              ➕ 新增 Embedding
            </button>
          </div>
        </div>
        {showEmbeddingCurlHelper && (
          <div style={{ marginTop: 12 }}>
            <textarea
              value={embeddingCurlInput}
              onChange={(e) => setEmbeddingCurlInput(e.target.value)}
              placeholder={`例如：\n${`curl --location --request POST 'https://host/v1/embeddings' \\\n  -H "Authorization: Bearer sk-xxx" \\\n  -H "Content-Type: application/json" \\\n  -d '{ "model": "bge-m3", "input": ["hello"] }'`}`}
              style={{
                width: "100%",
                minHeight: "100px",
                borderRadius: "8px",
                border: "1px solid rgba(148,163,184,0.3)",
                background: "rgba(15, 23, 42, 0.9)",
                color: "#e5e7eb",
                fontSize: 13,
                padding: "8px",
                marginBottom: "8px",
              }}
            />
            <button
              onClick={parseEmbeddingCurlCommand}
              style={{
                padding: "6px 14px",
                borderRadius: "6px",
                border: "none",
                background: "linear-gradient(135deg, #4f46e5, #22c55e)",
                color: "#fff",
                cursor: "pointer",
                fontSize: 13,
              }}
            >
              预填 Embedding 表单
            </button>
          </div>
        )}
        <div style={{ marginTop: 16 }}>
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              background: "rgba(15,23,42,0.9)",
              borderRadius: "8px",
              overflow: "hidden",
            }}
          >
            <thead>
              <tr style={{ background: "rgba(79, 70, 229, 0.1)" }}>
                <th style={{ padding: "12px", textAlign: "left" }}>名称</th>
                <th style={{ padding: "12px", textAlign: "left" }}>Endpoint</th>
                <th style={{ padding: "12px", textAlign: "left" }}>模型</th>
                <th style={{ padding: "12px", textAlign: "left" }}>Dense/Sparse</th>
                <th style={{ padding: "12px", textAlign: "left" }}>Dense 维度</th>
                <th style={{ padding: "12px", textAlign: "left" }}>默认</th>
                <th style={{ padding: "12px", textAlign: "left" }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {embeddingProviders.map((provider) => (
                <tr key={provider.id} style={{ borderBottom: "1px solid rgba(148,163,184,0.1)" }}>
                  <td style={{ padding: "12px" }}>{provider.name}</td>
                  <td style={{ padding: "12px", fontSize: 12, color: "#9ca3af" }}>
                    {provider.base_url}
                    {provider.endpoint_path}
                  </td>
                  <td style={{ padding: "12px" }}>{provider.model}</td>
                  <td style={{ padding: "12px" }}>
                    {provider.output_dense ? "Dense" : ""} {provider.output_sparse ? "Sparse" : ""}
                  </td>
                  <td style={{ padding: "12px" }}>
                    {provider.dense_dim != null ? provider.dense_dim : "未知"}
                  </td>
                  <td style={{ padding: "12px" }}>
                    {provider.is_default ? <span style={{ color: "#22c55e" }}>✓</span> : ""}
                  </td>
                  <td style={{ padding: "12px" }}>
                    <button
                      onClick={() => handleEmbeddingEdit(provider)}
                      style={{
                        padding: "4px 8px",
                        marginRight: 4,
                        background: "rgba(59, 130, 246, 0.2)",
                        color: "#60a5fa",
                        border: "none",
                        borderRadius: 4,
                        cursor: "pointer",
                      }}
                    >
                      编辑
                    </button>
                    <button
                      onClick={() => handleEmbeddingTest(provider.id)}
                      style={{
                        padding: "4px 8px",
                        marginRight: 4,
                        background: "rgba(14, 165, 233, 0.2)",
                        color: "#38bdf8",
                        border: "none",
                        borderRadius: 4,
                        cursor: "pointer",
                      }}
                    >
                      测试
                    </button>
                    {!provider.is_default && (
                      <button
                        onClick={() => handleEmbeddingSetDefault(provider.id)}
                        style={{
                          padding: "4px 8px",
                          marginRight: 4,
                          background: "rgba(34, 197, 94, 0.2)",
                          color: "#22c55e",
                          border: "none",
                          borderRadius: 4,
                          cursor: "pointer",
                        }}
                      >
                        设为默认
                      </button>
                    )}
                    <button
                      onClick={() => handleEmbeddingDelete(provider.id)}
                      style={{
                        padding: "4px 8px",
                        background: "rgba(239, 68, 68, 0.2)",
                        color: "#ef4444",
                        border: "none",
                        borderRadius: 4,
                        cursor: "pointer",
                      }}
                    >
                      删除
                    </button>
                  </td>
                </tr>
              ))}
              {embeddingProviders.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ padding: 32, textAlign: "center", color: "#9ca3af" }}>
                    暂无 Embedding 服务配置，请点击右上角新增
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Google CSE 配置 */}
      <div
        style={{
          background: "rgba(15,23,42,0.9)",
          padding: "16px",
          borderRadius: "10px",
          marginBottom: "20px",
          border: "1px solid rgba(148,163,184,0.2)",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 8,
            flexWrap: "wrap",
          }}
        >
          <h3 style={{ margin: 0 }}>Google CSE 搜索</h3>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              disabled={savingSearch || !searchForm}
              onClick={async () => {
              if (!searchForm) return;
              setSavingSearch(true);
              try {
                const { google_cse_api_key, google_cse_cx, ...rest } = searchForm;
                const resp = await fetch(`${apiBaseUrl}/api/settings/app`, {
                  method: "PUT",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ search: rest }),
                });
                if (!resp.ok) {
                  const err = await resp.text();
                  throw new Error(err);
                }
                if (googleKeyDraft.apiKey || googleKeyDraft.cx) {
                  const respKey = await fetch(`${apiBaseUrl}/api/settings/search/google-key`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      google_cse_api_key: googleKeyDraft.apiKey || undefined,
                      google_cse_cx: googleKeyDraft.cx || undefined,
                    }),
                  });
                  if (!respKey.ok) {
                    const err = await respKey.text();
                    throw new Error(err);
                  }
                  setGoogleKeyDraft({ apiKey: "", cx: "" });
                }
                await loadAppSettings();
                alert("搜索配置已保存");
              } catch (error: any) {
                alert(`保存失败: ${error?.message || error}`);
              } finally {
                setSavingSearch(false);
              }
            }}
            style={{
              padding: "6px 14px",
              background: "linear-gradient(135deg, #4f46e5, #22c55e)",
              borderRadius: 6,
              border: "none",
              color: "#fff",
              cursor: savingSearch ? "not-allowed" : "pointer",
            }}
            >
              {savingSearch ? "保存中..." : "保存配置"}
            </button>
            <button
              type="button"
              disabled={testingSearch}
              onClick={handleTestGoogleSearch}
              style={{
                padding: "6px 14px",
                background: "rgba(14,165,233,0.15)",
                borderRadius: 6,
                border: "1px solid rgba(14,165,233,0.4)",
                color: "#38bdf8",
                cursor: testingSearch ? "not-allowed" : "pointer",
              }}
            >
              {testingSearch ? "测试中..." : "测试连接"}
            </button>
          </div>
        </div>
        {searchForm ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))",
              gap: "12px",
              marginTop: "12px",
            }}
          >
            <label style={{ fontSize: 12 }}>
              模式
              <select
                value={searchForm.mode}
                onChange={(e) => setSearchForm({ ...searchForm, mode: e.target.value as any })}
                style={{
                  width: "100%",
                  padding: "8px",
                  borderRadius: 6,
                  border: "1px solid rgba(148,163,184,0.3)",
                  background: "rgba(15,23,42,0.9)",
                  color: "#e5e7eb",
                }}
              >
                <option value="smart">Smart</option>
                <option value="force">Force</option>
                <option value="off">Off</option>
              </select>
            </label>
            <label style={{ fontSize: 12 }}>
              Warn
              <input
                type="number"
                min={1}
                value={searchForm.warn}
                onChange={(e) => setSearchForm({ ...searchForm, warn: Number(e.target.value) })}
                style={{
                  width: "100%",
                  padding: "8px",
                  borderRadius: 6,
                  border: "1px solid rgba(148,163,184,0.3)",
                  background: "rgba(15,23,42,0.9)",
                  color: "#e5e7eb",
                }}
              />
            </label>
            <label style={{ fontSize: 12 }}>
              Limit
              <input
                type="number"
                min={searchForm.warn}
                value={searchForm.limit}
                onChange={(e) => setSearchForm({ ...searchForm, limit: Number(e.target.value) })}
                style={{
                  width: "100%",
                  padding: "8px",
                  borderRadius: 6,
                  border: "1px solid rgba(148,163,184,0.3)",
                  background: "rgba(15,23,42,0.9)",
                  color: "#e5e7eb",
                }}
              />
            </label>
            <label style={{ fontSize: 12 }}>
              Max URLs
              <input
                type="number"
                min={1}
                value={searchForm.max_urls}
                onChange={(e) => setSearchForm({ ...searchForm, max_urls: Number(e.target.value) })}
                style={{
                  width: "100%",
                  padding: "8px",
                  borderRadius: 6,
                  border: "1px solid rgba(148,163,184,0.3)",
                  background: "rgba(15,23,42,0.9)",
                  color: "#e5e7eb",
                }}
              />
            </label>
            <label style={{ fontSize: 12 }}>
              每 query 条数
              <input
                type="number"
                min={1}
                value={searchForm.results_per_query}
                onChange={(e) =>
                  setSearchForm({ ...searchForm, results_per_query: Number(e.target.value) })
                }
                style={{
                  width: "100%",
                  padding: "8px",
                  borderRadius: 6,
                  border: "1px solid rgba(148,163,184,0.3)",
                  background: "rgba(15,23,42,0.9)",
                  color: "#e5e7eb",
                }}
              />
            </label>
            <label style={{ fontSize: 12 }}>
              API Key
              <input
                type="password"
                value={googleKeyDraft.apiKey}
                placeholder={appSettings?.search?.has_google_key ? "已配置" : ""}
                onChange={(e) => setGoogleKeyDraft({ ...googleKeyDraft, apiKey: e.target.value })}
                style={{
                  width: "100%",
                  padding: "8px",
                  borderRadius: 6,
                  border: "1px solid rgba(148,163,184,0.3)",
                  background: "rgba(15,23,42,0.9)",
                  color: "#e5e7eb",
                }}
              />
            </label>
            <label style={{ fontSize: 12 }}>
              CX
              <input
                type="password"
                value={googleKeyDraft.cx}
                placeholder={appSettings?.search?.has_google_key ? "已配置" : ""}
                onChange={(e) => setGoogleKeyDraft({ ...googleKeyDraft, cx: e.target.value })}
                style={{
                  width: "100%",
                  padding: "8px",
                  borderRadius: 6,
                  border: "1px solid rgba(148,163,184,0.3)",
                  background: "rgba(15,23,42,0.9)",
                  color: "#e5e7eb",
                }}
              />
            </label>
          </div>
        ) : (
          <div style={{ marginTop: 12, fontSize: 12, color: "#9ca3af" }}>加载中...</div>
        )}
      </div>
        </div>
      )}

      {/* 应用设置标签页 */}
      {currentTab === 'app' && (
        <div>
          <h3>应用设置</h3>
          <p style={{ color: "#94a3b8", marginTop: "16px" }}>
            应用级别的配置项将在此处展示
          </p>
        </div>
      )}

      {/* Embedding 新增/编辑表单 */}
      {showEmbeddingModal &&
        createPortal(
          <div
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0, 0, 0, 0.7)",
              zIndex: 2000,
              display: "flex",
              justifyContent: "center",
              alignItems: "flex-start",
              padding: "min(env(safe-area-inset-top), 24px) 12px max(env(safe-area-inset-bottom), 120px)",
              overflowY: "auto",
              boxSizing: "border-box",
              minHeight: "100vh",
            }}
            onClick={(e) => {
              if (e.target === e.currentTarget) {
                resetEmbeddingForm();
              }
            }}
          >
            <div
              style={{
                width: "min(640px, calc(100vw - 24px))",
                maxHeight: "calc(100vh - 160px)",
                background: "rgba(15, 23, 42, 0.97)",
                borderRadius: "18px",
                boxShadow: "0 18px 60px rgba(0,0,0,0.55)",
                padding: "24px",
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
                margin: "20px auto",
                border: "1px solid rgba(148, 163, 184, 0.2)",
              }}
            >
              <h3 style={{ marginTop: 0, marginBottom: 20 }}>
                {editingEmbedding ? "编辑 Embedding 服务" : "新增 Embedding 服务"}
              </h3>
              <form
                onSubmit={handleEmbeddingSubmit}
                style={{
                  flex: 1,
                  overflowY: "auto",
                  paddingRight: 6,
                  marginRight: -6,
                }}
              >
                <div style={{ marginBottom: 16 }}>
                  <label style={{ display: "block", marginBottom: 4 }}>名称 *</label>
                  <input
                    type="text"
                    value={embeddingFormData.name}
                    onChange={(e) =>
                      setEmbeddingFormData({ ...embeddingFormData, name: e.target.value })
                    }
                    required
                    style={{
                      width: "100%",
                      padding: "8px",
                      background: "rgba(255, 255, 255, 0.1)",
                      border: "1px solid rgba(148, 163, 184, 0.3)",
                      borderRadius: "6px",
                      color: "#e5e7eb",
                    }}
                  />
                </div>
                <div style={{ marginBottom: 16 }}>
                  <label style={{ display: "block", marginBottom: 4 }}>Base URL *</label>
                  <input
                    type="url"
                    value={embeddingFormData.base_url}
                    onChange={(e) =>
                      setEmbeddingFormData({ ...embeddingFormData, base_url: e.target.value })
                    }
                    required
                    placeholder="https://embed.example.com"
                    style={{
                      width: "100%",
                      padding: "8px",
                      background: "rgba(255, 255, 255, 0.1)",
                      border: "1px solid rgba(148, 163, 184, 0.3)",
                      borderRadius: "6px",
                      color: "#e5e7eb",
                    }}
                  />
                </div>
                <div style={{ marginBottom: 16 }}>
                  <label style={{ display: "block", marginBottom: 4 }}>Endpoint Path</label>
                  <input
                    type="text"
                    value={embeddingFormData.endpoint_path}
                    onChange={(e) =>
                      setEmbeddingFormData({ ...embeddingFormData, endpoint_path: e.target.value })
                    }
                    placeholder="/v1/embeddings"
                    style={{
                      width: "100%",
                      padding: "8px",
                      background: "rgba(255, 255, 255, 0.1)",
                      border: "1px solid rgba(148, 163, 184, 0.3)",
                      borderRadius: "6px",
                      color: "#e5e7eb",
                    }}
                  />
                </div>
                <div style={{ marginBottom: 16 }}>
                  <label style={{ display: "block", marginBottom: 4 }}>模型 *</label>
                  <input
                    type="text"
                    value={embeddingFormData.model}
                    onChange={(e) =>
                      setEmbeddingFormData({ ...embeddingFormData, model: e.target.value })
                    }
                    required
                    placeholder="bge-m3"
                    style={{
                      width: "100%",
                      padding: "8px",
                      background: "rgba(255, 255, 255, 0.1)",
                      border: "1px solid rgba(148, 163, 184, 0.3)",
                      borderRadius: "6px",
                      color: "#e5e7eb",
                    }}
                  />
                </div>
                <div style={{ marginBottom: 16 }}>
                  <label style={{ display: "block", marginBottom: 4 }}>
                    API Key {editingEmbedding && "(留空表示不更改)"}
                  </label>
                  <input
                    type="password"
                    value={embeddingFormData.api_key || ""}
                    onChange={(e) =>
                      setEmbeddingFormData({ ...embeddingFormData, api_key: e.target.value })
                    }
                    placeholder="sk-..."
                    style={{
                      width: "100%",
                      padding: "8px",
                      background: "rgba(255, 255, 255, 0.1)",
                      border: "1px solid rgba(148, 163, 184, 0.3)",
                      borderRadius: "6px",
                      color: "#e5e7eb",
                    }}
                  />
                </div>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))",
                    gap: 16,
                    marginBottom: 16,
                  }}
                >
                  <label style={{ fontSize: 12 }}>
                    Timeout (ms)
                    <input
                      type="number"
                      min={1000}
                      value={embeddingFormData.timeout_ms}
                      onChange={(e) =>
                        setEmbeddingFormData({
                          ...embeddingFormData,
                          timeout_ms: Number(e.target.value),
                        })
                      }
                      style={{
                        width: "100%",
                        padding: "8px",
                        borderRadius: 6,
                        border: "1px solid rgba(148,163,184,0.3)",
                        background: "rgba(15,23,42,0.9)",
                        color: "#e5e7eb",
                      }}
                    />
                  </label>
                  <label style={{ fontSize: 12 }}>
                    Batch Size
                    <input
                      type="number"
                      min={1}
                      value={embeddingFormData.batch_size}
                      onChange={(e) =>
                        setEmbeddingFormData({
                          ...embeddingFormData,
                          batch_size: Number(e.target.value),
                        })
                      }
                      style={{
                        width: "100%",
                        padding: "8px",
                        borderRadius: 6,
                        border: "1px solid rgba(148,163,184,0.3)",
                        background: "rgba(15,23,42,0.9)",
                        color: "#e5e7eb",
                      }}
                    />
                  </label>
                  <label style={{ fontSize: 12 }}>
                    Dense 维度（可选）
                    <input
                      type="number"
                      min={1}
                      value={embeddingFormData.dense_dim ?? ""}
                      onChange={(e) => {
                        const value = e.target.value;
                        setEmbeddingFormData({
                          ...embeddingFormData,
                          dense_dim: value === "" ? undefined : Number(value),
                        });
                      }}
                      placeholder="自动写入"
                      style={{
                        width: "100%",
                        padding: "8px",
                        borderRadius: 6,
                        border: "1px solid rgba(148,163,184,0.3)",
                        background: "rgba(15,23,42,0.9)",
                        color: "#e5e7eb",
                      }}
                    />
                  </label>
                </div>
                <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
                  <label style={{ fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
                    <input
                      type="checkbox"
                      checked={embeddingFormData.output_dense}
                      onChange={(e) =>
                        setEmbeddingFormData({
                          ...embeddingFormData,
                          output_dense: e.target.checked,
                        })
                      }
                    />
                    输出 Dense
                  </label>
                  <label style={{ fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
                    <input
                      type="checkbox"
                      checked={embeddingFormData.output_sparse}
                      onChange={(e) =>
                        setEmbeddingFormData({
                          ...embeddingFormData,
                          output_sparse: e.target.checked,
                        })
                      }
                    />
                    输出 Sparse
                  </label>
                </div>
                <div
                  style={{
                    display: "flex",
                    gap: 12,
                    justifyContent: "flex-end",
                    position: "sticky",
                    bottom: 0,
                    padding: "12px 0 4px",
                    marginTop: "12px",
                    background: "rgba(15, 23, 42, 0.97)",
                    boxShadow: "0 -8px 10px rgba(15,23,42,0.85)",
                  }}
                >
                  <button
                    type="button"
                    onClick={resetEmbeddingForm}
                    style={{
                      padding: "8px 16px",
                      background: "transparent",
                      color: "#9ca3af",
                      border: "1px solid rgba(148, 163, 184, 0.3)",
                      borderRadius: "6px",
                      cursor: "pointer",
                    }}
                  >
                    取消
                  </button>
                  <button
                    type="submit"
                    disabled={savingEmbedding}
                    style={{
                      padding: "8px 16px",
                      background: "linear-gradient(135deg, #4f46e5, #22c55e)",
                      color: "white",
                      border: "none",
                      borderRadius: "6px",
                      cursor: savingEmbedding ? "not-allowed" : "pointer",
                    }}
                  >
                    {savingEmbedding ? "保存中..." : editingEmbedding ? "更新" : "创建"}
                  </button>
                </div>
              </form>
            </div>
          </div>,
          document.body
        )}

      {/* ASR配置标签页 */}
      {currentTab === 'asr' && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
            <h3 style={{ margin: 0 }}>语音转文本API配置</h3>
            <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
              <button
                onClick={() => setShowAsrForm(true)}
                style={{
                  padding: "8px 16px",
                  background: "linear-gradient(135deg, #4f46e5, #22c55e)",
                  color: "white",
                  border: "none",
                  borderRadius: "6px",
                  cursor: "pointer",
                }}
              >
                ➕ 新增ASR配置
              </button>
            </div>
          </div>

          {/* curl导入助手 */}
          <div
            style={{
              background: "rgba(15,23,42,0.8)",
              padding: "12px",
              borderRadius: "8px",
              marginBottom: "16px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
              <div style={{ fontSize: 13, color: "#9ca3af" }}>从 curl 命令导入配置</div>
              <button
                onClick={() => setShowAsrCurlHelper((prev) => !prev)}
                style={{
                  padding: "4px 10px",
                  borderRadius: "6px",
                  border: "1px solid rgba(148,163,184,0.4)",
                  background: "transparent",
                  color: "#e5e7eb",
                  cursor: "pointer",
                  fontSize: 12,
                }}
              >
                {showAsrCurlHelper ? "收起" : "展开"}
              </button>
            </div>
            {showAsrCurlHelper && (
              <div>
                <textarea
                  value={asrCurlInput}
                  onChange={(e) => setAsrCurlInput(e.target.value)}
                  placeholder={`例如：\ncurl --location --request POST 'https://ai.yglinker.com:6399/v1/audio/transcriptions' \\\n  --form 'model="whisper"' \\\n  --form 'response_format="verbose_json"' \\\n  --form 'file=@"path/to/audio.mp3"'`}
                  style={{
                    width: "100%",
                    minHeight: "100px",
                    borderRadius: "8px",
                    border: "1px solid rgba(148,163,184,0.3)",
                    background: "rgba(15, 23, 42, 0.9)",
                    color: "#e5e7eb",
                    fontSize: 13,
                    padding: "8px",
                    marginBottom: "8px",
                  }}
                />
                <button
                  onClick={importAsrFromCurl}
                  style={{
                    padding: "6px 14px",
                    borderRadius: "6px",
                    border: "none",
                    background: "linear-gradient(135deg, #4f46e5, #22c55e)",
                    color: "#fff",
                    cursor: "pointer",
                    fontSize: 13,
                  }}
                >
                  从 curl 导入
                </button>
              </div>
            )}
          </div>

          {/* ASR配置列表 */}
          {asrLoading ? (
            <div style={{ textAlign: "center", padding: "40px", color: "#94a3b8" }}>
              加载中...
            </div>
          ) : asrConfigs.length === 0 ? (
            <div style={{ textAlign: "center", padding: "40px", color: "#94a3b8" }}>
              <div style={{ fontSize: "48px", marginBottom: "16px" }}>🎤</div>
              <p>还没有ASR配置，点击上方"新增ASR配置"或"从curl导入"添加</p>
            </div>
          ) : (
            <div style={{ marginBottom: "20px" }}>
              <table style={{
                width: "100%",
                borderCollapse: "collapse",
                background: "rgba(15, 23, 42, 0.9)",
                borderRadius: "8px",
                overflow: "hidden"
              }}>
                <thead>
                  <tr style={{ background: "rgba(79, 70, 229, 0.1)" }}>
                    <th style={{ padding: "12px", textAlign: "left", borderBottom: "1px solid rgba(148, 163, 184, 0.2)" }}>名称</th>
                    <th style={{ padding: "12px", textAlign: "left", borderBottom: "1px solid rgba(148, 163, 184, 0.2)" }}>API地址</th>
                    <th style={{ padding: "12px", textAlign: "left", borderBottom: "1px solid rgba(148, 163, 184, 0.2)" }}>模型</th>
                    <th style={{ padding: "12px", textAlign: "left", borderBottom: "1px solid rgba(148, 163, 184, 0.2)" }}>状态</th>
                    <th style={{ padding: "12px", textAlign: "left", borderBottom: "1px solid rgba(148, 163, 184, 0.2)" }}>测试</th>
                    <th style={{ padding: "12px", textAlign: "left", borderBottom: "1px solid rgba(148, 163, 184, 0.2)" }}>使用次数</th>
                    <th style={{ padding: "12px", textAlign: "left", borderBottom: "1px solid rgba(148, 163, 184, 0.2)" }}>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {asrConfigs.map((config) => (
                    <tr key={config.id} style={{ borderBottom: "1px solid rgba(148, 163, 184, 0.1)" }}>
                      <td style={{ padding: "12px" }}>
                        <div style={{ fontWeight: "600" }}>{config.name}</div>
                        {config.is_default && (
                          <span style={{
                            fontSize: "11px",
                            background: "rgba(34, 197, 94, 0.2)",
                            color: "#22c55e",
                            padding: "2px 8px",
                            borderRadius: "4px",
                            marginTop: "4px",
                            display: "inline-block"
                          }}>
                            ✓ 默认
                          </span>
                        )}
                      </td>
                      <td style={{ padding: "12px", fontSize: "13px", color: "#94a3b8" }}>
                        {config.api_url}
                      </td>
                      <td style={{ padding: "12px", fontSize: "13px" }}>
                        {config.model_name}
                        <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>
                          {config.response_format}
                        </div>
                      </td>
                      <td style={{ padding: "12px" }}>
                        <span style={{
                          fontSize: "12px",
                          padding: "4px 8px",
                          borderRadius: "4px",
                          background: config.is_active 
                            ? "rgba(34, 197, 94, 0.2)" 
                            : "rgba(148, 163, 184, 0.2)",
                          color: config.is_active ? "#86efac" : "#94a3b8"
                        }}>
                          {config.is_active ? "激活" : "停用"}
                        </span>
                      </td>
                      <td style={{ padding: "12px", fontSize: "12px" }}>
                        {config.last_test_status && (
                          <div>
                            <span style={{
                              color: config.last_test_status === 'success' ? "#86efac" : "#fca5a5"
                            }}>
                              {config.last_test_status === 'success' ? "✓ 成功" : "✗ 失败"}
                            </span>
                            {config.last_test_at && (
                              <div style={{ fontSize: "10px", color: "#64748b", marginTop: "2px" }}>
                                {new Date(config.last_test_at).toLocaleString('zh-CN')}
                              </div>
                            )}
                          </div>
                        )}
                      </td>
                      <td style={{ padding: "12px", fontSize: "13px" }}>
                        {config.usage_count}
                      </td>
                      <td style={{ padding: "12px" }}>
                        <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                          <button
                            onClick={() => testAsrConfig(config.id)}
                            disabled={testingAsrConfig === config.id}
                            style={{
                              padding: "4px 8px",
                              fontSize: "12px",
                              background: "rgba(96, 165, 250, 0.2)",
                              color: "#93c5fd",
                              border: "1px solid rgba(96, 165, 250, 0.3)",
                              borderRadius: "4px",
                              cursor: testingAsrConfig === config.id ? "not-allowed" : "pointer"
                            }}
                          >
                            {testingAsrConfig === config.id ? "测试中..." : "测试"}
                          </button>
                          <button
                            onClick={() => openEditAsrConfig(config)}
                            style={{
                              padding: "4px 8px",
                              fontSize: "12px",
                              background: "rgba(168, 85, 247, 0.2)",
                              color: "#c084fc",
                              border: "1px solid rgba(168, 85, 247, 0.3)",
                              borderRadius: "4px",
                              cursor: "pointer"
                            }}
                          >
                            编辑
                          </button>
                          <button
                            onClick={() => deleteAsrConfig(config.id)}
                            style={{
                              padding: "4px 8px",
                              fontSize: "12px",
                              background: "rgba(239, 68, 68, 0.2)",
                              color: "#fca5a5",
                              border: "1px solid rgba(239, 68, 68, 0.3)",
                              borderRadius: "4px",
                              cursor: "pointer"
                            }}
                          >
                            删除
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* 测试结果显示 */}
          {testResult && (
            <div style={{
              marginTop: "16px",
              padding: "12px 16px",
              background: testResult.success 
                ? "rgba(34, 197, 94, 0.1)" 
                : "rgba(239, 68, 68, 0.1)",
              border: `1px solid ${testResult.success ? "rgba(34, 197, 94, 0.3)" : "rgba(239, 68, 68, 0.3)"}`,
              borderRadius: "8px",
              color: testResult.success ? "#86efac" : "#fca5a5"
            }}>
              <div style={{ fontWeight: "600", marginBottom: "8px" }}>
                {testResult.success ? "✓ 测试成功" : "✗ 测试失败"}
              </div>
              <div style={{ fontSize: "13px" }}>{testResult.message}</div>
              {testResult.test_result && (
                <div style={{ fontSize: "12px", marginTop: "8px", color: "#94a3b8" }}>
                  <div>响应时间: {testResult.response_time?.toFixed(2)}秒</div>
                  {testResult.test_result.text && (
                    <div>转写预览: {testResult.test_result.text}</div>
                  )}
                </div>
              )}
              <button
                onClick={() => setTestResult(null)}
                style={{
                  marginTop: "8px",
                  padding: "4px 12px",
                  fontSize: "12px",
                  background: "transparent",
                  color: "#94a3b8",
                  border: "1px solid rgba(148, 163, 184, 0.3)",
                  borderRadius: "4px",
                  cursor: "pointer"
                }}
              >
                关闭
              </button>
            </div>
          )}
        </div>
      )}

      {/* ASR配置表单Modal */}
      {showAsrForm &&
        createPortal(
          <div
            onClick={() => {
              setShowAsrForm(false);
              setEditingAsrConfig(null);
              resetAsrForm();
            }}
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.75)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 9999,
              padding: "20px",
            }}
          >
            <div
              onClick={(e) => e.stopPropagation()}
              style={{
                background: "rgba(15, 23, 42, 0.95)",
                borderRadius: "12px",
                width: "100%",
                maxWidth: "600px",
                maxHeight: "90vh",
                overflow: "auto",
                border: "1px solid rgba(148, 163, 184, 0.2)",
              }}
            >
              <div style={{
                padding: "20px",
                borderBottom: "1px solid rgba(148, 163, 184, 0.2)",
                position: "sticky",
                top: 0,
                background: "rgba(15, 23, 42, 0.98)",
                zIndex: 1
              }}>
                <h3 style={{ margin: 0 }}>
                  {editingAsrConfig ? "编辑ASR配置" : "新增ASR配置"}
                </h3>
              </div>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (editingAsrConfig) {
                    updateAsrConfig();
                  } else {
                    createAsrConfig();
                  }
                }}
                style={{ padding: "20px" }}
              >
                <div style={{ marginBottom: "16px" }}>
                  <label style={{ display: "block", marginBottom: "6px", fontSize: "14px" }}>
                    配置名称 *
                  </label>
                  <input
                    required
                    value={asrFormData.name}
                    onChange={(e) => setAsrFormData({ ...asrFormData, name: e.target.value })}
                    placeholder="例如：默认语音转文本API"
                    style={{
                      width: "100%",
                      padding: "8px",
                      borderRadius: "6px",
                      border: "1px solid rgba(148,163,184,0.3)",
                      background: "rgba(15,23,42,0.9)",
                      color: "#e5e7eb",
                    }}
                  />
                </div>

                <div style={{ marginBottom: "16px" }}>
                  <label style={{ display: "block", marginBottom: "6px", fontSize: "14px" }}>
                    API地址 *
                  </label>
                  <input
                    required
                    value={asrFormData.api_url}
                    onChange={(e) => setAsrFormData({ ...asrFormData, api_url: e.target.value })}
                    placeholder="https://ai.yglinker.com:6399/v1/audio/transcriptions"
                    style={{
                      width: "100%",
                      padding: "8px",
                      borderRadius: "6px",
                      border: "1px solid rgba(148,163,184,0.3)",
                      background: "rgba(15,23,42,0.9)",
                      color: "#e5e7eb",
                    }}
                  />
                </div>

                <div style={{ display: "flex", gap: "12px", marginBottom: "16px" }}>
                  <div style={{ flex: 1 }}>
                    <label style={{ display: "block", marginBottom: "6px", fontSize: "14px" }}>
                      模型名称
                    </label>
                    <input
                      value={asrFormData.model_name}
                      onChange={(e) => setAsrFormData({ ...asrFormData, model_name: e.target.value })}
                      placeholder="whisper"
                      style={{
                        width: "100%",
                        padding: "8px",
                        borderRadius: "6px",
                        border: "1px solid rgba(148,163,184,0.3)",
                        background: "rgba(15,23,42,0.9)",
                        color: "#e5e7eb",
                      }}
                    />
                  </div>
                  <div style={{ flex: 1 }}>
                    <label style={{ display: "block", marginBottom: "6px", fontSize: "14px" }}>
                      响应格式
                    </label>
                    <select
                      value={asrFormData.response_format}
                      onChange={(e) => setAsrFormData({ ...asrFormData, response_format: e.target.value })}
                      style={{
                        width: "100%",
                        padding: "8px",
                        borderRadius: "6px",
                        border: "1px solid rgba(148,163,184,0.3)",
                        background: "rgba(15,23,42,0.9)",
                        color: "#e5e7eb",
                      }}
                    >
                      <option value="verbose_json">verbose_json</option>
                      <option value="json">json</option>
                      <option value="text">text</option>
                    </select>
                  </div>
                </div>

                <div style={{ marginBottom: "16px" }}>
                  <label style={{ display: "block", marginBottom: "6px", fontSize: "14px" }}>
                    API密钥（可选）
                  </label>
                  <input
                    type="password"
                    value={asrFormData.api_key}
                    onChange={(e) => setAsrFormData({ ...asrFormData, api_key: e.target.value })}
                    placeholder="留空表示无需密钥"
                    style={{
                      width: "100%",
                      padding: "8px",
                      borderRadius: "6px",
                      border: "1px solid rgba(148,163,184,0.3)",
                      background: "rgba(15,23,42,0.9)",
                      color: "#e5e7eb",
                    }}
                  />
                </div>

                <div style={{ display: "flex", gap: "16px", marginBottom: "16px" }}>
                  <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "14px" }}>
                    <input
                      type="checkbox"
                      checked={asrFormData.is_active}
                      onChange={(e) => setAsrFormData({ ...asrFormData, is_active: e.target.checked })}
                    />
                    激活配置
                  </label>
                  <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "14px" }}>
                    <input
                      type="checkbox"
                      checked={asrFormData.is_default}
                      onChange={(e) => setAsrFormData({ ...asrFormData, is_default: e.target.checked })}
                    />
                    设为默认
                  </label>
                </div>

                <div style={{
                  display: "flex",
                  gap: "12px",
                  justifyContent: "flex-end",
                  marginTop: "20px",
                  paddingTop: "16px",
                  borderTop: "1px solid rgba(148, 163, 184, 0.2)"
                }}>
                  <button
                    type="button"
                    onClick={() => {
                      setShowAsrForm(false);
                      setEditingAsrConfig(null);
                      resetAsrForm();
                    }}
                    style={{
                      padding: "8px 16px",
                      background: "transparent",
                      color: "#9ca3af",
                      border: "1px solid rgba(148, 163, 184, 0.3)",
                      borderRadius: "6px",
                      cursor: "pointer",
                    }}
                  >
                    取消
                  </button>
                  <button
                    type="submit"
                    style={{
                      padding: "8px 16px",
                      background: "linear-gradient(135deg, #4f46e5, #22c55e)",
                      color: "white",
                      border: "none",
                      borderRadius: "6px",
                      cursor: "pointer",
                    }}
                  >
                    {editingAsrConfig ? "更新" : "创建"}
                  </button>
                </div>
              </form>
            </div>
          </div>,
          document.body
        )}

      {/* Prompt管理标签页 */}
      {currentTab === 'prompts' && (
        <div>
          {/* 模块选择 */}
          <div style={{ marginBottom: "20px", display: "flex", gap: "10px", flexWrap: "wrap" }}>
            {promptModules.map((mod) => (
              <button
                key={mod.id}
                onClick={() => setSelectedModule(mod.id)}
                style={{
                  padding: "10px 20px",
                  border: selectedModule === mod.id ? "2px solid #22c55e" : "1px solid rgba(148, 163, 184, 0.2)",
                  background: selectedModule === mod.id ? "rgba(34, 197, 94, 0.2)" : "rgba(15, 23, 42, 0.8)",
                  borderRadius: "6px",
                  cursor: "pointer",
                  fontSize: "14px",
                  color: "#e5e7eb",
                  transition: "all 0.2s"
                }}
              >
                {mod.icon} {mod.name}
              </button>
            ))}
          </div>

          {promptModules.find(m => m.id === selectedModule) && (
            <div style={{ marginBottom: "20px", padding: "15px", background: "rgba(15, 23, 42, 0.8)", borderRadius: "6px", border: "1px solid rgba(148, 163, 184, 0.2)" }}>
              <strong>{promptModules.find(m => m.id === selectedModule)?.icon} {promptModules.find(m => m.id === selectedModule)?.name}</strong>
              <div style={{ color: "#94a3b8", marginTop: "5px", fontSize: "13px" }}>{promptModules.find(m => m.id === selectedModule)?.description}</div>
            </div>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "250px 1fr", gap: "20px" }}>
            {/* 左侧：Prompt列表 */}
            <div>
              <h3 style={{ marginTop: 0 }}>版本列表</h3>
              {prompts.length === 0 ? (
                <div style={{ color: "#94a3b8", padding: "20px", textAlign: "center", background: "rgba(15, 23, 42, 0.8)", borderRadius: "6px" }}>
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
                        border: selectedPrompt?.id === p.id ? "2px solid #22c55e" : "1px solid rgba(148, 163, 184, 0.2)",
                        borderRadius: "6px",
                        cursor: "pointer",
                        background: selectedPrompt?.id === p.id ? "rgba(34, 197, 94, 0.2)" : "rgba(15, 23, 42, 0.8)",
                        transition: "all 0.2s"
                      }}
                    >
                      <div style={{ fontWeight: 600 }}>{p.name}</div>
                      <div style={{ fontSize: "12px", color: "#94a3b8", marginTop: "4px" }}>
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
                    <h3 style={{ margin: 0 }}>{selectedPrompt.name} (v{selectedPrompt.version})</h3>
                    <div style={{ display: "flex", gap: "10px" }}>
                      <button
                        onClick={() => loadPromptHistory(selectedPrompt.id)}
                        style={{ padding: "8px 16px", cursor: "pointer", background: "rgba(79, 70, 229, 0.2)", color: "#e5e7eb", border: "1px solid rgba(148, 163, 184, 0.2)", borderRadius: "6px" }}
                      >
                        📜 查看历史
                      </button>
                      {!isEditingPrompt ? (
                        <button
                          onClick={() => setIsEditingPrompt(true)}
                          style={{ padding: "8px 16px", background: "linear-gradient(135deg, #4f46e5, #22c55e)", color: "white", border: "none", borderRadius: "6px", cursor: "pointer" }}
                        >
                          ✏️ 编辑
                        </button>
                      ) : (
                        <>
                          <button
                            onClick={() => { setIsEditingPrompt(false); setEditingContent(selectedPrompt.content); }}
                            style={{ padding: "8px 16px", cursor: "pointer", background: "rgba(239, 68, 68, 0.2)", color: "#fca5a5", border: "1px solid rgba(239, 68, 68, 0.3)", borderRadius: "6px" }}
                          >
                            取消
                          </button>
                          <button
                            onClick={handlePromptSave}
                            disabled={promptLoading}
                            style={{ padding: "8px 16px", background: "linear-gradient(135deg, #10b981, #22c55e)", color: "white", border: "none", borderRadius: "6px", cursor: promptLoading ? "not-allowed" : "pointer" }}
                          >
                            {promptLoading ? "保存中..." : "💾 保存"}
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {isEditingPrompt && (
                    <div style={{ marginBottom: "10px" }}>
                      <input
                        type="text"
                        placeholder="变更说明（必填）"
                        value={changeNote}
                        onChange={(e) => setChangeNote(e.target.value)}
                        style={{ width: "100%", padding: "8px", border: "1px solid rgba(148, 163, 184, 0.2)", borderRadius: "6px", background: "rgba(15, 23, 42, 0.8)", color: "#e5e7eb" }}
                      />
                    </div>
                  )}

                  {showPromptHistory ? (
                    <div style={{ border: "1px solid rgba(148, 163, 184, 0.2)", borderRadius: "6px", padding: "20px", background: "rgba(15, 23, 42, 0.8)" }}>
                      <h4>变更历史</h4>
                      {promptHistory.length === 0 ? (
                        <div style={{ color: "#94a3b8", textAlign: "center", padding: "20px" }}>暂无历史记录</div>
                      ) : (
                        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                          {promptHistory.map((h) => (
                            <div
                              key={h.id}
                              style={{ padding: "12px", border: "1px solid rgba(148, 163, 184, 0.2)", borderRadius: "6px", cursor: "pointer", background: "rgba(30, 41, 59, 0.8)" }}
                              onClick={() => viewPromptVersion(selectedPrompt.id, h.version)}
                            >
                              <div style={{ fontWeight: 600 }}>版本 v{h.version}</div>
                              <div style={{ fontSize: "12px", color: "#94a3b8", marginTop: "4px" }}>
                                {h.change_note}
                              </div>
                              <div style={{ fontSize: "12px", color: "#6b7280", marginTop: "4px" }}>
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
                      disabled={!isEditingPrompt}
                      style={{
                        width: "100%",
                        height: "500px",
                        padding: "12px",
                        border: "1px solid rgba(148, 163, 184, 0.2)",
                        borderRadius: "6px",
                        fontFamily: "Consolas, Monaco, monospace",
                        fontSize: "13px",
                        lineHeight: "1.6",
                        background: isEditingPrompt ? "rgba(15, 23, 42, 0.8)" : "rgba(30, 41, 59, 0.8)",
                        color: "#e5e7eb",
                        resize: "vertical",
                      }}
                    />
                  )}

                  <div style={{ marginTop: "10px", padding: "10px", background: "rgba(251, 191, 36, 0.1)", border: "1px solid rgba(251, 191, 36, 0.3)", borderRadius: "6px", fontSize: "12px", color: "#fbbf24" }}>
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
                <div style={{ textAlign: "center", color: "#94a3b8", padding: "60px", background: "rgba(15, 23, 42, 0.8)", borderRadius: "6px" }}>
                  请选择一个Prompt模板
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* LLM 新增/编辑表单 */}
      {showCreateForm &&
        createPortal(
          <div
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0, 0, 0, 0.7)",
              zIndex: 2000,
              display: "flex",
              justifyContent: "center",
              alignItems: "flex-start",
              padding: "min(env(safe-area-inset-top), 24px) 12px max(env(safe-area-inset-bottom), 120px)",
              overflowY: "auto",
              boxSizing: "border-box",
              minHeight: "100vh",
            }}
            onClick={(e) => {
              if (e.target === e.currentTarget) {
                resetForm();
              }
            }}
          >
            <div
              style={{
                width: "min(640px, calc(100vw - 24px))",
                maxHeight: "calc(100vh - 160px)",
                background: "rgba(15, 23, 42, 0.97)",
                borderRadius: "18px",
                boxShadow: "0 18px 60px rgba(0,0,0,0.55)",
                padding: "24px",
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
                margin: "20px auto",
                border: "1px solid rgba(148, 163, 184, 0.2)",
              }}
            >
            <h3 style={{ marginTop: 0, marginBottom: "20px" }}>
              {editingModel ? "编辑模型" : "新增模型"}
            </h3>

            <form
              onSubmit={handleSubmit}
              style={{
                flex: 1,
                overflowY: "auto",
                paddingRight: "6px",
                marginRight: "-6px",
              }}
            >
              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", marginBottom: "4px" }}>模型名称 *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                  style={{
                    width: "100%",
                    padding: "8px",
                    background: "rgba(255, 255, 255, 0.1)",
                    border: "1px solid rgba(148, 163, 184, 0.3)",
                    borderRadius: "6px",
                    color: "#e5e7eb"
                  }}
                />
              </div>

              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", marginBottom: "4px" }}>Base URL *</label>
                <input
                  type="url"
                  value={formData.base_url}
                  onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
                  required
                  placeholder="https://api.example.com"
                  style={{
                    width: "100%",
                    padding: "8px",
                    background: "rgba(255, 255, 255, 0.1)",
                    border: "1px solid rgba(148, 163, 184, 0.3)",
                    borderRadius: "6px",
                    color: "#e5e7eb"
                  }}
                />
              </div>

              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", marginBottom: "4px" }}>Endpoint Path</label>
                <input
                  type="text"
                  value={formData.endpoint_path}
                  onChange={(e) => setFormData({ ...formData, endpoint_path: e.target.value })}
                  placeholder="/v1/chat/completions"
                  style={{
                    width: "100%",
                    padding: "8px",
                    background: "rgba(255, 255, 255, 0.1)",
                    border: "1px solid rgba(148, 163, 184, 0.3)",
                    borderRadius: "6px",
                    color: "#e5e7eb"
                  }}
                />
              </div>

              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", marginBottom: "4px" }}>Model *</label>
                <input
                  type="text"
                  value={formData.model}
                  onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                  required
                  placeholder="gpt-3.5-turbo"
                  style={{
                    width: "100%",
                    padding: "8px",
                    background: "rgba(255, 255, 255, 0.1)",
                    border: "1px solid rgba(148, 163, 184, 0.3)",
                    borderRadius: "6px",
                    color: "#e5e7eb"
                  }}
                />
              </div>

              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", marginBottom: "4px" }}>
                  API Key {editingModel && "(留空表示不更改)"}
                </label>
                <input
                  type="password"
                  value={formData.api_key}
                  onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                  placeholder="sk-..."
                  style={{
                    width: "100%",
                    padding: "8px",
                    background: "rgba(255, 255, 255, 0.1)",
                    border: "1px solid rgba(148, 163, 184, 0.3)",
                    borderRadius: "6px",
                    color: "#e5e7eb"
                  }}
                />
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
                  gap: "16px",
                  marginBottom: "16px",
                }}
              >
                <div>
                  <label style={{ display: "block", marginBottom: "4px" }}>Temperature</label>
                  <input
                    type="number"
                    min="0"
                    max="2"
                    step="0.1"
                    value={formData.temperature}
                    onChange={(e) => setFormData({ ...formData, temperature: parseFloat(e.target.value) })}
                    style={{
                      width: "100%",
                      padding: "8px",
                      background: "rgba(255, 255, 255, 0.1)",
                      border: "1px solid rgba(148, 163, 184, 0.3)",
                      borderRadius: "6px",
                      color: "#e5e7eb"
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", marginBottom: "4px" }}>Max Tokens</label>
                  <input
                    type="number"
                    min="1"
                    value={formData.max_tokens}
                    onChange={(e) => setFormData({ ...formData, max_tokens: parseInt(e.target.value) })}
                    style={{
                      width: "100%",
                      padding: "8px",
                      background: "rgba(255, 255, 255, 0.1)",
                      border: "1px solid rgba(148, 163, 184, 0.3)",
                      borderRadius: "6px",
                      color: "#e5e7eb"
                    }}
                  />
                </div>
              </div>

              <div
                style={{
                  display: "flex",
                  gap: "12px",
                  justifyContent: "flex-end",
                  position: "sticky",
                  bottom: 0,
                  padding: "12px 0 4px",
                  marginTop: "12px",
                  background: "rgba(15, 23, 42, 0.97)",
                  boxShadow: "0 -8px 10px rgba(15,23,42,0.85)",
                }}
              >
                <button
                  type="button"
                  onClick={resetForm}
                  style={{
                    padding: "8px 16px",
                    background: "transparent",
                    color: "#9ca3af",
                    border: "1px solid rgba(148, 163, 184, 0.3)",
                    borderRadius: "6px",
                    cursor: "pointer"
                  }}
                >
                  取消
                </button>
                <button
                  type="submit"
                  style={{
                    padding: "8px 16px",
                    background: "linear-gradient(135deg, #4f46e5, #22c55e)",
                    color: "white",
                    border: "none",
                    borderRadius: "6px",
                    cursor: "pointer"
                  }}
                >
                  {editingModel ? "更新" : "创建"}
                </button>
              </div>
            </form>
            </div>
          </div>,
          document.body
        )}
    </div>
  );
};

export default SystemSettings;
