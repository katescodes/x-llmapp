/**
 * 申报书 API
 * 真实后端接口封装
 */
import { api } from '../config/api';

// ==================== Types ====================

export interface DeclareProject {
  project_id: string;
  kb_id: string;
  name: string;
  description?: string;
  owner_id?: string;
  created_at: string;
  updated_at: string;
}

export interface DeclareAsset {
  asset_id: string;
  project_id: string;
  kind: 'notice' | 'company' | 'tech' | 'other';
  filename: string;
  storage_path?: string;
  file_size?: number;
  mime_type?: string;
  document_id?: string;
  doc_version_id?: string;
  meta_json?: any;
  created_at: string;
  updated_at: string;
}

export interface DeclareRun {
  run_id: string;
  project_id: string;
  task_type: string;
  status: 'pending' | 'running' | 'success' | 'failed';
  progress: number;
  message?: string;
  result_json?: any;
  platform_job_id?: string;
  created_at: string;
  updated_at: string;
}

export interface DeclareRequirements {
  project_id: string;
  data_json: {
    eligibility_conditions?: Array<{
      condition: string;
      category?: string;
      evidence_chunk_ids?: string[];
    }>;
    materials_required?: Array<{
      material: string;
      required: boolean;
      format_requirements?: string;
      evidence_chunk_ids?: string[];
    }>;
    deadlines?: Array<{
      event: string;
      date_text: string;
      notes?: string;
      evidence_chunk_ids?: string[];
    }>;
    contact_info?: Array<{
      contact_type: string;
      contact_value: string;
      notes?: string;
      evidence_chunk_ids?: string[];
    }>;
    summary?: string;
  };
  evidence_chunk_ids?: string[];
  retrieval_trace?: any;
  updated_at: string;
}

export interface DeclareDirectoryNode {
  id: string;
  version_id: string;
  project_id: string;
  parent_id?: string;
  order_no: number;
  numbering?: string;
  level: number;
  title: string;
  is_required: boolean;
  source: string;
  evidence_chunk_ids_json?: string[];
  meta_json?: any;
  created_at: string;
}

export interface DeclareSection {
  section_id: string;
  version_id: string;
  project_id: string;
  node_id: string;
  node_title: string;
  content_md: string;
  content_html?: string;
  evidence_chunk_ids?: string[];
  retrieval_trace?: any;
  meta_json?: any;
  created_at: string;
  updated_at: string;
}

// ==================== API Methods ====================

/**
 * 创建申报项目
 */
export async function createProject(input: {
  name: string;
  description?: string;
}): Promise<DeclareProject> {
  return api.post('/api/apps/declare/projects', input);
}

/**
 * 列出申报项目
 */
export async function listProjects(): Promise<DeclareProject[]> {
  return api.get('/api/apps/declare/projects');
}

/**
 * 获取项目详情
 */
export async function getProject(projectId: string): Promise<DeclareProject> {
  return api.get(`/api/apps/declare/projects/${projectId}`);
}

/**
 * 上传资产文件
 */
export async function uploadAssets(
  projectId: string,
  kind: 'notice' | 'user_doc' | 'image' | 'company' | 'tech' | 'other',
  files: File[]
): Promise<{ assets: DeclareAsset[] }> {
  const formData = new FormData();
  formData.append('kind', kind);
  files.forEach(file => {
    formData.append('files', file);
  });
  
  return api.post(`/api/apps/declare/projects/${projectId}/assets/import`, formData);
}

/**
 * 列出资产
 */
export async function listAssets(
  projectId: string,
  kind?: string
): Promise<{ assets: DeclareAsset[] }> {
  const query = kind ? `?kind=${kind}` : '';
  return api.get(`/api/apps/declare/projects/${projectId}/assets${query}`);
}

/**
 * 抽取申报要求
 */
export async function extractRequirements(
  projectId: string,
  options: {
    model_id?: string;
    sync?: number;
  } = {}
): Promise<DeclareRun> {
  const { sync = 0, model_id } = options;
  const query = `?sync=${sync}${model_id ? `&model_id=${model_id}` : ''}`;
  return api.post(`/api/apps/declare/projects/${projectId}/extract/requirements${query}`, {});
}

/**
 * 获取申报要求
 */
export async function getRequirements(projectId: string): Promise<DeclareRequirements | null> {
  const result = await api.get(`/api/apps/declare/projects/${projectId}/requirements`);
  return result?.data ? null : result;
}

/**
 * 生成申报书目录
 */
export async function generateDirectory(
  projectId: string,
  options: {
    model_id?: string;
    sync?: number;
  } = {}
): Promise<DeclareRun> {
  const { sync = 0, model_id } = options;
  const query = `?sync=${sync}${model_id ? `&model_id=${model_id}` : ''}`;
  return api.post(`/api/apps/declare/projects/${projectId}/directory/generate${query}`, {});
}

/**
 * 获取目录节点
 */
export async function getDirectoryNodes(projectId: string): Promise<DeclareDirectoryNode[]> {
  const result = await api.get(`/api/apps/declare/projects/${projectId}/directory/nodes`);
  return result?.nodes || [];
}

/**
 * 自动填充章节
 */
export async function autofillSections(
  projectId: string,
  options: {
    model_id?: string;
    sync?: number;
  } = {}
): Promise<DeclareRun> {
  const { sync = 0, model_id } = options;
  const query = `?sync=${sync}${model_id ? `&model_id=${model_id}` : ''}`;
  return api.post(`/api/apps/declare/projects/${projectId}/sections/autofill${query}`, {});
}

/**
 * 获取章节内容
 */
export async function getSections(
  projectId: string,
  nodeId?: string
): Promise<DeclareSection[]> {
  const query = nodeId ? `?node_id=${nodeId}` : '';
  const result = await api.get(`/api/apps/declare/projects/${projectId}/sections${query}`);
  return result?.sections || [];
}

/**
 * 生成申报书文档
 */
export async function generateDocument(
  projectId: string,
  options: {
    sync?: number;
  } = {}
): Promise<DeclareRun> {
  const { sync = 0 } = options;
  const query = `?sync=${sync}`;
  return api.post(`/api/apps/declare/projects/${projectId}/document/generate${query}`, {});
}

/**
 * 导出 DOCX
 */
export async function exportDocx(projectId: string): Promise<Blob> {
  return api.get(`/api/apps/declare/projects/${projectId}/export/docx`);
}

/**
 * 获取任务运行记录
 */
export async function getRun(runId: string): Promise<DeclareRun> {
  return api.get(`/api/apps/declare/runs/${runId}`);
}

/**
 * 轮询任务运行状态
 */
export async function pollDeclareRun(
  runId: string,
  options: {
    intervalMs?: number;
    timeoutMs?: number;
    onTick?: (run: DeclareRun) => void;
  } = {}
): Promise<DeclareRun> {
  const {
    intervalMs = 1500,
    timeoutMs = 10 * 60 * 1000, // 10分钟
    onTick,
  } = options;

  const startTime = Date.now();

  while (true) {
    const run = await getRun(runId);
    
    if (onTick) {
      onTick(run);
    }

    // 成功或失败都返回
    if (run.status === 'success' || run.status === 'failed') {
      return run;
    }

    // 超时
    if (Date.now() - startTime > timeoutMs) {
      throw new Error(`任务超时: ${runId}`);
    }

    // 等待后继续轮询
    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }
}

/**
 * 下载文件（触发浏览器下载）
 */
export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

