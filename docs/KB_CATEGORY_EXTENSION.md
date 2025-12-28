# 知识库文档类型扩展与自动映射

## 功能概述

为知识库系统新增了6种专业文档类型，并实现了各应用模块上传文档时自动映射到对应知识库类型的功能。

## 新增的知识库类型

### 原有类型
1. `general_doc` - 📄 普通文档
2. `history_case` - 📋 历史案例
3. `reference_rule` - 📘 规章制度
4. `web_snapshot` - 🌐 网页快照
5. `tender_app` - 📋 招投标文档（旧，保留兼容）

### 新增类型
6. `tender_notice` - 📑 **招标文件**
7. `bid_document` - 📝 **投标文件**
8. `format_template` - 📋 **格式模板**
9. `standard_spec` - 📚 **标准规范**
10. `technical_material` - 🔧 **技术资料**
11. `qualification_doc` - 🏆 **资质资料**

## 自动映射功能

### 映射机制

在各应用模块上传文档时，系统会自动将应用内的文档类型映射到知识库的标准分类。

### 映射规则

#### 1. 招投标应用
| 应用内类型 | 知识库类型 | 说明 |
|-----------|-----------|------|
| `tender` | `tender_notice` | 招标文件 |
| `bid` | `bid_document` | 投标文件 |
| `template` | `format_template` | 格式模板 |
| `custom_rule` | `reference_rule` | 自定义规则 |

#### 2. 用户文档管理
| 应用内类型/分类 | 知识库类型 | 说明 |
|----------------|-----------|------|
| 默认 | `technical_material` | 默认为技术资料 |
| 技术资料 | `technical_material` | 技术资料 |
| 资质文件 | `qualification_doc` | 资质资料 |
| 标准规范 | `standard_spec` | 标准规范 |

**特殊处理**：用户文档会根据分类名称智能推断：
- 包含"资质"关键字 → `qualification_doc`
- 包含"技术"关键字 → `technical_material`
- 包含"标准"或"规范"关键字 → `standard_spec`
- 包含"模板"关键字 → `format_template`

#### 3. 申报应用
| 应用内类型 | 知识库类型 | 说明 |
|-----------|-----------|------|
| `declare_notice` | `tender_notice` | 申报通知 |
| `declare_company` | `qualification_doc` | 企业信息/资质 |
| `declare_tech` | `technical_material` | 技术资料 |
| `declare_other` | `general_doc` | 其他文档 |

## 技术实现

### 1. 类型定义更新

**后端** (`backend/app/schemas/types.py`)
```python
KbCategory = Literal[
    "general_doc",
    "history_case", 
    "reference_rule", 
    "web_snapshot", 
    "tender_app",
    "tender_notice",      # 新增
    "bid_document",       # 新增
    "format_template",    # 新增
    "standard_spec",      # 新增
    "technical_material", # 新增
    "qualification_doc"   # 新增
]
```

**前端** (`frontend/src/types/index.ts`)
```typescript
export type DocCategory = 
  | "general_doc"
  | "history_case" 
  | "reference_rule" 
  | "web_snapshot" 
  | "tender_app"
  | "tender_notice"        // 招标文件
  | "bid_document"         // 投标文件
  | "format_template"      // 格式模板
  | "standard_spec"        // 标准规范
  | "technical_material"   // 技术资料
  | "qualification_doc";   // 资质资料
```

### 2. 映射工具函数

创建了统一的映射工具 (`backend/app/utils/doc_type_mapper.py`)：

```python
def map_doc_type_to_kb_category(doc_type: str, context: str = "") -> KbCategory:
    """
    将文档类型映射到知识库分类
    
    Args:
        doc_type: 文档类型（应用内定义）
        context: 上下文信息（可选，用于更精确的映射）
    
    Returns:
        知识库分类
    """
```

### 3. 集成点

#### 招投标服务 (`tender_service.py`)
```python
# 映射文档类型到知识库分类
from app.utils.doc_type_mapper import map_doc_type_to_kb_category
kb_category = map_doc_type_to_kb_category(kind)

ingest_v2_result = await ingest_v2.ingest_asset_v2(
    project_id=project_id,
    asset_id=temp_asset_id,
    file_bytes=b,
    filename=filename,
    doc_type=kb_category,  # 使用映射后的知识库分类
    ...
)
```

#### 用户文档服务 (`user_document_service.py`)
```python
# 根据分类映射文档类型
from app.utils.doc_type_mapper import map_doc_type_to_kb_category

kb_category = "technical_material"  # 默认为技术资料
if category_id:
    category = self.get_category(category_id)
    if category:
        category_name = category.get("category_name", "").lower()
        kb_category = map_doc_type_to_kb_category("tender_user_doc", context=category_name)

ingest_result = await ingest_service.ingest_asset_v2(
    ...
    doc_type=kb_category,  # 使用映射后的知识库分类
)
```

#### 申报服务 (`declare_service.py`)
```python
# doc_type 映射到知识库分类
from app.utils.doc_type_mapper import map_doc_type_to_kb_category

doc_type = doc_type_map.get(kind, "declare_other")
kb_category = map_doc_type_to_kb_category(doc_type)

ingest_result = run_async(ingest_service.ingest_asset_v2(
    ...
    doc_type=kb_category,  # 使用映射后的知识库分类
))
```

### 4. 前端UI更新

更新了知识库管理器的类型标签和颜色显示 (`KnowledgeBaseManager.tsx`)：

```typescript
const categoryLabels: Record<DocCategory, string> = {
  general_doc: "📄 普通文档",
  history_case: "📋 历史案例",
  reference_rule: "📘 规章制度",
  web_snapshot: "🌐 网页快照",
  tender_app: "📋 招投标文档",
  tender_notice: "📑 招标文件",
  bid_document: "📝 投标文件",
  format_template: "📋 格式模板",
  standard_spec: "📚 标准规范",
  technical_material: "🔧 技术资料",
  qualification_doc: "🏆 资质资料"
};
```

### 5. 数据库支持

创建了新的迁移文件 (`032_add_new_kb_categories.sql`)：
- 更新字段注释，说明新增的分类类型
- 创建映射关系说明表 `kb_category_mappings`（可选）
- 记录应用文档类型到知识库分类的映射关系

## 文件清单

### 后端文件
1. `backend/app/schemas/types.py` - 更新类型定义
2. `backend/app/utils/doc_type_mapper.py` - **新增**映射工具函数
3. `backend/app/services/tender_service.py` - 集成映射逻辑
4. `backend/app/services/user_document_service.py` - 集成映射逻辑
5. `backend/app/services/declare_service.py` - 集成映射逻辑
6. `backend/migrations/032_add_new_kb_categories.sql` - **新增**数据库迁移

### 前端文件
1. `frontend/src/types/index.ts` - 更新类型定义
2. `frontend/src/components/KnowledgeBaseManager.tsx` - 更新UI显示

## 使用说明

### 1. 部署

运行数据库迁移：
```bash
cd backend
python migrations/run_migrations.py
```

### 2. 上传文档

在各应用中上传文档时，系统会自动将文档归类到对应的知识库类型：

#### 招投标应用
- 上传招标文件 → 自动分类为"招标文件"
- 上传投标文件 → 自动分类为"投标文件"
- 上传格式模板 → 自动分类为"格式模板"

#### 用户文档管理
- 创建"技术资料"分类并上传 → 自动分类为"技术资料"
- 创建"资质文件"分类并上传 → 自动分类为"资质资料"
- 创建"标准规范"分类并上传 → 自动分类为"标准规范"

#### 申报应用
- 上传申报通知 → 自动分类为"招标文件"
- 上传企业信息 → 自动分类为"资质资料"
- 上传技术资料 → 自动分类为"技术资料"

### 3. 查看知识库

在知识库管理界面，文档会显示对应的类型标签和颜色：
- 📑 招标文件 - 橙色
- 📝 投标文件 - 青色
- 📋 格式模板 - 紫色
- 📚 标准规范 - 青绿色
- 🔧 技术资料 - 绿色
- 🏆 资质资料 - 黄色

## 优势

### 1. 自动化
- ✅ 无需手动选择类型，系统自动识别和映射
- ✅ 减少用户操作步骤，提高效率

### 2. 统一性
- ✅ 统一的知识库分类标准
- ✅ 所有应用共享相同的分类体系
- ✅ 便于跨应用检索和管理

### 3. 智能性
- ✅ 支持根据分类名称智能推断类型
- ✅ 支持上下文感知的映射规则
- ✅ 灵活的映射扩展机制

### 4. 兼容性
- ✅ 保留旧的类型定义，向后兼容
- ✅ 数据库字段使用TEXT类型，无需修改表结构
- ✅ 平滑升级，不影响现有数据

## 扩展建议

### 1. 增加新类型
如需增加新的知识库类型：
1. 在 `backend/app/schemas/types.py` 中添加新的 Literal 值
2. 在 `frontend/src/types/index.ts` 中添加新的类型
3. 在 `doc_type_mapper.py` 中添加映射规则
4. 在 `KnowledgeBaseManager.tsx` 中添加显示标签和颜色

### 2. 自定义映射规则
可以在 `doc_type_mapper.py` 中自定义更复杂的映射逻辑：
- 基于文件名模式匹配
- 基于文件内容分析
- 基于用户标签
- 基于AI分类

### 3. 映射规则管理
可以考虑将映射规则存储到数据库：
- 支持运行时动态修改
- 支持用户自定义映射
- 支持映射规则版本管理

## 总结

通过知识库类型扩展和自动映射功能，系统能够更精确地组织和管理不同类型的文档，为用户提供更好的文档分类和检索体验。各应用模块上传文档时无需手动选择类型，系统会根据上下文自动识别和映射，大大提高了易用性和效率。

