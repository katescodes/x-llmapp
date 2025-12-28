# 用户文档管理功能

## 功能概述

为招投标系统新增用户文档管理功能，允许用户上传和管理技术资料、资质文件等文档，用于自动生成标书时系统自动分析并加入标书使用。

## 功能特性

### 1. 文档分类管理
- **创建分类**：支持创建自定义文档分类（如：技术资料、资质文件、企业介绍等）
- **查看分类列表**：显示所有分类及其文档数量
- **更新分类**：修改分类名称、描述和显示顺序
- **删除分类**：删除不需要的分类（文档会被移至"未分类"）

### 2. 文档上传与管理
- **上传文档**：
  - 支持多种文件类型：PDF、Word、Excel、PPT、图片（JPG、PNG等）、文本文件等
  - 文件自动存储到项目目录
  - 文档自动入库到知识库，支持RAG检索
- **文档信息**：
  - 文档名称、描述
  - 文件类型、大小
  - 文档标签（支持多个标签，逗号分隔）
  - 所属分类
  - 上传时间、上传者
- **查看文档列表**：
  - 按分类筛选
  - 显示文档详细信息
  - 文档卡片展示
- **更新文档**：修改文档名称、分类、描述、标签
- **删除文档**：删除文档及其磁盘文件

### 3. AI文档分析（预留功能）
- **分析文档内容**：使用LLM提取文档摘要、关键信息
- **识别适用场景**：分析文档的适用场景和关键点
- **分析结果展示**：在文档详情中显示AI分析结果

### 4. 标书生成集成
- **自动检索**：生成标书时，系统可以从用户文档中检索相关内容
- **内容引用**：根据标书需求自动引用合适的用户文档内容
- **证据追溯**：保留文档来源信息，支持证据回溯

## 文件结构

### 后端文件

```
backend/
├── app/
│   ├── migrations/
│   │   └── 031_create_user_documents_table.sql  # 数据库迁移文件
│   ├── routers/
│   │   └── user_documents.py                     # API路由
│   ├── schemas/
│   │   └── user_documents.py                     # Schema定义
│   ├── services/
│   │   └── user_document_service.py              # 服务层
│   └── main.py                                   # 注册路由
```

### 前端文件

```
frontend/
└── src/
    └── components/
        ├── UserDocumentsPage.tsx                 # 用户文档管理页面
        └── TenderWorkspace.tsx                   # 招投标工作台（已更新）
```

### 数据库表

使用新增的两张表：

1. **tender_user_doc_categories** - 文档分类表
   - id: 分类ID
   - project_id: 项目ID
   - category_name: 分类名称
   - category_desc: 分类描述
   - display_order: 显示顺序
   - created_at, updated_at

2. **tender_user_documents** - 用户文档表
   - id: 文档ID
   - project_id: 项目ID
   - category_id: 分类ID
   - doc_name: 文档名称
   - filename: 原始文件名
   - file_type: 文件类型
   - mime_type: MIME类型
   - file_size: 文件大小
   - storage_path: 存储路径
   - kb_doc_id: 知识库文档ID（用于检索）
   - doc_tags: 文档标签数组
   - description: 文档描述
   - is_analyzed: 是否已分析
   - analysis_json: 分析结果
   - owner_id: 上传者ID
   - created_at, updated_at

## API接口

### 分类管理

- `POST /user-documents/categories` - 创建分类
- `GET /user-documents/categories?project_id={id}` - 列出分类
- `GET /user-documents/categories/{id}` - 获取分类详情
- `PATCH /user-documents/categories/{id}` - 更新分类
- `DELETE /user-documents/categories/{id}` - 删除分类

### 文档管理

- `POST /user-documents/documents` - 上传文档（multipart/form-data）
- `GET /user-documents/documents?project_id={id}&category_id={id}` - 列出文档
- `GET /user-documents/documents/{id}` - 获取文档详情
- `PATCH /user-documents/documents/{id}` - 更新文档信息
- `DELETE /user-documents/documents/{id}` - 删除文档
- `POST /user-documents/documents/{id}/analyze` - AI分析文档

## 使用说明

### 1. 访问入口

在招投标工作台左侧边栏，"自定义规则"按钮下方，点击"📁 用户文档"按钮进入用户文档管理页面。

**注意**：需要先选择项目，才能访问用户文档管理功能。

### 2. 创建分类

1. 点击右上角"+ 新建分类"按钮
2. 输入分类名称（必填）
3. 输入分类描述（可选）
4. 点击"创建分类"

### 3. 上传文档

1. 点击右上角"+ 上传文档"按钮
2. 填写文档信息：
   - 文档名称（必填）
   - 选择分类（可选，默认为"未分类"）
   - 文档描述（可选）
   - 文档标签（可选，逗号分隔）
3. 选择文件
4. 点击"上传文档"

支持的文件格式：
- 文档：PDF、Word（.doc/.docx）、Excel（.xls/.xlsx）、PPT（.ppt/.pptx）
- 图片：JPG、PNG、GIF、BMP、WebP
- 文本：TXT、Markdown

### 4. 管理文档

- **查看文档列表**：左侧选择分类，中间显示文档列表
- **查看文档详情**：点击文档卡片，右侧显示详细信息
- **分析文档**：点击文档卡片上的"🔍 分析"按钮，使用AI分析文档
- **删除文档**：点击文档卡片上的"🗑️"按钮

### 5. 管理分类

- **删除分类**：点击分类卡片上的"🗑️"按钮
- 删除分类后，该分类下的文档会被移至"未分类"

## 技术实现

### 后端实现

1. **文件存储**：
   - 文件保存在 `./data/tender/user_documents/{project_id}/` 目录
   - 使用UUID作为文件名前缀，保证唯一性

2. **知识库集成**：
   - 使用 `IngestV2Service` 将文档入库
   - 文档类型为 `tender_user_doc`
   - 返回的 `doc_version_id` 存储为 `kb_doc_id`

3. **AI分析**（预留）：
   - 使用 LLM 分析文档内容
   - 提取摘要、关键点、适用场景
   - 结果存储在 `analysis_json` 字段

### 前端实现

1. **三栏布局**：
   - 左侧：分类列表
   - 中间：文档列表
   - 右侧：文档详情

2. **文件上传**：
   - 使用 `multipart/form-data` 格式
   - 显示文件选择和上传进度

3. **响应式设计**：
   - 适配不同屏幕尺寸
   - 使用深色主题，与系统风格一致

## 后续扩展

### 1. AI分析功能增强
- 实现文档内容的深度分析
- 识别文档中的关键信息（公司资质、技术参数等）
- 建立文档与标书章节的映射关系

### 2. 文档检索优化
- 在生成标书时，自动从用户文档中检索相关内容
- 支持按标签、类型、关键词检索
- 智能推荐合适的文档

### 3. 版本管理
- 支持文档版本控制
- 保留文档历史版本
- 版本对比功能

### 4. 协作功能
- 文档共享和权限控制
- 文档评论和批注
- 团队协作编辑

## 数据库迁移

在部署前需要运行数据库迁移：

```bash
cd backend
python migrations/run_migrations.py
```

迁移文件会自动创建以下表：
- `tender_user_doc_categories` - 文档分类表
- `tender_user_documents` - 用户文档表

## 注意事项

1. **权限控制**：
   - 当前版本使用基础的身份验证
   - 用户只能访问自己有权限的项目的文档
   - 后续可以增强权限控制（文档级权限）

2. **文件大小限制**：
   - 建议设置合理的文件大小限制（如50MB）
   - 大文件可能影响上传和分析速度

3. **存储空间**：
   - 定期清理已删除项目的文档
   - 考虑使用对象存储服务（如S3、OSS）

4. **性能优化**：
   - 对于大量文档的项目，考虑分页加载
   - 文档列表可以增加搜索和排序功能

## 测试建议

1. **功能测试**：
   - 创建、查看、更新、删除分类
   - 上传、查看、更新、删除文档
   - 测试不同文件类型的上传
   - 测试文件大小限制

2. **集成测试**：
   - 验证文档入库到知识库
   - 验证文档检索功能
   - 验证标书生成时的文档引用

3. **性能测试**：
   - 测试大文件上传
   - 测试大量文档的加载速度
   - 测试并发上传

## 总结

用户文档管理功能为招投标系统提供了强大的文档管理能力，使用户能够方便地管理和使用各类技术资料、资质文件，为自动生成标书提供了丰富的素材来源。通过与知识库的集成，系统能够智能地检索和引用用户文档，大大提高了标书生成的质量和效率。

