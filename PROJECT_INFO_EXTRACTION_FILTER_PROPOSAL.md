# 项目信息提取：过滤合同条款

## 📋 需求分析

在**项目基本信息提取**（6阶段提取）时，招标文档中的**合同条款**部分对提取项目概览、资格要求等信息没有帮助，反而可能：
- 消耗 token
- 混淆 LLM（合同条款中的付款方式、违约责任等可能被误提取）
- 降低提取准确性

## 🎯 目标

在项目信息提取时，过滤掉以下类型的内容：
1. **合同条款**（如付款方式、违约责任、争议解决等）
2. **合同格式文本**（合同主体、签字栏等）
3. **发票和付款条款**

## 🔍 实现方案

### 方案 1: 在 TenderContextRetriever 中后处理过滤（推荐）

**优点**：
- ✅ 集中管理，修改一处影响所有调用
- ✅ 不影响其他功能（如招标要求提取）
- ✅ 实现简单，易于调试

**实现位置**：`backend/app/works/tender/tender_context_retriever.py`

```python
class TenderContextRetriever:
    """招标文档上下文检索器（公共组件）"""
    
    # 合同条款相关的关键词（用于过滤）
    CONTRACT_KEYWORDS = [
        "合同条款", "合同格式", "合同主要条款", "合同文本",
        "合同协议书", "合同签订", "合同履行", "合同范本",
        "合同专用条款", "合同通用条款",
        "甲方：", "乙方：", "签字盖章：",
        "（甲方）", "（乙方）", "法定代表人签字",
    ]
    
    def _is_contract_clause_chunk(self, chunk: Any) -> bool:
        """
        判断 chunk 是否属于合同条款部分
        
        Args:
            chunk: 检索到的 chunk
        
        Returns:
            True 如果是合同条款，应该被过滤
        """
        text = chunk.text or ""
        
        # 1. 检查是否包含合同条款关键词
        for keyword in self.CONTRACT_KEYWORDS:
            if keyword in text:
                return True
        
        # 2. 检查 heading_path（如果有）
        if hasattr(chunk, 'meta') and chunk.meta:
            heading_path = chunk.meta.get('heading_path', '')
            if heading_path and (
                '合同' in heading_path or 
                'contract' in heading_path.lower()
            ):
                return True
        
        return False
    
    async def retrieve_tender_context(
        self,
        project_id: str,
        query: Optional[str] = None,
        top_k: int = 150,
        max_context_chunks: int = 100,
        sort_by_position: bool = True,
        filter_contract_clauses: bool = False,  # ✨ 新增参数
    ) -> TenderContextData:
        """
        检索招标文档上下文（统一入口）
        
        Args:
            ...
            filter_contract_clauses: 是否过滤合同条款相关内容（默认False，保持向后兼容）
        """
        # ... 原有的检索逻辑 ...
        
        # 2. 可选：按文档位置排序
        if sort_by_position:
            context_chunks = self._sort_by_position(context_chunks)
            logger.info("TenderContextRetriever: 已按文档位置排序")
        
        # ✨ 2.5. 可选：过滤合同条款
        if filter_contract_clauses:
            original_count = len(context_chunks)
            context_chunks = [
                chunk for chunk in context_chunks 
                if not self._is_contract_clause_chunk(chunk)
            ]
            filtered_count = original_count - len(context_chunks)
            logger.info(
                f"TenderContextRetriever: 过滤了 {filtered_count} 个合同条款相关chunks "
                f"({original_count} → {len(context_chunks)})"
            )
        
        # 3. 截取（token限制）
        used_chunks = context_chunks[:max_context_chunks]
        
        # ... 剩余逻辑 ...
```

### 方案 2: 在提取服务调用时指定过滤

**修改位置**：`backend/app/works/tender/extract_v2_service.py`

```python
# 在 _extract_project_info_staged 方法中

context_retriever = TenderContextRetriever(self.retriever)
context_data = await context_retriever.retrieve_tender_context(
    project_id=project_id,
    top_k=150,
    max_context_chunks=100,
    sort_by_position=True,
    filter_contract_clauses=True,  # ✨ 启用合同条款过滤
)
```

### 方案 3: 使用环境变量控制（灵活性最高）

```python
import os

filter_enabled = os.getenv("FILTER_CONTRACT_CLAUSES", "true").lower() in ("true", "1", "yes")

context_data = await context_retriever.retrieve_tender_context(
    project_id=project_id,
    top_k=150,
    max_context_chunks=100,
    sort_by_position=True,
    filter_contract_clauses=filter_enabled,
)
```

在 `docker-compose.yml` 中配置：
```yaml
backend:
  environment:
    - FILTER_CONTRACT_CLAUSES=true
```

## 🧪 过滤规则设计

### 基于内容的关键词

**强匹配**（几乎100%是合同条款）：
```python
STRONG_CONTRACT_KEYWORDS = [
    "甲方：", "乙方：",
    "法定代表人签字", "授权代表签字",
    "（甲方）", "（乙方）", "（盖章）",
    "签订地点：", "签订日期：",
    "本合同一式", "份正本",
]
```

**中等匹配**（很可能是合同条款）：
```python
MEDIUM_CONTRACT_KEYWORDS = [
    "合同条款", "合同格式", "合同协议书",
    "合同专用条款", "合同通用条款",
    "合同主要条款", "合同范本",
    "付款方式：", "违约责任：", "争议解决：",
    "质保期自", "质保金",
]
```

**弱匹配**（可能是合同条款，但也可能是其他）：
```python
WEAK_CONTRACT_KEYWORDS = [
    "合同", "履约", "违约",
    "甲方", "乙方", "双方",
]
```

### 建议的过滤策略

```python
def _is_contract_clause_chunk(self, chunk: Any) -> bool:
    text = chunk.text or ""
    
    # 强匹配：直接过滤
    for keyword in STRONG_CONTRACT_KEYWORDS:
        if keyword in text:
            logger.debug(f"过滤合同条款chunk（强匹配）: {keyword}")
            return True
    
    # 中等匹配：计数
    medium_matches = sum(1 for kw in MEDIUM_CONTRACT_KEYWORDS if kw in text)
    if medium_matches >= 2:  # 至少2个中等关键词
        logger.debug(f"过滤合同条款chunk（中等匹配）: {medium_matches}个关键词")
        return True
    
    # 弱匹配 + 中等匹配组合
    weak_matches = sum(1 for kw in WEAK_CONTRACT_KEYWORDS if kw in text)
    if weak_matches >= 2 and medium_matches >= 1:
        logger.debug(f"过滤合同条款chunk（组合匹配）: weak={weak_matches}, medium={medium_matches}")
        return True
    
    return False
```

## 📊 预期效果

### 当前情况（未过滤）
- 检索到 150 个 chunks
- 使用前 100 个拼接上下文
- 其中可能 10-20 个是合同条款相关

### 过滤后
- 检索到 150 个 chunks
- 过滤掉 10-20 个合同条款 chunks
- 使用剩余的前 100 个（实际提取更多有用内容）

### 提升
- ✅ 减少无关信息干扰
- ✅ 提升项目信息提取准确性
- ✅ token 利用率更高

## ⚠️ 注意事项

### 1. 不要过度过滤

**需要保留的内容**（虽然包含"合同"字样）：
- "投标人须知"中提到的合同签订流程
- "评分标准"中关于合同履约能力的评分
- "商务要求"中的合同工期要求

**解决方案**：使用组合匹配策略，避免单一关键词误杀

### 2. 不影响其他功能

**招标要求提取**时，合同条款可能包含重要要求（如付款条件、质保要求），所以：
- 只在**项目信息提取**时启用过滤
- 在**招标要求提取**时不启用过滤

### 3. 可配置性

建议使用参数控制，而不是硬编码：
```python
# ✅ 推荐：参数化
filter_contract_clauses=True

# ❌ 不推荐：硬编码
if "合同条款" in text:
    continue  # 无法关闭
```

## 🚀 实施步骤

### 步骤 1：实现过滤逻辑
1. 修改 `TenderContextRetriever.retrieve_tender_context()`
2. 添加 `_is_contract_clause_chunk()` 方法
3. 添加 `filter_contract_clauses` 参数（默认 False）

### 步骤 2：在项目信息提取中启用
修改 `extract_v2_service.py`：
```python
context_data = await context_retriever.retrieve_tender_context(
    project_id=project_id,
    top_k=150,
    max_context_chunks=100,
    sort_by_position=True,
    filter_contract_clauses=True,  # ✨ 启用
)
```

### 步骤 3：测试验证
1. 运行项目信息提取
2. 检查日志中过滤的 chunks 数量
3. 对比过滤前后的提取结果质量

### 步骤 4：调优
根据实际效果调整关键词列表和匹配策略

## 💻 完整实现代码

见下一条消息...

