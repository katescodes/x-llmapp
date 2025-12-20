export type Role = "user" | "assistant" | "system";
export type ChatMode = "normal" | "decision" | "history_decision";
export type DocCategory = "history_case" | "reference_rule" | "general_doc" | "web_snapshot" | "tender_app";

export interface ChatSection {
  id: string;
  title: string;
  markdown: string;
  collapsed: boolean;
}

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  createdAt: string;
  metadata?: Record<string, any>;
  sources?: Source[];
  // 编排器相关
  sections?: ChatSection[];
  followups?: string[];
}

export interface Source {
  id: number;
  kb_id?: string | null;
  kb_name?: string | null;
  doc_id?: string | null;
  doc_name?: string | null;
  title?: string | null;
  url?: string | null;
  score?: number | null;
  snippet?: string | null;
}

export interface LLMProfile {
  key: string;
  name: string;
  description?: string;
  is_default: boolean;
}

export interface UsedModelInfo {
  id?: string | null;
  name?: string | null;
}

export interface ChatSessionMeta {
  last_model?: UsedModelInfo | null;
  last_enable_web?: boolean;
  last_kb_ids?: string[];
  [key: string]: any;
}

export interface LLMModel {
  id: string;
  name: string;
  base_url: string;
  endpoint_path: string;
  model: string;
  temperature: number;
  max_tokens: number;
  top_p?: number;
  presence_penalty?: number;
  frequency_penalty?: number;
  timeout_ms: number;
  extra_headers?: Record<string, any>;
  has_token: boolean;
  token_hint: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface LLMModelCreate {
  name: string;
  base_url: string;
  endpoint_path?: string;
  model: string;
  api_key?: string;
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
  presence_penalty?: number;
  frequency_penalty?: number;
  timeout_ms?: number;
  extra_headers?: Record<string, any>;
}

export interface LLMModelUpdate {
  name?: string;
  base_url?: string;
  endpoint_path?: string;
  model?: string;
  api_key?: string;
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
  presence_penalty?: number;
  frequency_penalty?: number;
  timeout_ms?: number;
  extra_headers?: Record<string, any>;
}

export type DetailLevel = "brief" | "normal" | "detailed";

export interface ChatRequestPayload {
  message: string;
  history: { role: Role; content: string }[];
  llm_key?: string;
  session_id?: string;
  mode?: ChatMode;
  enable_web?: boolean;
  selected_kb_ids?: string[];
  attachment_ids?: string[];
  // 编排器相关
  enable_orchestrator?: boolean;
  detail_level?: DetailLevel;
}

export interface ChatResponsePayload {
  answer: string;
  sources: Source[];
  llm_key: string;
  llm_name: string;
  session_id: string;
  search_mode?: "off" | "smart" | "force";
  used_search: boolean;
  search_queries: string[];
  search_usage_count?: number;
  search_usage_warning?: string | null;
  used_model?: UsedModelInfo | null;
  // 编排器相关
  sections?: ChatSection[];
  followups?: string[];
  orchestrator_meta?: Record<string, any>;
}

export interface ChatSessionSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  default_kb_ids: string[];
  search_mode: "off" | "smart" | "force";
  model_id?: string | null;
  meta?: ChatSessionMeta;
}

export interface ChatHistoryMessage {
  id: string;
  role: Role;
  content: string;
  created_at: string;
  metadata?: Record<string, any>;
}

export interface ChatSessionDetail extends ChatSessionSummary {
  messages: ChatHistoryMessage[];
}

export interface EmbeddingConfig {
  provider?: "http";
  base_url: string;
  endpoint_path: string;
  model: string;
  api_key?: string | null;
  has_api_key?: boolean;
  timeout_ms: number;
  batch_size: number;
  output_dense: boolean;
  output_sparse: boolean;
  dense_dim?: number | null;
  sparse_format: "indices_values";
}

export interface EmbeddingProvider {
  id: string;
  name: string;
  base_url: string;
  endpoint_path: string;
  model: string;
  timeout_ms: number;
  batch_size: number;
  output_dense: boolean;
  output_sparse: boolean;
  dense_dim?: number | null;
  sparse_format: "indices_values" | string;
  has_api_key: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface EmbeddingProviderCreate {
  name: string;
  base_url: string;
  endpoint_path?: string;
  model: string;
  api_key?: string;
  timeout_ms?: number;
  batch_size?: number;
  output_dense?: boolean;
  output_sparse?: boolean;
  dense_dim?: number | null;
  sparse_format?: "indices_values" | string;
}

export interface EmbeddingProviderUpdate {
  name?: string;
  base_url?: string;
  endpoint_path?: string;
  model?: string;
  api_key?: string;
  timeout_ms?: number;
  batch_size?: number;
  output_dense?: boolean;
  output_sparse?: boolean;
  dense_dim?: number | null;
  sparse_format?: "indices_values" | string;
}

export interface SearchConfig {
  provider: "cse" | "html" | "browser";
  mode: "off" | "smart" | "force";
  google_cse_api_key?: string | null;
  google_cse_cx?: string | null;
  has_google_key?: boolean;
  warn: number;
  limit: number;
  max_urls: number;
  results_per_query: number;
}

export interface RetrievalConfig {
  topk_dense: number;
  topk_sparse: number;
  topk_final: number;
  min_sources: number;
  ranker: "rrf" | "weighted";
  rrf_k: number;
  weight_dense: number;
  weight_sparse: number;
}

export interface CrawlConfig {
  max_pages: number;
  concurrency: number;
  timeout_sec: number;
}

export interface AppSettings {
  embedding_config?: EmbeddingConfig | null;
  search: SearchConfig;
  retrieval: RetrievalConfig;
  crawl: CrawlConfig;
}

export interface KbCategory {
  id: string;
  name: string;
  display_name: string;
  color: string;
  icon: string;
  description?: string | null;
  created_at: string;
}

export interface KnowledgeBase {
  id: string;
  name: string;
  description?: string | null;
  category_id?: string | null;
  category_name?: string | null;
  category_display_name?: string | null;
  category_color?: string | null;
  category_icon?: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeBaseDocument {
  id: string;
  filename: string;
  source: string;
  status: string;
  created_at: string;
  updated_at: string;
  meta?: Record<string, any>;
  kb_category: DocCategory;
}

export interface ImportResultItem {
  filename: string;
  status: string;
  doc_id?: string;
  chunks?: number;
  error?: string;
}

export interface ImportResponse {
  items: ImportResultItem[];
}

export * from "./tender";
