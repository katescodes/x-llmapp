/**
 * 招投标工作台 V2 - 全新4步流程
 * 1️⃣ 上传文档
 * 2️⃣ 提取信息（项目信息/招标要求/目录三个子标签）
 * 3️⃣ AI生成标书
 * 4️⃣ 审核
 */
import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { api } from '../config/api';
import ProjectInfoV3View from './tender/ProjectInfoV3View';
import RiskAnalysisTables from './tender/RiskAnalysisTables';
import DocumentComponentManagement from './DocumentComponentManagement';
import ReviewTable from './tender/ReviewTable';
import FormatTemplatesPage from './FormatTemplatesPage';
import CustomRulesPage from './CustomRulesPage';
import UserDocumentsPage from './UserDocumentsPage';
import type { TenderReviewItem } from '../types/tender';
import { countByStatus } from '../types/reviewUtils';

// ==================== 类型定义 ====================

type TenderAssetKind = 'tender' | 'bid' | 'template' | 'custom_rule' | 'company_profile' | 'tech_doc' | 'case_study' | 'finance_doc' | 'cert_doc';

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
  size_bytes?: number;
  bidder_name?: string;
  created_at?: string;
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
}

interface Requirement {
  id: string;
  dimension: string;
  req_type: string;
  requirement_text: string;
  priority: string;
}

interface ProjectState {
  runs: {
    info: TenderRun | null;
    risk: TenderRun | null;
    directory: TenderRun | null;
    review: TenderRun | null;
  };
}

// ==================== 范文匹配确认面板 ====================

const SnippetMatchPanel: React.FC<{
  matches: any[];
  onConfirm: () => void;
  onCancel: () => void;
}> = ({ matches, onConfirm, onCancel }) => {
  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0,0,0,0.7)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999
    }}>
      <div style={{
        backgroundColor: '#1e293b',
        padding: '24px',
        borderRadius: '12px',
        maxWidth: '600px',
        maxHeight: '80vh',
        overflow: 'auto',
        border: '1px solid rgba(139, 92, 246, 0.3)',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.3)'
      }}>
        <h3 style={{ color: '#e2e8f0', marginBottom: '16px' }}>
          📋 检测到 {matches.length} 个章节可使用范文
        </h3>
        
        <div style={{ marginTop: '16px' }}>
          {matches.map((match, i) => (
            <div key={i} style={{
              padding: '12px',
              marginBottom: '8px',
              backgroundColor: 'rgba(16, 185, 129, 0.1)',
              borderRadius: '6px',
              borderLeft: '4px solid #10b981'
            }}>
              <div style={{ fontWeight: 'bold', marginBottom: '4px', color: '#10b981' }}>
                ✅ {match.node_title}
              </div>
              <div style={{ fontSize: '14px', color: '#94a3b8' }}>
                来源: {match.snippet_title} (置信度: {(match.confidence * 100).toFixed(0)}%)
              </div>
              <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>
                匹配类型: {match.match_type === 'exact' ? '精确匹配' : 
                          match.match_type === 'synonym' ? '同义词匹配' : 
                          match.match_type === 'keyword' ? '关键词匹配' : '包含匹配'}
              </div>
            </div>
          ))}
        </div>
        
        <div style={{ marginTop: '24px', display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
          <button
            onClick={onCancel}
            style={{
              padding: '10px 20px',
              backgroundColor: '#475569',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '14px'
            }}
          >
            取消
          </button>
          <button
            onClick={onConfirm}
            style={{
              padding: '10px 20px',
              backgroundColor: '#10b981',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: '500'
            }}
          >
            确认插入
          </button>
        </div>
      </div>
    </div>
  );
};

// ==================== 主组件 ====================

export default function TenderWorkspaceV2() {
  // ========== 状态管理 ==========
  
  // 视图状态
  const [viewMode, setViewMode] = useState<'projectList' | 'projectDetail' | 'formatTemplates' | 'customRules' | 'userDocuments'>('projectList');
  const [activeTab, setActiveTab] = useState(1); // 1-4对应4个步骤
  const [step2SubTab, setStep2SubTab] = useState<'info' | 'requirements' | 'directory' | 'snippets'>('info');
  
  // 项目状态（为每个项目保存独立状态）
  const projectStatesRef = useRef<Map<string, ProjectState>>(new Map());
  
  // 轮询定时器管理（projectId -> taskType -> timer）
  const pollTimersRef = useRef<Map<string, Map<string, NodeJS.Timeout>>>(new Map());
  
  // 项目相关
  const [projects, setProjects] = useState<TenderProject[]>([]);
  const [currentProject, setCurrentProject] = useState<TenderProject | null>(null);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectDesc, setNewProjectDesc] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);

  // 搜索和批量操作
  const [searchKeyword, setSearchKeyword] = useState('');
  const [selectedProjectIds, setSelectedProjectIds] = useState<Set<string>>(new Set());
  
  // 编辑项目
  const [editingProject, setEditingProject] = useState<TenderProject | null>(null);
  const [editProjectName, setEditProjectName] = useState('');
  const [editProjectDesc, setEditProjectDesc] = useState('');
  
  // 删除项目
  const [deletingProject, setDeletingProject] = useState<TenderProject | null>(null);
  const [deletePlan, setDeletePlan] = useState<any>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isBatchDeleting, setIsBatchDeleting] = useState(false);
  
  // 文件上传
  const [assets, setAssets] = useState<TenderAsset[]>([]);
  const [uploadKind, setUploadKind] = useState<TenderAssetKind>('tender');
  const [bidderName, setBidderName] = useState('');
  const [uploadingMap, setUploadingMap] = useState<Map<string, string>>(new Map());
  
  // 提取信息
  const [projectInfo, setProjectInfo] = useState<ProjectInfo | null>(null);
  const [requirements, setRequirements] = useState<any>(null); // RiskAnalysisData类型
  const [directory, setDirectory] = useState<DirectoryNode[]>([]);
  const [infoRun, setInfoRun] = useState<TenderRun | null>(null);
  const [reqRun, setReqRun] = useState<TenderRun | null>(null);
  const [dirRun, setDirRun] = useState<TenderRun | null>(null);
  
  // 审核
  const [reviewItems, setReviewItems] = useState<TenderReviewItem[]>([]);
  const [reviewRun, setReviewRun] = useState<TenderRun | null>(null);
  const [rulePacks, setRulePacks] = useState<any[]>([]);
  const [selectedRulePackId, setSelectedRulePackId] = useState<string>('');
  const [selectedRulePackIds, setSelectedRulePackIds] = useState<string[]>([]);
  const [selectedRuleAssetIds, setSelectedRuleAssetIds] = useState<string[]>([]);
  const [selectedBidder, setSelectedBidder] = useState<string>('');
  
  // 格式模板相关
  const [formatTemplates, setFormatTemplates] = useState<any[]>([]);
  const [selectedFormatTemplateId, setSelectedFormatTemplateId] = useState('');
  const [applyingFormat, setApplyingFormat] = useState(false);
  const [formatPreviewUrl, setFormatPreviewUrl] = useState('');
  const [formatDownloadUrl, setFormatDownloadUrl] = useState('');
  const [formatPreviewBlobUrl, setFormatPreviewBlobUrl] = useState('');
  const [formatPreviewLoading, setFormatPreviewLoading] = useState(false);
  const [previewMode, setPreviewMode] = useState<'content' | 'format'>('content');
  
  // 证据面板
  const [evidencePanelOpen, setEvidencePanelOpen] = useState(false);
  const [evidenceChunks, setEvidenceChunks] = useState<any[]>([]);
  
  // 范文相关
  const [snippets, setSnippets] = useState<any[]>([]);
  const [snippetMatches, setSnippetMatches] = useState<any[]>([]);
  const [showSnippetMatchPanel, setShowSnippetMatchPanel] = useState(false);
  const [extractingSnippets, setExtractingSnippets] = useState(false);  // 范文提取状态
  
  // 获取/更新项目状态的辅助函数
  const getProjectState = useCallback((projectId: string): ProjectState => {
    let state = projectStatesRef.current.get(projectId);
    if (!state) {
      state = {
        runs: {
          info: null,
          risk: null,
          directory: null,
          review: null,
        },
      };
      projectStatesRef.current.set(projectId, state);
    }
    return state;
  }, []);
  
  const updateProjectState = useCallback((projectId: string, updates: Partial<ProjectState>) => {
    const state = getProjectState(projectId);
    projectStatesRef.current.set(projectId, { ...state, ...updates });
  }, [getProjectState]);
  
  // 停止轮询
  const stopPolling = useCallback((projectId: string, taskType?: 'info' | 'risk' | 'directory' | 'review') => {
    const timers = pollTimersRef.current.get(projectId);
    if (!timers) return;
    
    if (taskType) {
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
  
  // 启动轮询
  const startPolling = useCallback((
    projectId: string,
    taskType: 'info' | 'risk' | 'directory' | 'review',
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
            alert(`任务失败: ${run.message || 'unknown error'}`);
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
          const updatedRuns = { ...state.runs, [taskType]: run };
          updateProjectState(projectId, { runs: updatedRuns });
          
          // 同时更新组件状态
          if (taskType === 'info') setInfoRun(run);
          else if (taskType === 'risk') setReqRun(run);
          else if (taskType === 'directory') setDirRun(run);
          else if (taskType === 'review') setReviewRun(run);
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

  // ========== 生命周期 ==========
  
  useEffect(() => {
    loadProjects();
  }, []);
  
  useEffect(() => {
    if (currentProject) {
      loadAssets();
    }
  }, [currentProject]);

  // ========== API 调用 ==========
  
  const loadProjects = async () => {
    try {
      const data = await api.get('/api/apps/tender/projects');
      setProjects(data);
    } catch (err) {
      console.error('加载项目失败:', err);
    }
  };
  
  const createProject = async () => {
    if (!newProjectName.trim()) return;
    try {
      const data = await api.post('/api/apps/tender/projects', {
        name: newProjectName,
        description: newProjectDesc || undefined,
      });
      setProjects([data, ...projects]);
      setNewProjectName('');
      setNewProjectDesc('');
      setShowCreateForm(false);
      setCurrentProject(data);
      setViewMode('projectDetail');
    } catch (err) {
      alert(`创建失败: ${err}`);
    }
  };

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
      const updated = await api.request(`/api/apps/tender/projects/${editingProject.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          name: editProjectName,
          description: editProjectDesc,
        }),
        headers: { 'Content-Type': 'application/json' },
      });
      
      setProjects(projects.map(p => p.id === updated.id ? updated : p));
      if (currentProject?.id === updated.id) {
        setCurrentProject(updated);
      }
      setEditingProject(null);
      alert('项目更新成功');
    } catch (err: any) {
      alert(`更新失败: ${err.message || err}`);
    }
  };

  // 删除项目
  const openDeleteProject = async (proj: TenderProject) => {
    setDeletingProject(proj);
    try {
      const plan = await api.request(`/api/apps/tender/projects/${proj.id}/delete-plan`);
      setDeletePlan(plan);
    } catch (err: any) {
      alert(`获取删除计划失败: ${err.message || err}`);
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
      
      setProjects(projects.filter(p => p.id !== deletingProject.id));
      if (currentProject?.id === deletingProject.id) {
        setCurrentProject(null);
        setViewMode('projectList');
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
        const plan = await api.request(`/api/apps/tender/projects/${projectId}/delete-plan`);
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
  
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0 || !currentProject) return;

    const fileArray = Array.from(files);
    const formData = new FormData();
    formData.append('kind', uploadKind);
    if (uploadKind === 'bid' && bidderName) {
      formData.append('bidder_name', bidderName);
    }
    fileArray.forEach(f => formData.append('files', f)); // 注意：使用 'files' 而不是 'file'

    // 显示上传进度
    fileArray.forEach(file => {
      setUploadingMap(prev => new Map(prev).set(file.name, '上传中...'));
    });

    try {
      // 使用正确的批量导入API端点
      const newAssets = await api.post(
        `/api/apps/tender/projects/${currentProject.id}/assets/import`,
        formData
      );
      
      // 更新状态
      fileArray.forEach(file => {
        setUploadingMap(prev => {
          const newMap = new Map(prev);
          newMap.set(file.name, '✓ 完成');
          return newMap;
        });
      });
      
      // 更新资产列表
      setAssets([...assets, ...newAssets]);
      
      // 清空输入
      setBidderName('');
      
      // 2秒后清除上传状态
      setTimeout(() => {
        setUploadingMap(new Map());
      }, 2000);
      
    } catch (err) {
      fileArray.forEach(file => {
        setUploadingMap(prev => {
          const newMap = new Map(prev);
          newMap.set(file.name, '✗ 失败');
          return newMap;
        });
      });
      alert(`上传失败: ${err}`);
      
      setTimeout(() => {
        setUploadingMap(new Map());
      }, 2000);
    }
    
    e.target.value = '';
  };
  
  const handleDeleteAsset = async (assetId: string) => {
    if (!currentProject) return;
    
    const asset = assets.find(a => a.id === assetId);
    const filename = asset?.filename || '此文件';
    
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

  const handleOpenTenderFile = async (asset: TenderAsset) => {
    if (!currentProject) return;
    
    try {
      // 通过 API 获取文件内容（会自动带上 Authorization header）
      const response = await fetch(`${api.baseURL}/api/apps/tender/projects/${currentProject.id}/assets/${asset.id}/view`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
        },
      });
      
      if (!response.ok) {
        throw new Error('文件加载失败');
      }
      
      // 获取文件内容和类型
      const blob = await response.blob();
      const contentType = response.headers.get('Content-Type') || 'application/octet-stream';
      
      // 创建带类型的 Blob
      const typedBlob = new Blob([blob], { type: contentType });
      const blobUrl = URL.createObjectURL(typedBlob);
      
      // 创建一个隐藏的 a 标签来触发打开
      const link = document.createElement('a');
      link.href = blobUrl;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      
      // 对于 PDF 和图片，使用 window.open；其他文件下载
      if (contentType.includes('pdf') || contentType.includes('image')) {
        // 使用 window.open 并确保不被路由拦截
        const newWindow = window.open('', '_blank');
        if (newWindow) {
          newWindow.location.href = blobUrl;
        }
      } else {
        // 其他文件类型：触发下载
        link.download = asset.filename || 'download';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      }
      
      // 延迟释放 URL
      setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
    } catch (err) {
      alert(`打开文件失败: ${err}`);
    }
  };
  
  // 计算投标人列表（从已上传的投标文件中提取）
  const bidderOptions = useMemo(() => {
    const names = assets
      .filter(a => a.kind === 'bid' && a.bidder_name)
      .map(a => a.bidder_name)
      .filter((name): name is string => !!name);
    return Array.from(new Set(names)); // 去重
  }, [assets]);
  
  // 按kind分组的assets
  const assetsByKind = useMemo(() => {
    const grouped: Record<TenderAssetKind, TenderAsset[]> = {
      tender: [],
      bid: [],
      template: [],
      custom_rule: [],
      company_profile: [],
      tech_doc: [],
      case_study: [],
      finance_doc: [],
      cert_doc: [],
    };
    assets.forEach(asset => {
      if (grouped[asset.kind]) {
      grouped[asset.kind].push(asset);
      }
    });
    return grouped;
  }, [assets]);
  
  // 提取项目信息
  const extractProjectInfo = async () => {
    if (!currentProject) return;
    const projectId = currentProject.id;
    
    // 清空旧数据
    setProjectInfo(null);
    
    try {
      const res = await api.post(`/api/apps/tender/projects/${projectId}/extract/project-info`, {
        model_id: null,
      });
      
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
      alert(`提取失败: ${err}`);
      setInfoRun(null);
    }
  };
  
  const loadProjectInfo = async (forceProjectId?: string) => {
    const projectId = forceProjectId || currentProject?.id;
    if (!projectId) return;
    
    // 加载前验证项目ID
    if (!forceProjectId && currentProject && currentProject.id !== projectId) {
      console.log('[loadProjectInfo] 项目已切换，跳过加载');
      return;
    }
    
    try {
      const data = await api.get(`/api/apps/tender/projects/${projectId}/project-info`);
      
      // 加载后验证项目ID
      if (currentProject && currentProject.id !== projectId) {
        console.log('[loadProjectInfo] 加载完成时项目已切换，丢弃数据');
        return;
      }
      
      setProjectInfo(data);
    } catch (err) {
      console.error('加载项目信息失败:', err);
    }
  };
  
  // 提取招标要求
  const extractRequirements = async () => {
    if (!currentProject) return;
    const projectId = currentProject.id;
    
    // 清空旧数据
    setRequirements(null);
    
    try {
      const res = await api.post(`/api/apps/tender/projects/${projectId}/extract/risks?use_checklist=1`, {
        model_id: null,
      });
      
      const newRun: TenderRun = {
        id: res.run_id,
        status: 'running',
        progress: 0,
        message: '开始提取招标要求...',
        kind: 'extract_risks'
      } as TenderRun;
      setReqRun(newRun);
      
      // 启动轮询
      startPolling(projectId, 'risk', res.run_id, () => loadRequirements(projectId));
    } catch (err) {
      alert(`提取失败: ${err}`);
      setReqRun(null);
    }
  };
  
  const loadRequirements = async (forceProjectId?: string) => {
    const projectId = forceProjectId || currentProject?.id;
    if (!projectId) return;
    
    if (!forceProjectId && currentProject && currentProject.id !== projectId) {
      console.log('[loadRequirements] 项目已切换，跳过加载');
      return;
    }
    
    try {
      const data = await api.get(`/api/apps/tender/projects/${projectId}/risk-analysis`);
      
      if (currentProject && currentProject.id !== projectId) {
        console.log('[loadRequirements] 加载完成时项目已切换，丢弃数据');
        return;
      }
      
      setRequirements(data);
    } catch (err) {
      console.error('加载要求失败:', err);
    }
  };
  
  // 生成目录
  const generateDirectory = async () => {
    if (!currentProject) return;
    const projectId = currentProject.id;
    
    setDirectory([]);
    
    try {
      const res = await api.post(`/api/apps/tender/projects/${projectId}/directory/generate`, {
        mode: 'requirements_v2',
      });
      
      const newRun: TenderRun = {
        id: res.run_id,
        status: 'running',
        progress: 0,
        message: '开始生成目录...',
        kind: 'generate_directory'
      } as TenderRun;
      setDirRun(newRun);
      
      // 启动轮询
      startPolling(projectId, 'directory', res.run_id, () => loadDirectory(projectId));
    } catch (err) {
      alert(`生成失败: ${err}`);
      setDirRun(null);
    }
  };
  
  const loadDirectory = async (forceProjectId?: string) => {
    const projectId = forceProjectId || currentProject?.id;
    if (!projectId) return [];
    
    if (!forceProjectId && currentProject && currentProject.id !== projectId) {
      console.log('[loadDirectory] 项目已切换，跳过加载');
      return [];
    }
    
    try {
      const data = await api.get(`/api/apps/tender/projects/${projectId}/directory`);
      
      if (currentProject && currentProject.id !== projectId) {
        console.log('[loadDirectory] 加载完成时项目已切换，丢弃数据');
        return [];
      }
      
      setDirectory(data);
      return data;
    } catch (err) {
      console.error('加载目录失败:', err);
      return [];
    }
  };
  
  // 审核
  const loadRulePacks = async () => {
    try {
      // 加载所有共享规则包（不传project_id参数，获取project_id为NULL的共享规则包）
      const data = await api.get(`/api/custom-rules/rule-packs`);
      setRulePacks(data);
    } catch (err) {
      console.error('加载规则包失败:', err);
    }
  };
  
  const startReview = async () => {
    if (!currentProject) return;
    
    // 必须选择投标人
    if (!selectedBidder && assetsByKind.bid.length > 0) {
      alert('请先选择投标人');
      return;
    }
    
    const projectId = currentProject.id;
    
    setReviewItems([]);
    
    try {
      // ✅ 方案A：使用一体化审核API（自动提取投标响应 + 审核一次完成）
      // 构建API参数（包含自定义规则包）
      let apiUrl = `/api/apps/tender/projects/${projectId}/audit/unified?sync=0&bidder_name=${encodeURIComponent(selectedBidder)}`;
      
      // 如果选中了自定义规则包，添加到URL参数
      if (selectedRulePackIds.length > 0) {
        const packIdsParam = selectedRulePackIds.join(',');
        apiUrl += `&custom_rule_pack_ids=${encodeURIComponent(packIdsParam)}`;
      }
      
      // 注意：一体化审核API不支持custom_rule_asset_ids（自定义规则文件）
      // 如果用户同时选择了规则文件，给出提示
      if (selectedRuleAssetIds.length > 0) {
        console.warn('一体化审核暂不支持自定义规则文件，已忽略');
      }
      
      // 调用一体化审核接口
      const res = await api.post(apiUrl);
      
      const modeMsg = selectedRulePackIds.length > 0 
        ? `（启用${selectedRulePackIds.length}个自定义规则包）` 
        : '（基础评估模式）';
      
      const newRun: TenderRun = {
        id: res.run_id,
        status: 'running',
        progress: 0,
        message: `一体化审核中${modeMsg}...`,
        kind: 'review'
      } as TenderRun;
      setReviewRun(newRun);
      
      // 启动轮询
      startPolling(projectId, 'review', res.run_id, () => loadReviewItems(projectId));
    } catch (err: any) {
      // 检查是否是"未提取招标要求"错误
      const errorMsg = err?.response?.data?.detail || err?.message || String(err);
      if (errorMsg.includes('招标要求') || errorMsg.includes('② 要求')) {
        alert('⚠️ 请先提取招标要求\n\n请在【提取信息】→【招标要求】标签页点击"开始提取"按钮，\n完成招标要求提取后再进行审核。');
      } else {
        alert(`审核失败: ${errorMsg}`);
      }
      setReviewRun(null);
    }
  };
  
  // ==================== 范文提取和匹配 ====================
  
  const loadSnippets = async (projectId: string) => {
    console.log(`[loadSnippets] 开始加载范文: project=${projectId}`);
    try {
      const result = await api.get(
        `/api/apps/tender/projects/${projectId}/format-snippets`
      );
      
      console.log(`[loadSnippets] API返回数据:`, result);
      console.log(`[loadSnippets] API返回数组长度:`, Array.isArray(result) ? result.length : 'not array');
      
      // 竞态条件保护：加载完成时项目已切换
      if (currentProject?.id !== projectId) {
        console.log(`[loadSnippets] 加载完成时项目已切换，丢弃数据 (当前=${currentProject?.id}, 加载=${projectId})`);
        return;
      }
      
      setSnippets(result || []);
      console.log(`✅ 加载范文成功: project=${projectId}, count=${result?.length || 0}`);
      console.log(`✅ 设置后snippets state长度:`, result?.length);
      if (result && result.length > 0) {
        console.log(`   第1个范文: ${result[0].title} (id=${result[0].id})`);
        console.log(`   最后1个范文: ${result[result.length-1].title} (id=${result[result.length-1].id})`);
      }
    } catch (err: any) {
      console.error('加载范文失败:', err);
      // 不弹出错误提示，静默失败
      if (currentProject?.id === projectId) {
        setSnippets([]);
      }
    }
  };
  
  const extractFormatSnippets = async (projectId: string) => {
    setExtractingSnippets(true);
    
    try {
      // 获取招标文件
      const tenderAssets = assets.filter(a => a.kind === 'tender');
      if (tenderAssets.length === 0) {
        alert('请先上传招标文件');
        return;
      }
      
      const tenderFile = tenderAssets[0];
      
      // 调用提取API
      const result = await api.post(
        `/api/apps/tender/projects/${projectId}/extract-format-snippets`,
        {
          source_file_path: tenderFile.storage_path,
          source_file_id: tenderFile.asset_id,
          model_id: 'gpt-oss-120b'
        }
      );
      
      setSnippets(result.snippets);
      alert(`✅ 提取成功！找到 ${result.total} 个格式范文`);
    } catch (err: any) {
      console.error('提取范文失败:', err);
      alert(`提取失败: ${err.message || err}`);
    } finally {
      setExtractingSnippets(false);
    }
  };
  
  const matchSnippetsToDirectory = async (projectId: string) => {
    if (snippets.length === 0) {
      alert('请先提取格式范文');
      return;
    }
    
    if (directory.length === 0) {
      alert('请先生成投标书目录');
      return;
    }
    
    setMatchingSnippets(true);
    try {
      const result = await api.post(
        `/api/apps/tender/projects/${projectId}/snippets/match`,
        {
          directory_nodes: directory.map(node => ({
            id: node.id,
            title: node.title,
            level: node.level
          })),
          confidence_threshold: 0.7
        }
      );
      
      // result.matches 是匹配成功的
      setSnippetMatches(result.matches || []);
      
      if (result.matches && result.matches.length > 0) {
        setShowSnippetMatchPanel(true);
        alert(`✅ 匹配成功！找到 ${result.matches.length} 个可用范文`);
      } else {
        alert('未找到匹配的范文');
      }
    } catch (err: any) {
      console.error('匹配范文失败:', err);
      alert(`匹配失败: ${err.response?.data?.detail || err.message || err}`);
    } finally {
      setMatchingSnippets(false);
    }
  };
  
  const [matchingSnippets, setMatchingSnippets] = useState(false);
  
  // 查看范文详情
  const viewSnippetContent = async (snippetId: string) => {
    setViewingSnippetId(snippetId);
    setLoadingSnippetContent(true);
    try {
      const result = await api.get(`/api/apps/tender/format-snippets/${snippetId}`);
      setViewingSnippetContent(result);
    } catch (err: any) {
      console.error('加载范文内容失败:', err);
      alert(`加载失败: ${err.message || err}`);
      setViewingSnippetId(null);
    } finally {
      setLoadingSnippetContent(false);
    }
  };
  
  // ==================== 自动加载数据 ====================
  
  // ==================== 审核相关 ====================
  
  const loadReviewItems = async (forceProjectId?: string) => {
    const projectId = forceProjectId || currentProject?.id;
    if (!projectId) return;
    
    if (!forceProjectId && currentProject && currentProject.id !== projectId) {
      console.log('[loadReviewItems] 项目已切换，跳过加载');
      return;
    }
    
    try {
      const data = await api.get(`/api/apps/tender/projects/${projectId}/review`);
      
      if (currentProject && currentProject.id !== projectId) {
        console.log('[loadReviewItems] 加载完成时项目已切换，丢弃数据');
        return;
      }
      
      setReviewItems(data);
    } catch (err) {
      console.error('加载审核结果失败:', err);
    }
  };
  
  // 轮询Run状态（已弃用，使用 startPolling 替代）
  // const pollRun = ...已删除
  
  // 加载资产
  const loadAssets = async (forceProjectId?: string) => {
    const projectId = forceProjectId || currentProject?.id;
    if (!projectId) return;
    
    try {
      const data = await api.get(`/api/apps/tender/projects/${projectId}/assets`);
      if (currentProject && currentProject.id !== projectId) {
        console.log('[loadAssets] 加载完成时项目已切换，丢弃数据');
        return;
      }
      setAssets(data);
    } catch (err) {
      console.error('加载资产失败:', err);
      setAssets([]);
    }
  };
  
  // ✅ 切换到审核tab时自动加载审核记录
  useEffect(() => {
    if (!currentProject || activeTab !== 4) return;
    
    // 每次切换到审核tab时，重新加载审核记录（确保显示最新数据）
    console.log('[useEffect] 切换到审核tab，加载审核记录');
    loadReviewItems(currentProject.id);
  }, [activeTab, currentProject?.id]);
  
  // 项目切换时加载数据并恢复run状态
  useEffect(() => {
    if (!currentProject) return;
    
    const projectId = currentProject.id;
    console.log('[useEffect] 项目切换，加载新项目数据:', projectId);
    
    // 立即清空旧数据，避免显示混乱
    setSnippets([]);
    
    // 加载项目数据
    loadAssets(projectId);
    loadProjectInfo(projectId);
    loadRequirements(projectId);
    loadDirectory(projectId);
    loadReviewItems(projectId);
    loadSnippets(projectId);  // 加载范文
    
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
        const reviewRunData = data.review || null;
        
        // 更新状态到ProjectState
        updateProjectState(projectId, {
          runs: {
            info: infoRunData,
            risk: riskRunData,
            directory: dirRunData,
            review: reviewRunData,
          }
        });
        
        // 同时更新组件状态
        setInfoRun(infoRunData);
        setReqRun(riskRunData);
        setDirRun(dirRunData);
        setReviewRun(reviewRunData);
        
        // 恢复running任务的轮询
        if (infoRunData?.status === 'running') {
          console.log('[loadAndRestoreRuns] 恢复项目信息抽取轮询:', infoRunData.id);
          startPolling(projectId, 'info', infoRunData.id, () => loadProjectInfo(projectId));
        }
        if (riskRunData?.status === 'running') {
          console.log('[loadAndRestoreRuns] 恢复招标要求提取轮询:', riskRunData.id);
          startPolling(projectId, 'risk', riskRunData.id, () => loadRequirements(projectId));
        }
        if (dirRunData?.status === 'running') {
          console.log('[loadAndRestoreRuns] 恢复目录生成轮询:', dirRunData.id);
          startPolling(projectId, 'directory', dirRunData.id, () => loadDirectory(projectId));
        }
        if (reviewRunData?.status === 'running') {
          console.log('[loadAndRestoreRuns] 恢复审核轮询:', reviewRunData.id);
          startPolling(projectId, 'review', reviewRunData.id, () => loadReviewItems(projectId));
        }
      } catch (err) {
        console.error('[loadAndRestoreRuns] 加载项目run状态失败:', err);
      }
    };
    
    loadAndRestoreRuns();
    
    // 清理函数：停止轮询
    return () => {
      console.log('[useEffect cleanup] 停止项目轮询:', projectId);
      stopPolling(projectId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentProject?.id]); // 只监听项目ID变化，其他依赖已经在函数内部正确处理
  
  // 加载格式模板列表
  useEffect(() => {
    const loadFormatTemplates = async () => {
      try {
        const data = await api.get('/api/apps/tender/format-templates');
        setFormatTemplates(data);
      } catch (err) {
        console.error('加载格式模板失败:', err);
      }
    };
    loadFormatTemplates();
  }, []);
  
  // 恢复项目的格式模板选择
  useEffect(() => {
    if (!currentProject) return;
    const key = `tender.formatTemplateId.${currentProject.id}`;
    const saved = localStorage.getItem(key) || '';
    setSelectedFormatTemplateId(saved);
  }, [currentProject]);
  
  // 当切换到步骤3时，自动加载格式范文数据
  useEffect(() => {
    if (activeTab === 3 && currentProject && snippets.length === 0) {
      console.log('[步骤3] 自动加载格式范文数据:', currentProject.id);
      loadSnippets(currentProject.id);
    }
  }, [activeTab, currentProject?.id]);
  
  // 清理旧的Blob URL
  useEffect(() => {
    return () => {
      if (formatPreviewBlobUrl) {
        URL.revokeObjectURL(formatPreviewBlobUrl);
      }
    };
  }, [formatPreviewBlobUrl]);
  
  // 加载格式预览（使用fetch + Blob URL以携带Authorization）
  useEffect(() => {
    if (!formatPreviewUrl) {
      setFormatPreviewBlobUrl('');
      return;
    }

    const loadPreview = async () => {
      setFormatPreviewLoading(true);
      console.log('[格式预览] 开始加载:', formatPreviewUrl);
      
      try {
        const token = localStorage.getItem('auth_token');
        
        // 构建完整URL（如果是相对路径，浏览器会自动补全）
        const fullUrl = formatPreviewUrl.startsWith('http') 
          ? formatPreviewUrl 
          : `${window.location.origin}${formatPreviewUrl}`;
        
        console.log('[格式预览] 请求URL:', fullUrl);
        console.log('[格式预览] Token:', token ? `${token.substring(0, 20)}...` : 'none');
        
        const response = await fetch(fullUrl, {
          method: 'GET',
          headers: {
            'Authorization': token ? `Bearer ${token}` : '',
          },
        });

        console.log('[格式预览] 响应状态:', response.status, response.statusText);

        if (!response.ok) {
          const errorText = await response.text();
          console.error('[格式预览] 错误响应:', errorText);
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const blob = await response.blob();
        console.log('[格式预览] Blob大小:', blob.size, 'bytes');
        
        const blobUrl = URL.createObjectURL(blob);
        setFormatPreviewBlobUrl(blobUrl);
        console.log('[格式预览] 加载成功');
      } catch (err: any) {
        console.error('[格式预览] 加载失败:', err);
        console.error('[格式预览] 错误详情:', {
          name: err.name,
          message: err.message,
          stack: err.stack
        });
        alert(`格式预览加载失败: ${err.message || err}\n\n请检查：\n1. 网络连接是否正常\n2. 是否已成功套用格式模板\n3. 查看浏览器控制台了解详细错误`);
        setFormatPreviewBlobUrl('');
      } finally {
        setFormatPreviewLoading(false);
      }
    };

    loadPreview();
  }, [formatPreviewUrl]);
  
  // 证据面板
  const showEvidence = async (chunkIds: string[]) => {
    if (chunkIds.length === 0) return;
    try {
      const data = await api.post('/api/apps/tender/chunks/lookup', { chunk_ids: chunkIds });
      setEvidenceChunks(data);
      setEvidencePanelOpen(true);
    } catch (err) {
      alert(`加载证据失败: ${err}`);
    }
  };
  
  // 套用格式模板
  const applyFormatTemplate = async () => {
    if (!currentProject) return;
    if (!selectedFormatTemplateId) {
      alert('请先选择格式模板');
      return;
    }

    try {
      setApplyingFormat(true);

      const data: any = await api.post(
        `/api/apps/tender/projects/${currentProject.id}/directory/apply-format-template?return_type=json`,
        { format_template_id: selectedFormatTemplateId }
      );

      if (!data?.ok) {
        throw new Error(data?.detail || "套用格式失败");
      }

      // 刷新目录
      await loadDirectory(currentProject.id);

      // 设置预览URL
      const ts = Date.now();
      const fallbackPreviewUrl = `/api/apps/tender/projects/${currentProject.id}/directory/format-preview?format=pdf&format_template_id=${selectedFormatTemplateId}`;
      const fallbackDownloadUrl = `/api/apps/tender/projects/${currentProject.id}/directory/format-preview?format=docx&format_template_id=${selectedFormatTemplateId}`;
      
      const previewUrl = data.preview_pdf_url || fallbackPreviewUrl;
      const downloadUrl = data.download_docx_url || fallbackDownloadUrl;
      
      setFormatPreviewUrl(previewUrl ? `${previewUrl}${previewUrl.includes("?") ? "&" : "?"}ts=${ts}` : "");
      setFormatDownloadUrl(downloadUrl);
      setPreviewMode("format"); // 切换到格式预览

      // 记录选择
      localStorage.setItem(`tender.formatTemplateId.${currentProject.id}`, selectedFormatTemplateId);
      
      alert('格式模板套用成功！');
    } catch (err: any) {
      console.error("[applyFormatTemplate] 错误详情:", err);
      alert(`套用格式失败: ${err.message || err}`);
    } finally {
      setApplyingFormat(false);
    }
  };
  
  // 下载Word文件
  const downloadWordFile = async () => {
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
      
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = `投标文件_${currentProject?.name || '导出'}_${new Date().toISOString().split('T')[0]}.docx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      setTimeout(() => URL.revokeObjectURL(blobUrl), 100);
    } catch (err) {
      console.error('Failed to download Word file:', err);
      alert(`Word文件下载失败: ${err}`);
    }
  };

  // ========== 渲染 ==========

  // 主视图渲染
  return (
    <div className="workspace-container" style={{ display: 'flex', height: '100vh' }}>
      {/* 左侧工作台 */}
      <div className="sidebar">
        <div className="sidebar-title">招投标工作台</div>
        <div className="sidebar-subtitle">项目管理 + 智能审核 + 文档生成</div>
        
        <div style={{ flex: 1, overflow: 'auto', padding: '16px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <button
              onClick={() => setViewMode("projectList")}
              className="sidebar-btn"
              style={{ 
                width: '100%',
                padding: '12px 16px',
                background: viewMode === "projectList" || viewMode === "projectDetail" ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' : 'rgba(255, 255, 255, 0.05)',
                border: (viewMode === "projectList" || viewMode === "projectDetail") ? 'none' : '1px solid rgba(148, 163, 184, 0.25)',
                borderLeft: (viewMode === "projectList" || viewMode === "projectDetail") ? '4px solid #667eea' : '4px solid transparent',
                borderRadius: '8px',
                color: '#ffffff',
                fontSize: '14px',
                fontWeight: (viewMode === "projectList" || viewMode === "projectDetail") ? '600' : '500',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-start',
                gap: '12px',
                boxShadow: (viewMode === "projectList" || viewMode === "projectDetail") ? '0 2px 8px rgba(102, 126, 234, 0.3)' : 'none',
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

      {/* 右侧主内容区 */}
      <div className="main-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {renderMainContent()}
      </div>
    </div>
  );

  // 渲染主内容区域
  function renderMainContent() {
    // 格式模板页面
    if (viewMode === 'formatTemplates') {
      return <FormatTemplatesPage />;
    }
    
    // 自定义规则页面
    if (viewMode === 'customRules') {
      return <CustomRulesPage />;
    }
    
    // 用户文档页面
    if (viewMode === 'userDocuments') {
      return <UserDocumentsPage />;
    }
    
    // 项目列表视图
    if (viewMode === 'projectList') {
      return renderProjectList();
    }
    
    // 项目详情视图
    if (viewMode === 'projectDetail') {
      return renderProjectDetail();
    }
    
    return null;
  }

  // 渲染项目列表
  function renderProjectList() {
    return (
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
            </div>
          </div>
        )}

        {/* 搜索和批量操作工具栏 */}
        {projects.length > 0 && (
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
        )}

        {/* 项目数量显示 */}
        {projects.length > 0 && (
          <div style={{ marginBottom: '16px', color: '#cbd5e1', fontSize: '14px' }}>
            共 {filteredProjects.length} 个项目{projects.length !== filteredProjects.length ? ` (已筛选 ${projects.length - filteredProjects.length} 个)` : ''}
          </div>
        )}

        {/* 项目列表网格 */}
        {filteredProjects.length > 0 ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '20px' }}>
            {filteredProjects.map(project => {
              const isSelected = selectedProjectIds.has(project.id);
              return (
            <div
              key={project.id}
              style={{
                padding: '24px',
                background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.8) 100%)',
                    border: isSelected ? '2px solid rgba(79, 70, 229, 0.8)' : '1px solid rgba(148, 163, 184, 0.25)',
                borderRadius: '12px',
                transition: 'all 0.3s ease',
                    position: 'relative',
                  }}
                >
                  {/* Checkbox */}
                  <div
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleProjectSelection(project.id);
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

                  <div
                    onClick={() => {
                      setCurrentProject(project);
                      setViewMode('projectDetail');
                      setActiveTab(1);
                    }}
                    style={{ cursor: 'pointer', paddingRight: '32px' }}
            >
              <div style={{ 
                fontSize: '18px', 
                fontWeight: '600', 
                color: '#e2e8f0', 
                marginBottom: '12px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <span style={{ fontSize: '20px' }}>📁</span>
                {project.name}
              </div>
              {project.description && (
                <div style={{ 
                  fontSize: '14px', 
                  color: '#94a3b8', 
                  marginBottom: '16px',
                  lineHeight: '1.5'
                }}>
                  {project.description}
                </div>
              )}
              <div style={{ 
                fontSize: '12px', 
                color: '#64748b',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <span>🕒</span>
                {project.created_at && new Date(project.created_at).toLocaleDateString('zh-CN', {
                  year: 'numeric',
                  month: '2-digit',
                  day: '2-digit'
                })}
              </div>
            </div>

                  {/* 操作按钮 */}
                  <div style={{ 
                    marginTop: '16px', 
                    paddingTop: '16px',
                    borderTop: '1px solid rgba(148, 163, 184, 0.2)',
                    display: 'flex',
                    gap: '8px',
                  }}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        openEditProject(project);
                      }}
                      title="编辑项目"
                      style={{
                        flex: 1,
                        padding: '8px 12px',
                        background: 'rgba(255, 255, 255, 0.05)',
                        border: '1px solid rgba(148, 163, 184, 0.25)',
                        borderRadius: '6px',
                        color: '#cbd5e1',
                        fontSize: '13px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '6px',
                      }}
                    >
                      ✏️ 编辑
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        openDeleteProject(project);
                      }}
                      title="删除项目"
                      style={{
                        flex: 1,
                        padding: '8px 12px',
                        background: 'rgba(239, 68, 68, 0.1)',
                        border: '1px solid rgba(239, 68, 68, 0.3)',
                        borderRadius: '6px',
                        color: '#fca5a5',
                        fontSize: '13px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '6px',
                      }}
                    >
                      🗑️ 删除
                    </button>
        </div>
                </div>
              );
            })}
          </div>
        ) : projects.length > 0 ? (
          <div style={{
            textAlign: 'center',
            padding: '80px 20px',
            color: '#64748b',
            fontSize: '16px'
          }}>
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>🔍</div>
            <div>没有找到匹配的项目</div>
            <div style={{ fontSize: '14px', marginTop: '8px' }}>尝试使用不同的关键词搜索</div>
          </div>
        ) : null}

        {projects.length === 0 && !showCreateForm && (
          <div style={{
            textAlign: 'center',
            padding: '80px 20px',
            color: '#64748b',
            fontSize: '16px'
          }}>
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>📂</div>
            <div>暂无项目，点击"新建项目"开始</div>
          </div>
        )}
      </div>
    );
  }

  // 渲染项目详情视图
  function renderProjectDetail() {
    return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
      {/* 顶部栏 */}
      <div className="workspace-header" style={{ flexShrink: 0 }}>
        <div>
          <button 
            onClick={() => {
              setViewMode('projectList');
              setCurrentProject(null);
            }}
            className="link-button"
            style={{ marginRight: '16px' }}
          >
            ← 返回项目列表
          </button>
          <span style={{ fontSize: '18px', fontWeight: '500' }}>{currentProject?.name}</span>
        </div>
      </div>

      {/* 步骤标签页 */}
      <div style={{ 
        display: 'flex', 
        gap: '8px', 
        padding: '16px 24px', 
        borderBottom: '1px solid rgba(255,255,255,0.1)',
        flexShrink: 0,
      }}>
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
              if (tab.id === 4) loadRulePacks();
            }}
            className={activeTab === tab.id ? 'pill-button' : 'link-button'}
            style={{ 
              padding: activeTab === tab.id ? '10px 20px' : '8px 16px',
              flex: 1,
              maxWidth: '200px',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* 内容区域 */}
      <div style={{ flex: 1, overflow: 'auto', padding: '24px' }}>
        {/* Step 1: 上传文档 */}
        {activeTab === 1 && (
          <div>
            {/* 上传控件 */}
            <div style={{ 
              padding: '24px', 
              background: 'rgba(255,255,255,0.05)', 
              borderRadius: '12px',
              marginBottom: '24px'
            }}>
              <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', flexWrap: 'wrap', alignItems: 'center' }}>
                <select
                  value={uploadKind}
                  onChange={(e) => setUploadKind(e.target.value as TenderAssetKind)}
                  className="kb-select"
                  style={{ width: '200px' }}
                >
                  <option value="tender">招标文件</option>
                  <option value="bid">投标文件</option>
                  <option value="company_profile">企业资料</option>
                  <option value="tech_doc">技术文档</option>
                  <option value="case_study">案例证明</option>
                  <option value="finance_doc">财务文档</option>
                  <option value="cert_doc">证书资质</option>
                  <option value="template">格式模板</option>
                  <option value="custom_rule">自定义规则文件</option>
                </select>
                
                {uploadKind === 'bid' && (
                  <input
                    type="text"
                    placeholder="投标人名称（选填）"
                    value={bidderName}
                    onChange={(e) => setBidderName(e.target.value)}
                    className="kb-input"
                    style={{ width: '200px' }}
                  />
                )}

                <label className="kb-create-form" style={{ width: 'auto', marginBottom: 0, cursor: 'pointer' }}>
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.docx,.doc,.txt"
                    onChange={handleFileUpload}
                    style={{ display: 'none' }}
                  />
                  选择文件上传
                </label>
              </div>

              {/* 上传进度 */}
              {uploadingMap.size > 0 && (
                <div style={{ marginTop: '16px' }}>
                  {Array.from(uploadingMap.entries()).map(([filename, status]) => (
                    <div key={filename} style={{ padding: '8px', color: '#94a3b8', fontSize: '13px' }}>
                      {filename}: {status}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 已上传文件列表 */}
            {assets.length > 0 ? (
              <div>
                <h4 style={{ marginBottom: '16px', color: '#e2e8f0' }}>已上传文件 ({assets.length})</h4>
                <div style={{ display: 'grid', gap: '12px' }}>
                  {assets.map(asset => (
                    <div
                      key={asset.id}
                      style={{
                        padding: '16px',
                        background: 'rgba(255,255,255,0.05)',
                        borderRadius: '8px',
                        border: '1px solid rgba(255,255,255,0.1)',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center'
                      }}
                    >
                      <div style={{ flex: 1 }}>
                        <div style={{ color: '#e2e8f0', marginBottom: '6px', fontWeight: '500' }}>
                          📄 {asset.filename}
                          {asset.bidder_name && (
                            <span style={{ marginLeft: '12px', color: '#94a3b8', fontSize: '13px', fontWeight: 'normal' }}>
                              ({asset.bidder_name})
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                          类型: {
                            asset.kind === 'tender' ? '招标文件' :
                            asset.kind === 'bid' ? '投标文件' :
                            asset.kind === 'company_profile' ? '企业资料' :
                            asset.kind === 'tech_doc' ? '技术文档' :
                            asset.kind === 'case_study' ? '案例证明' :
                            asset.kind === 'finance_doc' ? '财务文档' :
                            asset.kind === 'cert_doc' ? '证书资质' :
                            asset.kind === 'template' ? '格式模板' :
                            '自定义规则'
                          }
                          {asset.size_bytes && ` · ${(asset.size_bytes / 1024).toFixed(1)} KB`}
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <button
                          onClick={() => handleOpenTenderFile(asset)}
                          style={{
                            padding: '6px 12px',
                            background: 'rgba(79, 70, 229, 0.2)',
                            border: '1px solid rgba(79, 70, 229, 0.5)',
                            borderRadius: '6px',
                            color: '#a5b4fc',
                            fontSize: '13px',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            transition: 'all 0.2s',
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = 'rgba(79, 70, 229, 0.3)';
                            e.currentTarget.style.borderColor = 'rgba(79, 70, 229, 0.8)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = 'rgba(79, 70, 229, 0.2)';
                            e.currentTarget.style.borderColor = 'rgba(79, 70, 229, 0.5)';
                          }}
                        >
                          👁️ 打开
                        </button>
                      <button
                        onClick={() => handleDeleteAsset(asset.id)}
                        className="link-button"
                        style={{ color: '#ef4444' }}
                      >
                        删除
                      </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="kb-empty">
                暂无文件，请先上传文档
              </div>
            )}
          </div>
        )}

        {/* Step 2: 提取信息（三个子标签） */}
        {activeTab === 2 && (
          <div>
            {/* 子标签导航 */}
            <div style={{ display: 'flex', gap: '8px', marginBottom: '24px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '12px' }}>
              {[
                { id: 'info' as const, label: '📋 项目信息', count: projectInfo ? 1 : 0 },
                { id: 'requirements' as const, label: '📝 招标要求', count: requirements ? 1 : 0 },
                { id: 'directory' as const, label: '📑 投标目录', count: directory.length },
                { id: 'snippets' as const, label: '📄 格式范文', count: snippets.length },
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setStep2SubTab(tab.id)}
                  style={{
                    padding: '10px 20px',
                    background: step2SubTab === tab.id ? 'rgba(139, 92, 246, 0.2)' : 'transparent',
                    color: step2SubTab === tab.id ? '#a78bfa' : '#94a3b8',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontSize: '14px',
                    fontWeight: step2SubTab === tab.id ? '600' : 'normal',
                    transition: 'all 0.2s',
                  }}
                >
                  {tab.label} {tab.count > 0 && `(${tab.count})`}
                </button>
              ))}
            </div>

            {/* 子标签1: 项目信息 */}
            {step2SubTab === 'info' && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <h4 style={{ color: '#e2e8f0' }}>项目信息抽取</h4>
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
                  <div style={{ 
                    padding: '12px', 
                    background: 'rgba(255,255,255,0.05)', 
                    borderRadius: '8px',
                    marginBottom: '16px'
                  }}>
                    <div style={{ color: '#94a3b8' }}>
                      状态: {infoRun.status}
                      {infoRun.message && ` - ${infoRun.message}`}
                    </div>
                  </div>
                )}
                
                {projectInfo ? (
                  <div>
                    <ProjectInfoV3View info={projectInfo.data_json} onEvidence={showEvidence} />
                  </div>
                ) : (
                  <div className="kb-empty">
                    暂无数据，请点击"开始抽取"
                  </div>
                )}
              </div>
            )}

            {/* 子标签2: 招标要求 */}
            {step2SubTab === 'requirements' && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <h4 style={{ color: '#e2e8f0' }}>招标要求提取</h4>
                  <button 
                    onClick={extractRequirements} 
                    className="kb-create-form" 
                    style={{ width: 'auto', marginBottom: 0 }}
                    disabled={reqRun?.status === 'running'}
                  >
                    {reqRun?.status === 'running' ? '提取中...' : '开始提取'}
                  </button>
                </div>
                
                {reqRun && (
                  <div style={{ 
                    padding: '12px', 
                    background: 'rgba(255,255,255,0.05)', 
                    borderRadius: '8px',
                    marginBottom: '16px'
                  }}>
                    <div style={{ color: '#94a3b8' }}>
                      状态: {reqRun.status}
                      {reqRun.message && ` - ${reqRun.message}`}
                    </div>
                  </div>
                )}
                
                {requirements ? (
                  <RiskAnalysisTables
                    data={requirements}
                    onOpenEvidence={showEvidence}
                  />
                ) : (
                  <div className="kb-empty">
                    暂无数据，请点击"开始提取"
                  </div>
                )}
              </div>
            )}

            {/* 子标签3: 投标目录 */}
            {step2SubTab === 'directory' && (
              <div>
                {/* 工具栏 */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
                  <h4 style={{ color: '#e2e8f0', margin: 0 }}>投标目录生成</h4>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <button 
                      onClick={generateDirectory} 
                      className="kb-create-form" 
                      style={{ width: 'auto', marginBottom: 0 }}
                      disabled={dirRun?.status === 'running'}
                    >
                      {dirRun?.status === 'running' ? '生成中...' : '生成目录'}
                    </button>
                    
                    {/* 格式模板选择 */}
                    {directory.length > 0 && formatTemplates.length > 0 && (
                      <>
                        <select
                          value={selectedFormatTemplateId}
                          onChange={(e) => setSelectedFormatTemplateId(e.target.value)}
                          className="kb-select"
                          style={{ width: '200px', marginBottom: 0 }}
                        >
                          <option value="">选择格式模板</option>
                          {formatTemplates.map((tpl: any) => (
                            <option key={tpl.id} value={tpl.id}>
                              {tpl.name || tpl.id}
                            </option>
                          ))}
                        </select>
                        
                        <button 
                          onClick={applyFormatTemplate} 
                          className="kb-create-form" 
                          style={{ width: 'auto', marginBottom: 0 }}
                          disabled={!selectedFormatTemplateId || applyingFormat}
                          title="套用选中的格式模板"
                        >
                          {applyingFormat ? '⏳ 套用中...' : '📐 自动套用格式'}
                        </button>
                      </>
                    )}
                  </div>
                </div>
                
                {/* Run状态显示 */}
                {dirRun && (
                  <div style={{ 
                    padding: '12px', 
                    background: 'rgba(255,255,255,0.05)', 
                    borderRadius: '8px',
                    marginBottom: '16px'
                  }}>
                    <div style={{ color: '#94a3b8' }}>
                      状态: {dirRun.status}
                      {dirRun.message && ` - ${dirRun.message}`}
                    </div>
                  </div>
                )}
                
                {/* 目录内容或预览切换 */}
                {directory.length > 0 && (
                  <>
                    {/* 切换按钮 */}
                    <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                      <button
                        className="kb-create-form"
                        style={{ 
                          width: 'auto', 
                          marginBottom: 0, 
                          opacity: previewMode === 'content' ? 1 : 0.6,
                          background: previewMode === 'content' ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' : 'rgba(255,255,255,0.1)'
                        }}
                        onClick={() => setPreviewMode('content')}
                      >
                        📋 章节目录
                      </button>

                      <button
                        className="kb-create-form"
                        style={{ 
                          width: 'auto', 
                          marginBottom: 0, 
                          opacity: previewMode === 'format' && formatPreviewUrl ? 1 : 0.6,
                          background: previewMode === 'format' && formatPreviewUrl ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' : 'rgba(255,255,255,0.1)'
                        }}
                        onClick={() => setPreviewMode('format')}
                        disabled={!formatPreviewUrl}
                        title={!formatPreviewUrl ? '请先执行「自动套用格式」生成预览' : '查看套用格式后的整体预览'}
                      >
                        📄 格式预览
                      </button>

                      {previewMode === 'format' && formatDownloadUrl && (
                        <button
                          onClick={downloadWordFile}
                          className="link-button"
                          style={{ marginLeft: '8px', color: '#3b82f6', textDecoration: 'underline', fontSize: '14px' }}
                          title="下载Word文档"
                        >
                          📥 下载Word
                        </button>
                      )}
                    </div>

                    {/* 内容显示 */}
                    {previewMode === 'content' ? (
                      <div style={{ 
                        padding: '20px', 
                        background: 'rgba(255,255,255,0.03)', 
                        borderRadius: '8px',
                        fontFamily: 'monospace'
                      }}>
                        {directory.map((node, idx) => (
                          <div 
                            key={idx} 
                            style={{ 
                              marginLeft: `${(node.level - 1) * 24}px`,
                              padding: '8px',
                              color: '#e2e8f0',
                              borderLeft: `2px solid ${node.level === 1 ? '#667eea' : node.level === 2 ? '#10b981' : '#f59e0b'}`,
                              paddingLeft: '12px',
                              marginBottom: '4px'
                            }}
                          >
                            <span style={{ color: '#94a3b8', marginRight: '8px' }}>{node.numbering}</span>
                            <span>{node.title}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div style={{ 
                        background: 'rgba(255,255,255,0.03)', 
                        borderRadius: '8px',
                        overflow: 'hidden',
                        minHeight: '600px',
                        position: 'relative'
                      }}>
                        {formatPreviewLoading ? (
                          <div style={{ 
                            display: 'flex', 
                            alignItems: 'center', 
                            justifyContent: 'center',
                            minHeight: '600px',
                            color: '#94a3b8'
                          }}>
                            <div style={{ textAlign: 'center' }}>
                              <div style={{ fontSize: '48px', marginBottom: '16px' }}>⏳</div>
                              <div>正在加载预览...</div>
                            </div>
                          </div>
                        ) : formatPreviewBlobUrl ? (
                          <iframe
                            src={formatPreviewBlobUrl}
                            style={{
                              width: '100%',
                              height: '800px',
                              border: 'none',
                              background: '#fff'
                            }}
                            title="格式预览"
                          />
                        ) : formatPreviewUrl ? (
                          <div style={{ 
                            display: 'flex', 
                            alignItems: 'center', 
                            justifyContent: 'center',
                            minHeight: '600px',
                            color: '#94a3b8'
                          }}>
                            <div style={{ textAlign: 'center' }}>
                              <div style={{ fontSize: '48px', marginBottom: '16px' }}>❌</div>
                              <div>预览加载失败</div>
                            </div>
                          </div>
                        ) : (
                          <div style={{ 
                            display: 'flex', 
                            alignItems: 'center', 
                            justifyContent: 'center',
                            minHeight: '600px',
                            color: '#94a3b8'
                          }}>
                            <div style={{ textAlign: 'center' }}>
                              <div style={{ fontSize: '48px', marginBottom: '16px' }}>📄</div>
                              <div>请先选择格式模板并点击"自动套用格式"</div>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </>
                )}
                
                {directory.length === 0 && (
                  <div className="kb-empty">
                    暂无目录，请点击"生成目录"
                  </div>
                )}
              </div>
            )}

            {/* 子标签4: 格式范文 */}
            {step2SubTab === 'snippets' && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <h4 style={{ color: '#e2e8f0', margin: 0 }}>格式范文提取</h4>
                  <button 
                    onClick={() => currentProject && extractFormatSnippets(currentProject.id)} 
                    className="kb-create-form" 
                    style={{ 
                      width: 'auto', 
                      marginBottom: 0,
                      backgroundColor: extractingSnippets ? '#6b7280' : '#10b981'
                    }}
                    disabled={!currentProject || extractingSnippets || assets.filter(a => a.kind === 'tender').length === 0}
                  >
                    {extractingSnippets ? '🔍 提取中...' : '📋 提取格式范文'}
                  </button>
                </div>

                {/* 提取提示 */}
                {assets.filter(a => a.kind === 'tender').length === 0 && (
                  <div style={{
                    padding: '12px',
                    backgroundColor: 'rgba(251, 191, 36, 0.1)',
                    borderRadius: '8px',
                    border: '1px solid rgba(251, 191, 36, 0.3)',
                    marginBottom: '16px'
                  }}>
                    <div style={{ color: '#fbbf24', fontSize: '14px' }}>
                      ⚠️ 请先在Step 1中上传招标文件
                    </div>
                  </div>
                )}

                {/* 范文列表 */}
                {snippets.length > 0 ? (
                  <div>
                    <div style={{
                      marginBottom: '16px',
                      padding: '12px',
                      backgroundColor: 'rgba(16, 185, 129, 0.1)',
                      borderRadius: '8px',
                      border: '1px solid rgba(16, 185, 129, 0.3)'
                    }}>
                      <div style={{ fontWeight: 'bold', marginBottom: '8px', color: '#10b981' }}>
                        ✅ 已保存 {snippets.length} 个格式范文
                      </div>
                      <div style={{ fontSize: '12px', color: '#64748b' }}>
                        💡 提示：这些范文会自动保存，切换Tab后仍可查看
                      </div>
                    </div>

                    {/* 范文卡片列表 */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                      {snippets.map((snippet, index) => (
                        <div
                          key={snippet.id}
                          style={{
                            padding: '20px',
                            backgroundColor: 'rgba(255,255,255,0.05)',
                            borderRadius: '8px',
                            border: '1px solid rgba(255,255,255,0.1)'
                          }}
                        >
                          {/* 标题行 */}
                              <div style={{ 
                                fontSize: '16px', 
                                fontWeight: '600', 
                                color: '#e2e8f0',
                            marginBottom: '12px',
                            paddingBottom: '12px',
                            borderBottom: '1px solid rgba(255,255,255,0.1)'
                              }}>
                            📄 {index + 1}. {snippet.title}
                              </div>
                          
                          {/* 元信息 */}
                          <div style={{ 
                            fontSize: '13px', 
                            color: '#94a3b8', 
                            marginBottom: '12px',
                            display: 'flex',
                            gap: '16px',
                            flexWrap: 'wrap'
                          }}>
                            <span>类型: <span style={{ color: '#a78bfa' }}>{snippet.norm_key}</span></span>
                            <span>·</span>
                            <span>置信度: <span style={{ 
                                  color: snippet.confidence >= 0.9 ? '#10b981' : 
                                        snippet.confidence >= 0.7 ? '#fbbf24' : '#ef4444',
                                  fontWeight: '600'
                                }}>
                                  {(snippet.confidence * 100).toFixed(0)}%
                            </span></span>
                              {snippet.suggest_outline_titles && snippet.suggest_outline_titles.length > 0 && (
                              <>
                                <span>·</span>
                                <span>💡 建议匹配: {snippet.suggest_outline_titles.join(', ')}</span>
                              </>
                              )}
                            </div>
                          
                          {/* 正文内容 */}
                          {snippet.content_text && (
                            <div style={{
                              marginTop: '12px',
                              padding: '16px',
                              backgroundColor: 'rgba(0,0,0,0.2)',
                              borderRadius: '6px',
                              color: '#cbd5e1',
                              fontSize: '14px',
                              lineHeight: '1.8',
                              whiteSpace: 'pre-wrap',
                              fontFamily: 'ui-monospace, monospace',
                              maxHeight: '400px',
                              overflow: 'auto',
                              border: '1px solid rgba(255,255,255,0.05)'
                            }}>
                              {snippet.content_text.split('\n').map((line: string, i: number) => {
                                // 识别并高亮表格标记
                                if (line.includes('[表格开始]')) {
                                  return (
                                    <div key={i} style={{ 
                                      color: '#8b5cf6', 
                                      fontWeight: 'bold', 
                                      marginTop: i > 0 ? '12px' : 0,
                                      marginBottom: '6px'
                                    }}>
                                      {line}
                          </div>
                                  );
                                }
                                if (line.includes('[表格结束]')) {
                                  return (
                                    <div key={i} style={{ 
                                      color: '#8b5cf6', 
                                      fontWeight: 'bold',
                                      marginTop: '6px',
                                      marginBottom: '12px'
                                    }}>
                                      {line}
                                    </div>
                                  );
                                }
                                // 表格分隔线
                                if (line.match(/^-+$/)) {
                                  return <div key={i} style={{ color: '#475569' }}>{line}</div>;
                                }
                                // 表格行（包含 | 符号）
                                if (line.includes('|')) {
                                  return <div key={i} style={{ color: '#93c5fd' }}>{line}</div>;
                                }
                                // 空行
                                if (!line.trim()) {
                                  return <div key={i} style={{ height: '0.5em' }}>&nbsp;</div>;
                                }
                                // 普通文本
                                return <div key={i}>{line}</div>;
                              })}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="kb-empty">
                    暂无数据，请点击"提取格式范文"按钮
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Step 3: AI生成标书 */}
        {activeTab === 3 && (
          <div style={{ 
            height: '100%',  // ✅ 填满父容器
            display: 'flex', 
            flexDirection: 'column',
            overflow: 'hidden'  // ✅ 防止双滚动条
          }}>
            {directory.length > 0 ? (
              <div style={{ 
                flex: 1,  // ✅ 占据剩余空间
                position: 'relative',  // ✅ 为内部absolute/fixed定位提供参考
                overflow: 'hidden',  // ✅ 防止溢出
                display: 'flex',
                flexDirection: 'column'
              }}>
                {/* 插入范文按钮区域 */}
                  <div style={{ 
                    padding: '12px 16px', 
                  backgroundColor: snippets.length > 0 ? 'rgba(139, 92, 246, 0.1)' : 'rgba(251, 191, 36, 0.1)',
                  borderBottom: snippets.length > 0 ? '1px solid rgba(139, 92, 246, 0.2)' : '1px solid rgba(251, 191, 36, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                  gap: '12px',
                  flexWrap: 'wrap'
                  }}>
                  {snippets.length > 0 ? (
                    <>
                    <button
                      onClick={() => currentProject && matchSnippetsToDirectory(currentProject.id)}
                      disabled={!currentProject || matchingSnippets || snippets.length === 0}
                      style={{
                        padding: '8px 16px',
                        backgroundColor: matchingSnippets ? '#6b7280' : '#8b5cf6',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: matchingSnippets ? 'not-allowed' : 'pointer',
                        fontSize: '14px',
                        fontWeight: '500'
                      }}
                    >
                      {matchingSnippets ? '🔄 匹配中...' : '📋 插入范文'}
                    </button>
                    <span style={{ color: '#a78bfa', fontSize: '14px' }}>
                      已提取 {snippets.length} 个范文，点击匹配到目录节点
                    </span>
                    </>
                  ) : (
                    <>
                      <span style={{ color: '#f59e0b', fontSize: '14px', flex: 1 }}>
                        ⚠️ 暂无格式范文数据
                      </span>
                      <button
                        onClick={() => {
                          if (currentProject) {
                            console.log('[手动刷新] 加载格式范文:', currentProject.id);
                            loadSnippets(currentProject.id);
                          }
                        }}
                        disabled={!currentProject}
                        style={{
                          padding: '6px 12px',
                          backgroundColor: '#f59e0b',
                          color: 'white',
                          border: 'none',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          fontSize: '13px',
                          fontWeight: '500'
                        }}
                      >
                        🔄 刷新范文数据
                      </button>
                      <span style={{ color: '#f59e0b', fontSize: '13px' }}>
                        或前往"步骤2 → 格式范文"提取
                      </span>
                    </>
                )}
                </div>
                
                <div style={{ flex: 1, overflow: 'hidden' }}>
                <DocumentComponentManagement
                  embedded={true}
                  initialDirectory={directory}
                  projectId={currentProject?.id}
                />
                </div>
              </div>
            ) : (
              <div className="kb-empty">
                请先在"提取信息"步骤中生成投标目录
              </div>
            )}
          </div>
        )}

        {/* Step 4: 审核 */}
        {activeTab === 4 && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: '16px' }}>
              <button 
                onClick={startReview} 
                className="kb-create-form"
                style={{ width: 'auto', marginBottom: 0 }}
                disabled={reviewRun?.status === 'running' || !selectedBidder}
                title="一体化审核：提取投标响应 + 审核判断一次完成"
              >
                {reviewRun?.status === 'running' ? '审核中...' : '🚀 开始审核'}
              </button>
            </div>
            
            <div style={{ 
              padding: '24px', 
              background: 'rgba(255,255,255,0.05)', 
              borderRadius: '12px',
              marginBottom: '24px'
            }}>
              {/* 投标人选择 */}
              {bidderOptions.length > 0 && (
                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', color: '#e2e8f0', marginBottom: '8px', fontWeight: '500' }}>
                    选择投标人:
                  </label>
                  <select
                    value={selectedBidder}
                    onChange={e => setSelectedBidder(e.target.value)}
                    className="kb-select"
                    style={{ width: '100%' }}
                  >
                    <option value="">-- 请选择 --</option>
                    {bidderOptions.map(name => (
                      <option key={name} value={name}>{name}</option>
                    ))}
                  </select>
                </div>
              )}
              
              {/* 自定义规则包 */}
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', color: '#e2e8f0', marginBottom: '8px', fontWeight: '500' }}>
                  自定义规则包（可选，不选则使用基础评估）:
                </label>
                <div style={{
                  padding: '12px',
                  background: 'rgba(59, 130, 246, 0.1)',
                  borderLeft: '4px solid #3b82f6',
                  marginBottom: '12px',
                  borderRadius: '4px'
                }}>
                  <div style={{ fontWeight: 600, marginBottom: '8px', color: '#60a5fa' }}>💡 审核模式说明</div>
                  <ul style={{ margin: 0, paddingLeft: '20px', color: '#94a3b8', fontSize: '13px' }}>
                    <li style={{ marginBottom: '4px' }}><strong>不选规则包</strong>：基础评估模式 - 基于招标要求快速检查投标响应的完整性</li>
                    <li><strong>选择规则包</strong>：详细审核模式 - 叠加自定义合规规则，进行全面深度审核</li>
                    <li style={{ color: '#fbbf24' }}>💡 <strong>规则包 ≠ 招标要求</strong>：规则包是通用的合规检查规则（如资质、格式等），招标要求是从招标文件中提取的具体要求</li>
                  </ul>
                </div>
                {rulePacks.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {rulePacks.map(pack => (
                      <label key={pack.id} style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        gap: '8px',
                        padding: '8px 12px',
                        background: 'rgba(255,255,255,0.03)',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        color: '#e2e8f0'
                      }}>
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
                    ))}
                  </div>
                ) : (
                  <div className="kb-empty">
                    暂无自定义规则包（可在左侧"自定义规则"页面创建）
                  </div>
                )}
              </div>
              
              {/* 自定义审核规则文件 */}
              <div>
                <label style={{ display: 'block', color: '#e2e8f0', marginBottom: '8px', fontWeight: '500' }}>
                  可选：叠加自定义审核规则文件（可多选）:
                </label>
                <div style={{ 
                  padding: '8px 12px', 
                  background: 'rgba(59, 130, 246, 0.1)', 
                  borderRadius: '4px',
                  marginBottom: '12px',
                  color: '#94a3b8',
                  fontSize: '13px'
                }}>
                  💡 选中的规则文件将作为额外上下文，与招标要求一起用于审核
                </div>
                {assetsByKind.custom_rule.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {assetsByKind.custom_rule.map(asset => (
                      <label key={asset.id} style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        gap: '8px',
                        padding: '8px 12px',
                        background: 'rgba(255,255,255,0.03)',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        color: '#e2e8f0'
                      }}>
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
                    ))}
                  </div>
                ) : (
                  <div className="kb-empty">
                    暂无自定义规则文件（可选，如需要请在"上传文档"步骤中上传"自定义规则文件"类型）
                  </div>
                )}
              </div>
            </div>
            
            {/* 审核状态 */}
            {reviewRun && (
              <div style={{ 
                padding: '12px', 
                background: 'rgba(255,255,255,0.05)', 
                borderRadius: '8px',
                marginBottom: '16px'
              }}>
                <div style={{ color: '#94a3b8' }}>
                  状态: {reviewRun.status}
                  {reviewRun.message && ` - ${reviewRun.message}`}
                  {reviewRun.progress && ` (${(reviewRun.progress * 100).toFixed(0)}%)`}
                </div>
              </div>
            )}
            
            {/* 统计卡片 */}
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
            
            {/* 审核结果表格 */}
            {reviewItems.length > 0 ? (
              <ReviewTable items={reviewItems} onOpenEvidence={showEvidence} />
            ) : (
              <div className="kb-empty" style={{ marginTop: '16px' }}>
                暂无审核记录，请选择投标人并点击"开始审核"
              </div>
            )}
          </div>
        )}
      </div>

      {/* 右侧证据面板 */}
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
            
            {evidenceChunks.map((chunk, idx) => (
              <div key={idx} className="source-item">
                <div className="source-doc-title">{chunk.title || '未命名文档'}</div>
                <div className="source-text">{chunk.text}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 编辑项目模态框 */}
      {editingProject && (
        <div className="modal-overlay" onClick={() => setEditingProject(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginBottom: '16px', color: '#e2e8f0' }}>编辑项目</h3>
            <div style={{ marginBottom: '12px' }}>
              <label className="label-text" style={{ color: '#cbd5e1' }}>项目名称 *</label>
              <input
                type="text"
                value={editProjectName}
                onChange={(e) => setEditProjectName(e.target.value)}
                placeholder="请输入项目名称"
                style={{
                  width: '100%',
                  padding: '10px',
                  background: 'rgba(15, 23, 42, 0.6)',
                  border: '1px solid rgba(148, 163, 184, 0.25)',
                  borderRadius: '6px',
                  color: '#e2e8f0',
                  fontSize: '14px',
                }}
              />
            </div>
            <div style={{ marginBottom: '16px' }}>
              <label className="label-text" style={{ color: '#cbd5e1' }}>项目描述</label>
              <textarea
                value={editProjectDesc}
                onChange={(e) => setEditProjectDesc(e.target.value)}
                placeholder="可选"
                style={{
                  width: '100%',
                  padding: '10px',
                  minHeight: '60px',
                  background: 'rgba(15, 23, 42, 0.6)',
                  border: '1px solid rgba(148, 163, 184, 0.25)',
                  borderRadius: '6px',
                  color: '#e2e8f0',
                  fontSize: '14px',
                  resize: 'vertical',
                }}
              />
            </div>
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setEditingProject(null)}
                style={{
                  padding: '8px 16px',
                  background: 'rgba(148, 163, 184, 0.2)',
                  border: '1px solid rgba(148, 163, 184, 0.3)',
                  borderRadius: '6px',
                  color: '#cbd5e1',
                  fontSize: '14px',
                  cursor: 'pointer',
                }}
              >
                取消
              </button>
              <button
                onClick={saveEditProject}
                style={{
                  padding: '8px 16px',
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  border: 'none',
                  borderRadius: '6px',
                  color: '#ffffff',
                  fontSize: '14px',
                  cursor: 'pointer',
                }}
              >
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
            <div style={{ marginBottom: '16px', padding: '12px', background: 'rgba(252, 211, 77, 0.1)', border: '1px solid rgba(252, 211, 77, 0.3)', borderRadius: '6px', color: '#fbbf24' }}>
              <strong>{deletePlan.warning}</strong>
            </div>
            
            {deletePlan.items && deletePlan.items.length > 0 && (
              <div style={{ marginBottom: '16px' }}>
                <h4 style={{ marginBottom: '8px', color: '#e2e8f0' }}>将删除以下资源：</h4>
                {deletePlan.items.map((item: any, idx: number) => (
                  <div key={idx} style={{ padding: '8px', background: 'rgba(30, 41, 59, 0.6)', marginBottom: '8px', borderRadius: '6px', border: '1px solid rgba(148, 163, 184, 0.2)' }}>
                    <div style={{ fontWeight: 'bold', marginBottom: '4px', color: '#e2e8f0' }}>
                      {item.type}: {item.count} 个
                    </div>
                    {item.samples && item.samples.length > 0 && (
                      <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                        示例: {item.samples.slice(0, 3).join(', ')}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
            
            <div style={{ marginBottom: '16px', padding: '12px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', color: '#fca5a5' }}>
              确定要删除项目 "<strong>{deletingProject.name}</strong>" 吗？此操作无法撤销！
            </div>
            
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button 
                onClick={() => setDeletingProject(null)}
                disabled={isDeleting}
                style={{
                  padding: '8px 16px',
                  background: 'rgba(148, 163, 184, 0.2)',
                  border: '1px solid rgba(148, 163, 184, 0.3)',
                  borderRadius: '6px',
                  color: '#cbd5e1',
                  fontSize: '14px',
                  cursor: isDeleting ? 'not-allowed' : 'pointer',
                  opacity: isDeleting ? 0.6 : 1,
                }}
              >
                取消
              </button>
              <button 
                onClick={confirmDeleteProject}
                disabled={isDeleting}
                style={{
                  padding: '8px 16px',
                  background: '#dc3545',
                  border: 'none',
                  borderRadius: '6px',
                  color: '#ffffff',
                  fontSize: '14px',
                  cursor: isDeleting ? 'not-allowed' : 'pointer',
                  opacity: isDeleting ? 0.6 : 1,
                }}
              >
                {isDeleting ? '删除中...' : '确认删除'}
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* 范文匹配确认面板 */}
      {showSnippetMatchPanel && snippetMatches.length > 0 && (
        <SnippetMatchPanel
          matches={snippetMatches.filter(m => m.snippet_id !== null)}
          onConfirm={async () => {
            if (!currentProject) return;
            
            try {
              // 批量应用范文
              const matchesToApply = snippetMatches
                .filter(m => m.snippet_id !== null)
                .map(m => ({
                  node_id: m.node_id,
                  snippet_id: m.snippet_id
                }));
              
              const result = await api.post(
                `/api/apps/tender/projects/${currentProject.id}/snippets/batch-apply`,
                {
                  matches: matchesToApply,
                  mode: 'replace',
                  auto_fill: true
                }
              );
              
              alert(`✅ 成功应用 ${result.success_count} 个范文！`);
              setShowSnippetMatchPanel(false);
            } catch (err: any) {
              console.error('应用范文失败:', err);
              alert(`应用失败: ${err.response?.data?.detail || err.message || err}`);
            }
          }}
          onCancel={() => setShowSnippetMatchPanel(false)}
        />
      )}
    </div>
    );
  }
}

