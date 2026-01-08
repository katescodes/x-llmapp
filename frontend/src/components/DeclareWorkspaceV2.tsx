/**
 * 申报书工作台组件 V2
 * 改进：
 * 1. 左侧菜单栏始终显示（项目管理等功能）
 * 2. 中间区域：项目列表或项目详情（5个Step工作流）
 * 3. 支持多个申报指南项目，目录分开显示
 * 4. 目录显示格式改为树形结构（类似招投标）
 * 5. Step5 文档生成改为左右布局（左侧目录可编辑，右侧正文预览）
 */
import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../config/api';
import * as declareApi from '../api/declareApiProvider';
import type {
  DeclareProject,
  DeclareAsset,
  DeclareRequirements,
  DeclareDirectoryNode,
  DeclareSection,
  DeclareRun,
} from '../api/declareApi';
import DeclareUserDocumentsPage from './DeclareUserDocumentsPage';
import DocumentComponentManagement from './DocumentComponentManagement';

// ==================== 类型定义 ====================

type Step = 1 | 2 | 3;

type ViewMode = 'projectList' | 'projectDetail';

type Step2Tab = 'requirements' | 'directory';

// ==================== 工具函数 ====================

/**
 * 格式化显示申报要求（非JSON格式）
 */
function renderRequirementsFormatted(data: any) {
  if (!data) return null;
  
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* 资格条件 */}
      {data.eligibility_conditions && data.eligibility_conditions.length > 0 && (
        <div>
          <h5 style={{ margin: '0 0 12px 0', color: '#60a5fa', fontSize: '16px', fontWeight: '600' }}>
            📋 资格条件
          </h5>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {data.eligibility_conditions.map((item: any, idx: number) => (
              <div
                key={idx}
                style={{
                  padding: '12px',
                  background: 'rgba(15, 23, 42, 0.6)',
                  border: '1px solid rgba(148, 163, 184, 0.2)',
                  borderRadius: '6px',
                  color: '#cbd5e1',
                  fontSize: '14px',
                  lineHeight: '1.6',
                }}
              >
                {idx + 1}. {item.condition || item}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 所需材料 */}
      {data.materials_required && data.materials_required.length > 0 && (
        <div>
          <h5 style={{ margin: '0 0 12px 0', color: '#34d399', fontSize: '16px', fontWeight: '600' }}>
            📑 所需材料
          </h5>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {data.materials_required.map((item: any, idx: number) => (
              <div
                key={idx}
                style={{
                  padding: '12px',
                  background: 'rgba(15, 23, 42, 0.6)',
                  border: '1px solid rgba(148, 163, 184, 0.2)',
                  borderRadius: '6px',
                  color: '#cbd5e1',
                  fontSize: '14px',
                  lineHeight: '1.6',
                }}
              >
                {idx + 1}. {item.material || item}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 评审标准 */}
      {data.evaluation_criteria && data.evaluation_criteria.length > 0 && (
        <div>
          <h5 style={{ margin: '0 0 12px 0', color: '#fbbf24', fontSize: '16px', fontWeight: '600' }}>
            ⭐ 评审标准
          </h5>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {data.evaluation_criteria.map((item: any, idx: number) => (
              <div
                key={idx}
                style={{
                  padding: '12px',
                  background: 'rgba(15, 23, 42, 0.6)',
                  border: '1px solid rgba(148, 163, 184, 0.2)',
                  borderRadius: '6px',
                  color: '#cbd5e1',
                  fontSize: '14px',
                  lineHeight: '1.6',
                }}
              >
                {idx + 1}. {item.criterion || item}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * 构建树形结构
 */
function buildTree(nodes: DeclareDirectoryNode[]): DeclareDirectoryNode[] {
  const nodeMap: Record<string, DeclareDirectoryNode & { children: DeclareDirectoryNode[] }> = {};
  const roots: (DeclareDirectoryNode & { children: DeclareDirectoryNode[] })[] = [];

  // 初始化节点映射
  nodes.forEach((node) => {
    nodeMap[node.id] = { ...node, children: [] };
  });

  // 构建树
  nodes.forEach((node) => {
    const treeNode = nodeMap[node.id];
    if (node.parent_id && nodeMap[node.parent_id]) {
      nodeMap[node.parent_id].children.push(treeNode);
    } else {
      roots.push(treeNode);
    }
  });

  return roots;
}

/**
 * 扁平化树节点
 */
function flattenTree(nodes: (DeclareDirectoryNode & { children?: DeclareDirectoryNode[] })[]): DeclareDirectoryNode[] {
  const result: DeclareDirectoryNode[] = [];
  
  const traverse = (node: DeclareDirectoryNode & { children?: DeclareDirectoryNode[] }) => {
    result.push(node);
    if (node.children) {
      node.children.forEach(traverse);
    }
  };
  
  nodes.forEach(traverse);
  return result;
}

// ==================== 主组件 ====================

export default function DeclareWorkspaceV2() {
  // -------------------- 视图模式 --------------------
  const [viewMode, setViewMode] = useState<ViewMode>('projectList');
  
  // -------------------- 项目管理 --------------------
  const [projects, setProjects] = useState<DeclareProject[]>([]);
  const [currentProject, setCurrentProject] = useState<DeclareProject | null>(null);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectDesc, setNewProjectDesc] = useState('');
  const [creatingProject, setCreatingProject] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);

  // 搜索和批量操作
  const [searchKeyword, setSearchKeyword] = useState('');
  const [selectedProjectIds, setSelectedProjectIds] = useState<Set<string>>(new Set());

  // 编辑项目
  const [editingProject, setEditingProject] = useState<DeclareProject | null>(null);
  const [editProjectName, setEditProjectName] = useState('');
  const [editProjectDesc, setEditProjectDesc] = useState('');

  // 删除项目
  const [deletingProject, setDeletingProject] = useState<DeclareProject | null>(null);
  const [deletePlan, setDeletePlan] = useState<any>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // 批量删除
  const [isBatchDeleting, setIsBatchDeleting] = useState(false);

  // -------------------- 文件上传 --------------------
  const [noticeFiles, setNoticeFiles] = useState<File[]>([]);
  const [userDocFiles, setUserDocFiles] = useState<File[]>([]); // 合并原company+tech
  const [imageFiles, setImageFiles] = useState<File[]>([]); // 新增图片
  const [assets, setAssets] = useState<DeclareAsset[]>([]);
  const [uploading, setUploading] = useState(false);

  // -------------------- 流程步骤 --------------------
  const [activeStep, setActiveStep] = useState<Step>(1);

  // Step2: 提取信息（申报要求 + 申报目录）
  const [step2Tab, setStep2Tab] = useState<Step2Tab>('requirements');
  const [requirements, setRequirements] = useState<DeclareRequirements | null>(null);
  const [directoryByNotice, setDirectoryByNotice] = useState<Record<string, DeclareDirectoryNode[]>>({});
  const [directoryVersions, setDirectoryVersions] = useState<any[]>([]);  // 所有项目类型的目录版本
  const [selectedProjectType, setSelectedProjectType] = useState<string | null>(null);  // 当前选择的项目类型
  const [extracting, setExtracting] = useState(false);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [selectedNoticeId, setSelectedNoticeId] = useState<string | null>(null);
  const [noticeAssets, setNoticeAssets] = useState<DeclareAsset[]>([]);

  // Step3: AI生成
  const [sections, setSections] = useState<Record<string, DeclareSection>>({});
  const [generating, setGenerating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [docMeta, setDocMeta] = useState<{ generated: boolean; run_id?: string } | null>(null);

  // -------------------- Toast 提示 --------------------
  const [toast, setToast] = useState<{ kind: 'success' | 'error'; msg: string } | null>(null);
  const showToast = (kind: 'success' | 'error', msg: string) => {
    setToast({ kind, msg });
    setTimeout(() => setToast(null), 3500);
  };

  // -------------------- 初始化 --------------------
  useEffect(() => {
    loadProjects();
  }, []);

  // ✅ 监听 activeStep 变化，重新加载 assets
  useEffect(() => {
    const reloadAssets = async () => {
      if (currentProject && activeStep === 2) {
        try {
          const result = await declareApi.listAssets(currentProject.project_id);
          if (result && result.assets) {
            setAssets(result.assets);
            
            // 筛选申报通知文件
            const notices = result.assets.filter((a: DeclareAsset) => a.kind === 'notice');
            setNoticeAssets(notices);
            
            console.log('[DeclareWorkspace] Step2: 重新加载资产列表, 申报通知数量:', notices.length);
          }
        } catch (err: any) {
          console.error('[DeclareWorkspace] 重新加载资产失败:', err);
        }
      }
    };
    reloadAssets();
  }, [activeStep, currentProject]);

  const loadProjects = async () => {
    try {
      console.log('[DeclareWorkspace] 加载项目列表...');
      const data = await declareApi.listProjects();
      console.log('[DeclareWorkspace] 项目列表数据:', data);
      setProjects(data);
    } catch (err: any) {
      console.error('[DeclareWorkspace] 加载项目列表失败:', err);
      showToast('error', '加载项目列表失败: ' + err.message);
    }
  };

  // -------------------- 项目操作 --------------------
  const handleCreateProject = async () => {
    if (!newProjectName.trim()) {
      showToast('error', '请输入项目名称');
      return;
    }

    setCreatingProject(true);
    try {
      const project = (await declareApi.createProject({
        name: newProjectName,
        description: newProjectDesc || undefined,
      })) as DeclareProject;
      setProjects([project, ...projects]);
      setNewProjectName('');
      setNewProjectDesc('');
      setShowCreateForm(false);
      showToast('success', '项目创建成功');
    } catch (err: any) {
      showToast('error', '创建项目失败: ' + err.message);
    } finally {
      setCreatingProject(false);
    }
  };

  // 编辑项目
  const openEditProject = (proj: DeclareProject) => {
    setEditingProject(proj);
    setEditProjectName(proj.name);
    setEditProjectDesc(proj.description || '');
  };

  const saveEditProject = async () => {
    if (!editingProject || !editProjectName.trim()) {
      showToast('error', '项目名称不能为空');
      return;
    }
    try {
      const updated = await api.request(`/api/apps/declare/projects/${editingProject.project_id}`, {
        method: 'PUT',
        body: JSON.stringify({
          name: editProjectName,
          description: editProjectDesc,
        }),
        headers: { 'Content-Type': 'application/json' },
      });
      
      setProjects(projects.map(p => p.project_id === updated.project_id ? updated : p));
      if (currentProject?.project_id === updated.project_id) {
        setCurrentProject(updated);
      }
      setEditingProject(null);
      showToast('success', '项目更新成功');
    } catch (err: any) {
      showToast('error', `更新失败: ${err.message || err}`);
    }
  };

  // 删除项目
  const openDeleteProject = async (proj: DeclareProject) => {
    setDeletingProject(proj);
    try {
      const plan = await api.request(`/api/apps/declare/projects/${proj.project_id}/delete-plan`);
      setDeletePlan(plan);
    } catch (err: any) {
      showToast('error', `获取删除计划失败: ${err.message || err}`);
      setDeletingProject(null);
    }
  };

  const confirmDeleteProject = async () => {
    if (!deletingProject || !deletePlan) return;
    
    setIsDeleting(true);
    try {
      await api.request(`/api/apps/declare/projects/${deletingProject.project_id}`, {
        method: 'DELETE',
        body: JSON.stringify({
          confirm_token: deletePlan.confirm_token,
        }),
        headers: { 'Content-Type': 'application/json' },
      });
      
      setProjects(projects.filter(p => p.project_id !== deletingProject.project_id));
      if (currentProject?.project_id === deletingProject.project_id) {
        setCurrentProject(null);
        setViewMode('projectList');
      }
      setDeletingProject(null);
      setDeletePlan(null);
      showToast('success', '项目删除成功');
    } catch (err: any) {
      showToast('error', `删除失败: ${err.message || err}`);
    } finally {
      setIsDeleting(false);
    }
  };

  // 批量删除
  const handleBatchDelete = async () => {
    if (selectedProjectIds.size === 0) {
      showToast('error', '请先选择要删除的项目');
      return;
    }

    if (!confirm(`确定要删除选中的 ${selectedProjectIds.size} 个项目吗？此操作不可撤销！`)) {
      return;
    }

    setIsBatchDeleting(true);
    try {
      const deletePromises = Array.from(selectedProjectIds).map(async (projectId) => {
        // 获取删除计划
        const plan = await api.request(`/api/apps/declare/projects/${projectId}/delete-plan`);
        
        // 执行删除
        await api.request(`/api/apps/declare/projects/${projectId}`, {
          method: 'DELETE',
          body: JSON.stringify({ confirm_token: plan.confirm_token }),
          headers: { 'Content-Type': 'application/json' },
        });
      });

      await Promise.all(deletePromises);
      
      setProjects(projects.filter(p => !selectedProjectIds.has(p.project_id)));
      setSelectedProjectIds(new Set());
      showToast('success', `成功删除 ${selectedProjectIds.size} 个项目`);
    } catch (err: any) {
      showToast('error', `批量删除失败: ${err.message || err}`);
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
      setSelectedProjectIds(new Set(filteredProjects.map(p => p.project_id)));
    }
  };

  // 过滤项目
  const filteredProjects = projects.filter(p => 
    p.name.toLowerCase().includes(searchKeyword.toLowerCase()) ||
    (p.description && p.description.toLowerCase().includes(searchKeyword.toLowerCase()))
  );

  const handleSelectProject = async (project: DeclareProject) => {
    console.log('[DeclareWorkspace] 选择项目:', project);
    setCurrentProject(project);
    setViewMode('projectDetail');
    // 重置状态
    setActiveStep(1);
    setAssets([]);
    setRequirements(null);
    setDirectoryByNotice({});
    setSections({});
    setDocMeta(null);
    setNoticeFiles([]);
    setUserDocFiles([]);
    setImageFiles([]);
    setSelectedNodeId(null);
    setSelectedNoticeId(null);
    setStep2Tab('requirements');
    
    // 加载项目的已上传资产
    try {
      const result = await declareApi.listAssets(project.project_id);
      if (result && result.assets && result.assets.length > 0) {
        setAssets(result.assets);
        
        // 筛选申报通知文件
        const notices = result.assets.filter((a: DeclareAsset) => a.kind === 'notice');
        setNoticeAssets(notices);
        
        if (result.assets.length > 0) {
          setActiveStep(2);
        }
      }
      
      // 加载申报要求
      const req = await declareApi.getRequirements(project.project_id);
      if (req && req.data_json) {
        setRequirements(req);
      }
      
      // 加载所有项目类型的目录
      const versions = await declareApi.getAllDirectoryVersions(project.project_id);
      setDirectoryVersions(versions);
      
      if (versions && versions.length > 0) {
        // 设置默认选中第一个项目类型
        const firstVersion = versions[0];
        setSelectedProjectType(firstVersion.project_type);
        setDirectoryByNotice({ [firstVersion.project_type]: firstVersion.nodes });
        
        // 展开一级节点
        const level1Ids = firstVersion.nodes.filter((n: any) => n.level === 1).map((n: any) => n.id);
        setExpandedNodes(new Set(level1Ids));
      }
      
      // 加载章节
      const sectionsData = await declareApi.getSections(project.project_id);
      if (sectionsData && sectionsData.sections && sectionsData.sections.length > 0) {
        const sectionsMap: Record<string, DeclareSection> = {};
        sectionsData.sections.forEach((sec: DeclareSection) => {
          sectionsMap[sec.node_id] = sec;
        });
        setSections(sectionsMap);
        if (Object.keys(sectionsMap).length > 0) {
          setActiveStep(3);
        }
      }
    } catch (err: any) {
      console.error('加载项目数据失败:', err);
    }
  };

  // -------------------- Step1: 上传文件 --------------------
  const handleFileSelect = (kind: 'notice' | 'user_doc' | 'image', files: FileList | null) => {
    if (!files || files.length === 0) return;
    const fileArray = Array.from(files);

    if (kind === 'notice') {
      setNoticeFiles((prev) => [...prev, ...fileArray]);
    } else if (kind === 'user_doc') {
      setUserDocFiles((prev) => [...prev, ...fileArray]);
    } else if (kind === 'image') {
      setImageFiles((prev) => [...prev, ...fileArray]);
    }
  };

  const handleRemoveFile = (kind: 'notice' | 'user_doc' | 'image', index: number) => {
    if (kind === 'notice') {
      setNoticeFiles((prev) => prev.filter((_, i) => i !== index));
    } else if (kind === 'user_doc') {
      setUserDocFiles((prev) => prev.filter((_, i) => i !== index));
    } else if (kind === 'image') {
      setImageFiles((prev) => prev.filter((_, i) => i !== index));
    }
  };

  const handleUploadFiles = async () => {
    if (!currentProject) return;
    
    const allFiles = [
      ...noticeFiles.map(f => ({ kind: 'notice' as const, file: f })),
      ...userDocFiles.map(f => ({ kind: 'user_doc' as const, file: f })),
      ...imageFiles.map(f => ({ kind: 'image' as const, file: f })),
    ];
    
    if (allFiles.length === 0) {
      showToast('error', '请选择文件');
      return;
    }

    setUploading(true);
    try {
      const uploaded: DeclareAsset[] = [];
      
      for (const { kind, file } of allFiles) {
        const result = await declareApi.uploadAssets(currentProject.project_id, kind, [file]) as { assets: DeclareAsset[] };
        uploaded.push(...result.assets);
      }
      
      setAssets([...assets, ...uploaded]);
      
      // 更新申报通知列表
      const notices = [...assets, ...uploaded].filter((a: DeclareAsset) => a.kind === 'notice');
      setNoticeAssets(notices);
      
      setNoticeFiles([]);
      setUserDocFiles([]);
      setImageFiles([]);
      
      showToast('success', `上传成功 ${uploaded.length} 个文件`);
    } catch (err: any) {
      showToast('error', '上传失败: ' + err.message);
    } finally {
      setUploading(false);
    }
  };

  const getAssetsByKind = (kind: string) => {
    return assets.filter((a) => a.kind === kind);
  };

  // -------------------- Step2: 提取信息（申报要求 + 申报目录）--------------------
  const handleExtractInfo = async () => {
    if (!currentProject) return;

    setExtracting(true);
    try {
      // 1. 抽取申报要求
      const reqResult = await declareApi.extractRequirements(currentProject.project_id);
      const reqRunId = (reqResult as DeclareRun).run_id;
      
      // 2. 生成申报目录
      const dirResult = await declareApi.generateDirectory(currentProject.project_id);
      const dirRunId = (dirResult as DeclareRun).run_id;
      
      // 轮询两个任务
      let reqDone = false;
      let dirDone = false;
      let reqSuccess = false;
      let dirSuccess = false;
      
      const checkRuns = async () => {
        try {
          // 检查申报要求
          if (!reqDone) {
            const reqRun = await declareApi.getRun(reqRunId);
            console.log('[DeclareWorkspace] 申报要求状态:', reqRun.status);
            
            if (reqRun.status === 'success') {
              const req = await declareApi.getRequirements(currentProject.project_id);
              setRequirements(req);
              reqDone = true;
              reqSuccess = true;
            } else if (reqRun.status === 'failed') {
              showToast('error', '申报要求提取失败: ' + (reqRun.message || 'Unknown error'));
              reqDone = true;
              reqSuccess = false;
            }
          }
          
          // 检查申报目录
          if (!dirDone) {
            const dirRun = await declareApi.getRun(dirRunId);
            console.log('[DeclareWorkspace] 申报目录状态:', dirRun.status);
            
            if (dirRun.status === 'success') {
              // 加载所有项目类型的目录
              const versions = await declareApi.getAllDirectoryVersions(currentProject.project_id);
              setDirectoryVersions(versions);
              
              if (versions && versions.length > 0) {
                // 设置默认选中第一个项目类型
                const firstVersion = versions[0];
                setSelectedProjectType(firstVersion.project_type);
                setDirectoryByNotice({ [firstVersion.project_type]: firstVersion.nodes });
                
                // 展开一级节点
                const level1Ids = firstVersion.nodes.filter((n: any) => n.level === 1).map((n: any) => n.id);
                setExpandedNodes(new Set(level1Ids));
              }
              
              dirDone = true;
              dirSuccess = true;
            } else if (dirRun.status === 'failed') {
              showToast('error', '申报目录生成失败: ' + (dirRun.message || 'Unknown error'));
              dirDone = true;
              dirSuccess = false;
            }
          }
          
          // 都完成了
          if (reqDone && dirDone) {
            setExtracting(false);
            if (reqSuccess && dirSuccess) {
              showToast('success', '信息提取完成');
            } else if (!reqSuccess && !dirSuccess) {
              showToast('error', '信息提取失败');
            } else {
              showToast('error', '部分信息提取失败');
            }
          } else {
            // 继续轮询
            setTimeout(checkRuns, 2000);
          }
        } catch (err: any) {
          console.error('[DeclareWorkspace] 轮询错误:', err);
          setExtracting(false);
          showToast('error', '检查任务状态失败: ' + err.message);
        }
      };
      
      checkRuns();
    } catch (err: any) {
      setExtracting(false);
      showToast('error', '提取失败: ' + err.message);
    }
  };

  // -------------------- Step3: AI生成文档 --------------------
  const handleGenerateDocument = async () => {
    if (!currentProject) return;

    setGenerating(true);
    try {
      const result = await declareApi.generateDocument(currentProject.project_id);
      
      // 轮询run状态
      const runId = (result as DeclareRun).run_id;
      console.log('[DeclareWorkspace] 开始生成文档, run_id:', runId);
      
      const checkRun = async () => {
        try {
          const run = await declareApi.getRun(runId);
          console.log('[DeclareWorkspace] 文档生成状态:', run.status, 'progress:', run.progress);
          
          if (run.status === 'success') {
            // 重新加载章节内容
            const sectionsData = await declareApi.getSections(currentProject.project_id);
            if (sectionsData && sectionsData.sections) {
              const sectionsMap: Record<string, DeclareSection> = {};
              sectionsData.sections.forEach((sec: DeclareSection) => {
                sectionsMap[sec.node_id] = sec;
              });
              setSections(sectionsMap);
            }
            
            setDocMeta({ generated: true, run_id: runId });
            setGenerating(false);
            showToast('success', '文档生成完成');
          } else if (run.status === 'failed') {
            setGenerating(false);
            showToast('error', '生成失败: ' + (run.message || 'Unknown error'));
          } else {
            // 继续轮询
            setTimeout(checkRun, 2000);
          }
        } catch (err: any) {
          console.error('[DeclareWorkspace] 轮询文档生成状态失败:', err);
          setGenerating(false);
          showToast('error', '检查生成状态失败: ' + err.message);
        }
      };
      
      checkRun();
    } catch (err: any) {
      setGenerating(false);
      showToast('error', '生成失败: ' + err.message);
    }
  };

  const handleExportDocument = async () => {
    if (!currentProject) return;

    setExporting(true);
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        showToast('error', '未登录，请先登录');
        return;
      }

      const response = await fetch(`/api/apps/declare/projects/${currentProject.project_id}/export/docx`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`导出失败: ${response.status} - ${response.statusText}`);
      }
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${currentProject.name}_申报书.docx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      
      showToast('success', '文档导出成功');
    } catch (err: any) {
      showToast('error', '导出失败: ' + err.message);
    } finally {
      setExporting(false);
    }
  };

  // -------------------- 树形目录渲染 --------------------
  const toggleNode = (nodeId: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  };

  const renderDirectoryTree = (
    nodes: (DeclareDirectoryNode & { children?: DeclareDirectoryNode[] })[],
    depth: number = 0
  ) => {
    return nodes.map((node) => {
      const hasChildren = node.children && node.children.length > 0;
      const isExpanded = expandedNodes.has(node.id);
      const isSelected = selectedNodeId === node.id;

      return (
        <div key={node.id}>
          <div
            onClick={() => setSelectedNodeId(node.id)}
            style={{
              padding: '8px 12px',
              paddingLeft: `${12 + depth * 20}px`,
              cursor: 'pointer',
              background: isSelected ? 'rgba(79, 70, 229, 0.2)' : 'transparent',
              borderLeft: isSelected ? '3px solid rgba(79, 70, 229, 0.8)' : '3px solid transparent',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '14px',
              color: isSelected ? '#e5e7eb' : '#cbd5e1',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              if (!isSelected) {
                e.currentTarget.style.background = 'rgba(30, 41, 59, 0.5)';
              }
            }}
            onMouseLeave={(e) => {
              if (!isSelected) {
                e.currentTarget.style.background = 'transparent';
              }
            }}
          >
            {hasChildren && (
              <span
                onClick={(e) => {
                  e.stopPropagation();
                  toggleNode(node.id);
                }}
                style={{
                  cursor: 'pointer',
                  fontSize: '12px',
                  transition: 'transform 0.2s',
                  transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                }}
              >
                ▶
              </span>
            )}
            {!hasChildren && <span style={{ width: '12px' }}></span>}
            <span style={{ fontWeight: node.level === 1 ? '600' : '400' }}>
              {node.numbering && `${node.numbering} `}
              {node.title}
            </span>
          </div>
          {hasChildren && isExpanded && renderDirectoryTree(node.children!, depth + 1)}
        </div>
      );
    });
  };

  // -------------------- 渲染 --------------------
  return (
    <div className="app-root">
      {/* Toast */}
      {toast && (
        <div
          style={{
            position: 'fixed',
            top: '20px',
            right: '20px',
            padding: '16px 24px',
            background: toast.kind === 'success' ? 'rgba(34, 197, 94, 0.9)' : 'rgba(239, 68, 68, 0.9)',
            color: '#ffffff',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
            zIndex: 9999,
            fontSize: '14px',
            fontWeight: '500',
          }}
        >
          {toast.msg}
        </div>
      )}

      {/* 左侧菜单栏（始终显示）*/}
      <div className="sidebar">
        <div className="sidebar-header">
          <h2 style={{ margin: 0 }}>申报书系统</h2>
        </div>
        <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <button
            onClick={() => {
              setViewMode('projectList');
              setCurrentProject(null);
            }}
            className="sidebar-btn"
            style={{ 
              width: '100%',
              padding: '12px 16px',
              background: viewMode === 'projectList' ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' : 'rgba(255, 255, 255, 0.05)',
              border: viewMode === 'projectList' ? 'none' : '1px solid rgba(148, 163, 184, 0.25)',
              borderLeft: viewMode === 'projectList' ? '4px solid #667eea' : '4px solid transparent',
              borderRadius: '8px',
              color: '#ffffff',
              fontSize: '14px',
              fontWeight: viewMode === 'projectList' ? '600' : '500',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-start',
              gap: '12px',
              boxShadow: viewMode === 'projectList' ? '0 2px 8px rgba(102, 126, 234, 0.3)' : 'none',
              transition: 'all 0.2s ease',
            }}
          >
            <span style={{ fontSize: '18px' }}>📂</span>
            <span>项目管理</span>
          </button>
        </div>
      </div>

      {/* 中间工作区 */}
      <div className="main-panel">
        {viewMode === 'projectList' && (
          <div className="kb-detail" style={{ padding: '32px' }}>
            {/* 页面标题 */}
            <div style={{ marginBottom: '32px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h2 style={{ margin: 0, color: '#e2e8f0', fontSize: '28px', fontWeight: '600' }}>项目管理</h2>
                <p style={{ margin: '8px 0 0 0', color: '#94a3b8', fontSize: '14px' }}>管理您的申报书项目</p>
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

            {/* 创建项目表单 */}
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
                        background: 'rgba(15, 23, 42, 0.6)',
                        border: '1px solid rgba(148, 163, 184, 0.25)',
                        borderRadius: '8px',
                        color: '#e2e8f0',
                        fontSize: '14px',
                        minHeight: '80px',
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
                        background: 'rgba(148, 163, 184, 0.2)',
                        border: '1px solid rgba(148, 163, 184, 0.3)',
                        borderRadius: '8px',
                        color: '#cbd5e1',
                        fontSize: '14px',
                        cursor: 'pointer',
                      }}
                    >
                      取消
                    </button>
                    <button
                      onClick={handleCreateProject}
                      disabled={creatingProject || !newProjectName.trim()}
                      style={{
                        padding: '10px 20px',
                        background: creatingProject || !newProjectName.trim() 
                          ? 'rgba(148, 163, 184, 0.3)' 
                          : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        border: 'none',
                        borderRadius: '8px',
                        color: '#ffffff',
                        fontSize: '14px',
                        cursor: creatingProject || !newProjectName.trim() ? 'not-allowed' : 'pointer',
                        opacity: creatingProject || !newProjectName.trim() ? 0.6 : 1,
                      }}
                    >
                      {creatingProject ? '创建中...' : '创建项目'}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* 项目列表 */}
            <div>
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
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h3 style={{ margin: 0, color: '#cbd5e1', fontSize: '18px', fontWeight: '600' }}>
                  现有项目 ({filteredProjects.length}{projects.length !== filteredProjects.length ? ` / ${projects.length}` : ''})
                </h3>
                {filteredProjects.length > 0 && (
                  <button
                    onClick={toggleSelectAll}
                    style={{
                      padding: '6px 12px',
                      background: 'rgba(148, 163, 184, 0.1)',
                      border: '1px solid rgba(148, 163, 184, 0.3)',
                      borderRadius: '6px',
                      color: '#cbd5e1',
                      fontSize: '13px',
                      cursor: 'pointer',
                    }}
                  >
                    {selectedProjectIds.size === filteredProjects.length ? '☑ 取消全选' : '☐ 全选'}
                  </button>
                )}
              </div>
              
              {filteredProjects.length > 0 ? (
                <div style={{ 
                  display: 'grid', 
                  gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', 
                  gap: '20px' 
                }}>
                  {filteredProjects.map((project) => (
                    <div
                      key={project.project_id}
                      style={{
                        background: 'rgba(30, 41, 59, 0.6)',
                        border: selectedProjectIds.has(project.project_id) 
                          ? '2px solid rgba(79, 70, 229, 0.8)' 
                          : '1px solid rgba(148, 163, 184, 0.25)',
                        borderRadius: '12px',
                        padding: '20px',
                        transition: 'all 0.2s ease',
                        position: 'relative',
                      }}
                    >
                      {/* Checkbox */}
                      <div
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleProjectSelection(project.project_id);
                        }}
                        style={{
                          position: 'absolute',
                          top: '12px',
                          left: '12px',
                          width: '20px',
                          height: '20px',
                          background: selectedProjectIds.has(project.project_id) 
                            ? 'rgba(79, 70, 229, 0.8)' 
                            : 'rgba(30, 41, 59, 0.6)',
                          border: '2px solid rgba(148, 163, 184, 0.5)',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: '#fff',
                          fontSize: '12px',
                        }}
                      >
                        {selectedProjectIds.has(project.project_id) && '✓'}
                      </div>

                      {/* 项目内容 */}
                      <div
                        onClick={() => handleSelectProject(project)}
                        style={{ cursor: 'pointer', paddingLeft: '32px' }}
                      >
                        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '12px' }}>
                          <div style={{ 
                            fontSize: '18px', 
                            fontWeight: '600', 
                            color: '#e2e8f0',
                            flex: 1,
                            wordBreak: 'break-word',
                          }}>
                            {project.name}
                          </div>
                          <div style={{
                            fontSize: '24px',
                            opacity: 0.6,
                          }}>
                            📋
                          </div>
                        </div>
                        {project.description && (
                          <div style={{
                            fontSize: '14px',
                            color: '#94a3b8',
                            marginBottom: '12px',
                            lineHeight: '1.5',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}>
                            {project.description}
                          </div>
                        )}
                        <div style={{
                          fontSize: '12px',
                          color: '#64748b',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                        }}>
                          <span>📅</span>
                          <span>{new Date(project.created_at).toLocaleDateString('zh-CN')}</span>
                        </div>
                      </div>

                      {/* 操作按钮 */}
                      <div style={{ 
                        marginTop: '12px', 
                        paddingTop: '12px',
                        borderTop: '1px solid rgba(148, 163, 184, 0.2)',
                        display: 'flex',
                        gap: '8px',
                        paddingLeft: '32px',
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
                  ))}
                </div>
              ) : projects.length > 0 ? (
                <div style={{
                  textAlign: 'center',
                  padding: '60px 20px',
                  background: 'rgba(30, 41, 59, 0.4)',
                  borderRadius: '12px',
                  border: '2px dashed rgba(148, 163, 184, 0.3)',
                }}>
                  <div style={{ fontSize: '48px', marginBottom: '16px', opacity: 0.5 }}>🔍</div>
                  <div style={{ fontSize: '16px', color: '#94a3b8', marginBottom: '8px' }}>没有找到匹配的项目</div>
                  <div style={{ fontSize: '14px', color: '#64748b' }}>尝试使用不同的关键词搜索</div>
                </div>
              ) : (
                <div style={{
                  textAlign: 'center',
                  padding: '60px 20px',
                  background: 'rgba(30, 41, 59, 0.4)',
                  borderRadius: '12px',
                  border: '2px dashed rgba(148, 163, 184, 0.3)',
                }}>
                  <div style={{ fontSize: '48px', marginBottom: '16px', opacity: 0.5 }}>📋</div>
                  <div style={{ fontSize: '16px', color: '#94a3b8', marginBottom: '8px' }}>还没有项目</div>
                  <div style={{ fontSize: '14px', color: '#64748b' }}>点击右上角"新建项目"按钮创建第一个项目</div>
                </div>
              )}
            </div>
          </div>
        )}

        {viewMode === 'projectDetail' && currentProject && (
          <>
            {/* 项目头部 */}
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

              {/* 步骤导航 */}
              <div
                style={{
                  display: 'flex',
                  gap: '8px',
                  padding: '12px 24px',
                  borderBottom: '1px solid rgba(148, 163, 184, 0.2)',
                  background: 'rgba(15, 23, 42, 0.8)',
                  flexWrap: 'wrap',
                }}
              >
                {[1, 2, 3].map((step) => (
                  <button
                    key={step}
                    onClick={() => setActiveStep(step as Step)}
                    className={activeStep === step ? 'pill-button' : 'link-button'}
                    style={{
                      flex: 1,
                      minWidth: '180px',
                      padding: activeStep === step ? '10px' : '10px 12px',
                      ...(activeStep === step ? {
                        background: 'rgba(79, 70, 229, 0.3)',
                        border: '2px solid rgba(79, 70, 229, 0.8)',
                        borderRadius: '6px',
                        color: '#e5e7eb',
                      } : {
                        background: 'rgba(30, 41, 59, 0.5)',
                        border: '1px solid rgba(148, 163, 184, 0.2)',
                        borderRadius: '6px',
                        color: '#e5e7eb',
                      }),
                    }}
                  >
                    Step{step}:{' '}
                    {step === 1
                      ? '上传文档'
                      : step === 2
                      ? '提取信息'
                      : 'AI生成'}
                  </button>
                ))}
              </div>

              {/* 工作区内容 */}
              <div className="kb-detail" style={{ padding: activeStep === 3 ? '0' : '24px', height: 'calc(100vh - 180px)', overflow: 'auto' }}>
                {/* Step1: 上传文档（新样式） */}
                <div style={{ display: activeStep === 1 ? 'block' : 'none' }}>
                  <DeclareUserDocumentsPage projectId={currentProject.project_id} />
                </div>

                {/* Step1: 上传文档（旧版本，已废弃） */}
                {false && activeStep === 1 && (
                  <section className="kb-upload-section">
                    <h4>📤 上传申报材料</h4>

                    {/* 申报通知 */}
                    <div className="source-card" style={{ marginBottom: '20px' }}>
                      <div className="source-card-title" style={{ color: '#60a5fa', marginBottom: '12px' }}>
                        📄 申报通知文件
                      </div>
                      <input
                        type="file"
                        multiple
                        accept=".pdf,.doc,.docx,.txt"
                        onChange={(e) => handleFileSelect('notice', e.target.files)}
                        style={{ marginBottom: '12px', color: '#e5e7eb', fontSize: '13px' }}
                      />
                      <div className="sidebar-hint">
                        已选择 {noticeFiles.length} 个文件，已上传 {getAssetsByKind('notice').length} 个
                      </div>
                      {noticeFiles.map((file, idx) => (
                        <div
                          key={idx}
                          className="kb-doc-meta"
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '6px 8px',
                            marginTop: '6px',
                            background: 'rgba(15, 23, 42, 0.6)',
                            borderRadius: '4px',
                          }}
                        >
                          <span>{file.name}</span>
                          <button
                            onClick={() => handleRemoveFile('notice', idx)}
                            className="link-button"
                            style={{ color: '#fca5a5' }}
                          >
                            删除
                          </button>
                        </div>
                      ))}
                    </div>

                    {/* 用户资料（文档） */}
                    <div className="source-card" style={{ marginBottom: '20px' }}>
                      <div className="source-card-title" style={{ color: '#34d399', marginBottom: '12px' }}>
                        📋 用户资料（文档）
                      </div>
                      <input
                        type="file"
                        multiple
                        accept=".pdf,.doc,.docx,.txt,.xls,.xlsx"
                        onChange={(e) => handleFileSelect('user_doc', e.target.files)}
                        style={{ marginBottom: '12px', color: '#e5e7eb', fontSize: '13px' }}
                      />
                      <div className="sidebar-hint">
                        已选择 {userDocFiles.length} 个文件，已上传 {getAssetsByKind('user_doc').length} 个
                      </div>
                      {userDocFiles.map((file, idx) => (
                        <div
                          key={idx}
                          className="kb-doc-meta"
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '6px 8px',
                            marginTop: '6px',
                            background: 'rgba(15, 23, 42, 0.6)',
                            borderRadius: '4px',
                          }}
                        >
                          <span>{file.name}</span>
                          <button
                            onClick={() => handleRemoveFile('user_doc', idx)}
                            className="link-button"
                            style={{ color: '#fca5a5' }}
                          >
                            删除
                          </button>
                        </div>
                      ))}
                    </div>

                    {/* 用户资料（图片） */}
                    <div className="source-card" style={{ marginBottom: '20px' }}>
                      <div className="source-card-title" style={{ color: '#fbbf24', marginBottom: '12px' }}>
                        🖼️ 用户资料（图片）
                      </div>
                      <input
                        type="file"
                        multiple
                        accept=".jpg,.jpeg,.png,.gif,.bmp,.webp"
                        onChange={(e) => handleFileSelect('image', e.target.files)}
                        style={{ marginBottom: '12px', color: '#e5e7eb', fontSize: '13px' }}
                      />
                      <div className="sidebar-hint">
                        已选择 {imageFiles.length} 个文件，已上传 {getAssetsByKind('image').length} 个
                        <br />
                        <small style={{ color: '#94a3b8' }}>（可选：上传包含"图片文件名"和"图片说明"两列的Excel文件）</small>
                      </div>
                      {imageFiles.map((file, idx) => (
                        <div
                          key={idx}
                          className="kb-doc-meta"
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '6px 8px',
                            marginTop: '6px',
                            background: 'rgba(15, 23, 42, 0.6)',
                            borderRadius: '4px',
                          }}
                        >
                          <span>{file.name}</span>
                          <button
                            onClick={() => handleRemoveFile('image', idx)}
                            className="link-button"
                            style={{ color: '#fca5a5' }}
                          >
                            删除
                          </button>
                        </div>
                      ))}
                    </div>

                    {/* 上传按钮 */}
                    <div style={{ marginTop: '24px' }}>
                      <button
                        onClick={handleUploadFiles}
                        disabled={uploading}
                        className="sidebar-btn"
                        style={{
                          width: '100%',
                          padding: '14px',
                          fontSize: '15px',
                          opacity: uploading ? 0.6 : 1,
                          cursor: uploading ? 'not-allowed' : 'pointer',
                        }}
                      >
                        {uploading ? '上传中...' : '上传所有文件'}
                      </button>
                    </div>

                    {/* 已上传文件列表 */}
                    {assets.length > 0 && (
                      <div style={{ marginTop: '32px' }}>
                        <h4 style={{ margin: '0 0 16px 0', color: '#cbd5e1', fontSize: '16px' }}>已上传文件</h4>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                          {assets.map((asset) => (
                            <div
                              key={asset.asset_id}
                              style={{
                                padding: '12px',
                                background: 'rgba(30, 41, 59, 0.6)',
                                border: '1px solid rgba(148, 163, 184, 0.25)',
                                borderRadius: '8px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                              }}
                            >
                              <div style={{ flex: 1 }}>
                                <div style={{ color: '#e5e7eb', fontSize: '14px', fontWeight: '500', marginBottom: '4px' }}>
                                  {asset.filename}
                                </div>
                                <div style={{ color: '#94a3b8', fontSize: '12px' }}>
                                  {asset.kind === 'notice' ? '📄 申报通知' : asset.kind === 'company' ? '🏢 企业信息' : '🔬 技术资料'}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </section>
                )}

                {/* Step2: 提取信息（Tab切换：申报要求 + 申报目录）*/}
                {activeStep === 2 && (
                  <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    {/* Tab导航 + 提取按钮 */}
                    <div style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center',
                      marginBottom: '24px',
                      borderBottom: '2px solid rgba(148, 163, 184, 0.2)',
                      paddingBottom: '12px',
                    }}>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button
                          onClick={() => setStep2Tab('requirements')}
                          style={{
                            padding: '10px 20px',
                            background: step2Tab === 'requirements' ? 'rgba(79, 70, 229, 0.3)' : 'rgba(30, 41, 59, 0.5)',
                            border: step2Tab === 'requirements' ? '2px solid rgba(79, 70, 229, 0.8)' : '1px solid rgba(148, 163, 184, 0.2)',
                            borderRadius: '6px',
                            color: '#e5e7eb',
                            fontSize: '14px',
                            fontWeight: step2Tab === 'requirements' ? '600' : '400',
                            cursor: 'pointer',
                            transition: 'all 0.2s',
                          }}
                        >
                          📋 申报要求
                        </button>
                        <button
                          onClick={() => setStep2Tab('directory')}
                          style={{
                            padding: '10px 20px',
                            background: step2Tab === 'directory' ? 'rgba(79, 70, 229, 0.3)' : 'rgba(30, 41, 59, 0.5)',
                            border: step2Tab === 'directory' ? '2px solid rgba(79, 70, 229, 0.8)' : '1px solid rgba(148, 163, 184, 0.2)',
                            borderRadius: '6px',
                            color: '#e5e7eb',
                            fontSize: '14px',
                            fontWeight: step2Tab === 'directory' ? '600' : '400',
                            cursor: 'pointer',
                            transition: 'all 0.2s',
                          }}
                        >
                          📑 申报目录
                        </button>
                      </div>
                      
                      <button
                        onClick={handleExtractInfo}
                        disabled={extracting || noticeAssets.length === 0}
                        className="sidebar-btn"
                        style={{
                          padding: '10px 24px',
                          fontSize: '14px',
                          opacity: extracting || noticeAssets.length === 0 ? 0.6 : 1,
                          cursor: extracting || noticeAssets.length === 0 ? 'not-allowed' : 'pointer',
                        }}
                      >
                        {extracting ? '提取中...' : '🚀 提取信息'}
                      </button>
                    </div>

                    {/* Tab内容区 */}
                    <div style={{ flex: 1, overflow: 'auto' }}>
                      {step2Tab === 'requirements' && (
                        <div>
                          {requirements && requirements.data_json ? (
                            <div
                              style={{
                                padding: '20px',
                                background: 'rgba(30, 41, 59, 0.6)',
                                border: '1px solid rgba(148, 163, 184, 0.25)',
                                borderRadius: '12px',
                              }}
                            >
                              {renderRequirementsFormatted(requirements.data_json)}
                            </div>
                          ) : (
                            <div style={{
                              padding: '60px 20px',
                              background: 'rgba(30, 41, 59, 0.4)',
                              borderRadius: '12px',
                              border: '2px dashed rgba(148, 163, 184, 0.3)',
                              textAlign: 'center',
                            }}>
                              <div style={{ fontSize: '48px', marginBottom: '16px', opacity: 0.5 }}>📋</div>
                              <div style={{ fontSize: '16px', color: '#94a3b8', marginBottom: '8px' }}>还没有申报要求</div>
                              <div style={{ fontSize: '14px', color: '#64748b' }}>请先上传申报通知文件，然后点击"提取信息"按钮</div>
                            </div>
                          )}
                        </div>
                      )}

                      {step2Tab === 'directory' && (
                        <div>
                          {directoryVersions && directoryVersions.length > 0 ? (
                            <div>
                              {/* 项目类型选择器 */}
                              {directoryVersions.length > 1 && (
                                <div style={{
                                  marginBottom: '16px',
                                  padding: '12px 16px',
                                  background: 'rgba(59, 130, 246, 0.1)',
                                  border: '1px solid rgba(59, 130, 246, 0.3)',
                                  borderRadius: '8px',
                                }}>
                                  <label style={{ display: 'flex', alignItems: 'center', gap: '12px', color: '#e2e8f0', fontSize: '14px' }}>
                                    <span style={{ fontWeight: 600 }}>📂 选择项目类型：</span>
                                    <select
                                      value={selectedProjectType || ''}
                                      onChange={(e) => setSelectedProjectType(e.target.value)}
                                      style={{
                                        flex: 1,
                                        padding: '8px 12px',
                                        background: 'rgba(30, 41, 59, 0.8)',
                                        color: '#e2e8f0',
                                        border: '1px solid rgba(148, 163, 184, 0.3)',
                                        borderRadius: '6px',
                                        fontSize: '14px',
                                        cursor: 'pointer',
                                      }}
                                    >
                                      {directoryVersions.map((v: any) => (
                                        <option key={v.version_id} value={v.project_type}>
                                          {v.project_type}
                                          {v.project_description ? ` - ${v.project_description}` : ''}
                                        </option>
                                      ))}
                                    </select>
                                  </label>
                                </div>
                              )}
                              
                              {/* 显示选中项目类型的目录 */}
                              {selectedProjectType && directoryVersions.find((v: any) => v.project_type === selectedProjectType) && (
                                <div
                                  style={{
                                    background: 'rgba(30, 41, 59, 0.6)',
                                    border: '1px solid rgba(148, 163, 184, 0.25)',
                                    borderRadius: '12px',
                                    overflow: 'hidden',
                                  }}
                                >
                                  {renderDirectoryTree(buildTree(
                                    directoryVersions.find((v: any) => v.project_type === selectedProjectType)?.nodes || []
                                  ))}
                                </div>
                              )}
                            </div>
                          ) : (
                            <div style={{
                              padding: '60px 20px',
                              background: 'rgba(30, 41, 59, 0.4)',
                              borderRadius: '12px',
                              border: '2px dashed rgba(148, 163, 184, 0.3)',
                              textAlign: 'center',
                            }}>
                              <div style={{ fontSize: '48px', marginBottom: '16px', opacity: 0.5 }}>📑</div>
                              <div style={{ fontSize: '16px', color: '#94a3b8', marginBottom: '8px' }}>还没有申报目录</div>
                              <div style={{ fontSize: '14px', color: '#64748b' }}>请先上传申报通知文件，然后点击"提取信息"按钮</div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Step3: AI生成（使用统一的DocumentComponentManagement组件）*/}
                <div style={{ 
                  display: activeStep === 3 ? 'flex' : 'none',
                  height: '100%',
                  flexDirection: 'column',
                  overflow: 'hidden'
                }}>
                  {directoryVersions && directoryVersions.length > 0 ? (
                    <div style={{ 
                      flex: 1,
                      display: 'flex',
                      flexDirection: 'column',
                      overflow: 'hidden',
                      gap: '16px'
                    }}>
                      {/* 项目类型选择器 */}
                      {directoryVersions.length > 1 && (
                        <div style={{
                          flexShrink: 0,
                          padding: '12px 16px',
                          background: 'rgba(59, 130, 246, 0.1)',
                          border: '1px solid rgba(59, 130, 246, 0.3)',
                          borderRadius: '8px',
                        }}>
                          <label style={{ display: 'flex', alignItems: 'center', gap: '12px', color: '#e2e8f0', fontSize: '14px' }}>
                            <span style={{ fontWeight: 600 }}>📂 选择项目类型：</span>
                            <select
                              value={selectedProjectType || ''}
                              onChange={(e) => setSelectedProjectType(e.target.value)}
                              style={{
                                flex: 1,
                                padding: '8px 12px',
                                background: 'rgba(30, 41, 59, 0.8)',
                                color: '#e2e8f0',
                                border: '1px solid rgba(148, 163, 184, 0.3)',
                                borderRadius: '6px',
                                fontSize: '14px',
                                cursor: 'pointer',
                              }}
                            >
                              {directoryVersions.map((v: any) => (
                                <option key={v.version_id} value={v.project_type}>
                                  {v.project_type}
                                  {v.project_description ? ` - ${v.project_description}` : ''}
                                </option>
                              ))}
                            </select>
                          </label>
                        </div>
                      )}
                      
                      {/* 文档生成界面 */}
                      {selectedProjectType && directoryVersions.find((v: any) => v.project_type === selectedProjectType) && (
                        <div style={{ 
                          flex: 1,
                          position: 'relative',
                          overflow: 'hidden'
                        }}>
                          <DocumentComponentManagement
                            embedded={true}
                            initialDirectory={
                              directoryVersions.find((v: any) => v.project_type === selectedProjectType)?.nodes || []
                            }
                            projectId={currentProject?.project_id}
                            moduleType="declare"
                          />
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="kb-empty">
                      请先在"提取信息"步骤中生成申报目录
                    </div>
                  )}
                </div>

              </div>
            </>
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
    </div>
  );
}
