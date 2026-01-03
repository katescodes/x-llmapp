/**
 * 招投标工作台组件 V2
 * - 移除KB选择，改为先建项目→自动创建KB→项目内上传
 * - 使用深色主题，与系统风格一致
 * - 使用统一 API 请求方法（自动带 Authorization）
 */
import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { api } from '../config/api';
import ProjectInfoView from './tender/ProjectInfoView';
import ProjectInfoV3View from './tender/ProjectInfoV3View';
import RiskAnalysisTables from './tender/RiskAnalysisTables';
import DirectoryToolbar from './tender/DirectoryToolbar';
import DocumentCanvas from './tender/DocumentCanvas';
import SampleSidebar, { SamplePreviewState } from './tender/SampleSidebar';
import ReviewTable from './tender/ReviewTable';
import RichTocPreview from './template/RichTocPreview';
import { templateSpecToTemplateStyle, templateSpecToTocItems } from './template/templatePreviewUtils';
import FormatTemplatesPage from './FormatTemplatesPage';
import CustomRulesPage from './CustomRulesPage';
import UserDocumentsPage from './UserDocumentsPage';
import DocumentComponentManagement from './DocumentComponentManagement';
import type { SampleFragment, SampleFragmentPreview, TenderReviewItem } from '../types/tender';
import type { RiskAnalysisData } from '../types/riskAnalysis';
import { countByStatus } from '../types/reviewUtils';

// ==================== 类型定义 ====================

type TenderAssetKind = 'tender' | 'bid' | 'template' | 'custom_rule';

interface TenderProject {
  id: string;
  kb_id: string;
  name: string;
  description?: string;
  created_at?: string;
}

interface TenderAsset {
  id: string;
  project_id: string;
  kind: TenderAssetKind;
  filename?: string;
  mime_type?: string;
  size_bytes?: number;
  kb_doc_id?: string;
  storage_path?: string;
  bidder_name?: string;
  created_at?: string;
  meta_json?: {
    validate_status?: 'valid' | 'invalid' | 'error';
    validate_message?: string;
    [key: string]: any;
  };
}

interface TenderRun {
  id: string;
  project_id?: string;
  kind?: string;
  status: 'pending' | 'running' | 'success' | 'failed';
  progress?: number;
  message?: string;
  result_json?: any;
}

interface ProjectInfo {
  project_id: string;
  data_json: Record<string, any>;
  evidence_chunk_ids: string[];
}

interface DirectoryNode {
  id: string;
  parent_id?: string | null;
  order_no: number;
  numbering: string;
  level: number;
  title: string;
  required: boolean;
  source?: string;
  notes?: string;
  volume?: string;
  evidence_chunk_ids: string[];
  bodyMeta?: {
    source: 'EMPTY' | 'TEMPLATE_SAMPLE' | 'USER' | 'AI';
    fragmentId?: string | null;
    hasContent?: boolean;
  };
}

// RuleSet interface removed - 规则文件现在直接作为资产使用

// 使用统一的 TenderReviewItem 类型（从 types/tender.ts 导入）
// 保留向后兼容的别名
type ReviewItem = TenderReviewItem;

interface Chunk {
  chunk_id: string;
  doc_id: string;
  title: string;
  content: string;
  position?: number;
  highlightText?: string; // 高亮文本（可选）
}

type FormatTemplateOption = { id: string; name: string };

// ==================== 主组件 ====================

export default function TenderWorkspace() {
  // -------------------- 状态管理 --------------------
  const [projects, setProjects] = useState<TenderProject[]>([]);
  const [currentProject, setCurrentProject] = useState<TenderProject | null>(null);
  
  // 新建项目表单
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectDesc, setNewProjectDesc] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false); // 控制创建表单显示/隐藏
  
  // 编辑项目
  const [editingProject, setEditingProject] = useState<TenderProject | null>(null);
  const [editProjectName, setEditProjectName] = useState('');
  const [editProjectDesc, setEditProjectDesc] = useState('');
  
  // 删除项目
  const [deletingProject, setDeletingProject] = useState<TenderProject | null>(null);
  const [deletePlan, setDeletePlan] = useState<any>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  
  // 搜索和批量操作
  const [searchKeyword, setSearchKeyword] = useState('');
  const [selectedProjectIds, setSelectedProjectIds] = useState<Set<string>>(new Set());
  const [isBatchDeleting, setIsBatchDeleting] = useState(false);
  
  // 上传相关
  const [uploadKind, setUploadKind] = useState<TenderAssetKind>('tender');
  const [bidderName, setBidderName] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  
  // 五步工作流
  const [activeTab, setActiveTab] = useState<number>(1);

  // 视图模式：项目列表 / 项目详情（含 Step1-5）/ 嵌入式模板管理 / 自定义规则 / 用户文档
  const [viewMode, setViewMode] = useState<"projectList" | "projectDetail" | "formatTemplates" | "customRules" | "userDocuments">("projectList");
  
  // ========== 新架构：按项目ID存储所有状态 ==========
  
  // 每个项目的完整状态
  interface ProjectState {
    // 数据
    assets: TenderAsset[];
    projectInfo: ProjectInfo | null;
    riskAnalysisData: RiskAnalysisData | null;
    directory: DirectoryNode[];
    directoryGenerationMode: string;  // "fast" | "llm" | "hybrid"
    directoryFastStats: any;
    directoryRefinementStats: any;  // 规则细化统计
    directoryBracketParsingStats: any;  // 括号解析统计
    directoryTemplateMatchingStats: any;  // ✨ 新增：范本填充统计
    reviewItems: ReviewItem[];
    evidenceChunks: Chunk[];
    bodyByNodeId: Record<string, string>;
    
    // 运行状态
    runs: {
      info: TenderRun | null;
      risk: TenderRun | null;
      directory: TenderRun | null;
      review: TenderRun | null;
    };
    
    // UI状态
    samplesOpen: boolean;
    sampleFragments: SampleFragment[];
    samplePreviewById: Record<string, SamplePreviewState>;
    selectedFormatTemplateId: string;
    tocStyleVars: any;
    previewMode: "content" | "format";
    formatPreviewUrl: string;
    formatDownloadUrl: string;
    formatPreviewBlobUrl: string;
    selectedBidder: string;
    selectedRuleAssetIds: string[];
    selectedRulePackIds: string[];  // 新增：选中的自定义规则包ID列表
  }
  
  // 创建空状态
  const createEmptyState = useCallback((): ProjectState => ({
    assets: [],
    projectInfo: null,
    riskAnalysisData: null,
    directory: [],
    directoryGenerationMode: "",
    directoryFastStats: {},
    directoryRefinementStats: {},
    directoryBracketParsingStats: {},
    directoryTemplateMatchingStats: {},  // ✨ 新增
    reviewItems: [],
    evidenceChunks: [],
    bodyByNodeId: {},
    runs: {
      info: null,
      risk: null,
      directory: null,
      review: null,
    },
    samplesOpen: false,
    sampleFragments: [],
    samplePreviewById: {},
    selectedFormatTemplateId: "",
    tocStyleVars: null,
    previewMode: "content",
    formatPreviewUrl: "",
    formatDownloadUrl: "",
    formatPreviewBlobUrl: "",
    selectedBidder: "",
    selectedRuleAssetIds: [],
    selectedRulePackIds: [],  // 新增
  }), []);
  
  // 所有项目的状态存储
  const projectStatesRef = useRef<Map<string, ProjectState>>(new Map());
  
  // 强制重渲染计数器
  const [renderCounter, setRenderCounter] = useState(0);
  const forceRerender = useCallback(() => setRenderCounter(c => c + 1), []);
  
  // 获取当前项目状态
  const getProjectState = useCallback((projectId: string): ProjectState => {
    let state = projectStatesRef.current.get(projectId);
    if (!state) {
      state = createEmptyState();
      // 尝试从localStorage恢复formatTemplateId
      const savedTemplateId = localStorage.getItem(`tender.formatTemplateId.${projectId}`);
      if (savedTemplateId) {
        state.selectedFormatTemplateId = savedTemplateId;
      }
      projectStatesRef.current.set(projectId, state);
    }
    return state;
  }, [createEmptyState]);
  
  // 更新项目状态
  const updateProjectState = useCallback((projectId: string, updates: Partial<ProjectState> | ((prev: ProjectState) => Partial<ProjectState>)) => {
    const current = getProjectState(projectId);
    const updateObj = typeof updates === 'function' ? updates(current) : updates;
    const updated = { ...current, ...updateObj };
    projectStatesRef.current.set(projectId, updated);
    
    // 如果是当前项目，触发重渲染
    if (currentProject?.id === projectId) {
      forceRerender();
    }
  }, [currentProject?.id, getProjectState, forceRerender]);
  
  // 当前项目状态（用于渲染）
  const state = currentProject ? getProjectState(currentProject.id) : createEmptyState();
  
  // ========== 兼容层：提供旧的setState接口 ==========
  // 这样可以保持旧代码不变，逐步迁移
  
  const assets = state.assets;
  const setAssets = useCallback((value: TenderAsset[] | ((prev: TenderAsset[]) => TenderAsset[])) => {
    if (!currentProject) return;
    const newValue = typeof value === 'function' ? value(state.assets) : value;
    updateProjectState(currentProject.id, { assets: newValue });
  }, [currentProject, state.assets, updateProjectState]);
  
  const projectInfo = state.projectInfo;
  const setProjectInfo = useCallback((value: ProjectInfo | null) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { projectInfo: value });
  }, [currentProject, updateProjectState]);
  
  const infoRun = state.runs.info;
  const setInfoRun = useCallback((value: TenderRun | null) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { runs: { ...state.runs, info: value } });
  }, [currentProject, state.runs, updateProjectState]);
  
  const riskAnalysisData = state.riskAnalysisData;
  const setRiskAnalysisData = useCallback((value: RiskAnalysisData | null) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { riskAnalysisData: value });
  }, [currentProject, updateProjectState]);
  
  const riskRun = state.runs.risk;
  const setRiskRun = useCallback((value: TenderRun | null) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { runs: { ...state.runs, risk: value } });
  }, [currentProject, state.runs, updateProjectState]);
  
  const directory = state.directory;
  const setDirectory = useCallback((value: DirectoryNode[] | ((prev: DirectoryNode[]) => DirectoryNode[])) => {
    if (!currentProject) return;
    const newValue = typeof value === 'function' ? value(state.directory) : value;
    updateProjectState(currentProject.id, { directory: newValue });
  }, [currentProject, state.directory, updateProjectState]);
  
  const dirRun = state.runs.directory;
  const setDirRun = useCallback((value: TenderRun | null) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { runs: { ...state.runs, directory: value } });
  }, [currentProject, state.runs, updateProjectState]);
  
  const directoryGenerationMode = state.directoryGenerationMode;
  const setDirectoryGenerationMode = useCallback((value: string) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { directoryGenerationMode: value });
  }, [currentProject, updateProjectState]);
  
  const directoryFastStats = state.directoryFastStats;
  const directoryRefinementStats = state.directoryRefinementStats;
  const directoryBracketParsingStats = state.directoryBracketParsingStats;
  const directoryTemplateMatchingStats = state.directoryTemplateMatchingStats;  // ✨ 新增
  const setDirectoryFastStats = useCallback((value: any) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { directoryFastStats: value });
  }, [currentProject, updateProjectState]);
  
  const setDirectoryRefinementStats = useCallback((value: any) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { directoryRefinementStats: value });
  }, [currentProject, updateProjectState]);
  
  const setDirectoryBracketParsingStats = useCallback((value: any) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { directoryBracketParsingStats: value });
  }, [currentProject, updateProjectState]);
  
  const setDirectoryTemplateMatchingStats = useCallback((value: any) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { directoryTemplateMatchingStats: value });
  }, [currentProject, updateProjectState]);
  
  const bidResponses = state.bidResponses;
  const setBidResponses = useCallback((value: BidResponse[]) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { bidResponses: value });
  }, [currentProject, updateProjectState]);
  
  const bidResponseStats = state.bidResponseStats;
  const setBidResponseStats = useCallback((value: BidResponseStats[]) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { bidResponseStats: value });
  }, [currentProject, updateProjectState]);
  
  const bidResponseRun = state.runs.bidResponse;
  const setBidResponseRun = useCallback((value: TenderRun | null) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { runs: { ...state.runs, bidResponse: value } });
  }, [currentProject, state.runs, updateProjectState]);
  
  const bodyByNodeId = state.bodyByNodeId;
  const setBodyByNodeId = useCallback((value: Record<string, string> | ((prev: Record<string, string>) => Record<string, string>)) => {
    if (!currentProject) return;
    const newValue = typeof value === 'function' ? value(state.bodyByNodeId) : value;
    updateProjectState(currentProject.id, { bodyByNodeId: newValue });
  }, [currentProject, state.bodyByNodeId, updateProjectState]);
  
  const samplesOpen = state.samplesOpen;
  const setSamplesOpen = useCallback((value: boolean | ((prev: boolean) => boolean)) => {
    if (!currentProject) return;
    const newValue = typeof value === 'function' ? value(state.samplesOpen) : value;
    updateProjectState(currentProject.id, { samplesOpen: newValue });
  }, [currentProject, state.samplesOpen, updateProjectState]);
  
  const sampleFragments = state.sampleFragments;
  const setSampleFragments = useCallback((value: SampleFragment[]) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { sampleFragments: value });
  }, [currentProject, updateProjectState]);
  
  const samplePreviewById = state.samplePreviewById;
  const setSamplePreviewById = useCallback((value: Record<string, SamplePreviewState> | ((prev: Record<string, SamplePreviewState>) => Record<string, SamplePreviewState>)) => {
    if (!currentProject) return;
    const newValue = typeof value === 'function' ? value(state.samplePreviewById) : value;
    updateProjectState(currentProject.id, { samplePreviewById: newValue });
  }, [currentProject, state.samplePreviewById, updateProjectState]);
  
  const selectedFormatTemplateId = state.selectedFormatTemplateId;
  const setSelectedFormatTemplateId = useCallback((value: string) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { selectedFormatTemplateId: value });
    localStorage.setItem(`tender.formatTemplateId.${currentProject.id}`, value);
  }, [currentProject, updateProjectState]);
  
  const tocStyleVars = state.tocStyleVars;
  const setTocStyleVars = useCallback((value: any) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { tocStyleVars: value });
  }, [currentProject, updateProjectState]);
  
  const previewMode = state.previewMode;
  const setPreviewMode = useCallback((value: "content" | "format") => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { previewMode: value });
  }, [currentProject, updateProjectState]);
  
  const formatPreviewUrl = state.formatPreviewUrl;
  const setFormatPreviewUrl = useCallback((value: string) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { formatPreviewUrl: value });
  }, [currentProject, updateProjectState]);
  
  const formatDownloadUrl = state.formatDownloadUrl;
  const setFormatDownloadUrl = useCallback((value: string) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { formatDownloadUrl: value });
  }, [currentProject, updateProjectState]);
  
  const formatPreviewBlobUrl = state.formatPreviewBlobUrl;
  const setFormatPreviewBlobUrl = useCallback((value: string) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { formatPreviewBlobUrl: value });
  }, [currentProject, updateProjectState]);
  
  const reviewItems = state.reviewItems;
  const setReviewItems = useCallback((value: ReviewItem[]) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { reviewItems: value });
  }, [currentProject, updateProjectState]);
  
  const reviewRun = state.runs.review;
  const setReviewRun = useCallback((value: TenderRun | null) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { runs: { ...state.runs, review: value } });
  }, [currentProject, state.runs, updateProjectState]);
  
  const selectedBidder = state.selectedBidder;
  const setSelectedBidder = useCallback((value: string) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { selectedBidder: value });
  }, [currentProject, updateProjectState]);
  
  const selectedRuleAssetIds = state.selectedRuleAssetIds;
  const setSelectedRuleAssetIds = useCallback((value: string[] | ((prev: string[]) => string[])) => {
    if (!currentProject) return;
    const newValue = typeof value === 'function' ? value(state.selectedRuleAssetIds) : value;
    updateProjectState(currentProject.id, { selectedRuleAssetIds: newValue });
  }, [currentProject, state.selectedRuleAssetIds, updateProjectState]);
  
  // 新增：选中的规则包ID
  const selectedRulePackIds = state.selectedRulePackIds;
  const setSelectedRulePackIds = useCallback((value: string[] | ((prev: string[]) => string[])) => {
    if (!currentProject) return;
    const newValue = typeof value === 'function' ? value(state.selectedRulePackIds) : value;
    updateProjectState(currentProject.id, { selectedRulePackIds: newValue });
  }, [currentProject, state.selectedRulePackIds, updateProjectState]);
  
  const evidenceChunks = state.evidenceChunks;
  const setEvidenceChunks = useCallback((value: Chunk[]) => {
    if (!currentProject) return;
    updateProjectState(currentProject.id, { evidenceChunks: value });
  }, [currentProject, updateProjectState]);
  
  // ========== 兼容层结束 ==========
  
  // 全局共享状态（不按项目隔离）
  const [formatTemplates, setFormatTemplates] = useState<FormatTemplateOption[]>([]);
  const [applyingFormat, setApplyingFormat] = useState(false);
  const [autoFillingSamples, setAutoFillingSamples] = useState(false);
  const [formatPreviewLoading, setFormatPreviewLoading] = useState<boolean>(false);
  
  // 自定义规则包列表（全局共享，所有项目都能看到）
  const [rulePacks, setRulePacks] = useState<any[]>([]);

  // 轻量 Toast（不引入第三方库）
  const [toast, setToast] = useState<{ kind: 'success' | 'error' | 'warning'; msg: string; detail?: string } | null>(null);
  const showToast = useCallback((kind: 'success' | 'error' | 'warning', msg: string, detail?: string) => {
    setToast({ kind, msg, detail });
    window.setTimeout(() => setToast(null), kind === 'error' ? 5000 : 3500);
  }, []);
  
  // 证据面板（全局状态，默认收起）
  const [evidencePanelOpen, setEvidencePanelOpen] = useState(false);
  
  // 模板详情弹窗
  const [showTemplateDetail, setShowTemplateDetail] = useState(false);
  const [templateDetailSpec, setTemplateDetailSpec] = useState<any>(null);
  const [templateDetailSummary, setTemplateDetailSummary] = useState<any>(null);
  const [templateDetailTab, setTemplateDetailTab] = useState<'preview' | 'spec' | 'diagnostics'>('preview');
  
  // 轮询管理：每个项目独立的轮询timers
  const pollTimersRef = useRef<Map<string, Map<string, ReturnType<typeof setInterval>>>>(new Map());
  
  // 停止指定项目的轮询
  const stopPolling = useCallback((projectId: string, taskType?: 'info' | 'risk' | 'directory' | 'bidResponse' | 'review') => {
    const timers = pollTimersRef.current.get(projectId);
    if (!timers) return;
    
    if (taskType) {
      // 停止指定任务的轮询
      const timer = timers.get(taskType);
      if (timer) {
        clearInterval(timer);
        timers.delete(taskType);
        console.log(`[stopPolling] 已停止项目 ${projectId} 的 ${taskType} 轮询`);
      }
    } else {
      // 停止所有轮询
      timers.forEach((timer, type) => {
        clearInterval(timer);
        console.log(`[stopPolling] 已停止项目 ${projectId} 的 ${type} 轮询`);
      });
      timers.clear();
    }
  }, []);
  
  // 停止项目的所有轮询
  const stopAllPolling = useCallback((projectId: string) => {
    stopPolling(projectId);
  }, [stopPolling]);
  
  // 启动轮询
  const startPolling = useCallback((
    projectId: string,
    taskType: 'info' | 'risk' | 'directory' | 'bidResponse' | 'review' | 'full_content',
    runId: string,
    onSuccess: () => void
  ) => {
    // 先停止已有的轮询
    stopPolling(projectId, taskType);
    
    const check = async () => {
      try {
        // 验证项目是否切换
        if (currentProject?.id !== projectId) {
          console.log(`[startPolling] 项目已切换，停止 ${taskType} 轮询`);
          stopPolling(projectId, taskType);
          return;
        }
        
        const run: TenderRun = await api.get(`/api/apps/tender/runs/${runId}`);
        
        if (run.status === 'success') {
          console.log(`[startPolling] ${taskType} 任务完成`);
          stopPolling(projectId, taskType);
          
          // 只在当前项目时才调用回调
          if (currentProject?.id === projectId) {
            onSuccess();
          }
        } else if (run.status === 'failed') {
          console.error(`[startPolling] ${taskType} 任务失败:`, run.message);
          stopPolling(projectId, taskType);
          
          if (currentProject?.id === projectId) {
            const errorMsg = run.message || 'unknown error';
            // 检查是否是"未提取招标要求"错误
            if (errorMsg.includes('未找到招标要求') || errorMsg.includes('招标要求')) {
              alert('⚠️ 请先提取招标要求\n\n请在【② 要求】标签页点击"提取要求"按钮，\n完成招标要求提取后再进行审核。');
            } else {
              alert(`任务失败: ${errorMsg}`);
            }
          }
        } else if (run.status === 'running') {
          // 运行中：增量加载数据
          if (taskType === 'info' && currentProject?.id === projectId) {
            api.get(`/api/apps/tender/projects/${projectId}/project-info`)
              .then(data => {
                if (currentProject?.id === projectId) {
                  setProjectInfo(data);
                }
              })
              .catch(err => console.warn('增量加载项目信息失败:', err));
          }
        }
        
        // 更新run状态
        if (currentProject?.id === projectId) {
          const state = getProjectState(projectId);
          updateProjectState(projectId, {
            runs: {
              ...state.runs,
              [taskType]: run
            }
          });
        }
      } catch (err) {
        console.error(`[startPolling] ${taskType} 轮询失败:`, err);
      }
    };
    
    // 立即执行一次
    check();
    
    // 设置定时器
    const timer = setInterval(check, 2000);
    
    // 保存timer
    let timers = pollTimersRef.current.get(projectId);
    if (!timers) {
      timers = new Map();
      pollTimersRef.current.set(projectId, timers);
    }
    timers.set(taskType, timer);
    
    console.log(`[startPolling] 已启动项目 ${projectId} 的 ${taskType} 轮询`);
  }, [currentProject, stopPolling, getProjectState, updateProjectState]);

  // -------------------- 格式预览加载（使用 fetch + Blob URL 以携带 Authorization） --------------------
  
  useEffect(() => {
    // 清理函数：释放旧的 Blob URL
    return () => {
      if (formatPreviewBlobUrl) {
        URL.revokeObjectURL(formatPreviewBlobUrl);
      }
    };
  }, [formatPreviewBlobUrl]);

  useEffect(() => {
    if (!formatPreviewUrl) {
      setFormatPreviewBlobUrl("");
      return;
    }

    const loadPreview = async () => {
      setFormatPreviewLoading(true);
      try {
        // 使用 api.get 的底层 request 函数，但需要获取 Blob 响应
        const token = localStorage.getItem('auth_token');
        const response = await fetch(formatPreviewUrl, {
          method: 'GET',
          headers: {
            'Authorization': token ? `Bearer ${token}` : '',
          },
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const blob = await response.blob();
        const blobUrl = URL.createObjectURL(blob);
        setFormatPreviewBlobUrl(blobUrl);
      } catch (err) {
        console.error('Failed to load format preview:', err);
        showToast('error', '格式预览加载失败', String(err));
        setFormatPreviewBlobUrl("");
      } finally {
        setFormatPreviewLoading(false);
      }
    };

    loadPreview();
  }, [formatPreviewUrl, showToast]);

  // -------------------- 下载Word文件（携带 Authorization） --------------------
  
  const downloadWordFile = useCallback(async () => {
    if (!formatDownloadUrl) return;
    
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(formatDownloadUrl, {
        method: 'GET',
        headers: {
          'Authorization': token ? `Bearer ${token}` : '',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      
      // 触发下载
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = `投标文件_${currentProject?.name || '导出'}_${new Date().toISOString().split('T')[0]}.docx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      // 清理 Blob URL
      setTimeout(() => URL.revokeObjectURL(blobUrl), 100);
      
      showToast('success', 'Word文件下载成功');
    } catch (err) {
      console.error('Failed to download Word file:', err);
      showToast('error', 'Word文件下载失败', String(err));
    }
  }, [formatDownloadUrl, currentProject, showToast]);

  // -------------------- 数据加载 --------------------

  const loadProjects = useCallback(async () => {
    try {
      const data = await api.get('/api/apps/tender/projects');
      setProjects(data);
    } catch (err) {
      console.error('Failed to load projects:', err);
    }
  }, []);

  const loadAssets = useCallback(async (forceProjectId?: string) => {
    const projectId = forceProjectId || currentProject?.id;
    if (!projectId) return;
    
    // ✅ 加载前验证项目ID
    if (!forceProjectId && currentProject && currentProject.id !== projectId) {
      console.log('[loadAssets] 项目已切换，跳过加载');
      return;
    }
    
    try {
      const data = await api.get(`/api/apps/tender/projects/${projectId}/assets`);
      
      // ✅ 加载后验证项目ID
      if (currentProject && currentProject.id !== projectId) {
        console.log('[loadAssets] 加载完成时项目已切换，丢弃数据');
        return;
      }
      
      setAssets(data);
    } catch (err) {
      console.error('Failed to load assets:', err);
    }
  }, [currentProject]);
  
  // 加载自定义规则包列表（全局共享，不限制项目）
  const loadRulePacks = useCallback(async () => {
    try {
      // 不传project_id，加载所有共享规则包
      const data = await api.get(`/api/custom-rules/rule-packs`);
      setRulePacks(data || []);
    } catch (err) {
      console.error('Failed to load rule packs:', err);
      setRulePacks([]);
    }
  }, []); // 不依赖currentProject

  const loadProjectInfo = useCallback(async (forceProjectId?: string) => {
    // 使用传入的projectId或当前项目ID
    const projectId = forceProjectId || currentProject?.id;
    if (!projectId) return;
    
    // ✅ 加载前再次验证项目ID是否匹配（防止切换项目时加载错误数据）
    if (!forceProjectId && currentProject && currentProject.id !== projectId) {
      console.log('[loadProjectInfo] 项目已切换，跳过加载', { expectedProjectId: projectId, currentProjectId: currentProject.id });
      return;
    }
    
    try {
      const data = await api.get(`/api/apps/tender/projects/${projectId}/project-info`);
      
      // ✅ 加载后再次验证项目ID（防止异步加载完成时项目已切换）
      if (currentProject && currentProject.id !== projectId) {
        console.log('[loadProjectInfo] 加载完成时项目已切换，丢弃数据', { expectedProjectId: projectId, currentProjectId: currentProject.id });
        return;
      }
      
      setProjectInfo(data);
    } catch (err) {
      console.error('Failed to load project info:', err);
    }
  }, [currentProject]);

  // loadRisks 已重命名为 loadRiskAnalysis
  // 注：虽然API路径还是/risk-analysis，但数据来源已改为tender_requirements
  const loadRiskAnalysis = useCallback(async (forceProjectId?: string) => {
    const projectId = forceProjectId || currentProject?.id;
    if (!projectId) return;
    
    // ✅ 加载前验证项目ID
    if (!forceProjectId && currentProject && currentProject.id !== projectId) {
      console.log('[loadRiskAnalysis] 项目已切换，跳过加载');
      return;
    }
    
    try {
      // 使用新的 risk-analysis API（基于tender_requirements聚合）
      const data = await api.get(`/api/apps/tender/projects/${projectId}/risk-analysis`);
      
      // ✅ 加载后验证项目ID
      if (currentProject && currentProject.id !== projectId) {
        console.log('[loadRiskAnalysis] 加载完成时项目已切换，丢弃数据');
        return;
      }
      
      setRiskAnalysisData(data);
    } catch (err) {
      console.error('Failed to load risk analysis:', err);
      // 失败时清空数据
      setRiskAnalysisData(null);
    }
  }, [currentProject]);

  const loadDirectory = useCallback(async (forceProjectId?: string): Promise<DirectoryNode[]> => {
    const projectId = forceProjectId || currentProject?.id;
    if (!projectId) return [];
    
    // ✅ 加载前验证项目ID
    if (!forceProjectId && currentProject && currentProject.id !== projectId) {
      console.log('[loadDirectory] 项目已切换，跳过加载');
      return [];
    }
    
    try {
      console.log('[loadDirectory] 开始加载目录，项目ID:', projectId);
      const data = await api.get(`/api/apps/tender/projects/${projectId}/directory`);
      console.log('[loadDirectory] 加载到的目录数据:', data);
      
      // ✅ 加载后验证项目ID
      if (currentProject && currentProject.id !== projectId) {
        console.log('[loadDirectory] 加载完成时项目已切换，丢弃数据');
        return [];
      }
      
      setDirectory(data);
      return data as DirectoryNode[];
    } catch (err) {
      console.error('Failed to load directory:', err);
      // 如果加载失败，清空目录（可能是之前生成失败导致数据损坏）
      setDirectory([]);
      alert('加载目录失败，可能是之前生成失败导致数据损坏。请尝试重新生成目录。');
      return [];
    }
  }, [currentProject]);

  // 兼容命名：目录接口已自带 bodyMeta，这里保留一个语义更清晰的封装
  const loadDirectoryWithBodyMeta = useCallback(async (): Promise<DirectoryNode[]> => {
    const nodes = await loadDirectory();
    return nodes;
  }, [loadDirectory]);

  const loadBidResponses = useCallback(async (forceProjectId?: string) => {
    const projectId = forceProjectId || currentProject?.id;
    if (!projectId) return;
    
    // 加载前验证项目ID
    if (!forceProjectId && currentProject && currentProject.id !== projectId) {
      console.log('[loadBidResponses] 项目已切换，跳过加载');
      return;
    }
    
    try {
      // 传入bidder_name参数进行过滤
      // 现在后端已修改为使用前端传入的bidder_name，可以正确匹配
      const selectedBidderName = state.selectedBidder;
      const params = selectedBidderName ? `?bidder_name=${encodeURIComponent(selectedBidderName)}` : '';
      const data = await api.get(`/api/apps/tender/projects/${projectId}/bid-responses${params}`);
      
      // 加载后验证项目ID
      if (currentProject && currentProject.id !== projectId) {
        console.log('[loadBidResponses] 加载完成时项目已切换，丢弃数据');
        return;
      }
      
      setBidResponses(data.responses || []);
      setBidResponseStats(data.stats || []);
    } catch (err) {
      console.error('Failed to load bid responses:', err);
      setBidResponses([]);
      setBidResponseStats([]);
    }
  }, [currentProject, state.selectedBidder]);

  const extractBidResponses = useCallback(async () => {
    if (!currentProject) return;
    if (!state.selectedBidder) {
      alert('请先选择投标人');
      return;
    }
    
    const projectId = currentProject.id;
    const bidderName = state.selectedBidder;
    
    // 清空旧的投标响应数据
    setBidResponses([]);
    
    try {
      const res = await api.post(
        `/api/apps/tender/projects/${projectId}/extract-bid-responses?bidder_name=${encodeURIComponent(bidderName)}`,
        {}
      );
      
      // 设置新的run状态
      const newRun: TenderRun = { 
        id: res.run_id, 
        status: 'running', 
        progress: 0, 
        message: `开始抽取投标人：${bidderName}...`, 
        kind: 'extract_bid_responses' 
      } as TenderRun;
      setBidResponseRun(newRun);
      
      // 启动轮询
      startPolling(projectId, 'bidResponse', res.run_id, () => loadBidResponses(projectId));
    } catch (err) {
      alert(`抽取失败: ${err}`);
      setBidResponseRun(null);
    }
  }, [currentProject, state.selectedBidder, setBidResponses, setBidResponseRun, startPolling, loadBidResponses]);

  const loadFormatTemplates = useCallback(async () => {
    try {
      const rows = await api.get(`/api/apps/tender/format-templates`);
      const opts = (Array.isArray(rows) ? rows : []).map((r: any) => ({ id: String(r.id), name: String(r.name || r.id) }));
      setFormatTemplates(opts);
    } catch (err) {
      console.warn("Failed to load format templates:", err);
      setFormatTemplates([]);
    }
  }, []);

  function parsePx(v: any): number | undefined {
    if (v == null) return undefined;
    if (typeof v === "number" && Number.isFinite(v)) return v;
    const s = String(v).trim();
    const n = parseFloat(s.replace("px", ""));
    return Number.isFinite(n) ? n : undefined;
  }

  function ptToPx(pt: any): number | undefined {
    if (pt == null) return undefined;
    const n = typeof pt === "number" ? pt : parseFloat(String(pt));
    if (!Number.isFinite(n)) return undefined;
    return n * (96 / 72); // 1pt = 1.3333px
  }

  function parseLineHeight(v: any): number | undefined {
    if (v == null) return undefined;
    if (typeof v === "number" && Number.isFinite(v)) return v;
    const s = String(v).trim().toLowerCase();
    // 常见： "1.5"
    const n = parseFloat(s.replace("pt", ""));
    if (!Number.isFinite(n)) return undefined;
    // 如果像 12pt 这种绝对值（较大），前端预览不好直接用，先忽略
    if (s.endsWith("pt") && n > 5) return undefined;
    return n;
  }

  function buildTocStyleVarsFromTemplateSpec(spec: any) {
    const hints = (spec?.style_hints || spec?.styleHints || {}) as Record<string, any>;
    const styleRules = (spec?.style_rules || spec?.styleRules || []) as any[];
    const bodyRule = styleRules.find((r) => r && (r.target === "body" || r.target === "BODY"));
    const h1Rule = styleRules.find((r) => r && (r.target === "heading1" || r.target === "HEADING1"));

    const fontSizePx =
      ptToPx(bodyRule?.font_size_pt) ??
      parsePx(hints.font_size);
    const lineHeight =
      parseLineHeight(bodyRule?.line_spacing) ??
      (hints.line_height != null ? parseFloat(String(hints.line_height)) : undefined);
    return {
      fontFamily: bodyRule?.font_family || hints.font_family || undefined,
      fontSizePx,
      lineHeight: Number.isFinite(lineHeight as any) ? lineHeight : undefined,
      lvl1Bold: typeof h1Rule?.bold === "boolean" ? h1Rule.bold : true,
      lvl1FontSizePx: ptToPx(h1Rule?.font_size_pt) ?? (fontSizePx ? fontSizePx + 2 : undefined),
      indent1Px: parsePx(hints.toc_indent_1),
      indent2Px: parsePx(hints.toc_indent_2),
      indent3Px: parsePx(hints.toc_indent_3),
    };
  }

  const loadSelectedTemplateSpec = useCallback(async (templateId: string) => {
    if (!templateId) {
      setTocStyleVars(null);
      return;
    }
    try {
      const spec = await api.get(`/api/apps/tender/format-templates/${templateId}/spec`);
      setTocStyleVars(buildTocStyleVarsFromTemplateSpec(spec));
    } catch (err) {
      console.warn("Failed to load selected template spec:", err);
      setTocStyleVars(null);
    }
  }, []);

  // 画布：加载一个/全部正文
  const loadBodyForNode = useCallback(async (nodeId: string) => {
    if (!currentProject) return;
    try {
      const data = await api.get(`/api/apps/tender/projects/${currentProject.id}/directory/${nodeId}/body`);
      setBodyByNodeId((prev) => ({ ...prev, [nodeId]: data.contentHtml || '' }));
    } catch (err) {
      console.error('Failed to load section body:', err);
    }
  }, [currentProject]);

  const loadBodiesForAllNodes = useCallback(async (nodes: DirectoryNode[]) => {
    if (!currentProject) return;
    await Promise.all(nodes.map((n) => loadBodyForNode(n.id)));
  }, [currentProject, loadBodyForNode]);

  // Step3：范本原文侧边栏数据
  const loadSampleFragments = useCallback(async (forceProjectId?: string) => {
    const projectId = forceProjectId || currentProject?.id;
    if (!projectId) return;
    
    // ✅ 加载前验证项目ID
    if (!forceProjectId && currentProject && currentProject.id !== projectId) {
      console.log('[loadSampleFragments] 项目已切换，跳过加载');
      return;
    }
    
    try {
      const data = await api.get(`/api/apps/tender/projects/${projectId}/sample-fragments`);
      
      // ✅ 加载后验证项目ID
      if (currentProject && currentProject.id !== projectId) {
        console.log('[loadSampleFragments] 加载完成时项目已切换，丢弃数据');
        return;
      }
      
      setSampleFragments(Array.isArray(data) ? (data as SampleFragment[]) : []);
    } catch (err) {
      console.warn("Failed to load sample fragments:", err);
      setSampleFragments([]);
    }
  }, [currentProject]);

  const loadSamplePreview = useCallback(
    async (fragmentId: string) => {
      if (!currentProject) return;
      let shouldFetch = false;
      setSamplePreviewById((prev) => {
        const cur = prev[fragmentId];
        if (cur?.loading || cur?.data) return prev;
        shouldFetch = true;
        return { ...prev, [fragmentId]: { ...(cur || {}), loading: true, error: undefined } };
      });
      if (!shouldFetch) return;

      try {
        const data = (await api.get(
          `/api/apps/tender/projects/${currentProject.id}/sample-fragments/${fragmentId}/preview?max_elems=60`
        )) as SampleFragmentPreview;
        setSamplePreviewById((prev) => ({ ...prev, [fragmentId]: { loading: false, data } }));
      } catch (err) {
        setSamplePreviewById((prev) => ({ ...prev, [fragmentId]: { loading: false, error: String(err) } }));
      }
    },
    [currentProject]
  );

  // loadRuleSets 已删除 - 规则文件现在直接从 assets 中筛选

  const loadReview = useCallback(async (forceProjectId?: string) => {
    const projectId = forceProjectId || currentProject?.id;
    if (!projectId) return;
    
    // ✅ 加载前验证项目ID
    if (!forceProjectId && currentProject && currentProject.id !== projectId) {
      console.log('[loadReview] 项目已切换，跳过加载');
      return;
    }
    
    try {
      // ✅ 如果有选中的投标人，传递bidder_name参数
      const params = selectedBidder ? `?bidder_name=${encodeURIComponent(selectedBidder)}` : '';
      const data = await api.get(`/api/apps/tender/projects/${projectId}/review${params}`);
      console.log('[loadReview] 获取到审核数据:', data);
      console.log('[loadReview] bidder_name过滤:', selectedBidder || '无');
      console.log('[loadReview] 数据类型:', Array.isArray(data) ? 'Array' : typeof data);
      console.log('[loadReview] 数据长度:', data?.length);
      
      // ✅ 加载后验证项目ID
      if (currentProject && currentProject.id !== projectId) {
        console.log('[loadReview] 加载完成时项目已切换，丢弃数据');
        return;
      }
      
      setReviewItems(data);
      console.log('[loadReview] setReviewItems 调用完成');
    } catch (err) {
      console.error('Failed to load review:', err);
    }
  }, [currentProject, selectedBidder]);
  
  // -------------------- 项目操作 --------------------

  const createProject = async () => {
    if (!newProjectName.trim()) {
      alert('请输入项目名称');
      return;
    }
    try {
      const data = await api.post('/api/apps/tender/projects', {
        name: newProjectName,
        description: newProjectDesc,
      });
      setProjects([data, ...projects]);
      setNewProjectName('');
      setNewProjectDesc('');
      setShowCreateForm(false); // 隐藏创建表单
      // 自动选中新创建的项目
      selectProject(data);
      alert('项目创建成功（已自动创建知识库）');
    } catch (err) {
      alert(`创建失败: ${err}`);
    }
  };

  const selectProject = (proj: TenderProject) => {
    console.log('[selectProject] 切换项目:', { from: currentProject?.id, to: proj.id });
    
    // 停止当前项目的所有轮询
    if (currentProject?.id) {
      stopAllPolling(currentProject.id);
    }
    
    // 切换项目（状态由 ProjectState Map 管理，不需要清空）
    setCurrentProject(proj);
    setActiveTab(1);
    setViewMode("projectDetail"); // 切换到项目详情视图
  };
  
  // ✅ 当项目切换且run状态恢复后，自动恢复running任务的轮询
  // 编辑项目
  const openEditProject = (proj: TenderProject) => {
    setEditingProject(proj);
    setEditProjectName(proj.name);
    setEditProjectDesc(proj.description || '');
  };
  
  const saveEditProject = async () => {
    if (!editingProject || !editProjectName.trim()) {
      alert('项目名称不能为空');
      return;
    }
    try {
      const updated = await api.put(`/api/apps/tender/projects/${editingProject.id}`, {
        name: editProjectName,
        description: editProjectDesc,
      });
      // 更新列表
      setProjects(projects.map(p => p.id === updated.id ? updated : p));
      // 如果正在编辑当前项目，也更新当前项目
      if (currentProject?.id === updated.id) {
        setCurrentProject(updated);
      }
      setEditingProject(null);
      alert('项目更新成功');
    } catch (err) {
      alert(`更新失败: ${err}`);
    }
  };
  
  // 删除项目
  const openDeleteProject = async (proj: TenderProject) => {
    setDeletingProject(proj);
    try {
      const plan = await api.get(`/api/apps/tender/projects/${proj.id}/delete-plan`);
      setDeletePlan(plan);
    } catch (err) {
      alert(`获取删除计划失败: ${err}`);
      setDeletingProject(null);
    }
  };
  
  const confirmDeleteProject = async () => {
    if (!deletingProject || !deletePlan) return;
    
    setIsDeleting(true);
    try {
      await api.request(`/api/apps/tender/projects/${deletingProject.id}`, {
        method: 'DELETE',
        body: JSON.stringify({
          confirm_token: deletePlan.confirm_token,
        }),
        headers: { 'Content-Type': 'application/json' },
      });
      
      // 移除项目
      setProjects(projects.filter(p => p.id !== deletingProject.id));
      // 如果删除的是当前项目，清空当前项目
      if (currentProject?.id === deletingProject.id) {
        setCurrentProject(null);
      }
      setDeletingProject(null);
      setDeletePlan(null);
      alert('项目删除成功');
    } catch (err) {
      alert(`删除失败: ${err}`);
    } finally {
      setIsDeleting(false);
    }
  };

  // 批量删除
  const handleBatchDelete = async () => {
    if (selectedProjectIds.size === 0) {
      alert('请先选择要删除的项目');
      return;
    }

    if (!confirm(`确定要删除选中的 ${selectedProjectIds.size} 个项目吗？此操作不可撤销！`)) {
      return;
    }

    setIsBatchDeleting(true);
    try {
      const deletePromises = Array.from(selectedProjectIds).map(async (projectId) => {
        // 获取删除计划
        const plan = await api.request(`/api/apps/tender/projects/${projectId}/delete-plan`);
        
        // 执行删除
        await api.request(`/api/apps/tender/projects/${projectId}`, {
          method: 'DELETE',
          body: JSON.stringify({ confirm_token: plan.confirm_token }),
          headers: { 'Content-Type': 'application/json' },
        });
      });

      await Promise.all(deletePromises);
      
      setProjects(projects.filter(p => !selectedProjectIds.has(p.id)));
      setSelectedProjectIds(new Set());
      alert(`成功删除 ${selectedProjectIds.size} 个项目`);
    } catch (err: any) {
      alert(`批量删除失败: ${err.message || err}`);
    } finally {
      setIsBatchDeleting(false);
    }
  };

  // 切换项目选择
  const toggleProjectSelection = (projectId: string) => {
    const newSet = new Set(selectedProjectIds);
    if (newSet.has(projectId)) {
      newSet.delete(projectId);
    } else {
      newSet.add(projectId);
    }
    setSelectedProjectIds(newSet);
  };

  // 全选/取消全选
  const toggleSelectAll = () => {
    if (selectedProjectIds.size === filteredProjects.length) {
      setSelectedProjectIds(new Set());
    } else {
      setSelectedProjectIds(new Set(filteredProjects.map(p => p.id)));
    }
  };

  // 过滤项目
  const filteredProjects = projects.filter(p => 
    p.name.toLowerCase().includes(searchKeyword.toLowerCase()) ||
    (p.description && p.description.toLowerCase().includes(searchKeyword.toLowerCase()))
  );

  // -------------------- 文件上传 --------------------

  const handleFilesChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(Array.from(e.target.files));
    }
  };

  const handleUpload = async () => {
    if (!currentProject || files.length === 0) {
      alert('请选择文件');
      return;
    }
    if (uploadKind === 'bid' && !bidderName.trim()) {
      alert('投标文件需要填写投标人名称');
      return;
    }

    const formData = new FormData();
    formData.append('kind', uploadKind);
    if (bidderName) {
      formData.append('bidder_name', bidderName);
    }
    files.forEach(f => formData.append('files', f));

    setUploading(true);
    try {
      const newAssets = await api.post(
        `/api/apps/tender/projects/${currentProject.id}/assets/import`,
        formData
      );
      setAssets([...assets, ...newAssets]);
      setFiles([]);
      setBidderName('');
      alert('上传成功');
    } catch (err) {
      alert(`上传失败: ${err}`);
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteAsset = async (assetId: string, filename: string) => {
    if (!currentProject) return;
    
    if (!confirm(`确定要删除文件"${filename}"吗？

此操作将同时删除：
✓ 知识库中对应的文档及向量数据
✓ 该文档的所有文本分块（chunks）
✓ 项目中的资产记录
✓ 相关的证据引用（如有）

⚠️ 此操作不可恢复！请确认是否继续？`)) {
      return;
    }

    try {
      await api.delete(`/api/apps/tender/projects/${currentProject.id}/assets/${assetId}`);
      // 从列表中移除
      setAssets(assets.filter(a => a.id !== assetId));
      alert('删除成功');
    } catch (err) {
      alert(`删除失败: ${err}`);
    }
  };

  // -------------------- Run 轮询 --------------------
  // 已重构为 startPolling / stopPolling

  // -------------------- Step操作 --------------------
  
  const extractProjectInfo = async () => {
    if (!currentProject) return;
    const projectId = currentProject.id;
    
    // 清空旧的项目信息
    setProjectInfo(null);
    
    try {
      const res = await api.post(`/api/apps/tender/projects/${projectId}/extract/project-info`, { model_id: null });
      
      // 设置新的run状态
      const newRun: TenderRun = { 
        id: res.run_id, 
        status: 'running', 
        progress: 0, 
        message: '开始抽取...', 
        kind: 'extract_project_info' 
      } as TenderRun;
      setInfoRun(newRun);
      
      // 启动轮询
      startPolling(projectId, 'info', res.run_id, () => loadProjectInfo(projectId));
    } catch (err) {
      alert(`抽取失败: ${err}`);
      setInfoRun(null);
    }
  };

  // extractRisks 已重命名为 extractRequirements
  // 注：API路径保持/extract/risks，但后端已改为调用requirements_v1模块
  const extractRequirements = async () => {
    if (!currentProject) return;
    const projectId = currentProject.id;
    
    // 清空旧的风险分析数据
    setRiskAnalysisData(null);
    
    try {
      // ✨ 使用V2标准清单方式（覆盖率100%，置信度0.98）
      const res = await api.post(`/api/apps/tender/projects/${projectId}/extract/risks?use_checklist=1`, { model_id: null });
      
      // 设置新的run状态
      const newRun: TenderRun = { 
        id: res.run_id, 
        status: 'running', 
        progress: 0, 
        message: '开始提取招标要求（标准清单方式）...', 
        kind: 'extract_risks'  // 保持kind名称不变，以兼容现有代码
      } as TenderRun;
      setRiskRun(newRun);
      
      // 启动轮询（加载风险分析）
      startPolling(projectId, 'risk', res.run_id, () => loadRiskAnalysis(projectId));
    } catch (err) {
      alert(`提取失败: ${err}`);
      setRiskRun(null);
    }
  };

  const generateDirectory = async () => {
    if (!currentProject) return;
    const projectId = currentProject.id;
    
    // 清空旧的目录
    setDirectory([]);
    setBodyByNodeId({});
    
    try {
      console.log('[generateDirectory] 开始生成目录，项目ID:', projectId);
      const res = await api.post(`/api/apps/tender/projects/${projectId}/directory/generate`, { model_id: null });
      console.log('[generateDirectory] 生成目录任务已提交，run_id:', res.run_id);
      
      // 设置新的run状态
      const newRun: TenderRun = { 
        id: res.run_id, 
        status: 'running', 
        progress: 0, 
        message: '开始生成...', 
        kind: 'generate_directory' 
      } as TenderRun;
      setDirRun(newRun);
      
      // 启动轮询
      startPolling(projectId, 'directory', res.run_id, async () => {
        // 获取run结果，提取生成模式信息
        try {
          const run = await api.get(`/api/apps/tender/runs/${res.run_id}`);
          const resultJson = run.result_json || {};
          setDirectoryGenerationMode(resultJson.generation_mode || "");
          setDirectoryFastStats(resultJson.fast_stats || {});
          setDirectoryRefinementStats(resultJson.refinement_stats || {});
          setDirectoryBracketParsingStats(resultJson.bracket_parsing_stats || {});
          setDirectoryTemplateMatchingStats(resultJson.template_matching_stats || {});  // ✨ 新增
          console.log('[generateDirectory] 生成模式:', resultJson.generation_mode);
          console.log('[generateDirectory] 细化统计:', resultJson.refinement_stats);
          console.log('[generateDirectory] 括号解析统计:', resultJson.bracket_parsing_stats);
          console.log('[generateDirectory] 范本填充统计:', resultJson.template_matching_stats);
        } catch (err) {
          console.warn('[generateDirectory] 无法获取生成模式信息:', err);
        }
        
        const nodes = await loadDirectory(projectId);
        console.log('[generateDirectory] 后端返回目录(前5条title):', (nodes || []).slice(0, 5).map(n => n?.title));
        if (nodes.length > 0) {
          await loadBodiesForAllNodes(nodes);
        }
        await loadSampleFragments();
      });
    } catch (err) {
      console.error('[generateDirectory] 生成失败:', err);
      alert(`生成失败: ${err}`);
      setDirRun(null);
    }
  };

  const applyFormatTemplate = async () => {
    if (!currentProject) return;
    if (!selectedFormatTemplateId) return;

    try {
      setApplyingFormat(true);

      // ✅ 新逻辑：请求 JSON 格式，获取预览和下载链接
      const data: any = await api.post(
        `/api/apps/tender/projects/${currentProject.id}/directory/apply-format-template?return_type=json`,
        { format_template_id: selectedFormatTemplateId }
      );

      if (!data?.ok) {
        throw new Error(data?.detail || "套用格式失败");
      }

      // ✅ 立即刷新目录/正文（页面内容变化）
      const nodes = data.nodes || (await loadDirectoryWithBodyMeta());
      if (nodes.length > 0) {
        await loadBodiesForAllNodes(nodes);
      }

      // ✅ 内嵌格式预览：切换到格式预览Tab + 写入URL（带 fallback）
      const ts = Date.now();
      
      // Fallback: 如果后端未返回 URL，自动构造格式预览端点
      const fallbackPreviewUrl = `/api/apps/tender/projects/${currentProject.id}/directory/format-preview?format=pdf&format_template_id=${selectedFormatTemplateId}`;
      const fallbackDownloadUrl = `/api/apps/tender/projects/${currentProject.id}/directory/format-preview?format=docx&format_template_id=${selectedFormatTemplateId}`;
      
      const previewUrl = data.preview_pdf_url || fallbackPreviewUrl;
      const downloadUrl = data.download_docx_url || fallbackDownloadUrl;
      
      setFormatPreviewUrl(previewUrl ? `${previewUrl}${previewUrl.includes("?") ? "&" : "?"}ts=${ts}` : "");
      setFormatDownloadUrl(downloadUrl);
      setPreviewMode("format"); // ✅ 套用后直接切到"格式预览"

      // 记录选择
      localStorage.setItem(`tender.formatTemplateId.${currentProject.id}`, selectedFormatTemplateId);
      await loadSelectedTemplateSpec(selectedFormatTemplateId);
      
      // 成功提示
      showToast('success', '格式模板套用成功！预览已更新');

    } catch (err: any) {
      console.error("[applyFormatTemplate] 错误详情:", err);
      
      // 提取详细错误信息
      const errorDetail = err?.response?.data?.detail 
        || err?.response?.data?.message 
        || err?.message 
        || String(err);
      
      const errorStatus = err?.response?.status;
      const errorTitle = errorStatus 
        ? `套用格式失败 (HTTP ${errorStatus})`
        : `套用格式失败`;
      
      // 使用增强的 toast 显示错误（带详细信息）
      showToast('error', errorTitle, errorDetail);
      
      // 如果是后端返回的结构化错误，打印完整信息供调试
      if (err?.response?.data) {
        console.error("[applyFormatTemplate] 后端返回:", err.response.data);
      }
    } finally {
      setApplyingFormat(false);
    }
  };

  const autoFillSamples = async () => {
    if (!currentProject) return;
    try {
      setAutoFillingSamples(true);
      const res = await api.post(`/api/apps/tender/projects/${currentProject.id}/directory/auto-fill-samples`, {});
      // 轻量 toast（不引入第三方库）
      const ok = !!(res && (res as any).ok);
      const extracted = Number((res as any)?.tender_fragments_upserted ?? (res as any)?.extracted_fragments ?? 0);
      const total = Number((res as any)?.tender_fragments_total ?? 0);
      const attachedTpl = Number((res as any)?.attached_sections_template_sample ?? 0);
      const attachedBuiltin = Number((res as any)?.attached_sections_builtin ?? 0);
      const attached = (attachedTpl + attachedBuiltin) || Number((res as any)?.attached_sections || 0);
      const warnings = Array.isArray((res as any)?.warnings) ? (res as any).warnings : [];
      const needsReupload = !!(res as any)?.needs_reupload;
      const msg = ok
        ? `本次抽取 ${extracted} 条范本（库内共 ${total} 条），挂载 ${attached} 个章节（模板 ${attachedTpl} / 内置 ${attachedBuiltin}）`
        : (warnings[0] || (needsReupload ? '自动填充失败：请重新上传招标书 docx 以启用范本抽取' : '自动填充失败'));
      showToast(ok ? 'success' : 'error', msg);
      // 优先用后端返回的 nodes 刷新（避免再打一轮 GET）
      const respNodes = Array.isArray((res as any)?.nodes) ? ((res as any).nodes as DirectoryNode[]) : null;
      if (respNodes && respNodes.length >= 0) {
        setDirectory(respNodes);
        if (respNodes.length > 0) {
          await loadBodiesForAllNodes(respNodes);
        }
      } else {
        const nodes = await loadDirectoryWithBodyMeta();
        if (nodes.length > 0) {
          await loadBodiesForAllNodes(nodes);
        }
      }

      // 刷新范本侧边栏（列表 + 清缓存），并自动展开一次
      setSamplePreviewById({});
      await loadSampleFragments();
      setSamplesOpen(true);
    } catch (err) {
      showToast('error', `自动填充失败: ${err}`);
    } finally {
      setAutoFillingSamples(false);
    }
  };

  const generateDocx = async () => {
    // 保留空函数或删除，Step4不再需要
  };

  // ==================== Step4: AI生成全文 ====================
  
  const [generatingFullContent, setGeneratingFullContent] = useState(false);
  const [fullContentRun, setFullContentRun] = useState<TenderRun | null>(null);
  const [editingDirectory, setEditingDirectory] = useState<DirectoryNode[]>([]);
  const [showDirectoryEditor, setShowDirectoryEditor] = useState(false);
  const [showGeneratingPage, setShowGeneratingPage] = useState(false);
  const [generatedSections, setGeneratedSections] = useState<Record<string, { title: string; content: string; status: 'pending' | 'generating' | 'done' | 'error' }>>({});
  
  // 初始化可编辑目录（从当前目录复制）
  const initEditableDirectory = () => {
    setEditingDirectory(JSON.parse(JSON.stringify(directory)));
    setShowDirectoryEditor(true);
  };
  
  // 保存编辑后的目录
  const saveEditedDirectory = async () => {
    if (!currentProject) return;
    
    try {
      // 扁平化树形结构为节点列表
      const flattenNodes = (nodes: DirectoryNode[], result: any[] = []): any[] => {
        nodes.forEach(node => {
          result.push({
            numbering: node.numbering || '',
            level: node.level,
            title: node.title,
            required: node.required !== false,
            notes: node.notes || '',
            evidence_chunk_ids: node.evidence_chunk_ids || [],
          });
          if (node.children && node.children.length > 0) {
            flattenNodes(node.children, result);
          }
        });
        return result;
      };
      
      const flatNodes = flattenNodes(editingDirectory);
      
      await api.put(`/api/apps/tender/projects/${currentProject.id}/directory`, {
        nodes: flatNodes
      });
      
      // 重新加载目录
      await loadDirectory();
      setShowDirectoryEditor(false);
      showToast('success', '目录保存成功');
    } catch (err: any) {
      showToast('error', `保存目录失败: ${err.message}`);
    }
  };
  
  // 添加子节点
  const addChildNode = (parentNode: DirectoryNode) => {
    // 计算新节点的编号
    const parentNumbering = parentNode.numbering || '';
    const childrenCount = (parentNode.children?.length || 0) + 1;
    const newNumbering = parentNumbering ? `${parentNumbering}.${childrenCount}` : `${childrenCount}`;
    
    const newNode: DirectoryNode = {
      id: `temp_${Date.now()}`,
      numbering: newNumbering,
      level: parentNode.level + 1,
      title: '新章节',
      required: true,
      notes: '',
      evidence_chunk_ids: [],
      children: [],
    };
    
    if (!parentNode.children) {
      parentNode.children = [];
    }
    parentNode.children.push(newNode);
    setEditingDirectory([...editingDirectory]);
  };
  
  // 删除节点
  const deleteNode = (nodeToDelete: DirectoryNode, nodes: DirectoryNode[]): boolean => {
    for (let i = 0; i < nodes.length; i++) {
      if (nodes[i] === nodeToDelete) {
        nodes.splice(i, 1);
        return true;
      }
      if (nodes[i].children && deleteNode(nodeToDelete, nodes[i].children!)) {
        return true;
      }
    }
    return false;
  };
  
  const handleDeleteNode = (node: DirectoryNode) => {
    if (confirm(`确定删除节点"${node.title}"及其所有子节点？`)) {
      deleteNode(node, editingDirectory);
      setEditingDirectory([...editingDirectory]);
    }
  };
  
  // 更新节点标题
  const updateNodeTitle = (node: DirectoryNode, newTitle: string) => {
    node.title = newTitle;
    setEditingDirectory([...editingDirectory]);
  };
  
  // 收集所有节点（扁平化）
  const flattenDirectoryNodes = (nodes: DirectoryNode[], result: DirectoryNode[] = []): DirectoryNode[] => {
    nodes.forEach(node => {
      result.push(node);
      if (node.children && node.children.length > 0) {
        flattenDirectoryNodes(node.children, result);
      }
    });
    return result;
  };
  
  // AI生成全文
  const generateFullContent = async () => {
    if (!currentProject) {
      showToast('error', '请先选择项目');
      return;
    }
    
    if (directory.length === 0) {
      showToast('error', '请先在Step 3生成目录');
      return;
    }
    
    // 打开生成页面
    setShowGeneratingPage(true);
    setGeneratingFullContent(true);
    
    // 初始化节点状态
    const flatNodes = flattenDirectoryNodes(directory);
    const sectionsState: Record<string, any> = {};
    flatNodes.forEach(node => {
      sectionsState[node.id] = {
        title: node.title,
        content: '',
        status: 'pending'
      };
    });
    setGeneratedSections(sectionsState);
    
    try {
      // 调用后端API（同步执行，方便显示进度）
      const res = await api.post(`/api/apps/tender/projects/${currentProject.id}/generate-full-content?sync=1`);
      
      if (res.status === 'success') {
        showToast('success', 'AI生成完成！');
        
        // 标记所有章节为完成
        const updatedSections = { ...sectionsState };
        Object.keys(updatedSections).forEach(key => {
          updatedSections[key].status = 'done';
        });
        setGeneratedSections(updatedSections);
      } else {
        showToast('error', `生成失败: ${res.message || 'Unknown error'}`);
      }
      
    } catch (err: any) {
      showToast('error', `生成失败: ${err.message || err}`);
    } finally {
      setGeneratingFullContent(false);
    }
  };
  
  // 导出标书
  const exportFullDocument = async () => {
    if (!currentProject) return;
    
    try {
      // 使用已有的导出接口
      const selectedFormatTemplateId = state.selectedFormatTemplateId;
      const url = selectedFormatTemplateId
        ? `/api/apps/tender/projects/${currentProject.id}/export/docx?format_template_id=${selectedFormatTemplateId}`
        : `/api/apps/tender/projects/${currentProject.id}/export/docx`;
      
      // api.get 会根据 Content-Type 自动返回 Blob
      const blob = await api.get(url);
      const downloadUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `${currentProject.name}-投标书.docx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(downloadUrl);
      
      showToast('success', '标书导出成功');
    } catch (err: any) {
      showToast('error', `导出失败: ${err.message}`);
    }
  };

  // 已删除 runFullAudit 函数（改用一体化审核）

  const runReview = async () => {
    if (!currentProject) return;
    const projectId = currentProject.id;
    
    if (!selectedBidder && assetsByKind.bid.length > 0) {
      alert('请选择投标人');
      return;
    }
    
    try {
      // ✨ 构建API参数（包含自定义规则包）
      let apiUrl = `/api/apps/tender/projects/${projectId}/audit/unified?sync=0&bidder_name=${encodeURIComponent(selectedBidder)}`;
      
      // 如果选中了自定义规则包，添加到URL参数
      if (selectedRulePackIds.length > 0) {
        const packIdsParam = selectedRulePackIds.join(',');
        apiUrl += `&custom_rule_pack_ids=${encodeURIComponent(packIdsParam)}`;
      }
      
      // 调用新的一体化审核接口
      const res = await api.post(apiUrl);
      
      const modeMsg = selectedRulePackIds.length > 0 
        ? `（启用${selectedRulePackIds.length}个自定义规则包）` 
        : '（基础评估模式）';
      showToast('success', `一体化审核启动成功！正在审核投标人: ${selectedBidder} ${modeMsg}`);
      
      // 设置新的run状态
      const newRun: TenderRun = { 
        id: res.run_id, 
        status: 'running', 
        progress: 0, 
        message: `一体化审核中${modeMsg}...`, 
        kind: 'review' 
      } as TenderRun;
      setReviewRun(newRun);
      
      // 启动轮询
      startPolling(projectId, 'review', res.run_id, () => loadReview(projectId));
    } catch (err: any) {
      // 检查是否是"未提取招标要求"错误
      const errorMsg = err?.response?.data?.detail || err?.message || String(err);
      if (errorMsg.includes('招标要求') || errorMsg.includes('② 要求')) {
        alert('⚠️ 请先提取招标要求\n\n请在【② 要求】标签页点击"提取要求"按钮，\n完成招标要求提取后再进行审核。');
      } else {
        alert(`审核失败: ${errorMsg}`);
      }
      setReviewRun(null);
    }
  };

  const showEvidence = async (chunkIds: string[], highlightText?: string) => {
    if (chunkIds.length === 0) return;
    try {
      const data = await api.post('/api/apps/tender/chunks/lookup', { chunk_ids: chunkIds });
      // 为每个 chunk 添加高亮信息
      const chunksWithHighlight = data.map((chunk: any) => ({
        ...chunk,
        highlightText: highlightText || ''
      }));
      setEvidenceChunks(chunksWithHighlight);
      setEvidencePanelOpen(true);
    } catch (err) {
      alert(`加载证据失败: ${err}`);
    }
  };

  // -------------------- 数据衍生 --------------------

  const assetsByKind = useMemo(() => {
    const result: Record<TenderAssetKind, TenderAsset[]> = {
      tender: [],
      bid: [],
      template: [],
      custom_rule: [],
    };
    assets.forEach(a => {
      if (a.kind in result) {
        result[a.kind].push(a);
      }
    });
    return result;
  }, [assets]);

  const bidderOptions = useMemo(() => {
    return Array.from(new Set(
      assetsByKind.bid.map(a => a.bidder_name).filter(Boolean)
    )) as string[];
  }, [assetsByKind.bid]);

  // -------------------- 副作用 --------------------

  // 监控 viewMode 变化
  useEffect(() => {
    console.log('viewMode 已改变为:', viewMode);
  }, [viewMode]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  useEffect(() => {
    loadFormatTemplates();
  }, [loadFormatTemplates]);

  // 项目切换时：加载后端数据 + 恢复轮询
  useEffect(() => {
    if (!currentProject?.id) return;
    
    const projectId = currentProject.id;
    console.log('[useEffect] 项目切换，加载新项目数据和run状态:', projectId);
    
    // 加载项目数据
    loadAssets(projectId);
    loadProjectInfo(projectId);
    loadRiskAnalysis(projectId);  // 已改名
    loadDirectory(projectId);
    loadBidResponses(projectId);
    loadReview(projectId);
    loadSampleFragments(projectId);
    
    // 从后端加载run状态，并恢复轮询
    const loadAndRestoreRuns = async () => {
      try {
        const data = await api.get(`/api/apps/tender/projects/${projectId}/runs/latest`);
        console.log('[loadAndRestoreRuns] 收到run状态:', data);
        
        // 验证项目是否切换
        if (currentProject?.id !== projectId) {
          console.log('[loadAndRestoreRuns] 加载完成时项目已切换，丢弃数据');
          return;
        }
        
        const infoRunData = data.extract_project_info || null;
        const riskRunData = data.extract_risks || null;
        const dirRunData = data.generate_directory || null;
        const bidResponseRunData = data.extract_bid_responses || null;
        const reviewRunData = data.review || null;
        
        // 更新状态到ProjectState
        updateProjectState(projectId, {
          runs: {
            info: infoRunData,
            risk: riskRunData,
            directory: dirRunData,
            bidResponse: bidResponseRunData,
            review: reviewRunData,
          }
        });
        
        // 恢复running任务的轮询
        if (infoRunData?.status === 'running') {
          console.log('[loadAndRestoreRuns] 恢复项目信息抽取轮询:', infoRunData.id);
          startPolling(projectId, 'info', infoRunData.id, () => loadProjectInfo(projectId));
        }
        if (riskRunData?.status === 'running') {
          console.log('[loadAndRestoreRuns] 恢复招标要求提取轮询:', riskRunData.id);
          startPolling(projectId, 'risk', riskRunData.id, () => loadRiskAnalysis(projectId));
        }
        if (dirRunData?.status === 'running') {
          console.log('[loadAndRestoreRuns] 恢复目录生成轮询:', dirRunData.id);
          startPolling(projectId, 'directory', dirRunData.id, async () => {
            const nodes = await loadDirectory(projectId);
            if (nodes.length > 0) {
              await loadBodiesForAllNodes(nodes);
            }
            await loadSampleFragments(projectId);
          });
        }
        if (bidResponseRunData?.status === 'running') {
          console.log('[loadAndRestoreRuns] 恢复投标响应抽取轮询:', bidResponseRunData.id);
          startPolling(projectId, 'bidResponse', bidResponseRunData.id, () => loadBidResponses(projectId));
        }
        if (reviewRunData?.status === 'running') {
          console.log('[loadAndRestoreRuns] 恢复审核轮询:', reviewRunData.id);
          startPolling(projectId, 'review', reviewRunData.id, () => loadReview(projectId));
        }
      } catch (err) {
        console.error('[loadAndRestoreRuns] 加载项目run状态失败:', err);
      }
    };
    
    loadAndRestoreRuns();
  }, [currentProject?.id]); // 只监听项目ID变化

  // 切换项目时，恢复上次选择的格式模板（用于"自动套用格式"按钮）
  useEffect(() => {
    if (!currentProject) return;
    const key = `tender.formatTemplateId.${currentProject.id}`;
    const saved = localStorage.getItem(key) || "";
    setSelectedFormatTemplateId(saved);
  }, [currentProject]);

  // 监听投标人选择变化，重新加载审核数据
  useEffect(() => {
    if (!currentProject?.id) return;
    if (reviewItems.length > 0) {
      // 只有当已经有审核数据时才重新加载
      console.log('[useEffect] 投标人选择变化，重新加载审核数据:', selectedBidder || '全部');
      loadReview(currentProject.id);
    }
  }, [selectedBidder, currentProject?.id, loadReview]);

  // 选择模板后，加载 spec 并应用 tocStyleVars（画布原地刷新样式）
  useEffect(() => {
    loadSelectedTemplateSpec(selectedFormatTemplateId);
  }, [selectedFormatTemplateId, loadSelectedTemplateSpec]);

  // Step3：目录存在时，确保正文缓存就绪
  useEffect(() => {
    if (activeTab === 3 && currentProject && directory.length > 0) {
      loadBodiesForAllNodes(directory);
    }
  }, [activeTab, currentProject, directory, loadBodiesForAllNodes]);

  // ==================== 内联样式（仅布局） ====================
  // 所有颜色/背景/边框样式已移除，统一使用系统 className

  // ==================== 目录渲染辅助函数 ====================
  
  const renderDirectoryTree = (nodes: DirectoryNode[], level: number = 0): React.ReactNode => {
    if (!nodes || nodes.length === 0) return null;
    
    return (
      <div style={{ marginLeft: level > 0 ? '20px' : 0 }}>
        {nodes.map((node, idx) => (
          <div key={node.id || idx} style={{ marginBottom: '8px' }}>
            <div style={{ 
              display: 'flex', 
              alignItems: 'center',
              padding: '8px 12px',
              backgroundColor: 'rgba(148, 163, 184, 0.05)',
              borderRadius: '4px',
              borderLeft: `3px solid ${level === 0 ? '#667eea' : level === 1 ? '#10b981' : '#f59e0b'}`
            }}>
              <span style={{ 
                color: '#94a3b8', 
                fontSize: '13px', 
                marginRight: '8px',
                minWidth: '60px'
              }}>
                {node.numbering}
              </span>
              <span style={{ color: '#e5e7eb', fontSize: '14px', flex: 1 }}>
                {node.title}
              </span>
            </div>
            {node.children && node.children.length > 0 && renderDirectoryTree(node.children, level + 1)}
          </div>
        ))}
      </div>
    );
  };
  
  const renderEditableDirectoryTree = (nodes: DirectoryNode[], level: number = 0): React.ReactNode => {
    if (!nodes || nodes.length === 0) return null;
    
    return (
      <div style={{ marginLeft: level > 0 ? '20px' : 0 }}>
        {nodes.map((node, idx) => (
          <div key={node.id || idx} style={{ marginBottom: '12px' }}>
            <div style={{ 
              display: 'flex', 
              alignItems: 'center',
              gap: '8px',
              padding: '12px',
              backgroundColor: 'rgba(148, 163, 184, 0.05)',
              borderRadius: '4px',
              borderLeft: `3px solid ${level === 0 ? '#667eea' : level === 1 ? '#10b981' : '#f59e0b'}`
            }}>
              <span style={{ 
                color: '#94a3b8', 
                fontSize: '13px',
                minWidth: '50px'
              }}>
                {node.numbering}
              </span>
              <input
                type="text"
                value={node.title}
                onChange={(e) => updateNodeTitle(node, e.target.value)}
                style={{
                  flex: 1,
                  padding: '6px 10px',
                  backgroundColor: '#0f172a',
                  border: '1px solid rgba(148, 163, 184, 0.2)',
                  borderRadius: '4px',
                  color: '#e5e7eb',
                  fontSize: '14px'
                }}
              />
              <button
                onClick={() => addChildNode(node)}
                className="link-button"
                style={{
                  padding: '4px 8px',
                  fontSize: '12px',
                  backgroundColor: 'rgba(16, 185, 129, 0.1)',
                  color: '#10b981',
                  borderRadius: '4px'
                }}
                title="添加子章节"
              >
                ➕ 添加子节点
              </button>
              <button
                onClick={() => handleDeleteNode(node)}
                className="link-button"
                style={{
                  padding: '4px 8px',
                  fontSize: '12px',
                  backgroundColor: 'rgba(239, 68, 68, 0.1)',
                  color: '#ef4444',
                  borderRadius: '4px'
                }}
                title="删除此节点"
              >
                🗑️ 删除
              </button>
            </div>
            {node.children && node.children.length > 0 && renderEditableDirectoryTree(node.children, level + 1)}
          </div>
        ))}
      </div>
    );
  };

  // ==================== 渲染 ====================

  return (
    <div className="app-root">
      {toast && (
        <div
          style={{
            position: "fixed",
            top: 16,
            right: 16,
            zIndex: 9999,
            maxWidth: 480,
            padding: "12px 16px",
            borderRadius: 10,
            background: 
              toast.kind === "success" ? "rgba(16,185,129,0.95)" : 
              toast.kind === "warning" ? "rgba(245,158,11,0.95)" :
              "rgba(239,68,68,0.95)",
            color: "#fff",
            boxShadow: "0 8px 24px rgba(0,0,0,0.2)",
            fontSize: 14,
            lineHeight: 1.5,
            pointerEvents: "auto",
            cursor: "pointer",
          }}
          onClick={() => setToast(null)}
          aria-live="polite"
          title="点击关闭"
        >
          <div style={{ display: "flex", alignItems: "flex-start", gap: "8px" }}>
            <span style={{ fontSize: "18px", flexShrink: 0 }}>
              {toast.kind === "success" ? "✅" : toast.kind === "warning" ? "⚠️" : "❌"}
            </span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 500, marginBottom: toast.detail ? "4px" : 0 }}>
                {toast.msg}
              </div>
              {toast.detail && (
                <div style={{ 
                  fontSize: "12px", 
                  opacity: 0.9, 
                  marginTop: "4px",
                  padding: "6px 8px",
                  background: "rgba(0,0,0,0.15)",
                  borderRadius: "4px",
                  fontFamily: "monospace",
                  wordBreak: "break-word"
                }}>
                  {toast.detail}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
      {/* 左侧边栏：导航菜单 */}
      <div className="sidebar">
        <div className="sidebar-title">招投标工作台</div>
        <div className="sidebar-subtitle">项目管理 + 智能审核 + 文档生成</div>
        
        <div style={{ flex: 1, overflow: 'auto', padding: '16px' }}>
          {/* 导航菜单 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <button
              onClick={() => setViewMode("projectList")}
              className="sidebar-btn"
              style={{ 
                width: '100%',
                padding: '12px 16px',
                background: viewMode === "projectList" ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' : 'rgba(255, 255, 255, 0.05)',
                border: viewMode === "projectList" ? 'none' : '1px solid rgba(148, 163, 184, 0.25)',
                borderLeft: viewMode === "projectList" ? '4px solid #667eea' : '4px solid transparent',
                borderRadius: '8px',
                color: '#ffffff',
                fontSize: '14px',
                fontWeight: viewMode === "projectList" ? '600' : '500',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-start',
                gap: '12px',
                boxShadow: viewMode === "projectList" ? '0 2px 8px rgba(102, 126, 234, 0.3)' : 'none',
                transition: 'all 0.2s ease',
              }}
            >
              <span style={{ fontSize: '18px' }}>📂</span>
              <span>项目管理</span>
            </button>

            <button
              onClick={() => setViewMode("formatTemplates")}
              className="sidebar-btn"
              style={{ 
                width: '100%',
                padding: '12px 16px',
                background: viewMode === "formatTemplates" ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' : 'rgba(255, 255, 255, 0.05)',
                border: viewMode === "formatTemplates" ? 'none' : '1px solid rgba(148, 163, 184, 0.25)',
                borderLeft: viewMode === "formatTemplates" ? '4px solid #667eea' : '4px solid transparent',
                borderRadius: '8px',
                color: '#ffffff',
                fontSize: '14px',
                fontWeight: viewMode === "formatTemplates" ? '600' : '500',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-start',
                gap: '12px',
                boxShadow: viewMode === "formatTemplates" ? '0 2px 8px rgba(102, 126, 234, 0.3)' : 'none',
                transition: 'all 0.2s ease',
              }}
            >
              <span style={{ fontSize: '18px' }}>📋</span>
              <span>格式模板</span>
            </button>

            <button
              onClick={() => setViewMode("customRules")}
              className="sidebar-btn"
              style={{ 
                width: '100%',
                padding: '12px 16px',
                background: viewMode === "customRules" ? 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)' : 'rgba(255, 255, 255, 0.05)',
                border: viewMode === "customRules" ? 'none' : '1px solid rgba(148, 163, 184, 0.25)',
                borderLeft: viewMode === "customRules" ? '4px solid #f093fb' : '4px solid transparent',
                borderRadius: '8px',
                color: '#ffffff',
                fontSize: '14px',
                fontWeight: viewMode === "customRules" ? '600' : '500',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-start',
                gap: '12px',
                boxShadow: viewMode === "customRules" ? '0 2px 8px rgba(240, 147, 251, 0.3)' : 'none',
                transition: 'all 0.2s ease',
              }}
            >
              <span style={{ fontSize: '18px' }}>⚙️</span>
              <span>自定义规则</span>
            </button>

            <button
              onClick={() => setViewMode("userDocuments")}
              className="sidebar-btn"
              style={{ 
                width: '100%',
                padding: '12px 16px',
                background: viewMode === "userDocuments" ? 'linear-gradient(135deg, #fccb90 0%, #d57eeb 100%)' : 'rgba(255, 255, 255, 0.05)',
                border: viewMode === "userDocuments" ? 'none' : '1px solid rgba(148, 163, 184, 0.25)',
                borderLeft: viewMode === "userDocuments" ? '4px solid #fccb90' : '4px solid transparent',
                borderRadius: '8px',
                color: '#ffffff',
                fontSize: '14px',
                fontWeight: viewMode === "userDocuments" ? '600' : '500',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-start',
                gap: '12px',
                boxShadow: viewMode === "userDocuments" ? '0 2px 8px rgba(252, 203, 144, 0.3)' : 'none',
                transition: 'all 0.2s ease',
              }}
            >
              <span style={{ fontSize: '18px' }}>📁</span>
              <span>用户文档</span>
            </button>
          </div>
        </div>
      </div>

      {/* 中间工作区 */}
      <div className="main-panel">
        {viewMode === "projectList" ? (
          /* 项目管理视图 - 项目列表 + 创建表单 */
          <div className="kb-detail" style={{ padding: '32px' }}>
            {/* 页面标题 */}
            <div style={{ marginBottom: '32px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h2 style={{ margin: 0, color: '#e2e8f0', fontSize: '28px', fontWeight: '600' }}>项目管理</h2>
                <p style={{ margin: '8px 0 0 0', color: '#94a3b8', fontSize: '14px' }}>管理您的招投标项目</p>
              </div>
              <button
                onClick={() => setShowCreateForm(!showCreateForm)}
                className="sidebar-btn"
                style={{
                  padding: '12px 24px',
                  background: showCreateForm ? 'rgba(255, 255, 255, 0.1)' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  border: 'none',
                  borderRadius: '8px',
                  color: '#ffffff',
                  fontSize: '14px',
                  fontWeight: '500',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  boxShadow: showCreateForm ? 'none' : '0 2px 8px rgba(102, 126, 234, 0.3)',
                }}
              >
                <span style={{ fontSize: '18px' }}>{showCreateForm ? '✕' : '+'}</span>
                <span>{showCreateForm ? '取消' : '新建项目'}</span>
              </button>
            </div>

            {/* 创建项目表单（可折叠） */}
            {showCreateForm && (
              <div style={{
                background: 'rgba(30, 41, 59, 0.6)',
                border: '1px solid rgba(148, 163, 184, 0.25)',
                borderRadius: '12px',
                padding: '24px',
                marginBottom: '32px',
              }}>
                <h3 style={{ margin: '0 0 16px 0', color: '#e2e8f0', fontSize: '18px', fontWeight: '600' }}>创建新项目</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div>
                    <label style={{ display: 'block', marginBottom: '8px', color: '#cbd5e1', fontSize: '14px', fontWeight: '500' }}>
                      项目名称 <span style={{ color: '#f87171' }}>*</span>
                    </label>
                    <input
                      type="text"
                      placeholder="请输入项目名称"
                      value={newProjectName}
                      onChange={e => setNewProjectName(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '12px',
                        background: 'rgba(15, 23, 42, 0.6)',
                        border: '1px solid rgba(148, 163, 184, 0.25)',
                        borderRadius: '8px',
                        color: '#e2e8f0',
                        fontSize: '14px',
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: '8px', color: '#cbd5e1', fontSize: '14px', fontWeight: '500' }}>
                      项目描述（可选）
                    </label>
                    <textarea
                      placeholder="请输入项目描述"
                      value={newProjectDesc}
                      onChange={e => setNewProjectDesc(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '12px',
                        minHeight: '80px',
                        background: 'rgba(15, 23, 42, 0.6)',
                        border: '1px solid rgba(148, 163, 184, 0.25)',
                        borderRadius: '8px',
                        color: '#e2e8f0',
                        fontSize: '14px',
                        resize: 'vertical',
                      }}
                    />
                  </div>
                  <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
                    <button
                      onClick={() => {
                        setShowCreateForm(false);
                        setNewProjectName('');
                        setNewProjectDesc('');
                      }}
                      style={{
                        padding: '10px 20px',
                        background: 'rgba(255, 255, 255, 0.05)',
                        border: '1px solid rgba(148, 163, 184, 0.25)',
                        borderRadius: '8px',
                        color: '#cbd5e1',
                        fontSize: '14px',
                        cursor: 'pointer',
                      }}
                    >
                      取消
                    </button>
                    <button
                      onClick={createProject}
                      disabled={!newProjectName.trim()}
                      style={{
                        padding: '10px 20px',
                        background: newProjectName.trim() ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' : 'rgba(255, 255, 255, 0.1)',
                        border: 'none',
                        borderRadius: '8px',
                        color: '#ffffff',
                        fontSize: '14px',
                        fontWeight: '500',
                        cursor: newProjectName.trim() ? 'pointer' : 'not-allowed',
                        opacity: newProjectName.trim() ? 1 : 0.5,
                      }}
                    >
                      创建项目
                    </button>
                  </div>
                  <div style={{ color: '#94a3b8', fontSize: '13px', marginTop: '4px' }}>
                    💡 创建项目时会自动创建知识库
                  </div>
                </div>
              </div>
            )}

            {/* 项目列表 */}
            {projects.length === 0 ? (
              <div style={{
                background: 'rgba(30, 41, 59, 0.4)',
                border: '2px dashed rgba(148, 163, 184, 0.3)',
                borderRadius: '12px',
                padding: '64px 32px',
                textAlign: 'center',
              }}>
                <div style={{ fontSize: '64px', marginBottom: '16px' }}>📋</div>
                <div style={{ color: '#e2e8f0', fontSize: '18px', fontWeight: '500', marginBottom: '8px' }}>还没有项目</div>
                <div style={{ color: '#94a3b8', fontSize: '14px', marginBottom: '24px' }}>点击上方"新建项目"按钮开始创建您的第一个项目</div>
              </div>
            ) : (
              <>
                {/* 搜索和批量操作工具栏 */}
                <div style={{ marginBottom: '20px', display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
                  {/* 搜索框 */}
                  <input
                    type="text"
                    placeholder="🔍 搜索项目名称或描述..."
                    value={searchKeyword}
                    onChange={(e) => setSearchKeyword(e.target.value)}
                    style={{
                      flex: 1,
                      minWidth: '200px',
                      padding: '10px 16px',
                      background: 'rgba(15, 23, 42, 0.6)',
                      border: '1px solid rgba(148, 163, 184, 0.25)',
                      borderRadius: '8px',
                      color: '#e2e8f0',
                      fontSize: '14px',
                    }}
                  />
                  
                  {/* 批量操作按钮 */}
                  {selectedProjectIds.size > 0 && (
                    <>
                      <button
                        onClick={handleBatchDelete}
                        disabled={isBatchDeleting}
                        style={{
                          padding: '10px 16px',
                          background: 'rgba(239, 68, 68, 0.2)',
                          border: '1px solid rgba(239, 68, 68, 0.4)',
                          borderRadius: '8px',
                          color: '#fca5a5',
                          fontSize: '14px',
                          cursor: isBatchDeleting ? 'not-allowed' : 'pointer',
                          opacity: isBatchDeleting ? 0.6 : 1,
                        }}
                      >
                        {isBatchDeleting ? '删除中...' : `🗑️ 删除选中 (${selectedProjectIds.size})`}
                      </button>
                      <button
                        onClick={() => setSelectedProjectIds(new Set())}
                        style={{
                          padding: '10px 16px',
                          background: 'rgba(148, 163, 184, 0.2)',
                          border: '1px solid rgba(148, 163, 184, 0.3)',
                          borderRadius: '8px',
                          color: '#cbd5e1',
                          fontSize: '14px',
                          cursor: 'pointer',
                        }}
                      >
                        ✕ 取消选择
                      </button>
                    </>
                  )}

                  {/* 全选按钮 */}
                  {filteredProjects.length > 0 && (
                    <button
                      onClick={toggleSelectAll}
                      style={{
                        padding: '10px 16px',
                        background: 'rgba(148, 163, 184, 0.1)',
                        border: '1px solid rgba(148, 163, 184, 0.3)',
                        borderRadius: '8px',
                        color: '#cbd5e1',
                        fontSize: '14px',
                        cursor: 'pointer',
                      }}
                    >
                      {selectedProjectIds.size === filteredProjects.length ? '☑ 取消全选' : '☐ 全选'}
                    </button>
                  )}
                </div>

                {/* 项目数量显示 */}
                <div style={{ marginBottom: '16px', color: '#cbd5e1', fontSize: '14px' }}>
                  共 {filteredProjects.length} 个项目{projects.length !== filteredProjects.length ? ` (已筛选 ${projects.length - filteredProjects.length} 个)` : ''}
                </div>

                {filteredProjects.length === 0 ? (
                  <div style={{
                    background: 'rgba(30, 41, 59, 0.4)',
                    border: '2px dashed rgba(148, 163, 184, 0.3)',
                    borderRadius: '12px',
                    padding: '64px 32px',
                    textAlign: 'center',
                  }}>
                    <div style={{ fontSize: '64px', marginBottom: '16px' }}>🔍</div>
                    <div style={{ color: '#e2e8f0', fontSize: '18px', fontWeight: '500', marginBottom: '8px' }}>没有找到匹配的项目</div>
                    <div style={{ color: '#94a3b8', fontSize: '14px' }}>尝试使用不同的关键词搜索</div>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '24px' }}>
                    {filteredProjects.map(proj => {
                  // 计算项目进度（示例：基于state）
                  const projectState = projectStatesRef.current.get(proj.id);
                  const hasRequirements = projectState?.requirements && projectState.requirements.length > 0;
                  const hasDirectory = projectState?.directoryNodes && projectState.directoryNodes.length > 0;
                  const hasReview = projectState?.reviewItems && projectState.reviewItems.length > 0;
                  
                  let completedSteps = 0;
                  if (hasRequirements) completedSteps++;
                  if (hasDirectory) completedSteps++;
                  if (hasReview) completedSteps++;
                  
                  const progressPercent = Math.round((completedSteps / 5) * 100);
                      const isSelected = selectedProjectIds.has(proj.id);
                  
                  return (
                    <div
                      key={proj.id}
                      style={{
                        background: 'rgba(30, 41, 59, 0.6)',
                            border: isSelected ? '2px solid rgba(79, 70, 229, 0.8)' : '1px solid rgba(148, 163, 184, 0.25)',
                        borderRadius: '12px',
                        padding: '20px',
                            position: 'relative',
                          }}
                        >
                          {/* Checkbox */}
                          <div
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleProjectSelection(proj.id);
                            }}
                            style={{
                              position: 'absolute',
                              top: '12px',
                              right: '12px',
                              width: '24px',
                              height: '24px',
                              background: isSelected ? 'rgba(79, 70, 229, 0.8)' : 'rgba(30, 41, 59, 0.6)',
                              border: '2px solid rgba(148, 163, 184, 0.5)',
                              borderRadius: '4px',
                        cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              color: '#fff',
                              fontSize: '14px',
                              fontWeight: 'bold',
                      }}
                    >
                            {isSelected && '✓'}
                          </div>

                      {/* 项目名称和描述 */}
                          <div style={{ marginBottom: '16px', paddingRight: '32px' }} onClick={() => selectProject(proj)}>
                            <h3 style={{ margin: '0 0 8px 0', color: '#e2e8f0', fontSize: '18px', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                          <span>📦</span>
                          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{proj.name}</span>
                        </h3>
                        {proj.description && (
                              <p style={{ margin: 0, color: '#94a3b8', fontSize: '13px', lineHeight: '1.5', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', cursor: 'pointer' }}>
                            {proj.description}
                          </p>
                        )}
                      </div>

                      {/* 进度条 */}
                      <div style={{ marginBottom: '16px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                          <span style={{ color: '#cbd5e1', fontSize: '12px', fontWeight: '500' }}>完成进度</span>
                          <span style={{ color: '#667eea', fontSize: '12px', fontWeight: '600' }}>{progressPercent}%</span>
                        </div>
                        <div style={{ width: '100%', height: '6px', background: 'rgba(15, 23, 42, 0.6)', borderRadius: '3px', overflow: 'hidden' }}>
                          <div style={{ width: `${progressPercent}%`, height: '100%', background: 'linear-gradient(90deg, #667eea 0%, #764ba2 100%)', transition: 'width 0.3s ease' }} />
                        </div>
                      </div>

                      {/* 状态标签 */}
                      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', flexWrap: 'wrap' }}>
                        {hasRequirements && (
                          <span style={{ padding: '4px 10px', background: 'rgba(34, 197, 94, 0.15)', border: '1px solid rgba(34, 197, 94, 0.3)', borderRadius: '6px', color: '#86efac', fontSize: '11px', fontWeight: '500' }}>
                            ✓ 要求已提取
                          </span>
                        )}
                        {hasDirectory && (
                          <span style={{ padding: '4px 10px', background: 'rgba(59, 130, 246, 0.15)', border: '1px solid rgba(59, 130, 246, 0.3)', borderRadius: '6px', color: '#93c5fd', fontSize: '11px', fontWeight: '500' }}>
                            ✓ 目录已生成
                          </span>
                        )}
                        {hasReview && (
                          <span style={{ padding: '4px 10px', background: 'rgba(168, 85, 247, 0.15)', border: '1px solid rgba(168, 85, 247, 0.3)', borderRadius: '6px', color: '#c4b5fd', fontSize: '11px', fontWeight: '500' }}>
                            ✓ 已审核
                          </span>
                        )}
                      </div>

                      {/* 创建时间 */}
                      <div style={{ color: '#64748b', fontSize: '12px', marginBottom: '16px' }}>
                        创建时间：{proj.created_at ? new Date(proj.created_at).toLocaleString('zh-CN') : '未知'}
                      </div>

                      {/* 操作按钮 */}
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            selectProject(proj);
                          }}
                          style={{
                            flex: 1,
                            padding: '10px',
                            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                            border: 'none',
                            borderRadius: '8px',
                            color: '#ffffff',
                            fontSize: '13px',
                            fontWeight: '500',
                            cursor: 'pointer',
                          }}
                        >
                          进入项目
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            openEditProject(proj);
                          }}
                          title="编辑项目"
                          style={{
                            padding: '10px 14px',
                            background: 'rgba(255, 255, 255, 0.05)',
                            border: '1px solid rgba(148, 163, 184, 0.25)',
                            borderRadius: '8px',
                            color: '#cbd5e1',
                            fontSize: '16px',
                            cursor: 'pointer',
                          }}
                        >
                          ✏️
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            openDeleteProject(proj);
                          }}
                          title="删除项目"
                          style={{
                            padding: '10px 14px',
                            background: 'rgba(239, 68, 68, 0.1)',
                            border: '1px solid rgba(239, 68, 68, 0.3)',
                            borderRadius: '8px',
                            color: '#fca5a5',
                            fontSize: '16px',
                            cursor: 'pointer',
                          }}
                        >
                          🗑️
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
                )}
              </>
            )}
          </div>
        ) : viewMode === "formatTemplates" ? (
          /* 格式模板管理视图 - 独立于项目 */
          <div className="kb-detail">
            <FormatTemplatesPage embedded onBack={() => setViewMode("projectList")} />
          </div>
        ) : viewMode === "customRules" ? (
          /* 自定义规则管理视图 - 可不选项目 */
          <div className="kb-detail">
            <CustomRulesPage 
              projectId={currentProject?.id} 
              embedded 
              onBack={() => setViewMode("projectList")} 
            />
          </div>
        ) : viewMode === "userDocuments" ? (
          /* 用户文档管理视图 - 可不选项目 */
          <div className="kb-detail">
            <UserDocumentsPage
              projectId={currentProject?.id}
              embedded
              onBack={() => setViewMode("projectList")}
            />
          </div>
        ) : viewMode === "projectDetail" && currentProject ? (
          <>
            {/* 面包屑导航 + 返回按钮 */}
            <div style={{
              padding: '16px 24px',
              background: 'rgba(15, 23, 42, 0.6)',
              borderBottom: '1px solid rgba(148, 163, 184, 0.25)',
              display: 'flex',
              alignItems: 'center',
              gap: '16px',
            }}>
              <button
                onClick={() => setViewMode("projectList")}
                style={{
                  padding: '8px 16px',
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(148, 163, 184, 0.25)',
                  borderRadius: '8px',
                  color: '#cbd5e1',
                  fontSize: '14px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span>←</span>
                <span>返回项目列表</span>
              </button>
              
              {/* 面包屑 */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#94a3b8', fontSize: '14px' }}>
                <span style={{ cursor: 'pointer', color: '#cbd5e1' }} onClick={() => setViewMode("projectList")}>项目管理</span>
                <span>/</span>
                <span style={{ color: '#e2e8f0', fontWeight: '500' }}>{currentProject.name}</span>
                {activeTab > 1 && (
                  <>
                    <span>/</span>
                    <span style={{ color: '#e2e8f0' }}>
                      {activeTab === 1 ? 'Step1: 项目信息' : 
                       activeTab === 2 ? 'Step2: 招标要求' : 
                       activeTab === 3 ? 'Step3: 目录生成' : 
                       activeTab === 4 ? 'Step4: 全文生成' : 
                       'Step5: 审核'}
                    </span>
                  </>
                )}
              </div>
            </div>

            {/* 工作区头部 */}
            <div className="header-bar">
              <div>
                <div className="header-title">{currentProject.name}</div>
                {currentProject.description && (
                  <div className="sidebar-hint" style={{ marginTop: '4px' }}>
                    {currentProject.description}
                  </div>
                )}
              </div>
            </div>

            {/* 工作区内容 */}
            <div className="kb-detail">
              <>
              {/* 项目内上传区 */}
              <section className="kb-upload-section">
                <h4>📤 项目内上传</h4>
                <div style={{ display: 'flex', gap: '12px', marginBottom: '12px', flexWrap: 'wrap' }}>
                  <select
                    value={uploadKind}
                    onChange={e => setUploadKind(e.target.value as TenderAssetKind)}
                    className="sidebar-select"
                    style={{ width: 'auto', marginBottom: 0 }}
                  >
                    <option value="tender">招标文件</option>
                    <option value="bid">投标文件</option>
                    <option value="template">模板文件</option>
                    <option value="custom_rule">自定义规则</option>
                  </select>

                  {uploadKind === 'bid' && (
                    <input
                      type="text"
                      placeholder="投标人名称（必填）"
                      value={bidderName}
                      onChange={e => setBidderName(e.target.value)}
                      className="sidebar-select"
                      style={{ width: '200px', marginBottom: 0 }}
                    />
                  )}

                  <input
                    type="file"
                    multiple
                    onChange={handleFilesChange}
                    style={{ flex: 1, minWidth: '200px' }}
                  />

                  <button 
                    onClick={handleUpload} 
                    className="kb-create-form" 
                    style={{ width: 'auto', marginBottom: 0 }}
                    disabled={uploading || files.length === 0}
                  >
                    {uploading ? '上传中...' : '上传并绑定'}
                  </button>
                </div>
                
                {files.length > 0 && (
                  <div className="sidebar-hint">
                    已选择 {files.length} 个文件: {files.map(f => f.name).join(', ')}
                  </div>
                )}
              </section>

              {/* 文件列表 */}
              <section className="kb-doc-section">
                <h4>📁 项目文件</h4>
                <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                  {(['tender', 'bid', 'template', 'custom_rule'] as TenderAssetKind[]).map(kind => (
                    <div key={kind} style={{ flex: '1 1 200px' }}>
                      <div className="kb-doc-title">
                        {kind === 'tender' && '📄 招标文件'}
                        {kind === 'bid' && '📝 投标文件'}
                        {kind === 'template' && '📋 模板文件'}
                        {kind === 'custom_rule' && '📌 自定义规则'}
                        <span className="sidebar-hint" style={{ marginLeft: '8px' }}>
                          ({assetsByKind[kind].length})
                        </span>
                      </div>
                      {assetsByKind[kind].map(asset => {
                        // 提取规则校验状态（仅 custom_rule）
                        const metaJson = asset.meta_json || {};
                        const validateStatus = kind === 'custom_rule' ? metaJson.validate_status : null;
                        const validateMessage = kind === 'custom_rule' ? metaJson.validate_message : null;
                        
                        return (
                          <div key={asset.id} className="kb-doc-meta" style={{ 
                            padding: '4px 0', 
                            display: 'flex', 
                            justifyContent: 'space-between', 
                            alignItems: 'center',
                            gap: '8px'
                          }}>
                            <span style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '4px' }}>
                              <span>
                                • {asset.filename}
                                {asset.bidder_name && ` (${asset.bidder_name})`}
                              </span>
                              {validateStatus && (
                                <span 
                                  style={{ 
                                    fontSize: '11px',
                                    color: validateStatus === 'valid' ? '#22c55e' : 
                                           validateStatus === 'invalid' ? '#ef4444' : 
                                           '#f59e0b',
                                    marginLeft: '12px'
                                  }}
                                  title={validateMessage || ''}
                                >
                                  {validateStatus === 'valid' && '✓ 校验通过'}
                                  {validateStatus === 'invalid' && '✗ 校验失败'}
                                  {validateStatus === 'error' && '⚠ 解析错误'}
                                  {validateMessage && `: ${validateMessage.substring(0, 50)}${validateMessage.length > 50 ? '...' : ''}`}
                                </span>
                              )}
                            </span>
                            <button
                              onClick={() => handleDeleteAsset(asset.id, asset.filename || '未命名文件')}
                              className="link-button"
                              style={{ 
                                color: '#ef4444',
                                fontSize: '12px',
                                padding: '2px 6px',
                                flexShrink: 0
                              }}
                              title="删除文件"
                            >
                              删除
                            </button>
                          </div>
                        );
                      })}
                      {assetsByKind[kind].length === 0 && (
                        <div className="kb-empty">暂无文件</div>
                      )}
                    </div>
                  ))}
                </div>
              </section>

              {/* 五步工作流 Tabs */}
              <div style={{ display: 'flex', gap: '8px', marginTop: '24px', marginBottom: '16px', flexWrap: 'wrap' }}>
                {[
                  { id: 1, label: '1️⃣ 上传文档' },
                  { id: 2, label: '2️⃣ 提取信息' },
                  { id: 3, label: '3️⃣ AI生成标书' },
                  { id: 4, label: '4️⃣ 审核' },
                ].map(tab => (
                  <button
                    key={tab.id}
                    onClick={() => {
                      setActiveTab(tab.id);
                      // 切换到审核Tab时加载规则包列表
                      if (tab.id === 4) {
                        loadRulePacks();
                      }
                    }}
                    className={activeTab === tab.id ? 'pill-button' : 'link-button'}
                    style={{ 
                      padding: activeTab === tab.id ? '8px 16px' : '8px 12px',
                      flex: 1,
                      minWidth: '140px'
                    }}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Step 1: 项目信息 */}
              {activeTab === 1 && (
                <section className="kb-upload-section">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                    <h4>项目信息抽取</h4>
                    <button 
                      onClick={extractProjectInfo} 
                      className="kb-create-form" 
                      style={{ width: 'auto', marginBottom: 0 }}
                      disabled={infoRun?.status === 'running'}
                    >
                      {infoRun?.status === 'running' ? '抽取中...' : '开始抽取'}
                    </button>
                  </div>
                  
                  {infoRun && (
                    <div className="kb-import-results">
                      <div className="kb-import-item">
                        状态: {infoRun.status}
                      </div>
                      {infoRun.message && (
                        <div className="kb-import-item">{infoRun.message}</div>
                      )}
                    </div>
                  )}
                  
                  {projectInfo && (
                    <div style={{ marginTop: '16px' }}>
                      {/* 使用 V3 组件展示九大类信息 */}
                      <ProjectInfoV3View info={projectInfo.data_json} onEvidence={showEvidence} />
                      {projectInfo.evidence_chunk_ids.length > 0 && (
                        <button
                          onClick={() => showEvidence(projectInfo.evidence_chunk_ids)}
                          className="link-button"
                          style={{ marginTop: '12px' }}
                        >
                          查看证据 ({projectInfo.evidence_chunk_ids.length} 条)
                        </button>
                      )}
                    </div>
                  )}
                </section>
              )}

              {/* Step 2: 招标要求提取 */}
              {/* Step 2: 招标要求提取 */}
              {activeTab === 2 && (
                <section className="kb-upload-section">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                    <h4>招标要求提取</h4>
                    <button
                      onClick={extractRequirements} 
                      className="kb-create-form"
                      style={{ width: 'auto', marginBottom: 0 }}
                      disabled={riskRun?.status === 'running'}
                    >
                      {riskRun?.status === 'running' ? '提取中...' : '开始提取'}
                    </button>
                  </div>
                  
                  {riskRun && (
                    <div className="kb-import-results">
                      <div className="kb-import-item">
                        状态: {riskRun.status}
                      </div>
                      {riskRun.message && (
                        <div className="kb-import-item">{riskRun.message}</div>
                      )}
                    </div>
                  )}
                  
                  {riskAnalysisData ? (
                    <RiskAnalysisTables
                      data={riskAnalysisData}
                      onOpenEvidence={showEvidence}
                    />
                  ) : (
                    <div className="kb-empty" style={{ marginTop: '16px' }}>
                      暂无风险记录，点击"开始识别"
                    </div>
                  )}
                </section>
              )}

              {/* Step 3: 目录 & 正文编辑 */}
              {activeTab === 3 && (
                <>
                  <section className="kb-upload-section" style={{ display: "flex", flexDirection: "column" }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                      <h4>目录生成与正文编辑</h4>
                    </div>
                    
                    {dirRun && (
                      <div className="kb-import-results">
                        <div className="kb-import-item">
                          状态: {dirRun.status}
                        </div>
                        {dirRun.message && (
                          <div className="kb-import-item" style={{ 
                            color: dirRun.status === 'failed' ? '#ef4444' : undefined,
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word'
                          }}>
                            {dirRun.message}
                          </div>
                        )}
                      </div>
                    )}

                    <DirectoryToolbar
                      hasDirectory={directory.length > 0}
                      onGenerate={() => {
                        if (directory.length > 0 && !confirm("确认重新生成目录？当前目录将被替换。")) return;
                        generateDirectory();
                      }}
                      formatTemplates={formatTemplates}
                      selectedFormatTemplateId={selectedFormatTemplateId}
                      onChangeFormatTemplateId={(id) => {
                        setSelectedFormatTemplateId(id);
                        if (currentProject) {
                          localStorage.setItem(`tender.formatTemplateId.${currentProject.id}`, id);
                        }
                      }}
                      onApplyFormatTemplate={applyFormatTemplate}
                      onAutoFillSamples={autoFillSamples}
                      applyingFormat={applyingFormat}
                      autoFillingSamples={autoFillingSamples}
                      busy={dirRun?.status === "running"}
                      generationMode={directoryGenerationMode}
                      fastStats={directoryFastStats}
                      refinementStats={directoryRefinementStats}
                      bracketParsingStats={directoryBracketParsingStats}
                      templateMatchingStats={directoryTemplateMatchingStats}
                    />

                    {directory.length > 0 ? (
                      <div style={{ display: "flex", flexDirection: "column", minHeight: 0, flex: 1 }}>
                        {/* Tab 切换 */}
                        <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                          <button
                            className="kb-create-form"
                            style={{ width: "auto", marginBottom: 0, opacity: previewMode === "content" ? 1 : 0.7 }}
                            onClick={() => setPreviewMode("content")}
                          >
                            章节内容
                          </button>

                          <button
                            className="kb-create-form"
                            style={{ width: "auto", marginBottom: 0, opacity: previewMode === "format" ? 1 : 0.7 }}
                            onClick={() => setPreviewMode("format")}
                            disabled={!formatPreviewUrl}
                            title={!formatPreviewUrl ? "请先执行「自动套用格式」生成预览" : "查看套用格式后的整体预览"}
                          >
                            格式预览
                          </button>

                          {previewMode === "format" && !!formatDownloadUrl && (
                            <button
                              onClick={downloadWordFile}
                              className="link-button"
                              style={{ alignSelf: "center", marginLeft: 8, color: "#3b82f6", textDecoration: "underline" }}
                              title="下载Word文档"
                            >
                              📥 下载Word
                            </button>
                          )}
                        </div>

                        {/* 内容区域 */}
                        {previewMode === "content" ? (
                          <div style={{ display: "flex", minHeight: 0, flex: 1 }}>
                            <div style={{ flex: 1, minWidth: 0, minHeight: 0 }}>
                              <DocumentCanvas
                                outlineFlat={directory.map((n) => ({
                                  id: n.id,
                                  title: n.title,
                                  level: n.level,
                                  numbering: n.numbering,
                                  bodyMeta: n.bodyMeta,
                                }))}
                                tocStyleVars={tocStyleVars || undefined}
                                bodyByNodeId={bodyByNodeId}
                                bodyMetaByNodeId={Object.fromEntries(directory.map((n) => [n.id, n.bodyMeta]))}
                                onNodeClick={() => setPreviewMode("content")}
                              />
                            </div>

                            <SampleSidebar
                              open={samplesOpen}
                              onToggle={() => setSamplesOpen((v) => !v)}
                              fragments={sampleFragments}
                              previewById={samplePreviewById}
                              onLoadPreview={loadSamplePreview}
                            />
                          </div>
                        ) : (
                          <div style={{ height: "72vh", border: "1px solid #eee", borderRadius: 8, overflow: "hidden" }}>
                            {formatPreviewLoading ? (
                              <div style={{
                                display: "flex",
                                flexDirection: "column",
                                alignItems: "center",
                                justifyContent: "center",
                                height: "100%",
                                color: "#64748b"
                              }}>
                                <div style={{ fontSize: "32px", marginBottom: "16px" }}>⏳</div>
                                <div>加载格式预览中...</div>
                              </div>
                            ) : formatPreviewBlobUrl ? (
                              <iframe
                                title="格式预览"
                                src={formatPreviewBlobUrl}
                                style={{ width: "100%", height: "100%", border: "none" }}
                              />
                            ) : (
                              <div style={{
                                display: "flex",
                                flexDirection: "column",
                                alignItems: "center",
                                justifyContent: "center",
                                height: "100%",
                                color: "#64748b",
                                padding: "32px"
                              }}>
                                <div style={{ fontSize: "48px", marginBottom: "16px" }}>📄</div>
                                <div style={{ fontSize: "18px", fontWeight: 500, marginBottom: "8px", color: "#334155" }}>
                                  暂无格式预览
                                </div>
                                <div style={{ fontSize: "14px", marginBottom: "24px", textAlign: "center", maxWidth: "400px", lineHeight: "1.6" }}>
                                  请先在左侧选择格式模板，然后点击「自动套用格式」生成预览
                                  {selectedFormatTemplateId && (
                                    <div style={{ marginTop: "8px", color: "#94a3b8" }}>
                                      （后端可能未返回 preview_pdf_url，或 fallback 端点未实现）
                                    </div>
                                  )}
                                </div>
                                {selectedFormatTemplateId && (
                                  <button
                                    className="kb-create-form"
                                    onClick={applyFormatTemplate}
                                    disabled={applyingFormat}
                                    style={{ width: "auto" }}
                                  >
                                    {applyingFormat ? "生成中..." : "🔄 重新生成预览"}
                                  </button>
                                )}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="kb-empty">尚未生成目录，请点击上方"生成目录"。</div>
                    )}
                  </section>
                </>
              )}

              {/* Step 4: AI生成全文 */}
              {activeTab === 4 && (
                <section className="kb-upload-section">
                  {/* 生成页面（全屏覆盖） */}
                  {showGeneratingPage && (
                    <div style={{
                      position: 'fixed',
                      top: 0,
                      left: 0,
                      right: 0,
                      bottom: 0,
                      backgroundColor: '#0f172a',
                      zIndex: 10000,
                      display: 'flex',
                      flexDirection: 'column',
                      overflowY: 'auto'
                    }}>
                      {/* 头部 */}
                      <div style={{
                        padding: '20px 40px',
                        borderBottom: '1px solid rgba(148, 163, 184, 0.2)',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        backgroundColor: '#1e293b',
                        position: 'sticky',
                        top: 0,
                        zIndex: 10
                      }}>
                        <h2 style={{ margin: 0, color: '#e5e7eb' }}>🤖 AI生成标书内容</h2>
                        <div style={{ display: 'flex', gap: '12px' }}>
                          {!generatingFullContent && (
                            <>
                              <button
                                onClick={exportFullDocument}
                                className="kb-create-form"
                                style={{ 
                                  width: 'auto', 
                                  marginBottom: 0,
                                  background: 'linear-gradient(135deg, #10b981, #22c55e)',
                                }}
                              >
                                📥 导出标书
                              </button>
                              <button
                                onClick={() => setShowGeneratingPage(false)}
                                className="kb-create-form"
                                style={{ width: 'auto', marginBottom: 0, background: '#64748b' }}
                              >
                                ✖️ 关闭
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                      
                      {/* 内容区域 */}
                      <div style={{ flex: 1, padding: '40px' }}>
                        {generatingFullContent && (
                          <div className="kb-doc-meta" style={{ 
                            padding: '20px', 
                            backgroundColor: '#eff6ff',
                            borderLeft: '4px solid #3b82f6',
                            marginBottom: '30px',
                            textAlign: 'center'
                          }}>
                            <div style={{ fontSize: '18px', fontWeight: 600, color: '#1e40af', marginBottom: '12px' }}>
                              ⏳ AI正在生成标书内容，请稍候...
                            </div>
                            <div style={{ color: '#64748b', fontSize: '14px' }}>
                              这可能需要几分钟时间，请耐心等待
                            </div>
                          </div>
                        )}
                        
                        {/* 章节列表 */}
                        <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
                          {Object.entries(generatedSections).map(([nodeId, section]) => (
                            <div 
                              key={nodeId} 
                              style={{
                                marginBottom: '24px',
                                padding: '20px',
                                backgroundColor: '#1e293b',
                                borderRadius: '8px',
                                border: '1px solid rgba(148, 163, 184, 0.2)'
                              }}
                            >
                              <div style={{ 
                                display: 'flex', 
                                alignItems: 'center', 
                                gap: '12px',
                                marginBottom: '12px'
                              }}>
                                <span style={{
                                  fontSize: '20px',
                                  display: 'inline-block'
                                }}>
                                  {section.status === 'pending' && '⏸️'}
                                  {section.status === 'generating' && '⏳'}
                                  {section.status === 'done' && '✅'}
                                  {section.status === 'error' && '❌'}
                                </span>
                                <h3 style={{ margin: 0, color: '#e5e7eb', fontSize: '18px' }}>
                                  {section.title}
                                </h3>
                              </div>
                              
                              {section.status === 'done' && section.content && (
                                <div 
                                  style={{
                                    color: '#cbd5e1',
                                    fontSize: '14px',
                                    lineHeight: '1.8',
                                    padding: '16px',
                                    backgroundColor: 'rgba(148, 163, 184, 0.05)',
                                    borderRadius: '4px',
                                    maxHeight: '200px',
                                    overflow: 'auto'
                                  }}
                                  dangerouslySetInnerHTML={{ __html: section.content }}
                                />
                              )}
                              
                              {section.status === 'generating' && (
                                <div style={{ color: '#94a3b8', fontSize: '14px' }}>
                                  正在生成内容...
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                  
                  {/* 常规Step 4界面 - 使用新的文档编辑器 */}
                  {!showGeneratingPage && (
                    <>
                      <h4>📝 编辑标书内容（Word风格）</h4>
                      
                      {directory.length === 0 ? (
                        <div className="kb-doc-meta" style={{ padding: '20px', textAlign: 'center' }}>
                          <p style={{ color: '#f59e0b', fontSize: '16px', marginBottom: '12px' }}>
                            ⚠️ 尚未生成目录
                          </p>
                          <p style={{ color: '#94a3b8', fontSize: '14px' }}>
                            请先在 <strong>Step 3</strong> 生成目录，然后返回这里编辑内容
                          </p>
                          <button
                            onClick={() => setActiveTab(3)}
                            className="kb-create-form"
                            style={{ width: 'auto', marginTop: '16px' }}
                          >
                            前往 Step 3 生成目录
                          </button>
                        </div>
                      ) : (
                        <>
                          <div className="sidebar-hint" style={{ marginBottom: '20px' }}>
                            目录已自动导入到文档编辑器。您可以：
                            <ul style={{ margin: '8px 0 0 20px', paddingLeft: 0 }}>
                              <li>左侧：管理目录结构（增删改、无限层级、自动编号）</li>
                              <li>右侧：编辑文档内容（可手动输入，也可使用AI生成）</li>
                              <li>点击左侧目录自动定位到对应章节</li>
                            </ul>
                          </div>
                          
                          {/* 嵌入Word风格文档编辑器 */}
                          {(() => {
                            console.log('[TenderWorkspace] 传递给DocumentComponentManagement的props:', {
                              embedded: true,
                              initialDirectory: directory,
                              projectId: currentProject?.id,
                              currentProject: currentProject,
                            });
                            return null;
                          })()}
                          <DocumentComponentManagement 
                            embedded={true}
                            initialDirectory={directory}
                            projectId={currentProject?.id}
                          />
                        </>
                      )}
                    </>
                  )}
                </section>
              )}

              {/* Step 5: 投标响应抽取 */}
              {/* Step 5: 审核（改为选择规则文件资产） */}
              {activeTab === 5 && (
                <section className="kb-upload-section">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                    <h4>投标文件审核</h4>
                    <button 
                      onClick={runReview} 
                      className="kb-create-form"
                      style={{ width: 'auto', marginBottom: 0 }}
                      disabled={reviewRun?.status === 'running' || !selectedBidder}
                      title="一体化审核：提取投标响应 + 审核判断一次完成"
                    >
                      {reviewRun?.status === 'running' ? '审核中...' : '🚀 开始审核'}
                    </button>
                  </div>
                  
                  <div className="kb-create-form">
                    {bidderOptions.length > 0 && (
                      <>
                        <label className="sidebar-label">选择投标人:</label>
                        <select
                          value={selectedBidder}
                          onChange={e => setSelectedBidder(e.target.value)}
                          className="sidebar-select"
                        >
                          <option value="">-- 请选择 --</option>
                          {bidderOptions.map(name => (
                            <option key={name} value={name}>{name}</option>
                          ))}
                        </select>
                      </>
                    )}
                    
                    <label className="sidebar-label">自定义规则包（可选，不选则使用基础评估）:</label>
                    <div className="kb-doc-meta" style={{
                      padding: '12px',
                      backgroundColor: '#eff6ff',
                      borderLeft: '4px solid #3b82f6',
                      marginBottom: '12px',
                      fontSize: '13px'
                    }}>
                      <div style={{ fontWeight: 600, marginBottom: '8px', color: '#1e40af' }}>💡 审核模式说明</div>
                      <ul style={{ margin: 0, paddingLeft: '20px' }}>
                        <li style={{ marginBottom: '4px' }}><strong>不选规则包</strong>：基础评估模式 - 快速检查每个招标要求是否有投标响应</li>
                        <li><strong>选择规则包</strong>：详细审核模式 - 使用自定义规则 + 基础评估，进行全面合规性审核</li>
                      </ul>
                    </div>
                    {rulePacks.length > 0 ? (
                      rulePacks.map(pack => (
                        <label key={pack.id} className="kb-item">
                          <input
                            type="checkbox"
                            checked={selectedRulePackIds.includes(pack.id)}
                            onChange={() => {
                              setSelectedRulePackIds(prev =>
                                prev.includes(pack.id)
                                  ? prev.filter(id => id !== pack.id)
                                  : [...prev, pack.id]
                              );
                            }}
                          />
                          <span>{pack.pack_name} ({pack.rule_count || 0} 条规则)</span>
                        </label>
                      ))
                    ) : (
                      <div className="kb-empty">
                        暂无自定义规则包（可选，可在左侧"自定义规则"页面创建）
                      </div>
                    )}
                    
                    <label className="sidebar-label" style={{ marginTop: '16px' }}>可选：叠加自定义审核规则文件（可多选）:</label>
                    <div className="kb-doc-meta" style={{ marginBottom: '12px' }}>
                      💡 选中的规则文件将作为额外上下文，与招标要求一起用于审核
                    </div>
                    {assetsByKind.custom_rule.length > 0 ? (
                      assetsByKind.custom_rule.map(asset => (
                        <label key={asset.id} className="kb-item">
                          <input
                            type="checkbox"
                            checked={selectedRuleAssetIds.includes(asset.id)}
                            onChange={() => {
                              setSelectedRuleAssetIds(prev =>
                                prev.includes(asset.id)
                                  ? prev.filter(id => id !== asset.id)
                                  : [...prev, asset.id]
                              );
                            }}
                          />
                          <span>{asset.filename}</span>
                        </label>
                      ))
                    ) : (
                      <div className="kb-empty">
                        暂无自定义规则文件（可选，如需要请在上方"项目内上传"中上传）
                      </div>
                    )}
                  </div>
                  
                  {reviewRun && (
                    <div className="kb-import-results">
                      <div className="kb-import-item">
                        状态: {reviewRun.status}
                      </div>
                    </div>
                  )}
                  
                  {/* Step F-Frontend-3: 统计卡片 */}
                  {reviewItems.length > 0 && (() => {
                    const stats = countByStatus(reviewItems);
                    return (
                      <div style={{ 
                        display: 'flex', 
                        gap: '12px', 
                        marginBottom: '16px',
                        flexWrap: 'wrap'
                      }}>
                        <div className="stat-card" style={{ flex: '1 1 120px', borderColor: 'rgba(148, 163, 184, 0.3)' }}>
                          <div className="stat-value" style={{ color: '#e5e7eb' }}>{stats.total}</div>
                          <div className="stat-label">总计</div>
                        </div>
                        <div className="stat-card" style={{ flex: '1 1 120px' }}>
                          <div className="stat-value" style={{ color: '#22c55e' }}>{stats.pass}</div>
                          <div className="stat-label">通过</div>
                        </div>
                        <div className="stat-card" style={{ flex: '1 1 120px' }}>
                          <div className="stat-value" style={{ color: '#fbbf24' }}>{stats.warn}</div>
                          <div className="stat-label">风险</div>
                        </div>
                        <div className="stat-card" style={{ flex: '1 1 120px' }}>
                          <div className="stat-value" style={{ color: '#ef4444' }}>{stats.fail}</div>
                          <div className="stat-label">失败</div>
                        </div>
                        <div className="stat-card" style={{ flex: '1 1 120px' }}>
                          <div className="stat-value" style={{ color: '#94a3b8' }}>{stats.pending}</div>
                          <div className="stat-label">待复核</div>
                        </div>
                      </div>
                    );
                  })()}
                  
                  {reviewItems.length > 0 ? (
                    <ReviewTable items={reviewItems} onOpenEvidence={showEvidence} />
                  ) : (
                    <div className="kb-empty" style={{ marginTop: '16px' }}>
                      暂无审核记录，点击"开始审核"
                    </div>
                  )}
                </section>
              )}
              </>
            </div>
          </>
        ) : (
          /* 未选中项目的空状态（通常不会显示，因为默认是projectList视图） */
          <div className="kb-detail" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div className="kb-empty-state">
              <div style={{ fontSize: '48px', marginBottom: '16px', textAlign: 'center' }}>📋</div>
              <div>请在左侧菜单中选择"项目管理"</div>
            </div>
          </div>
        )}
      </div>

      {/* 右侧证据面板 - 复用 SourcePanel 样式结构 */}
      <div className={`source-panel-container ${evidencePanelOpen ? '' : 'collapsed'}`}>
        {!evidencePanelOpen ? (
          <div className="source-panel-collapsed">
            <button
              className="source-toggle collapsed"
              onClick={() => setEvidencePanelOpen(true)}
              title="展开证据面板"
            >
              ◀
            </button>
            <span className="source-collapsed-label">证据面板</span>
          </div>
        ) : (
          <div className="source-panel-body">
            <div className="source-title-row">
              <div className="source-title">证据面板</div>
              <button className="source-toggle" onClick={() => setEvidencePanelOpen(false)}>
                收起
              </button>
            </div>
            
            {evidenceChunks.length === 0 && (
              <div className="source-empty">
                点击"查看证据"按钮加载证据
              </div>
            )}
            
            {evidenceChunks.map(chunk => {
              // 高亮函数：将匹配的文本用红色标记
              const highlightContent = (content: string, highlight: string) => {
                if (!highlight || !highlight.trim()) {
                  return content;
                }
                
                // 转义特殊字符并创建正则表达式（不区分大小写）
                const escapedHighlight = highlight.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                const regex = new RegExp(`(${escapedHighlight})`, 'gi');
                
                // 分割内容并用 mark 标签包裹匹配部分
                const parts = content.split(regex);
                return (
                  <>
                    {parts.map((part, index) => 
                      regex.test(part) ? (
                        <mark 
                          key={index} 
                          style={{ 
                            backgroundColor: '#ff4444', 
                            color: 'white', 
                            padding: '2px 4px',
                            borderRadius: '2px',
                            fontWeight: 'bold'
                          }}
                        >
                          {part}
                        </mark>
                      ) : (
                        <span key={index}>{part}</span>
                      )
                    )}
                  </>
                );
              };

              return (
                <div key={chunk.chunk_id} className="source-card">
                  <div className="source-card-title">
                    {chunk.title} #{chunk.position}
                  </div>
                  <div className="source-card-snippet" style={{ whiteSpace: 'pre-wrap' }}>
                    {chunk.highlightText ? highlightContent(chunk.content, chunk.highlightText) : chunk.content}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
      
      {/* 编辑项目模态框 */}
      {editingProject && (
        <div className="modal-overlay" onClick={() => setEditingProject(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginBottom: '16px' }}>编辑项目</h3>
            <div style={{ marginBottom: '12px' }}>
              <label className="label-text">项目名称 *</label>
              <input
                type="text"
                value={editProjectName}
                onChange={(e) => setEditProjectName(e.target.value)}
                placeholder="请输入项目名称"
                className="sidebar-input"
                style={{ marginBottom: 0 }}
              />
            </div>
            <div style={{ marginBottom: '16px' }}>
              <label className="label-text">项目描述</label>
              <textarea
                value={editProjectDesc}
                onChange={(e) => setEditProjectDesc(e.target.value)}
                placeholder="可选"
                className="sidebar-input"
                style={{ minHeight: '60px', marginBottom: 0 }}
              />
            </div>
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button className="sidebar-btn" onClick={() => setEditingProject(null)}>
                取消
              </button>
              <button className="sidebar-btn primary" onClick={saveEditProject}>
                保存
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* 删除项目模态框 */}
      {deletingProject && deletePlan && (
        <div className="modal-overlay" onClick={() => !isDeleting && setDeletingProject(null)}>
          <div className="modal-content" style={{ maxWidth: '600px' }} onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginBottom: '16px', color: '#dc3545' }}>⚠️ 删除项目</h3>
            <div style={{ marginBottom: '16px', padding: '12px', background: '#fff3cd', borderRadius: '4px', color: '#856404' }}>
              <strong>{deletePlan.warning}</strong>
            </div>
            
            <div style={{ marginBottom: '16px' }}>
              <h4 style={{ marginBottom: '8px' }}>将删除以下资源：</h4>
              {deletePlan.items.map((item: any, idx: number) => (
                <div key={idx} style={{ padding: '8px', background: '#f8f9fa', marginBottom: '8px', borderRadius: '4px' }}>
                  <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>
                    {item.type}: {item.count} 个
                  </div>
                  {item.samples.length > 0 && (
                    <div style={{ fontSize: '12px', color: '#666' }}>
                      示例: {item.samples.slice(0, 3).join(', ')}
                    </div>
                  )}
                  {item.physical_targets.length > 0 && (
                    <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
                      物理资源: {item.physical_targets.slice(0, 2).join(', ')}
                    </div>
                  )}
                </div>
              ))}
            </div>
            
            <div style={{ marginBottom: '16px', padding: '12px', background: '#f8d7da', borderRadius: '4px', color: '#721c24' }}>
              确定要删除项目 "<strong>{deletingProject.name}</strong>" 吗？此操作无法撤销！
            </div>
            
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button 
                className="sidebar-btn" 
                onClick={() => setDeletingProject(null)}
                disabled={isDeleting}
              >
                取消
              </button>
              <button 
                className="sidebar-btn" 
                style={{ background: '#dc3545' }}
                onClick={confirmDeleteProject}
                disabled={isDeleting}
              >
                {isDeleting ? '删除中...' : '确认删除'}
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* 模板详情弹窗 */}
      {showTemplateDetail && (
        <div className="modal-overlay" onClick={() => setShowTemplateDetail(false)}>
          <div className="modal-content" style={{ maxWidth: '900px', maxHeight: '80vh', overflowY: 'auto' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ margin: 0, color: '#e2e8f0' }}>格式模板详情</h3>
              <button className="sidebar-btn" onClick={() => setShowTemplateDetail(false)}>
                ✕ 关闭
              </button>
            </div>

            {/* Tab 切换 */}
            <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', borderBottom: '1px solid #4a5568' }}>
              <button
                className={`sidebar-btn ${templateDetailTab === 'preview' ? 'primary' : ''}`}
                style={{ borderRadius: '4px 4px 0 0', marginBottom: 0 }}
                onClick={() => setTemplateDetailTab('preview')}
              >
                解析预览
              </button>
              <button
                className={`sidebar-btn ${templateDetailTab === 'spec' ? 'primary' : ''}`}
                style={{ borderRadius: '4px 4px 0 0', marginBottom: 0 }}
                onClick={() => setTemplateDetailTab('spec')}
              >
                解析结构
              </button>
              <button
                className={`sidebar-btn ${templateDetailTab === 'diagnostics' ? 'primary' : ''}`}
                style={{ borderRadius: '4px 4px 0 0', marginBottom: 0 }}
                onClick={() => setTemplateDetailTab('diagnostics')}
              >
                AI 诊断
              </button>
            </div>

            {/* Tab 内容 */}
            <div style={{ padding: '16px', background: '#1a202c', borderRadius: '8px', minHeight: '400px' }}>
              {templateDetailTab === 'preview' && (
                <div>
                  <h4 style={{ marginTop: 0, color: '#e2e8f0', marginBottom: '16px' }}>解析预览</h4>
                  <div className="kb-doc-meta" style={{ marginBottom: '12px' }}>
                    💡 用模板的样式提示（字体/字号/缩进/标题层级等）渲染一个"目录/标题示例"，让你直观看到"套用后大概长什么样"
                  </div>
                  {templateDetailSpec ? (
                    <div style={{ width: '100%', minHeight: 520 }}>
                      <RichTocPreview
                        items={templateSpecToTocItems(templateDetailSpec)}
                        templateStyle={templateSpecToTemplateStyle(templateDetailSpec)}
                        style={{ minHeight: '500px' }}
                      />
                    </div>
                  ) : (
                    <div className="kb-empty">模板尚未解析，请先上传文件并分析</div>
                  )}
                </div>
              )}

              {templateDetailTab === 'spec' && (
                <div>
                  <h4 style={{ marginTop: 0, color: '#e2e8f0', marginBottom: '16px' }}>解析结构</h4>
                  <div className="kb-doc-meta" style={{ marginBottom: '12px' }}>
                    💡 直接展示解析出来的结构化结果（TemplateSpec 的关键字段）
                  </div>
                  {templateDetailSpec ? (
                    <div style={{ fontSize: '14px', color: '#e2e8f0' }}>
                      <div style={{ marginBottom: '16px', padding: '12px', background: '#2d3748', borderRadius: '4px' }}>
                        <strong>底板保留策略（Base Policy）:</strong> {templateDetailSpec.base_policy?.policy || 'N/A'}
                        {templateDetailSpec.base_policy?.excluded_block_ids?.length > 0 && (
                          <div style={{ marginTop: '8px', fontSize: '12px', color: '#a0aec0' }}>
                            排除块数量（格式说明/操作指引）: {templateDetailSpec.base_policy.excluded_block_ids.length}
                          </div>
                        )}
                      </div>

                      {templateDetailSummary && (
                        <div style={{ marginBottom: '16px', padding: '12px', background: '#2d3748', borderRadius: '4px' }}>
                          <strong>目录骨架数量（Outline Nodes Count）:</strong> {templateDetailSummary.outline_node_count || 0}
                        </div>
                      )}

                      <div>
                        <strong>样式映射（Style Hints）:</strong>
                        <div style={{ marginTop: '8px', fontSize: '12px' }}>
                          <div className="kb-doc-meta">标题/正文/编号/缩进等样式映射</div>
                        </div>
                        <pre style={{ background: '#2d3748', padding: '12px', borderRadius: '4px', overflow: 'auto', marginTop: '8px', fontSize: '12px' }}>
                          {JSON.stringify(templateDetailSpec.style_hints, null, 2)}
                        </pre>
                      </div>
                    </div>
                  ) : (
                    <div className="kb-empty">模板尚未解析</div>
                  )}
                </div>
              )}

              {templateDetailTab === 'diagnostics' && (
                <div>
                  <h4 style={{ marginTop: 0, color: '#e2e8f0', marginBottom: '16px' }}>AI 解析诊断</h4>
                  <div className="kb-doc-meta" style={{ marginBottom: '12px' }}>
                    💡 展示"解析质量"指标：置信度、警告、模型、耗时等元信息（便于回溯）
                  </div>
                  {templateDetailSummary && templateDetailSummary.analyzed ? (
                    <div style={{ fontSize: '14px', color: '#e2e8f0' }}>
                      <div style={{ marginBottom: '16px', padding: '12px', background: '#2d3748', borderRadius: '4px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <strong>置信度（Confidence）:</strong>
                          <span style={{ 
                            fontSize: '18px',
                            fontWeight: 'bold',
                            color: templateDetailSummary.confidence >= 0.7 ? '#28a745' : templateDetailSummary.confidence >= 0.5 ? '#ffc107' : '#dc3545'
                          }}>
                            {(templateDetailSummary.confidence * 100).toFixed(1)}%
                          </span>
                        </div>
                      </div>

                      {templateDetailSummary.warnings && templateDetailSummary.warnings.length > 0 && (
                        <div style={{ marginBottom: '16px' }}>
                          <strong>警告（Warnings）:</strong>
                          <div className="kb-doc-meta" style={{ marginTop: '4px', marginBottom: '8px' }}>
                            例如：疑似说明文字占比高但没排除、底板范围疑似错误等
                          </div>
                          <div style={{ marginTop: '8px' }}>
                            {templateDetailSummary.warnings.map((warning: string, idx: number) => (
                              <div key={idx} style={{ padding: '8px 12px', background: '#fff3cd', color: '#856404', borderRadius: '4px', marginBottom: '4px' }}>
                                ⚠️ {warning}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      <div style={{ marginBottom: '16px', padding: '12px', background: '#2d3748', borderRadius: '4px' }}>
                        <strong>分析元信息:</strong>
                        <div style={{ marginTop: '8px', fontSize: '12px', color: '#a0aec0' }}>
                          <div>模型: {templateDetailSummary.llm_model || 'N/A'}</div>
                          <div>耗时: {templateDetailSummary.analysis_duration_ms ? `${templateDetailSummary.analysis_duration_ms}ms` : 'N/A'}</div>
                          {templateDetailSummary.analyzed_at && (
                            <div>分析时间: {new Date(templateDetailSummary.analyzed_at).toLocaleString()}</div>
                          )}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="kb-empty">
                      {templateDetailSummary?.analyzed === false ? templateDetailSummary.message || '模板尚未解析' : '加载诊断信息失败'}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
