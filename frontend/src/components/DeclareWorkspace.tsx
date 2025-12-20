/**
 * 申报书工作台组件
 * 对接真实后端 API
 */
import React, { useState, useEffect } from 'react';
import * as declareApi from '../api/declareApiProvider';
import type {
  DeclareProject,
  DeclareAsset,
  DeclareRequirements,
  DeclareDirectoryNode,
  DeclareSection,
  DeclareRun,
} from '../api/declareApi';

// ==================== 类型定义 ====================

type Step = 1 | 2 | 3 | 4 | 5;

type RightPanelTab = 'requirements' | 'directory' | 'section';

// ==================== 主组件 ====================

export default function DeclareWorkspace() {
  // -------------------- 项目管理 --------------------
  const [projects, setProjects] = useState<DeclareProject[]>([]);
  const [currentProject, setCurrentProject] = useState<DeclareProject | null>(null);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectDesc, setNewProjectDesc] = useState('');
  const [creatingProject, setCreatingProject] = useState(false);

  // -------------------- 文件上传 --------------------
  const [noticeFiles, setNoticeFiles] = useState<File[]>([]);
  const [companyFiles, setCompanyFiles] = useState<File[]>([]);
  const [techFiles, setTechFiles] = useState<File[]>([]);
  const [assets, setAssets] = useState<DeclareAsset[]>([]);
  const [uploading, setUploading] = useState(false);

  // -------------------- 流程步骤 --------------------
  const [activeStep, setActiveStep] = useState<Step>(1);

  // Step2: 申报要求
  const [requirements, setRequirements] = useState<DeclareRequirements | null>(null);
  const [extractingRequirements, setExtractingRequirements] = useState(false);

  // Step3: 目录
  const [directory, setDirectory] = useState<DeclareDirectoryNode[]>([]);
  const [generatingDirectory, setGeneratingDirectory] = useState(false);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  // Step4: 章节内容
  const [sections, setSections] = useState<Record<string, DeclareSection>>({});
  const [autoFilling, setAutoFilling] = useState(false);

  // Step5: 生成文档
  const [docMeta, setDocMeta] = useState<{ generated: boolean; run_id?: string } | null>(null);
  const [generating, setGenerating] = useState(false);
  const [exporting, setExporting] = useState(false);

  // Run状态
  const [runStatus, setRunStatus] = useState<{
    type: 'requirements' | 'directory' | 'sections' | 'document' | null;
    status: string;
    progress: number;
    message?: string;
  }>({ type: null, status: '', progress: 0 });

  // -------------------- 右侧面板 --------------------
  const [rightPanelTab, setRightPanelTab] = useState<RightPanelTab>('requirements');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

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

  const loadProjects = async () => {
    try {
      const data = await declareApi.listProjects();
      setProjects(data);
    } catch (err: any) {
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
      const project = await declareApi.createProject({
        name: newProjectName,
        description: newProjectDesc || undefined,
      });
      setProjects([project, ...projects]);
      setCurrentProject(project);
      setNewProjectName('');
      setNewProjectDesc('');
      showToast('success', '项目创建成功');
    } catch (err: any) {
      showToast('error', '创建项目失败: ' + err.message);
    } finally {
      setCreatingProject(false);
    }
  };

  const handleSelectProject = async (project: DeclareProject) => {
    setCurrentProject(project);
    // 重置状态
    setActiveStep(1);
    setAssets([]);
    setRequirements(null);
    setDirectory([]);
    setSections({});
    setDocMeta(null);
    setNoticeFiles([]);
    setCompanyFiles([]);
    setTechFiles([]);
    setSelectedNodeId(null);
    
    // 加载项目的已上传资产
    try {
      const result = await declareApi.listAssets(project.project_id);
      if (result && result.assets && result.assets.length > 0) {
        setAssets(result.assets);
        // 根据已有资产判断应该在哪个步骤
        if (result.assets.length > 0) {
          setActiveStep(2); // 有文件了，可以进入下一步
        }
      }
      
      // 加载申报要求
      const req = await declareApi.getRequirements(project.project_id);
      if (req && req.data_json) {
        setRequirements(req);
        setActiveStep(3); // 有申报要求了
      }
      
      // 加载目录
      const nodes = await declareApi.getDirectoryNodes(project.project_id);
      if (nodes && nodes.length > 0) {
        setDirectory(nodes);
        setActiveStep(4); // 有目录了
        
        // 展开一级节点
        const level1Ids = nodes.filter((n: any) => n.level === 1).map((n: any) => n.id);
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
        setActiveStep(5); // 有章节了
      }
    } catch (err: any) {
      console.error('加载项目数据失败:', err);
      // 不显示错误提示，静默失败
    }
  };

  // -------------------- Step1: 上传文件 --------------------
  const handleFileSelect = (kind: 'notice' | 'company' | 'tech', files: FileList | null) => {
    if (!files || files.length === 0) return;
    const fileArray = Array.from(files);

    if (kind === 'notice') {
      setNoticeFiles((prev) => [...prev, ...fileArray]);
    } else if (kind === 'company') {
      setCompanyFiles((prev) => [...prev, ...fileArray]);
    } else if (kind === 'tech') {
      setTechFiles((prev) => [...prev, ...fileArray]);
    }
  };

  const handleRemoveFile = (kind: 'notice' | 'company' | 'tech', index: number) => {
    if (kind === 'notice') {
      setNoticeFiles((prev) => prev.filter((_, i) => i !== index));
    } else if (kind === 'company') {
      setCompanyFiles((prev) => prev.filter((_, i) => i !== index));
    } else if (kind === 'tech') {
      setTechFiles((prev) => prev.filter((_, i) => i !== index));
    }
  };

  const handleUploadAll = async () => {
    if (!currentProject) {
      showToast('error', '请先选择项目');
      return;
    }

    const allFiles = [...noticeFiles, ...companyFiles, ...techFiles];
    if (allFiles.length === 0) {
      showToast('error', '请先选择文件');
      return;
    }

    setUploading(true);
    try {
      const uploadedAssets: DeclareAsset[] = [];

      if (noticeFiles.length > 0) {
        const result = await declareApi.uploadAssets(currentProject.project_id, 'notice', noticeFiles);
        uploadedAssets.push(...result.assets);
      }
      if (companyFiles.length > 0) {
        const result = await declareApi.uploadAssets(currentProject.project_id, 'company', companyFiles);
        uploadedAssets.push(...result.assets);
      }
      if (techFiles.length > 0) {
        const result = await declareApi.uploadAssets(currentProject.project_id, 'tech', techFiles);
        uploadedAssets.push(...result.assets);
      }

      setAssets((prev) => [...prev, ...uploadedAssets]);
      showToast('success', `成功上传 ${uploadedAssets.length} 个文件`);

      // 清空已上传的文件
      setNoticeFiles([]);
      setCompanyFiles([]);
      setTechFiles([]);
    } catch (err: any) {
      showToast('error', '上传失败: ' + err.message);
    } finally {
      setUploading(false);
    }
  };

  // -------------------- Step2: 分析申报要求 --------------------
  const handleExtractRequirements = async () => {
    if (!currentProject) {
      showToast('error', '请先选择项目');
      return;
    }

    const noticeAssets = assets.filter((a) => a.kind === 'notice');
    if (noticeAssets.length === 0) {
      showToast('error', '请先上传申报通知文件');
      return;
    }

    setExtractingRequirements(true);
    try {
      // 使用同步模式直接执行
      setRunStatus({
        type: 'requirements',
        status: 'running',
        progress: 0,
        message: '正在提取申报要求...',
      });
      
      const run = await declareApi.extractRequirements(currentProject.project_id, { sync: 1 });
      
      // 检查结果
      if (run.status === 'success') {
        const data = await declareApi.getRequirements(currentProject.project_id);
        if (data) {
          setRequirements(data);
          setRightPanelTab('requirements');
          setActiveStep(3);
          showToast('success', '申报要求分析完成');
        }
      } else {
        showToast('error', '分析失败: ' + (run.message || 'Unknown error'));
      }
    } catch (err: any) {
      showToast('error', '分析失败: ' + err.message);
    } finally {
      setExtractingRequirements(false);
      setRunStatus({ type: null, status: '', progress: 0 });
    }
  };

  // -------------------- Step3: 生成目录 --------------------
  const handleGenerateDirectory = async () => {
    if (!currentProject) {
      showToast('error', '请先选择项目');
      return;
    }

    if (!requirements) {
      showToast('error', '请先分析申报要求');
      return;
    }

    setGeneratingDirectory(true);
    try {
      // 使用同步模式直接执行
      setRunStatus({
        type: 'directory',
        status: 'running',
        progress: 0,
        message: '正在生成目录...',
      });
      
      const run = await declareApi.generateDirectory(currentProject.project_id, { sync: 1 });
      
      // 检查结果
      if (run.status === 'success') {
        const nodes = await declareApi.getDirectoryNodes(currentProject.project_id);
        setDirectory(nodes);
        setRightPanelTab('directory');
        setActiveStep(4);
        
        // 默认展开所有一级节点
        const level1Ids = nodes.filter((n) => n.level === 1).map((n) => n.id);
        setExpandedNodes(new Set(level1Ids));
        
        showToast('success', '申报书目录生成完成');
      } else {
        showToast('error', '生成失败: ' + (run.message || 'Unknown error'));
      }
    } catch (err: any) {
      showToast('error', '生成目录失败: ' + err.message);
    } finally {
      setGeneratingDirectory(false);
      setRunStatus({ type: null, status: '', progress: 0 });
    }
  };

  // -------------------- Step4: 自动填充 --------------------
  const handleAutofill = async () => {
    if (!currentProject) {
      showToast('error', '请先选择项目');
      return;
    }

    if (directory.length === 0) {
      showToast('error', '请先生成目录');
      return;
    }

    const companyAssets = assets.filter((a) => a.kind === 'company');
    const techAssets = assets.filter((a) => a.kind === 'tech');
    if (companyAssets.length === 0 && techAssets.length === 0) {
      showToast('error', '请先上传企业信息和技术资料');
      return;
    }

    setAutoFilling(true);
    try {
      // 使用同步模式直接执行
      setRunStatus({
        type: 'sections',
        status: 'running',
        progress: 0,
        message: '正在自动填充章节...',
      });
      
      const run = await declareApi.autofillSections(currentProject.project_id, { sync: 1 });
      
      // 检查结果
      if (run.status === 'success') {
        const sectionsList = await declareApi.getSections(currentProject.project_id);
        // 转换为 Record<node_id, section>
        const sectionsMap = sectionsList.reduce((acc, sec) => {
          acc[sec.node_id] = sec;
          return acc;
        }, {} as Record<string, DeclareSection>);
        setSections(sectionsMap);
        setActiveStep(5);
        showToast('success', `自动填充完成，已填充 ${sectionsList.length} 个章节`);
      } else {
        showToast('error', '填充失败: ' + (run.message || 'Unknown error'));
      }
    } catch (err: any) {
      showToast('error', '自动填充失败: ' + err.message);
    } finally {
      setAutoFilling(false);
      setRunStatus({ type: null, status: '', progress: 0 });
    }
  };

  // -------------------- Step5: 生成申报书 --------------------
  const handleGenerateDocument = async () => {
    if (!currentProject) {
      showToast('error', '请先选择项目');
      return;
    }

    if (directory.length === 0) {
      showToast('error', '请先生成目录');
      return;
    }

    setGenerating(true);
    try {
      // 使用同步模式直接执行
      setRunStatus({
        type: 'document',
        status: 'running',
        progress: 0,
        message: '正在生成文档...',
      });
      
      const run = await declareApi.generateDocument(currentProject.project_id, { sync: 1 });
      
      // 检查结果
      if (run.status === 'success') {
        setDocMeta({ generated: true, run_id: run.run_id });
        showToast('success', '申报书生成完成，可导出！');
      } else {
        showToast('error', '生成失败: ' + (run.message || 'Unknown error'));
      }
    } catch (err: any) {
      showToast('error', '生成失败: ' + err.message);
    } finally {
      setGenerating(false);
      setRunStatus({ type: null, status: '', progress: 0 });
    }
  };

  // -------------------- 导出 --------------------
  const handleExport = async () => {
    if (!currentProject) {
      showToast('error', '请先选择项目');
      return;
    }

    if (!docMeta) {
      showToast('error', '请先生成申报书');
      return;
    }

    setExporting(true);
    try {
      const blob = await declareApi.exportDocx(currentProject.project_id);
      const filename = `${currentProject.name}-申报书.docx`;
      declareApi.downloadBlob(blob, filename);
      showToast('success', '导出成功');
    } catch (err: any) {
      showToast('error', '导出失败: ' + err.message);
    } finally {
      setExporting(false);
    }
  };

  // -------------------- 目录树操作 --------------------
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

  const handleSelectNode = (nodeId: string) => {
    setSelectedNodeId(nodeId);
    setRightPanelTab('section');
  };

  // -------------------- 渲染辅助函数 --------------------
  const renderDirectoryTree = (parentId: string | null = null, depth: number = 0): React.ReactNode => {
    const children = directory.filter((n) => n.parent_id === parentId);
    if (children.length === 0) return null;

    return (
      <ul style={{ listStyle: 'none', paddingLeft: depth > 0 ? '20px' : '0', margin: 0 }}>
        {children.map((node) => {
          const isExpanded = expandedNodes.has(node.id);
          const hasChildren = directory.some((n) => n.parent_id === node.id);
          const isSelected = selectedNodeId === node.id;
          const isFilled = sections[node.id]?.content_md ? true : false;

          return (
            <li key={node.id} style={{ marginBottom: '4px' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '6px 8px',
                  borderRadius: '4px',
                  background: isSelected ? 'rgba(79, 70, 229, 0.2)' : 'transparent',
                  cursor: 'pointer',
                  transition: 'background 0.15s',
                }}
                onClick={() => handleSelectNode(node.id)}
              >
                {hasChildren && (
                  <span
                    style={{ marginRight: '6px', fontSize: '12px', userSelect: 'none' }}
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleNode(node.id);
                    }}
                  >
                    {isExpanded ? '▼' : '▶'}
                  </span>
                )}
                <span style={{ fontSize: '13px', color: '#e5e7eb', flex: 1 }}>
                  {node.numbering} {node.title}
                </span>
                {node.is_required && (
                  <span style={{ fontSize: '11px', color: '#ef4444', marginLeft: '8px' }}>*必填</span>
                )}
                {isFilled && (
                  <span style={{ fontSize: '11px', color: '#10b981', marginLeft: '8px' }}>✓</span>
                )}
              </div>
              {isExpanded && renderDirectoryTree(node.id, depth + 1)}
            </li>
          );
        })}
      </ul>
    );
  };

  const getAssetsByKind = (kind: 'notice' | 'company' | 'tech') => {
    return assets.filter((a) => a.kind === kind);
  };

  // ==================== 渲染 ====================

  return (
    <div className="app-root">
      {/* Toast 提示 */}
      {toast && (
        <div
          style={{
            position: 'fixed',
            top: '20px',
            right: '20px',
            zIndex: 9999,
            padding: '12px 20px',
            borderRadius: '8px',
            background: toast.kind === 'success' ? 'rgba(16, 185, 129, 0.9)' : 'rgba(239, 68, 68, 0.9)',
            color: '#fff',
            fontWeight: 500,
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
          }}
        >
          {toast.msg}
        </div>
      )}

      {/* 左侧：项目列表 */}
      <div className="sidebar">
        <div style={{ padding: '16px', borderBottom: '1px solid rgba(148, 163, 184, 0.2)' }}>
          <div className="sidebar-title">📋 申报书项目</div>
          <div className="sidebar-subtitle">AI辅助生成申报文档</div>
        </div>

        {/* 新建项目 */}
        <div className="kb-create-form" style={{ padding: '16px', borderBottom: '1px solid rgba(148, 163, 184, 0.2)' }}>
          <input
            type="text"
            placeholder="项目名称"
            value={newProjectName}
            onChange={(e) => setNewProjectName(e.target.value)}
          />
          <textarea
            placeholder="项目描述（可选）"
            value={newProjectDesc}
            onChange={(e) => setNewProjectDesc(e.target.value)}
            style={{ minHeight: '50px' }}
          />
          <button
            onClick={handleCreateProject}
            disabled={creatingProject}
          >
            {creatingProject ? '创建中...' : '+ 新建项目'}
          </button>
        </div>

        {/* 项目列表 */}
        <div className="kb-list-panel" style={{ flex: 1, overflowY: 'auto', padding: '8px' }}>
            {projects.map((proj) => (
              <div
                key={proj.project_id}
                onClick={() => handleSelectProject(proj)}
                className={`kb-row ${currentProject?.project_id === proj.project_id ? 'active' : ''}`}
              >
              <div className="kb-name">{proj.name}</div>
              {proj.description && (
                <div className="kb-meta">{proj.description}</div>
              )}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: '#64748b', marginTop: '6px' }}>
                <span>{new Date(proj.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))}
          {projects.length === 0 && (
            <div className="kb-empty">还没有项目，请先创建一个</div>
          )}
        </div>
      </div>

      {/* 中间：工作区 */}
      <div className="main-panel">
        {currentProject ? (
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
              {[1, 2, 3, 4, 5].map((step) => (
                <button
                  key={step}
                  onClick={() => setActiveStep(step as Step)}
                  className={activeStep === step ? 'pill-button' : 'link-button'}
                  style={{
                    flex: 1,
                    minWidth: '140px',
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
                    ? '上传文件'
                    : step === 2
                    ? '分析要求'
                    : step === 3
                    ? '生成目录'
                    : step === 4
                    ? '自动填充'
                    : '生成文档'}
                </button>
              ))}
            </div>

            {/* 工作区内容 */}
            <div className="kb-detail">
              {/* Step1: 上传文件 */}
              {activeStep === 1 && (
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

                  {/* 企业信息 */}
                  <div className="source-card" style={{ marginBottom: '20px' }}>
                    <div className="source-card-title" style={{ color: '#34d399', marginBottom: '12px' }}>
                      🏢 企业信息文件
                    </div>
                    <input
                      type="file"
                      multiple
                      onChange={(e) => handleFileSelect('company', e.target.files)}
                      style={{ marginBottom: '12px', color: '#e5e7eb', fontSize: '13px' }}
                    />
                    <div className="sidebar-hint">
                      已选择 {companyFiles.length} 个文件，已上传 {getAssetsByKind('company').length} 个
                    </div>
                    {companyFiles.map((file, idx) => (
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
                          onClick={() => handleRemoveFile('company', idx)}
                          className="link-button"
                          style={{ color: '#fca5a5' }}
                        >
                          删除
                        </button>
                      </div>
                    ))}
                  </div>

                  {/* 技术资料 */}
                  <div className="source-card" style={{ marginBottom: '20px' }}>
                    <div className="source-card-title" style={{ color: '#fbbf24', marginBottom: '12px' }}>
                      🔬 技术资料文件
                    </div>
                    <input
                      type="file"
                      multiple
                      onChange={(e) => handleFileSelect('tech', e.target.files)}
                      style={{ marginBottom: '12px', color: '#e5e7eb', fontSize: '13px' }}
                    />
                    <div className="sidebar-hint">
                      已选择 {techFiles.length} 个文件，已上传 {getAssetsByKind('tech').length} 个
                    </div>
                    {techFiles.map((file, idx) => (
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
                          onClick={() => handleRemoveFile('tech', idx)}
                          className="link-button"
                          style={{ color: '#fca5a5' }}
                        >
                          删除
                        </button>
                      </div>
                    ))}
                  </div>

                  {/* 上传按钮 */}
                  <button
                    onClick={handleUploadAll}
                    disabled={uploading || (noticeFiles.length === 0 && companyFiles.length === 0 && techFiles.length === 0)}
                    className="kb-create-form"
                    style={{ width: 'auto', marginBottom: 0, opacity: uploading ? 0.6 : 1 }}
                  >
                    {uploading ? '上传中...' : '📤 批量上传'}
                  </button>
                </section>
              )}

              {/* Step2: 分析申报要求 */}
              {activeStep === 2 && (
                <section className="kb-upload-section">
                  <h4>🔍 分析申报要求</h4>
                  <div className="sidebar-hint" style={{ marginBottom: '20px' }}>
                    AI 将分析申报通知文件，提取申报条件、材料清单、截止时间等关键信息。
                  </div>

                  <button
                    onClick={handleExtractRequirements}
                    disabled={extractingRequirements || getAssetsByKind('notice').length === 0}
                    className="kb-create-form"
                    style={{ width: 'auto', marginBottom: 0, opacity: extractingRequirements ? 0.6 : 1 }}
                  >
                    {extractingRequirements ? '分析中...' : '🔍 分析申报要求'}
                  </button>

                  {requirements && (
                    <div className="source-card" style={{ marginTop: '20px', background: 'rgba(16, 185, 129, 0.1)' }}>
                      <div style={{ fontSize: '14px', color: '#10b981', fontWeight: 500 }}>✓ 分析完成，请在右侧查看结果</div>
                    </div>
                  )}
                </section>
              )}

              {/* Step3: 生成目录 */}
              {activeStep === 3 && (
                <section className="kb-upload-section">
                  <h4>📑 生成申报书目录</h4>
                  <div className="sidebar-hint" style={{ marginBottom: '20px' }}>
                    根据申报要求，AI 将自动生成申报书目录结构。
                  </div>

                  <button
                    onClick={handleGenerateDirectory}
                    disabled={generatingDirectory || !requirements}
                    className="kb-create-form"
                    style={{ width: 'auto', marginBottom: 0, opacity: generatingDirectory ? 0.6 : 1 }}
                  >
                    {generatingDirectory ? '生成中...' : '📑 生成目录'}
                  </button>

                  {directory.length > 0 && (
                    <div className="source-card" style={{ marginTop: '20px', background: 'rgba(16, 185, 129, 0.1)' }}>
                      <div style={{ fontSize: '14px', color: '#10b981', fontWeight: 500 }}>
                        ✓ 目录生成完成，共 {directory.length} 个节点，请在右侧查看
                      </div>
                    </div>
                  )}
                </section>
              )}

              {/* Step4: 自动填充 */}
              {activeStep === 4 && (
                <section className="kb-upload-section">
                  <h4>✍️ 自动填充内容</h4>
                  <div className="sidebar-hint" style={{ marginBottom: '20px' }}>
                    AI 将根据上传的企业信息和技术资料，自动填充申报书各章节内容。
                  </div>

                  <button
                    onClick={handleAutofill}
                    disabled={autoFilling || directory.length === 0}
                    className="kb-create-form"
                    style={{ width: 'auto', marginBottom: 0, opacity: autoFilling ? 0.6 : 1 }}
                  >
                    {autoFilling ? '填充中...' : '✍️ 自动填充'}
                  </button>

                  {Object.keys(sections).length > 0 && (
                    <div className="source-card" style={{ marginTop: '20px', background: 'rgba(16, 185, 129, 0.1)' }}>
                      <div style={{ fontSize: '14px', color: '#10b981', fontWeight: 500 }}>
                        ✓ 自动填充完成，已填充 {Object.keys(sections).length} 个章节
                      </div>
                    </div>
                  )}
                </section>
              )}

              {/* Step5: 生成申报书 */}
              {activeStep === 5 && (
                <section className="kb-upload-section">
                  <h4>🤖 AI 生成申报书</h4>
                  <div className="sidebar-hint" style={{ marginBottom: '20px' }}>
                    AI 将完整生成申报书内容，包括所有未填充的章节。
                  </div>

                  <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                    <button
                      onClick={handleGenerateDocument}
                      disabled={generating || directory.length === 0}
                      className="kb-create-form"
                      style={{ width: 'auto', marginBottom: 0, opacity: generating ? 0.6 : 1 }}
                    >
                      {generating ? '生成中...' : '🤖 AI 生成申报书'}
                    </button>

                    <button
                      onClick={handleExport}
                      disabled={exporting || !docMeta}
                      className="kb-create-form"
                      style={{ 
                        width: 'auto', 
                        marginBottom: 0, 
                        opacity: exporting ? 0.6 : 1,
                        background: 'linear-gradient(135deg, #10b981, #22c55e)',
                      }}
                    >
                      {exporting ? '导出中...' : '📥 导出 DOCX'}
                    </button>
                  </div>

                  {docMeta && (
                    <div className="source-card" style={{ marginTop: '20px', background: 'rgba(16, 185, 129, 0.1)' }}>
                      <div style={{ fontSize: '14px', color: '#10b981', fontWeight: 500, marginBottom: '12px' }}>
                        ✓ 申报书生成完成
                      </div>
                      <div className="kb-doc-meta">
                        <div>Run ID: {docMeta.run_id || 'N/A'}</div>
                        <div>状态：已生成，可导出</div>
                      </div>
                    </div>
                  )}
                </section>
              )}
            </div>
          </>
        ) : (
          <div className="kb-detail" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div className="kb-empty-state">
              <div style={{ fontSize: '64px', marginBottom: '16px', textAlign: 'center' }}>📋</div>
              <div>请在左侧选择或创建项目</div>
            </div>
          </div>
        )}
      </div>

      {/* 右侧：信息面板 */}
      <div className="source-panel-container">
        <div className="source-panel-body">
          {/* Tab 切换 */}
          <div style={{ display: 'flex', borderBottom: '1px solid rgba(148, 163, 184, 0.2)', marginBottom: '16px' }}>
            <button
              onClick={() => setRightPanelTab('requirements')}
              className="link-button"
              style={{
                flex: 1,
                padding: '12px',
                ...(rightPanelTab === 'requirements' ? {
                  background: 'rgba(79, 70, 229, 0.2)',
                  borderBottom: '2px solid rgba(79, 70, 229, 0.8)',
                  color: '#e5e7eb',
                } : {}),
              }}
            >
              申报要求
            </button>
            <button
              onClick={() => setRightPanelTab('directory')}
              className="link-button"
              style={{
                flex: 1,
                padding: '12px',
                ...(rightPanelTab === 'directory' ? {
                  background: 'rgba(79, 70, 229, 0.2)',
                  borderBottom: '2px solid rgba(79, 70, 229, 0.8)',
                  color: '#e5e7eb',
                } : {}),
              }}
            >
              目录
            </button>
            <button
              onClick={() => setRightPanelTab('section')}
              className="link-button"
              style={{
                flex: 1,
                padding: '12px',
                ...(rightPanelTab === 'section' ? {
                  background: 'rgba(79, 70, 229, 0.2)',
                  borderBottom: '2px solid rgba(79, 70, 229, 0.8)',
                  color: '#e5e7eb',
                } : {}),
              }}
            >
              章节预览
            </button>
          </div>

          {/* Tab 内容 */}
          <div>
          {/* 申报要求 */}
          {rightPanelTab === 'requirements' && (
            <div>
              {requirements ? (
                <>
                  {requirements.data_json?.eligibility_conditions && requirements.data_json.eligibility_conditions.length > 0 && (
                    <div style={{ marginBottom: '20px' }}>
                      <div className="source-card-title" style={{ color: '#34d399', marginBottom: '8px' }}>申报条件</div>
                      {requirements.data_json.eligibility_conditions.map((cond, idx) => (
                        <div key={idx} className="source-card" style={{ marginBottom: '8px' }}>
                          <div className="source-card-title">
                            {cond.category || '一般条件'}
                          </div>
                          <div className="source-card-snippet">{cond.condition}</div>
                        </div>
                      ))}
                    </div>
                  )}

                  {requirements.data_json?.materials_required && requirements.data_json.materials_required.length > 0 && (
                    <div style={{ marginBottom: '20px' }}>
                      <div className="source-card-title" style={{ color: '#fbbf24', marginBottom: '8px' }}>材料清单</div>
                      {requirements.data_json.materials_required.map((mat, idx) => (
                        <div key={idx} className="source-card" style={{ marginBottom: '6px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <span className="source-card-title">{mat.material}</span>
                            {mat.required && <span style={{ color: '#ef4444', fontSize: '11px' }}>*必填</span>}
                          </div>
                          {mat.format_requirements && (
                            <div className="kb-doc-meta" style={{ marginTop: '2px' }}>格式：{mat.format_requirements}</div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {requirements.data_json?.deadlines && requirements.data_json.deadlines.length > 0 && (
                    <div style={{ marginBottom: '20px' }}>
                      <div className="source-card-title" style={{ color: '#60a5fa', marginBottom: '8px' }}>时间节点</div>
                      {requirements.data_json.deadlines.map((deadline, idx) => (
                        <div key={idx} className="source-card" style={{ marginBottom: '6px' }}>
                          <div className="source-card-title">{deadline.event}</div>
                          <div className="kb-doc-meta">{deadline.date_text}</div>
                          {deadline.notes && <div className="source-card-snippet" style={{ marginTop: '4px' }}>{deadline.notes}</div>}
                        </div>
                      ))}
                    </div>
                  )}

                  {requirements.data_json?.contact_info && requirements.data_json.contact_info.length > 0 && (
                    <div>
                      <div className="source-card-title" style={{ color: '#a78bfa', marginBottom: '8px' }}>咨询方式</div>
                      {requirements.data_json.contact_info.map((contact, idx) => (
                        <div key={idx} className="kb-doc-meta" style={{ marginBottom: '4px' }}>
                          <strong>{contact.contact_type}：</strong>{contact.contact_value}
                        </div>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <div className="source-empty" style={{ textAlign: 'center', paddingTop: '40px' }}>
                  <div style={{ fontSize: '32px', marginBottom: '12px' }}>📄</div>
                  <div>尚未分析申报要求</div>
                  <div style={{ marginTop: '8px' }}>请先上传申报通知并完成分析</div>
                </div>
              )}
            </div>
          )}

          {/* 目录 */}
          {rightPanelTab === 'directory' && (
            <div>
              {directory.length > 0 ? (
                <div style={{ fontSize: '13px' }}>{renderDirectoryTree()}</div>
              ) : (
                <div className="source-empty" style={{ textAlign: 'center', paddingTop: '40px' }}>
                  <div style={{ fontSize: '32px', marginBottom: '12px' }}>📑</div>
                  <div>尚未生成目录</div>
                  <div style={{ marginTop: '8px' }}>请先完成申报要求分析</div>
                </div>
              )}
            </div>
          )}

          {/* 章节预览 */}
          {rightPanelTab === 'section' && (
            <div>
              {selectedNodeId && sections[selectedNodeId] ? (
                <div>
                  <div className="source-card" style={{ marginBottom: '12px' }}>
                    <div className="source-card-title" style={{ marginBottom: '6px' }}>
                      {directory.find((n) => n.id === selectedNodeId)?.title}
                    </div>
                    <div className="kb-doc-meta">
                      状态：{sections[selectedNodeId].content_md ? '已填充' : '未填充'}
                    </div>
                  </div>
                  <div className="source-card-snippet" style={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}>
                    {sections[selectedNodeId].content_md || '（无内容）'}
                  </div>
                </div>
              ) : (
                <div className="source-empty" style={{ textAlign: 'center', paddingTop: '40px' }}>
                  <div style={{ fontSize: '32px', marginBottom: '12px' }}>📝</div>
                  <div>请在目录中选择章节</div>
                  <div style={{ marginTop: '8px' }}>点击目录节点查看内容</div>
                </div>
              )}
            </div>
          )}
          </div>
        </div>
      </div>
    </div>
  );
}

