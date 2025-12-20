/**
 * 申报书功能 Mock API
 * 本阶段不对接后端，所有数据均为前端 Mock
 * TODO: 后续替换为真实 API 调用
 */

// ==================== Mock 数据定义 ====================

export interface DeclareProject {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  status: 'draft' | 'processing' | 'completed';
}

export interface DeclareAsset {
  id: string;
  project_id: string;
  kind: 'notice' | 'company' | 'tech';
  filename: string;
  size_bytes: number;
  uploaded_at: string;
}

export interface DeclareRequirement {
  basic_info: {
    project_name: string;
    department: string;
    deadline: string;
    contact: string;
  };
  conditions: Array<{
    id: string;
    category: string;
    content: string;
    mandatory: boolean;
  }>;
  material_list: Array<{
    id: string;
    name: string;
    required: boolean;
    format?: string;
    note?: string;
  }>;
}

export interface DirectoryNode {
  id: string;
  parent_id: string | null;
  level: number;
  order_no: number;
  numbering: string;
  title: string;
  required: boolean;
}

export interface SectionContent {
  node_id: string;
  content_md: string;
  word_count: number;
  filled: boolean;
}

export interface DocumentMeta {
  total_chapters: number;
  total_words: number;
  completion_rate: number;
  generated_at: string;
}

// ==================== Mock 数据 ====================

const mockProjects: DeclareProject[] = [
  {
    id: 'dp-001',
    name: '2024年科技创新项目申报',
    description: '国家级科技创新项目',
    created_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
    status: 'completed',
  },
  {
    id: 'dp-002',
    name: '数字化转型专项资金申报',
    description: '省级数字化转型扶持项目',
    created_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    status: 'processing',
  },
];

const mockRequirements: DeclareRequirement = {
  basic_info: {
    project_name: '2025年度人工智能技术创新项目',
    department: '科技创新部',
    deadline: '2025-01-31 17:00',
    contact: '张经理 (010-12345678)',
  },
  conditions: [
    {
      id: 'c1',
      category: '企业资质',
      content: '申报单位须为注册满2年的高新技术企业',
      mandatory: true,
    },
    {
      id: 'c2',
      category: '技术要求',
      content: '项目需采用自主研发的核心技术，拥有相关专利或软著',
      mandatory: true,
    },
    {
      id: 'c3',
      category: '财务要求',
      content: '近三年研发投入占比不低于营收的5%',
      mandatory: true,
    },
    {
      id: 'c4',
      category: '团队要求',
      content: '项目负责人需具备相关领域工作经验5年以上',
      mandatory: false,
    },
  ],
  material_list: [
    { id: 'm1', name: '企业营业执照副本', required: true, format: 'PDF' },
    { id: 'm2', name: '高新技术企业证书', required: true, format: 'PDF' },
    { id: 'm3', name: '项目可行性研究报告', required: true, format: 'DOCX/PDF' },
    { id: 'm4', name: '企业近三年财务审计报告', required: true, format: 'PDF' },
    { id: 'm5', name: '专利证书或软著登记证书', required: true, format: 'PDF' },
    { id: 'm6', name: '项目团队成员简历', required: true, format: 'DOCX/PDF' },
    { id: 'm7', name: '项目预算明细表', required: true, format: 'XLSX/PDF' },
    { id: 'm8', name: '项目实施方案', required: false, format: 'DOCX', note: '建议提供' },
  ],
};

const mockDirectoryNodes: DirectoryNode[] = [
  { id: 'n1', parent_id: null, level: 1, order_no: 1, numbering: '一', title: '项目基本情况', required: true },
  { id: 'n1-1', parent_id: 'n1', level: 2, order_no: 1, numbering: '（一）', title: '企业基本信息', required: true },
  { id: 'n1-2', parent_id: 'n1', level: 2, order_no: 2, numbering: '（二）', title: '项目概述', required: true },
  { id: 'n1-3', parent_id: 'n1', level: 2, order_no: 3, numbering: '（三）', title: '申报理由', required: true },
  
  { id: 'n2', parent_id: null, level: 1, order_no: 2, numbering: '二', title: '技术创新与研发能力', required: true },
  { id: 'n2-1', parent_id: 'n2', level: 2, order_no: 1, numbering: '（一）', title: '核心技术说明', required: true },
  { id: 'n2-2', parent_id: 'n2', level: 2, order_no: 2, numbering: '（二）', title: '技术创新点', required: true },
  { id: 'n2-3', parent_id: 'n2', level: 2, order_no: 3, numbering: '（三）', title: '知识产权情况', required: true },
  { id: 'n2-4', parent_id: 'n2', level: 2, order_no: 4, numbering: '（四）', title: '研发团队介绍', required: true },
  
  { id: 'n3', parent_id: null, level: 1, order_no: 3, numbering: '三', title: '项目实施方案', required: true },
  { id: 'n3-1', parent_id: 'n3', level: 2, order_no: 1, numbering: '（一）', title: '实施目标', required: true },
  { id: 'n3-2', parent_id: 'n3', level: 2, order_no: 2, numbering: '（二）', title: '实施内容', required: true },
  { id: 'n3-3', parent_id: 'n3', level: 2, order_no: 3, numbering: '（三）', title: '实施进度安排', required: true },
  { id: 'n3-4', parent_id: 'n3', level: 2, order_no: 4, numbering: '（四）', title: '预期成果', required: true },
  
  { id: 'n4', parent_id: null, level: 1, order_no: 4, numbering: '四', title: '项目预算与经费使用', required: true },
  { id: 'n4-1', parent_id: 'n4', level: 2, order_no: 1, numbering: '（一）', title: '资金需求总额', required: true },
  { id: 'n4-2', parent_id: 'n4', level: 2, order_no: 2, numbering: '（二）', title: '预算明细', required: true },
  { id: 'n4-3', parent_id: 'n4', level: 2, order_no: 3, numbering: '（三）', title: '资金使用计划', required: false },
  
  { id: 'n5', parent_id: null, level: 1, order_no: 5, numbering: '五', title: '风险分析与应对措施', required: false },
  { id: 'n5-1', parent_id: 'n5', level: 2, order_no: 1, numbering: '（一）', title: '技术风险', required: false },
  { id: 'n5-2', parent_id: 'n5', level: 2, order_no: 2, numbering: '（二）', title: '市场风险', required: false },
  { id: 'n5-3', parent_id: 'n5', level: 2, order_no: 3, numbering: '（三）', title: '风险应对策略', required: false },
];

const mockSections: Record<string, SectionContent> = {
  'n1-1': {
    node_id: 'n1-1',
    content_md: `## 企业基本信息

**企业名称**：亿林科技有限公司

**统一社会信用代码**：91110000XXXXXXXXXXXX

**企业类型**：有限责任公司

**注册资本**：5000万元人民币

**成立时间**：2018年3月

**注册地址**：北京市海淀区中关村科技园XX路XX号

**法定代表人**：李明

**企业规模**：现有员工150人，其中研发人员80人，占比53.3%

**高新技术企业认定**：2020年首次认定，2023年重新认定通过

**主营业务**：人工智能算法研发、企业数字化解决方案、智能办公系统开发`,
    word_count: 186,
    filled: true,
  },
  'n1-2': {
    node_id: 'n1-2',
    content_md: `## 项目概述

本项目旨在基于大语言模型技术，研发面向企业办公场景的智能问答与文档处理系统。项目核心是构建领域知识增强的AI助手，能够理解企业内部文档、自动生成各类业务文档、辅助决策分析。

**项目名称**：企业级智能办公助手系统

**项目周期**：2025年1月-2026年12月（24个月）

**项目总投资**：800万元

**技术路线**：采用RAG（检索增强生成）架构，结合向量数据库、知识图谱等技术，实现高精度的领域知识问答。

**应用场景**：
- 招投标文档智能生成
- 企业知识库智能检索
- 会议纪要自动生成
- 合规审查辅助分析`,
    word_count: 234,
    filled: true,
  },
  'n2-1': {
    node_id: 'n2-1',
    content_md: `## 核心技术说明

本项目的核心技术包括：

### 1. 领域知识增强技术
通过向量化技术将企业文档转化为高维向量表示，建立企业专属知识库。采用自研的混合检索算法，结合语义检索和关键词检索，确保知识召回的准确性。

### 2. 上下文理解与生成技术
基于Transformer架构的大语言模型，通过Few-shot Learning和Prompt Engineering技术，使模型能够理解复杂业务场景，生成符合企业规范的专业文档。

### 3. 多模态文档解析技术
支持PDF、Word、Excel等多种格式文档的智能解析，能够提取表格、图片、结构化数据，实现跨格式知识融合。

### 4. 实时流式输出技术
采用流式传输协议，实现AI生成内容的实时展示，提升用户体验。同时支持生成过程的中断与恢复。`,
    word_count: 312,
    filled: true,
  },
};

// ==================== Mock API 方法 ====================

/**
 * 模拟网络延迟
 */
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * 获取项目列表
 */
export async function getProjects(): Promise<DeclareProject[]> {
  await delay(300);
  return [...mockProjects];
}

/**
 * 创建新项目
 */
export async function createProject(name: string, description?: string): Promise<DeclareProject> {
  await delay(500);
  const newProject: DeclareProject = {
    id: `dp-${Date.now()}`,
    name,
    description,
    created_at: new Date().toISOString(),
    status: 'draft',
  };
  mockProjects.unshift(newProject);
  return newProject;
}

/**
 * 上传文件（申报通知/企业信息/技术资料）
 * TODO: 后续对接真实上传接口
 */
export async function uploadAssets(
  projectId: string,
  kind: 'notice' | 'company' | 'tech',
  files: File[]
): Promise<DeclareAsset[]> {
  await delay(1500); // 模拟上传耗时
  
  const assets: DeclareAsset[] = files.map((file) => ({
    id: `asset-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
    project_id: projectId,
    kind,
    filename: file.name,
    size_bytes: file.size,
    uploaded_at: new Date().toISOString(),
  }));
  
  return assets;
}

/**
 * 分析申报通知，提取申报要求
 * TODO: 后续对接真实 API /api/declare/extract-requirements
 */
export async function extractRequirements(projectId: string): Promise<DeclareRequirement> {
  await delay(2000); // 模拟 AI 分析耗时
  return { ...mockRequirements };
}

/**
 * 生成申报书目录
 * TODO: 后续对接真实 API /api/declare/generate-directory
 */
export async function generateDirectory(projectId: string): Promise<DirectoryNode[]> {
  await delay(1800);
  return [...mockDirectoryNodes];
}

/**
 * 自动填充章节内容（基于企业信息和技术资料）
 * TODO: 后续对接真实 API /api/declare/autofill-sections
 */
export async function autofillSections(projectId: string): Promise<Record<string, SectionContent>> {
  await delay(3000); // 模拟批量填充耗时
  return { ...mockSections };
}

/**
 * AI 生成申报书（完整文档）
 * TODO: 后续对接真实 API /api/declare/generate-document
 */
export async function generateDocument(projectId: string): Promise<DocumentMeta> {
  await delay(4000); // 模拟 AI 大规模生成耗时
  
  const meta: DocumentMeta = {
    total_chapters: mockDirectoryNodes.filter(n => n.level === 1).length,
    total_words: Object.values(mockSections).reduce((sum, s) => sum + s.word_count, 0) + 3500,
    completion_rate: 0.95,
    generated_at: new Date().toISOString(),
  };
  
  // 生成更多章节内容（模拟）
  const additionalSections: Record<string, SectionContent> = {};
  mockDirectoryNodes.forEach((node) => {
    if (!mockSections[node.id]) {
      additionalSections[node.id] = {
        node_id: node.id,
        content_md: `## ${node.title}\n\n（AI 已自动生成内容，此处为示例）\n\n本章节内容已根据上传的企业信息和技术资料自动生成。内容包括：...\n\n详细信息请参考附件材料。`,
        word_count: 80 + Math.floor(Math.random() * 200),
        filled: true,
      };
    }
  });
  
  Object.assign(mockSections, additionalSections);
  
  return meta;
}

/**
 * 导出 DOCX 文档
 * TODO: 后续对接真实 API /api/declare/export-docx
 */
export async function exportDocx(projectId: string): Promise<Blob> {
  await delay(1000);
  
  // 创建一个假的 Blob（实际应该从后端下载）
  const fakeContent = `申报书文档内容（Mock）\n项目ID: ${projectId}\n生成时间: ${new Date().toLocaleString()}`;
  const blob = new Blob([fakeContent], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
  
  return blob;
}

/**
 * 获取章节内容
 */
export async function getSectionContent(nodeId: string): Promise<SectionContent | null> {
  await delay(200);
  return mockSections[nodeId] || null;
}

