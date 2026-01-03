# 统一文档生成框架

> 支持招投标和申报书两种场景的AI文档生成系统

## 📋 目录

- [概述](#概述)
- [核心组件](#核心组件)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [策略扩展](#策略扩展)
- [监控和日志](#监控和日志)
- [API文档](#api文档)

---

## 概述

统一文档生成框架是一个可扩展、可配置的AI文档生成系统，提供了从文档检索、Prompt构建、内容生成到质量评估的完整流程。

### 特性

- ✅ **统一接口**：Tender和Declare共享核心组件
- ✅ **智能检索**：基于语义的文档检索和相关性评估
- ✅ **模板化Prompt**：支持Markdown模板和变量替换
- ✅ **质量评估**：自动评估生成内容的完整度、证据充分度和格式规范度
- ✅ **可扩展**：支持自定义检索和生成策略
- ✅ **可配置**：YAML配置文件管理所有参数
- ✅ **可监控**：性能追踪和审计日志

---

## 核心组件

### 1. DocumentRetriever（文档检索器）

从知识库检索相关文档片段。

```python
from app.services.generation import DocumentRetriever, RetrievalContext

retriever = DocumentRetriever(pool)
context = RetrievalContext(
    kb_id="kb_123",
    section_title="公司简介",
    section_level=1,
    document_type="tender"
)
result = await retriever.retrieve(context, top_k=5)

print(f"检索到 {len(result.chunks)} 个相关片段")
print(f"质量评分: {result.quality_score:.2f}")
```

### 2. PromptBuilder（Prompt构建器）

从模板构建System和User Prompt。

```python
from app.services.generation import PromptBuilder, PromptContext

builder = PromptBuilder()
context = PromptContext(
    document_type="tender",
    section_title="公司简介",
    section_level=1,
    project_info={"project_name": "XX项目"},
    retrieval_result=result
)
prompt = builder.build(context)

print(f"System Prompt: {prompt.system_prompt}")
print(f"Temperature: {prompt.temperature}")
```

### 3. ContentGenerator（内容生成器）

调用LLM生成内容。

```python
from app.services.generation import ContentGenerator, GenerationContext

generator = ContentGenerator(llm_orchestrator)
gen_context = GenerationContext(
    document_type="tender",
    section_title="公司简介",
    prompt=prompt
)
result = await generator.generate(gen_context)

print(f"生成内容: {result.content}")
print(f"置信度: {result.confidence}")
print(f"字数: {result.word_count}")
```

### 4. QualityAssessor（质量评估器）

评估生成内容的质量。

```python
from app.services.generation import QualityAssessor

assessor = QualityAssessor()
metrics = assessor.assess(
    generation_result=result,
    retrieval_result=retrieval_result,
    section_level=1
)

print(f"总体评分: {metrics.overall_score:.2f}")
print(f"等级: {metrics.get_grade()}")
print(f"问题: {metrics.issues}")
```

---

## 快速开始

### 完整生成流程示例

```python
from app.services.generation import (
    DocumentRetriever,
    RetrievalContext,
    PromptBuilder,
    PromptContext,
    ContentGenerator,
    GenerationContext,
    QualityAssessor
)
from app.services.ingest_v2_service import IngestV2Service
from app.db.pool import get_pool

async def generate_section(project_id: str, section_title: str):
    """完整的章节生成流程"""
    
    # 1. 检索相关文档
    retriever = DocumentRetriever(get_pool())
    retrieval_context = RetrievalContext(
        kb_id="kb_123",
        section_title=section_title,
        section_level=1,
        document_type="tender",
        project_info={"project_name": "XX项目"}
    )
    retrieval_result = await retriever.retrieve(retrieval_context, top_k=5)
    
    # 2. 构建Prompt
    prompt_builder = PromptBuilder()
    prompt_context = PromptContext(
        document_type="tender",
        section_title=section_title,
        section_level=1,
        project_info={"project_name": "XX项目"},
        retrieval_result=retrieval_result
    )
    prompt = prompt_builder.build(prompt_context)
    
    # 3. 生成内容
    generator = ContentGenerator(llm_orchestrator)
    gen_context = GenerationContext(
        document_type="tender",
        section_title=section_title,
        prompt=prompt
    )
    generation_result = await generator.generate(gen_context)
    
    # 4. 评估质量
    assessor = QualityAssessor()
    quality_metrics = assessor.assess(
        generation_result,
        retrieval_result,
        1
    )
    
    return {
        "content": generation_result.content,
        "evidence_chunk_ids": retrieval_result.get_chunk_ids(),
        "quality_metrics": quality_metrics.to_dict()
    }
```

---

## 配置说明

### 配置文件位置

配置文件会按以下顺序查找：

1. 环境变量 `GENERATION_CONFIG_PATH` 指定的路径
2. `backend/app/services/generation/config.yaml`
3. 项目根目录下的 `generation_config.yaml`

### 配置文件结构

```yaml
# 全局配置
global:
  default_temperature: 0.7
  default_max_tokens: 2000
  default_concurrency: 5

# 检索配置
retrieval:
  default_top_k: 5
  quality_threshold: 0.4

# Tender配置
tender:
  templates:
    system: "tender_system.md"
    user: "tender_user.md"
  llm:
    temperature: 0.7
    max_tokens: 2000
  min_words:
    level_1: 800
    level_2: 500

# Declare配置
declare:
  templates:
    system: "declare_system.md"
    user: "declare_user.md"
  llm:
    temperature: 0.6
    max_tokens: 2500
```

### 使用配置

```python
from app.services.generation.config_loader import get_config

config = get_config()

# 获取配置值
temperature = config.get("tender.llm.temperature", 0.7)
top_k = config.get("retrieval.default_top_k", 5)

# 获取特定模块配置
tender_config = config.get_tender_config()
declare_config = config.get_declare_config()

# 重新加载配置
config.reload()
```

---

## 策略扩展

### 自定义检索策略

```python
from app.services.generation.strategies import RetrievalStrategy, get_strategy_registry

class CustomRetrievalStrategy(RetrievalStrategy):
    """自定义检索策略"""
    
    def build_query(self, section_title: str, context: Dict[str, Any]) -> str:
        # 自定义query构建逻辑
        return f"Custom: {section_title}"
    
    def get_doc_type_filters(self, document_type: str) -> List[str]:
        # 自定义文档类型过滤
        return ["custom_doc_type"]

# 注册策略
registry = get_strategy_registry()
registry.register_retrieval_strategy("custom", CustomRetrievalStrategy())

# 使用策略
strategy = registry.get_retrieval_strategy("custom")
query = strategy.build_query("公司简介", {"document_type": "tender"})
```

### 自定义生成策略

```python
from app.services.generation.strategies import GenerationStrategy, get_strategy_registry

class CustomGenerationStrategy(GenerationStrategy):
    """自定义生成策略"""
    
    def get_temperature(self, document_type: str, section_level: int) -> float:
        # 根据章节层级动态调整温度
        return 0.5 + (section_level * 0.1)
    
    def get_max_tokens(self, document_type: str, section_level: int) -> int:
        return 2000

# 注册策略
registry = get_strategy_registry()
registry.register_generation_strategy("custom", CustomGenerationStrategy())
```

---

## 监控和日志

### 性能监控

```python
from app.services.generation.monitoring import get_performance_monitor

monitor = get_performance_monitor()

# 追踪操作性能
with monitor.track("document_generation", section="公司简介"):
    result = await generate_content()

# 获取性能指标
metrics = monitor.get_metrics("document_generation")
summary = monitor.get_summary()

print(f"平均耗时: {summary['document_generation']['avg_duration_ms']}ms")
```

### 审计日志

```python
from app.services.generation.monitoring import get_audit_logger

audit = get_audit_logger()

# 记录审计日志
audit.log(
    operation="generate_section",
    resource_type="section",
    resource_id="section_123",
    action="generate",
    status="success",
    user_id="user_456",
    section_title="公司简介",
    word_count=1200
)

# 查询审计日志
logs = audit.get_logs(
    resource_type="section",
    action="generate"
)
```

---

## API文档

### DocumentRetriever

#### 方法

- `retrieve(context, top_k=5, strategy="auto")` - 检索相关文档

#### RetrievalContext

```python
@dataclass
class RetrievalContext:
    kb_id: str                           # 知识库ID
    section_title: str                   # 章节标题
    section_level: int                   # 章节层级
    document_type: str                   # 'tender' or 'declare'
    project_info: Optional[Dict] = None  # 项目信息
    requirements: Optional[Dict] = None  # 申报要求
```

#### RetrievalResult

```python
@dataclass
class RetrievalResult:
    chunks: List[Dict]           # 检索到的文档片段
    quality_score: float         # 质量评分 (0-1)
    has_relevant: bool           # 是否有相关内容
    retrieval_strategy: str      # 使用的检索策略
```

### PromptBuilder

#### 方法

- `build(context)` - 构建Prompt

#### PromptContext

```python
@dataclass
class PromptContext:
    document_type: str                      # 'tender' or 'declare'
    section_title: str                      # 章节标题
    section_level: int                      # 章节层级
    project_info: Dict                      # 项目信息
    requirements: Optional[Dict] = None     # 申报要求
    retrieval_result: Optional[RetrievalResult] = None  # 检索结果
```

#### PromptOutput

```python
@dataclass
class PromptOutput:
    system_prompt: str     # System Prompt
    user_prompt: str       # User Prompt
    temperature: float     # 温度参数
    max_tokens: int        # 最大token数
```

### ContentGenerator

#### 方法

- `generate(context)` - 生成内容

#### GenerationResult

```python
@dataclass
class GenerationResult:
    content: str              # 生成的内容
    raw_content: str          # 原始LLM输出
    confidence: str           # 'HIGH', 'MEDIUM', 'LOW'
    word_count: int           # 字数
    has_placeholder: bool     # 是否包含待补充标记
    format_type: str          # 'html' or 'markdown'
```

### QualityAssessor

#### 方法

- `assess(generation_result, retrieval_result, section_level)` - 评估质量

#### QualityMetrics

```python
@dataclass
class QualityMetrics:
    overall_score: float        # 总体评分 (0-1)
    completeness_score: float   # 完整度
    evidence_score: float       # 证据充分度
    format_score: float         # 格式规范度
    word_count: int             # 字数
    has_placeholder: bool       # 是否有待补充
    confidence_level: str       # 置信度等级
    evidence_count: int         # 证据数量
    issues: List[str]           # 问题列表
```

---

## 模板语法

### 变量替换

```markdown
章节标题：{{section_title}}
层级：{{section_level}}
```

### 条件渲染

```markdown
{{#if has_materials}}
# 有资料时显示的内容
{{else}}
# 无资料时显示的内容
{{/if}}
```

---

## 故障排查

### 1. 模板加载失败

**现象**：日志显示 "Failed to render template, using fallback"

**原因**：模板文件不存在或格式错误

**解决**：
- 检查 `prompts/` 目录下是否有对应的模板文件
- 检查模板文件格式是否正确
- 系统会自动降级为硬编码Prompt

### 2. 检索质量低

**现象**：`quality_score` 低于 0.4

**原因**：知识库中缺少相关资料

**解决**：
- 上传更多相关企业/用户资料
- 调整检索策略
- 检查文档分类是否正确

### 3. 生成内容质量差

**现象**：`overall_score` 低于 0.6

**原因**：检索资料不足或LLM参数不合适

**解决**：
- 检查 `evidence_count` 是否足够
- 调整 `temperature` 参数
- 使用不同的生成策略

---

## 最佳实践

1. **充分的资料准备**：确保知识库中有足够的企业/用户资料
2. **合理的参数配置**：根据文档类型调整温度和token数
3. **监控和优化**：定期查看性能指标和质量评分
4. **策略选择**：根据具体场景选择合适的检索和生成策略
5. **模板维护**：定期更新Prompt模板以提高生成质量

---

## 许可证

内部使用

---

## 联系方式

如有问题，请联系开发团队。

