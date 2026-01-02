# 通用文档编辑器系统设计方案

## 一、需求分析

### 1.1 核心需求
1. **Word 风格的编辑界面**：左侧目录树，右侧文档内容
2. **目录管理**：可增加、修改、删除节点
3. **内容生成**：支持 AI 生成、重新生成
4. **格式控制**：支持富文本编辑、格式模板
5. **通用性**：可被申报书、招投标等不同模块复用

### 1.2 参考现有实现
- **招投标模块**：已有 `RichTocBox`（只读目录显示）、`DocumentCanvas`（文档画布）
- **申报书模块**：目前使用简单的步骤流程
- **格式模板系统**：已有模板解析、样式应用功能

## 二、系统架构设计

### 2.1 前端组件架构

```
DocumentEditor (通用文档编辑器)
├── DocumentSidebar (左侧目录面板)
│   ├── DirectoryTree (目录树)
│   │   ├── 支持增删改
│   │   ├── 拖拽排序
│   │   └── 节点选择/高亮
│   └── DirectoryToolbar (目录工具栏)
│       ├── 新增节点
│       ├── 生成目录（AI）
│       └── 导入/导出
│
└── DocumentCanvas (右侧内容面板)
    ├── ContentEditor (内容编辑区)
    │   ├── 富文本编辑器
    │   ├── AI 生成按钮
    │   └── 格式控制
    ├── ContentToolbar (内容工具栏)
    │   ├── 生成/重新生成
    │   ├── 格式模板选择
    │   └── 导出预览
    └── ContentPreview (预览区)
        ├── 实时预览
        └── 格式应用
```

### 2.2 后端服务架构

```
通用文档服务 (DocumentService)
├── DirectoryService (目录服务)
│   ├── 目录生成（AI）
│   ├── 目录 CRUD
│   └── 目录树操作
│
├── ContentService (内容服务)
│   ├── 内容生成（AI）
│   ├── 内容 CRUD
│   └── 批量生成
│
├── TemplateService (模板服务)
│   ├── 模板解析
│   ├── 样式提取
│   └── 格式应用
│
└── ExportService (导出服务)
    ├── DOCX 导出
    ├── PDF 导出
    └── 预览生成
```

### 2.3 数据模型设计

#### 通用文档结构
```typescript
// 文档项目（可以是申报书、投标书等）
interface DocumentProject {
  project_id: string;
  app_type: 'declare' | 'tender' | 'custom'; // 应用类型
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
  meta_json?: Record<string, any>;
}

// 目录节点（通用）
interface DocumentNode {
  node_id: string;
  project_id: string;
  parent_id: string | null;
  title: string;
  order_no?: string; // "1", "1.1", "1.1.1"
  level: number;
  sort_index: number;
  is_active: boolean;
  meta_json?: {
    format_template_id?: string; // 格式模板
    page_variant?: string; // 页面变体
    style_hints?: Record<string, any>; // 样式提示
    [key: string]: any;
  };
}

// 节点内容（通用）
interface DocumentContent {
  content_id: string;
  node_id: string;
  content_html: string; // 富文本内容
  content_plain?: string; // 纯文本（用于搜索）
  version: number;
  status: 'draft' | 'generated' | 'reviewed' | 'final';
  generated_by?: 'user' | 'ai';
  created_at: string;
  updated_at: string;
  meta_json?: {
    word_count?: number;
    generation_params?: Record<string, any>;
    [key: string]: any;
  };
}
```

## 三、核心功能实现

### 3.1 通用文档编辑器组件

**位置**：`frontend/src/components/common/DocumentEditor.tsx`

**功能**：
- 左右分栏布局（可调整比例）
- 左侧：目录树 + 操作按钮
- 右侧：内容编辑 + 工具栏
- 支持配置化：不同 app 可定制行为

**核心接口**：
```typescript
interface DocumentEditorProps {
  projectId: string;
  appType: 'declare' | 'tender' | 'custom';
  
  // 目录相关
  directory: DocumentNode[];
  onDirectoryChange: (nodes: DocumentNode[]) => void;
  onGenerateDirectory?: () => Promise<void>;
  
  // 内容相关
  contents: Record<string, DocumentContent>;
  onContentChange: (nodeId: string, content: DocumentContent) => void;
  onGenerateContent?: (nodeId: string) => Promise<void>;
  
  // 模板相关
  formatTemplates?: FormatTemplate[];
  selectedTemplateId?: string;
  onTemplateChange?: (templateId: string) => void;
  
  // 导出相关
  onExport?: (format: 'docx' | 'pdf') => Promise<void>;
  onPreview?: () => Promise<void>;
  
  // 定制化配置
  config?: {
    enableAIGeneration?: boolean;
    enableTemplateFormat?: boolean;
    enableDragSort?: boolean;
    enableExport?: boolean;
    customToolbar?: React.ReactNode;
  };
}
```

### 3.2 通用目录树组件

**位置**：`frontend/src/components/common/DirectoryTree.tsx`

**功能**：
- 树形展示
- 节点增删改
- 拖拽排序（可选）
- 节点选中/高亮
- 支持图标、徽章

**核心接口**：
```typescript
interface DirectoryTreeProps {
  nodes: DocumentNode[];
  selectedNodeId?: string;
  onSelectNode: (nodeId: string) => void;
  onAddNode?: (parentId: string | null) => void;
  onUpdateNode?: (nodeId: string, updates: Partial<DocumentNode>) => void;
  onDeleteNode?: (nodeId: string) => void;
  onReorder?: (nodeId: string, newParentId: string | null, newIndex: number) => void;
  
  config?: {
    enableDrag?: boolean;
    enableEdit?: boolean;
    enableDelete?: boolean;
    showOrderNo?: boolean;
    customNodeRender?: (node: DocumentNode) => React.ReactNode;
  };
}
```

### 3.3 通用内容编辑器组件

**位置**：`frontend/src/components/common/ContentEditor.tsx`

**功能**：
- 富文本编辑（基于 `contenteditable` 或集成第三方库）
- 工具栏：加粗、斜体、列表、对齐等
- AI 生成按钮
- 格式预览

**核心接口**：
```typescript
interface ContentEditorProps {
  nodeId: string;
  nodeTitle: string;
  content: DocumentContent | null;
  onChange: (content: string) => void;
  onGenerate?: () => Promise<void>;
  onRegenerate?: () => Promise<void>;
  
  config?: {
    enableAI?: boolean;
    enableFormatting?: boolean;
    placeholder?: string;
    toolbarItems?: ToolbarItem[];
  };
  
  status?: {
    generating?: boolean;
    saving?: boolean;
  };
}
```

### 3.4 后端通用文档服务

**位置**：`backend/app/services/document/document_service.py`

**功能**：
- 提供统一的文档管理接口
- 支持不同 app_type 的差异化处理
- 集成 AI 生成、模板格式化、导出等功能

**核心接口**：
```python
class DocumentService:
    """通用文档服务"""
    
    def __init__(self, dao: DocumentDAO):
        self.dao = dao
    
    # ========== 目录管理 ==========
    async def generate_directory(
        self,
        project_id: str,
        app_type: str,
        context: Dict[str, Any],
        model_id: Optional[str] = None
    ) -> List[Dict]:
        """生成目录（AI）"""
        pass
    
    async def add_directory_node(
        self,
        project_id: str,
        parent_id: Optional[str],
        title: str,
        **kwargs
    ) -> Dict:
        """添加目录节点"""
        pass
    
    async def update_directory_node(
        self,
        node_id: str,
        updates: Dict[str, Any]
    ) -> Dict:
        """更新目录节点"""
        pass
    
    async def delete_directory_node(
        self,
        node_id: str,
        cascade: bool = False
    ) -> bool:
        """删除目录节点"""
        pass
    
    # ========== 内容管理 ==========
    async def generate_content(
        self,
        node_id: str,
        context: Dict[str, Any],
        model_id: Optional[str] = None
    ) -> Dict:
        """生成节点内容（AI）"""
        pass
    
    async def update_content(
        self,
        node_id: str,
        content_html: str,
        **kwargs
    ) -> Dict:
        """更新节点内容"""
        pass
    
    async def batch_generate_contents(
        self,
        project_id: str,
        node_ids: List[str],
        context: Dict[str, Any],
        model_id: Optional[str] = None
    ) -> Dict[str, Dict]:
        """批量生成内容"""
        pass
    
    # ========== 模板格式化 ==========
    async def apply_format_template(
        self,
        project_id: str,
        template_id: str
    ) -> Dict:
        """应用格式模板"""
        pass
    
    # ========== 导出 ==========
    async def export_document(
        self,
        project_id: str,
        format: str = 'docx',
        template_id: Optional[str] = None
    ) -> str:
        """导出文档"""
        pass
    
    async def preview_document(
        self,
        project_id: str,
        format: str = 'pdf',
        template_id: Optional[str] = None
    ) -> str:
        """生成预览文档"""
        pass
```

### 3.5 数据库表设计

**通用文档表**（可复用）：

```sql
-- 文档项目表
CREATE TABLE IF NOT EXISTS document_projects (
    project_id VARCHAR(50) PRIMARY KEY,
    app_type VARCHAR(50) NOT NULL,  -- 'declare', 'tender', 'custom'
    owner_id VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    meta_json JSONB
);

-- 目录节点表
CREATE TABLE IF NOT EXISTS document_nodes (
    node_id VARCHAR(50) PRIMARY KEY,
    project_id VARCHAR(50) NOT NULL REFERENCES document_projects(project_id) ON DELETE CASCADE,
    parent_id VARCHAR(50) REFERENCES document_nodes(node_id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    order_no VARCHAR(50),
    level INT NOT NULL,
    sort_index INT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    meta_json JSONB
);

-- 节点内容表
CREATE TABLE IF NOT EXISTS document_contents (
    content_id VARCHAR(50) PRIMARY KEY,
    node_id VARCHAR(50) NOT NULL REFERENCES document_nodes(node_id) ON DELETE CASCADE,
    content_html TEXT,
    content_plain TEXT,
    version INT DEFAULT 1,
    status VARCHAR(20) DEFAULT 'draft',  -- 'draft', 'generated', 'reviewed', 'final'
    generated_by VARCHAR(20),  -- 'user', 'ai'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    meta_json JSONB,
    UNIQUE(node_id, version)
);

CREATE INDEX idx_document_nodes_project ON document_nodes(project_id, is_active);
CREATE INDEX idx_document_contents_node ON document_contents(node_id);
```

## 四、实施计划

### Phase 1: 基础组件开发（1-2天）
1. ✅ 创建 `DocumentEditor` 基础布局
2. ✅ 实现 `DirectoryTree` 组件（增删改查）
3. ✅ 实现 `ContentEditor` 组件（富文本编辑）
4. ✅ 集成到申报书模块

### Phase 2: AI 生成功能（1-2天）
1. ✅ 实现目录 AI 生成
2. ✅ 实现内容 AI 生成（单个/批量）
3. ✅ 集成到编辑器组件

### Phase 3: 格式化与导出（1-2天）
1. ✅ 实现格式模板选择与应用
2. ✅ 实现实时预览
3. ✅ 实现 DOCX/PDF 导出

### Phase 4: 通用化与复用（1天）
1. ✅ 抽取通用服务
2. ✅ 配置化接口
3. ✅ 招投标模块复用

## 五、关键技术点

### 5.1 富文本编辑器选择
**方案A：轻量级（推荐）**
- 使用 `contenteditable` + 自定义工具栏
- 优点：轻量、可控
- 缺点：需要自己处理格式

**方案B：第三方库**
- Quill.js / TinyMCE / Draft.js
- 优点：功能完善
- 缺点：体积大、定制复杂

**建议**：先用方案A（参考现有 `SimpleHtmlEditor`），后续按需升级

### 5.2 目录树拖拽排序
- 使用 `react-dnd` 或 `@dnd-kit/core`
- 支持跨层级拖拽
- 实时更新 `sort_index`

### 5.3 AI 生成流程
```
用户点击"生成" 
  → 前端调用 API（传入上下文）
  → 后端调用 LLM
  → 流式返回（WebSocket/SSE）
  → 前端实时显示
  → 完成后保存到数据库
```

### 5.4 格式预览
- 使用 iframe 嵌入 PDF 预览
- 或使用 `@react-pdf-viewer/core` 等库
- 支持实时刷新

## 六、申报书模块改造方案

### 6.1 现状分析
- **当前**：4 步流程（上传 → 提取 → 生成目录 → 生成文档）
- **问题**：
  - 无法编辑目录和内容
  - 无法预览格式效果
  - 生成后无法修改

### 6.2 改造方案
**新流程**：
1. **项目列表页**：显示所有申报书项目
2. **项目详情页**：进入文档编辑器
   - 左侧：目录树（可编辑）
   - 右侧：内容编辑区
3. **工具栏**：
   - 上传文件（随时可上传）
   - 提取要求（AI）
   - 生成目录（AI）
   - 生成内容（AI，单个/批量）
   - 选择格式模板
   - 预览文档
   - 导出 DOCX/PDF

**界面示意**：
```
┌─────────────────────────────────────────────────┐
│  申报书项目：XXX 科技创新项目      [上传] [导出] │
├───────────────┬─────────────────────────────────┤
│               │  工具栏：[生成目录] [格式模板▼]  │
│               ├─────────────────────────────────┤
│  📁 第一章     │                                 │
│    📄 1.1 背景│  📝 第一章 项目概述             │
│    📄 1.2 意义│                                 │
│  📁 第二章     │  [🤖 AI生成内容] [💾 保存]      │
│    📄 2.1 目标│                                 │
│               │  <富文本编辑区>                  │
│  [➕ 新增章节] │                                 │
│               │                                 │
└───────────────┴─────────────────────────────────┘
```

### 6.3 迁移步骤
1. 保留现有数据表（`declare_projects`, `declare_directory`, `declare_sections`）
2. 新增通用组件但使用现有 API
3. 逐步迁移到通用服务
4. 最终统一数据模型

## 七、招投标模块复用

### 7.1 现状
- 已有目录展示（`RichTocBox`）
- 已有文档画布（`DocumentCanvas`）
- 缺少编辑功能

### 7.2 复用方案
- 使用通用 `DocumentEditor` 替换现有展示组件
- 启用编辑功能
- 复用 AI 生成逻辑

## 八、总结

### 优势
✅ **通用性**：一套组件服务多个模块
✅ **可维护性**：集中管理，统一升级
✅ **用户体验**：类 Word 界面，符合直觉
✅ **扩展性**：支持自定义配置，灵活适配

### 风险与应对
⚠️ **兼容性**：现有数据迁移
  → 保留旧表，逐步迁移
  
⚠️ **复杂度**：通用组件过于复杂
  → 配置化设计，按需启用功能
  
⚠️ **性能**：大文档编辑卡顿
  → 虚拟滚动、分页加载

---

**下一步行动**：
1. 评审本设计方案
2. 确定实施优先级
3. 开始 Phase 1 开发

