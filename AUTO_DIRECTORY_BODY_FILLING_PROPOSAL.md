# 自动抽取目录并填充格式文档 - 完整方案

**提出时间**: 2025-12-25  
**需求**: 自动抽取投标文件目录，并将招标书中的格式文档自动识别并填入目录正文

---

## 📋 需求分析

### 业务场景

```
招标书包含:
├─ 投标文件组成要求（目录结构）
│   ├─ 第一卷 商务文件
│   │   ├─ 1. 投标函
│   │   ├─ 2. 法人授权委托书
│   │   └─ 3. 投标保证金凭证
│   └─ 第二卷 技术文件
│       ├─ 1. 技术方案
│       └─ 2. 施工组织设计
└─ 投标文件格式（格式文档/样表）
    ├─ 附件1：投标函（格式）
    ├─ 附件2：法人授权委托书（格式）
    └─ 附件3：其他格式

当前问题:
1. 目录生成：✅ 已支持（directory generation）
2. 格式文档提取：✅ 已支持（snippet extraction）
3. 自动关联：❌ 未支持（需要人工匹配）

期望结果:
自动将格式文档填入对应的目录节点正文中
```

### 用户价值

1. **效率提升**
   - 当前：人工查找格式文档 → 复制 → 粘贴到目录节点
   - 优化后：一键自动填充，节省90%时间

2. **准确性提升**
   - 自动匹配，减少人为错误
   - 基于语义理解，而非简单字符串匹配

3. **用户体验**
   - 用户只需点击"生成目录"
   - 系统自动完成目录结构 + 格式文档填充

---

## 🎯 方案设计

### 核心思路

```
Phase 1: 目录生成（已有）
  ↓
Phase 2: 格式文档提取（已有）
  ↓
Phase 3: 智能匹配（新增）✨
  ├─ 基于标题相似度
  ├─ 基于关键词匹配
  ├─ 基于LLM语义理解
  └─ 基于证据chunk重叠度
  ↓
Phase 4: 自动填充（新增）✨
  └─ 将匹配的格式文档内容填入目录节点的body字段
```

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    前端（用户操作）                         │
├─────────────────────────────────────────────────────────────┤
│  1. 用户点击「生成目录」                                    │
│  2. 后端返回目录结构 + 格式文档自动填充                     │
│  3. 前端展示目录树，每个节点显示:                           │
│     - 节点标题                                              │
│     - 是否已填充正文（✅ 图标）                            │
│     - 正文预览（前100字）                                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  后端（智能处理流程）                       │
├─────────────────────────────────────────────────────────────┤
│  Step 1: 生成目录结构（directory generation）              │
│    - 调用 LLM 提取投标文件目录要求                          │
│    - 输出: nodes = [                                        │
│        {title: "投标函", level: 2, ...},                    │
│        {title: "法人授权委托书", level: 2, ...},            │
│        ...                                                  │
│      ]                                                      │
│                                                             │
│  Step 2: 提取格式文档（snippet extraction）                │
│    - 调用 LLM 识别招标书中的格式文档                        │
│    - 输出: snippets = [                                     │
│        {title: "投标函", content: "...", type: "BID_LETTER"},│
│        {title: "法人授权委托书", content: "...", ...},      │
│        ...                                                  │
│      ]                                                      │
│                                                             │
│  Step 3: 智能匹配 ✨ 新增                                   │
│    - 对每个目录节点:                                        │
│      for node in nodes:                                     │
│        matched_snippet = match_snippet(node, snippets)      │
│        if matched_snippet:                                  │
│          node.body = matched_snippet.content               │
│          node.auto_filled = True                           │
│          node.matched_snippet_id = matched_snippet.id      │
│                                                             │
│  Step 4: 保存到数据库                                       │
│    - 保存目录节点（包含body）                               │
│    - 记录匹配关系                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 技术方案

### 方案A：基于规则的匹配（简单，快速实施）⭐⭐⭐

**核心思想**: 使用标题相似度 + 关键词匹配

**匹配算法**:

```python
def match_snippet_by_rules(
    node: DirectoryNode,
    snippets: List[Snippet]
) -> Optional[Snippet]:
    """
    基于规则匹配格式文档
    
    匹配策略（优先级递减）:
    1. 标题完全匹配（去除空格、标点）
    2. 标题包含匹配（snippet标题包含node标题，或反之）
    3. 关键词匹配（预定义的同义词表）
    4. 模糊匹配（编辑距离、余弦相似度）
    """
    
    # 1. 标题完全匹配
    node_title_clean = clean_title(node.title)  # "投标函" -> "投标函"
    for snippet in snippets:
        snippet_title_clean = clean_title(snippet.title)
        if node_title_clean == snippet_title_clean:
            return snippet  # 完全匹配，置信度100%
    
    # 2. 标题包含匹配
    for snippet in snippets:
        if node_title_clean in snippet.title or snippet.title in node_title_clean:
            return snippet  # 包含匹配，置信度90%
    
    # 3. 关键词同义词匹配
    synonyms = {
        "投标函": ["投标书", "投标文件", "投标申请", "投标报价函"],
        "授权委托书": ["法人授权书", "授权书", "委托书", "法定代表人授权"],
        "保证金": ["投标保证金", "保证金凭证", "保函"],
        "报价表": ["投标报价表", "报价清单", "价格表", "费用清单"],
        "偏离表": ["技术偏离表", "商务偏离表", "响应偏离表"],
        # ... 更多同义词
    }
    
    for key, synonyms_list in synonyms.items():
        if key in node_title_clean:
            for snippet in snippets:
                for syn in synonyms_list:
                    if syn in snippet.title:
                        return snippet  # 同义词匹配，置信度80%
    
    # 4. 模糊匹配（使用fuzzywuzzy或difflib）
    from fuzzywuzzy import fuzz
    best_match = None
    best_score = 0
    
    for snippet in snippets:
        score = fuzz.token_sort_ratio(node_title_clean, snippet.title)
        if score > best_score and score >= 70:  # 相似度阈值70%
            best_score = score
            best_match = snippet
    
    if best_match:
        return best_match  # 模糊匹配，置信度60-80%
    
    return None  # 未匹配
```

**优点**:
- ✅ 实现简单，开发时间短（4-6小时）
- ✅ 速度快，无需调用LLM
- ✅ 可解释性强，用户能理解匹配逻辑
- ✅ 准确率中等（预计70-85%）

**缺点**:
- ❌ 需要维护同义词表
- ❌ 对复杂、非标准标题匹配效果差
- ❌ 无法理解语义（如"投标承诺函"和"承诺书"）

**适用场景**: 快速上线，80%的标准化招标项目

---

### 方案B：基于LLM的语义匹配（智能，推荐）⭐⭐⭐⭐⭐

**核心思想**: 使用小模型进行语义相似度判断

**匹配算法**:

```python
async def match_snippet_by_llm(
    node: DirectoryNode,
    snippets: List[Snippet],
    llm: LLMClient
) -> Optional[Snippet]:
    """
    使用LLM进行语义匹配
    
    策略:
    1. 批量调用LLM，判断每个snippet与node的匹配度
    2. 返回匹配度最高的snippet
    """
    
    # 构建匹配Prompt
    prompt = f"""
你是招投标文档匹配专家。请判断以下格式文档是否与目录节点匹配。

目录节点:
- 标题: {node.title}
- 层级: 第{node.level}级
- 说明: {node.notes or "无"}

候选格式文档列表:
{format_snippets_for_prompt(snippets)}

请为每个格式文档打分（0-100），并返回JSON:
{{
  "matches": [
    {{"snippet_id": "snippet_001", "score": 95, "reason": "标题完全匹配"}},
    {{"snippet_id": "snippet_002", "score": 60, "reason": "部分相关"}},
    ...
  ]
}}

评分标准:
- 95-100: 完全匹配（标题相同或同义）
- 80-94: 高度相关（内容高度吻合）
- 60-79: 部分相关（有一定关联）
- 0-59: 不相关或无关

只返回JSON，不要其他内容。
"""
    
    # 调用LLM
    response = await llm.chat(
        messages=[{"role": "user", "content": prompt}],
        model_id="gpt-4o-mini",  # 使用快速小模型
        temperature=0.0,
        max_tokens=1000
    )
    
    # 解析结果
    result = parse_json(response)
    matches = result.get("matches", [])
    
    # 找到最高分的匹配（阈值80分）
    best_match = max(matches, key=lambda m: m["score"], default=None)
    if best_match and best_match["score"] >= 80:
        snippet_id = best_match["snippet_id"]
        return next((s for s in snippets if s.id == snippet_id), None)
    
    return None
```

**优点**:
- ✅ 准确率高（预计90-95%）
- ✅ 理解语义，能处理同义词、近义词
- ✅ 适应性强，无需维护规则
- ✅ 能给出匹配理由，方便调试

**缺点**:
- ❌ 需要调用LLM，增加成本（约$0.001-0.002/节点）
- ❌ 速度略慢（每批10-20个节点，约2-3秒）
- ❌ 实现复杂度中等

**成本分析**:
```
假设:
- 每个项目平均30个目录节点
- 每个项目平均15个格式文档
- 使用GPT-4o-mini批量匹配

成本:
- 输入: 30个节点 × (节点信息100 tokens + 15个snippets × 50 tokens) = 30 × 850 = 25,500 tokens
- 输出: 30个节点 × 100 tokens = 3,000 tokens
- 总计: 28,500 tokens
- 成本: 28,500 × $0.15/1M (输入) + 3,000 × $0.6/1M (输出) = $0.0043 + $0.0018 = $0.0061
- 约0.6分钱/项目 ✅ 可接受

速度:
- 可批量处理，30个节点约3-5秒
```

**适用场景**: 中长期方案，追求高准确率

---

### 方案C：混合方案（平衡，最优）⭐⭐⭐⭐⭐

**核心思想**: 规则匹配 + LLM兜底

**匹配流程**:

```python
async def match_snippet_hybrid(
    node: DirectoryNode,
    snippets: List[Snippet],
    llm: Optional[LLMClient] = None
) -> Optional[Snippet]:
    """
    混合匹配策略
    
    流程:
    1. 先用规则快速匹配（高置信度cases）
    2. 规则无法匹配时，用LLM兜底
    """
    
    # Phase 1: 规则匹配
    matched, confidence = match_by_rules_with_confidence(node, snippets)
    
    if confidence >= 0.9:  # 高置信度，直接返回
        logger.info(f"Node '{node.title}' matched by rules with confidence {confidence}")
        return matched
    
    # Phase 2: LLM兜底（仅处理不确定的cases）
    if llm:
        logger.info(f"Node '{node.title}' low confidence ({confidence}), using LLM")
        matched_llm = await match_by_llm(node, snippets, llm)
        if matched_llm:
            return matched_llm
    
    # Phase 3: 返回规则匹配结果（如果有）
    if matched and confidence >= 0.6:
        logger.warning(f"Node '{node.title}' matched by rules with low confidence {confidence}")
        return matched
    
    return None  # 无匹配
```

**优点**:
- ✅ 兼具速度和准确率
- ✅ 成本低（只有20-30%的cases需要LLM）
- ✅ 可靠性高（多重保障）

**预期效果**:
- 70%的cases通过规则匹配（高置信度）
- 20%的cases通过LLM匹配（中等难度）
- 10%的cases无法匹配（需要人工确认）

**成本**: 约$0.002/项目（比纯LLM方案降低70%）

---

## 📊 数据库设计

### 新增字段

```sql
-- directory_nodes 表增加字段
ALTER TABLE directory_nodes ADD COLUMN IF NOT EXISTS body TEXT;
ALTER TABLE directory_nodes ADD COLUMN IF NOT EXISTS auto_filled BOOLEAN DEFAULT FALSE;
ALTER TABLE directory_nodes ADD COLUMN IF NOT EXISTS matched_snippet_id TEXT;
ALTER TABLE directory_nodes ADD COLUMN IF NOT EXISTS match_confidence FLOAT;
ALTER TABLE directory_nodes ADD COLUMN IF NOT EXISTS match_method VARCHAR(50);  -- 'rules', 'llm', 'manual'

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_directory_nodes_auto_filled 
  ON directory_nodes(project_id, auto_filled);
```

### 字段说明

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `body` | TEXT | 节点正文内容（格式文档内容） | "投标函格式：\n\n致：XX招标代理..." |
| `auto_filled` | BOOLEAN | 是否自动填充 | true/false |
| `matched_snippet_id` | TEXT | 匹配的格式文档ID | "snippet_abc123" |
| `match_confidence` | FLOAT | 匹配置信度（0-1） | 0.95 |
| `match_method` | VARCHAR | 匹配方法 | "rules", "llm", "manual" |

---

## 🚀 实施步骤

### Phase 1: 核心功能开发（1-2天）

#### 1.1 数据库迁移
```bash
# 添加新字段
alembic revision -m "add_directory_body_fields"
alembic upgrade head
```

#### 1.2 实现匹配服务
```python
# backend/app/services/directory_body_matcher.py
class DirectoryBodyMatcher:
    """目录节点与格式文档匹配服务"""
    
    async def match_and_fill(
        self,
        project_id: str,
        nodes: List[DirectoryNode],
        use_llm: bool = True
    ) -> List[DirectoryNode]:
        """
        匹配并填充目录节点
        
        Returns:
            填充后的节点列表
        """
        # 1. 获取项目的所有格式文档
        snippets = await self._get_project_snippets(project_id)
        
        if not snippets:
            logger.warning(f"No snippets found for project {project_id}")
            return nodes
        
        # 2. 对每个节点进行匹配
        filled_nodes = []
        for node in nodes:
            matched = await self.match_snippet_hybrid(node, snippets, use_llm)
            
            if matched:
                node.body = matched.content
                node.auto_filled = True
                node.matched_snippet_id = matched.id
                node.match_confidence = matched.confidence
                node.match_method = matched.method
                logger.info(f"Node '{node.title}' matched with snippet '{matched.title}'")
            
            filled_nodes.append(node)
        
        return filled_nodes
```

#### 1.3 集成到目录生成流程
```python
# backend/app/services/tender_service.py

def generate_directory(self, project_id: str, model_id: str, run_id: str):
    # ... 现有代码 ...
    
    # 6. 保存（使用replace_directory）
    self.dao.replace_directory(project_id, nodes_with_tree)
    
    # ✨ 7. 新增：匹配并填充格式文档
    from app.services.directory_body_matcher import DirectoryBodyMatcher
    matcher = DirectoryBodyMatcher(self.pool, self.llm)
    
    filled_nodes = run_async(matcher.match_and_fill(
        project_id=project_id,
        nodes=nodes_with_tree,
        use_llm=True  # 使用混合匹配
    ))
    
    # 8. 更新节点（保存body）
    self.dao.update_directory_nodes_body(project_id, filled_nodes)
    
    logger.info(f"[generate_directory] Matched {sum(1 for n in filled_nodes if n.auto_filled)}/{len(filled_nodes)} nodes")
```

---

### Phase 2: 前端展示优化（0.5-1天）

#### 2.1 目录树展示增强

```typescript
// frontend/src/components/tender/DirectoryTree.tsx

export type DirectoryNode = {
  id: string;
  title: string;
  level: number;
  required: boolean;
  // ✨ 新增字段
  body?: string;              // 正文内容
  auto_filled?: boolean;      // 是否自动填充
  match_confidence?: number;  // 匹配置信度
};

function DirectoryNodeItem({ node }: { node: DirectoryNode }) {
  return (
    <div className="directory-node">
      <div className="node-title">
        {node.title}
        
        {/* ✨ 显示自动填充标识 */}
        {node.auto_filled && (
          <span className="auto-fill-badge" title={`自动填充 (置信度: ${(node.match_confidence * 100).toFixed(0)}%)`}>
            ✅ 已填充
          </span>
        )}
      </div>
      
      {/* ✨ 显示正文预览 */}
      {node.body && (
        <div className="node-body-preview">
          {node.body.substring(0, 100)}...
        </div>
      )}
    </div>
  );
}
```

#### 2.2 正文编辑功能

```typescript
function DirectoryBodyEditor({ node, onSave }: Props) {
  const [body, setBody] = useState(node.body || '');
  const [isEditing, setIsEditing] = useState(false);
  
  const handleSave = async () => {
    await api.put(`/api/apps/tender/projects/${projectId}/directory/nodes/${node.id}/body`, {
      body: body
    });
    onSave(body);
    setIsEditing(false);
  };
  
  return (
    <div className="directory-body-editor">
      {node.auto_filled && (
        <div className="auto-fill-info">
          <Icon name="check-circle" />
          <span>此内容由系统自动填充</span>
          {node.match_confidence && (
            <span className="confidence">
              (置信度: {(node.match_confidence * 100).toFixed(0)}%)
            </span>
          )}
        </div>
      )}
      
      {isEditing ? (
        <>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={20}
          />
          <button onClick={handleSave}>保存</button>
          <button onClick={() => setIsEditing(false)}>取消</button>
        </>
      ) : (
        <>
          <div className="body-content">{body || '暂无内容'}</div>
          <button onClick={() => setIsEditing(true)}>编辑</button>
        </>
      )}
    </div>
  );
}
```

---

### Phase 3: 优化与扩展（1-2天）

#### 3.1 批量重新匹配

```python
@router.post("/projects/{project_id}/directory/rematch")
async def rematch_directory_bodies(
    project_id: str,
    request: RematchRequest,
    user=Depends(get_current_user_sync)
):
    """
    重新匹配目录节点与格式文档
    
    适用场景:
    - 格式文档更新后
    - 匹配效果不理想
    - 用户手动触发
    """
    from app.services.directory_body_matcher import DirectoryBodyMatcher
    
    # 获取现有节点
    nodes = tender_dao.get_directory_nodes(project_id)
    
    # 重新匹配
    matcher = DirectoryBodyMatcher(pool, llm)
    filled_nodes = await matcher.match_and_fill(
        project_id=project_id,
        nodes=nodes,
        use_llm=request.use_llm
    )
    
    # 更新数据库
    tender_dao.update_directory_nodes_body(project_id, filled_nodes)
    
    return {
        "status": "success",
        "matched": sum(1 for n in filled_nodes if n.auto_filled),
        "total": len(filled_nodes)
    }
```

#### 3.2 匹配质量报告

```python
def generate_match_report(project_id: str) -> Dict[str, Any]:
    """
    生成匹配质量报告
    
    Returns:
        {
            "total_nodes": 30,
            "auto_filled": 25,
            "manual_filled": 2,
            "not_filled": 3,
            "avg_confidence": 0.92,
            "match_methods": {
                "rules": 18,
                "llm": 7,
                "manual": 2
            },
            "low_confidence_nodes": [
                {"title": "其他文件", "confidence": 0.65}
            ]
        }
    """
    pass
```

---

## 📈 预期效果

### 效率提升

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| **目录节点填充时间** | 30个节点 × 2分钟 = 60分钟 | 自动填充 < 10秒 | ⬆ 99% |
| **匹配准确率** | 人工匹配 95% | 自动匹配 90% | - |
| **用户操作步骤** | 30次（每节点1次） | 1次（点击生成） | ⬇ 97% |
| **格式文档利用率** | 60%（部分遗漏） | 95%（全面覆盖） | ⬆ 58% |

### 用户体验

**优化前流程**:
```
1. 点击"生成目录" → 等待30秒
2. 手动查找格式文档章节 → 5-10分钟
3. 逐个复制粘贴 → 每个2分钟 × 30个 = 60分钟
4. 检查是否有遗漏 → 10分钟

总计: 约75-85分钟 ❌
```

**优化后流程**:
```
1. 点击"生成目录" → 等待30秒
2. 系统自动匹配填充 → 5秒
3. 用户检查和微调（可选） → 10分钟

总计: 约10-15分钟 ✅
```

**节省时间**: 约60-75分钟/项目

---

## 💰 成本分析

### 开发成本

| 阶段 | 工作量 | 说明 |
|------|--------|------|
| **Phase 1: 核心功能** | 1-2天 | 匹配算法 + 数据库 + API |
| **Phase 2: 前端展示** | 0.5-1天 | 目录树增强 + 编辑器 |
| **Phase 3: 优化扩展** | 1-2天 | 重新匹配 + 质量报告 |
| **总计** | 2.5-5天 | 含测试和调试 |

### 运行成本

**方案A（纯规则）**: $0/项目  
**方案B（纯LLM）**: $0.006/项目  
**方案C（混合，推荐）**: $0.002/项目 ✅

假设每月处理100个项目：
- 月成本：$0.002 × 100 = $0.2
- 年成本：$2.4

**成本收益比**:
- 每项目节省60-75分钟人力时间
- 假设人力成本50元/小时
- 每项目节省：50元 × 1.2小时 = 60元
- 月收益：60元 × 100 = 6000元
- **ROI: 30000倍** ✅

---

## 🧪 测试策略

### 功能测试

1. **标准化项目测试**
   - 使用典型的政府采购招标文件
   - 验证匹配准确率 ≥ 90%

2. **非标项目测试**
   - 使用格式不规范的招标文件
   - 验证系统的容错能力

3. **边界测试**
   - 无格式文档的项目
   - 格式文档很多（50+）的项目
   - 目录节点很多（100+）的项目

### 性能测试

```
测试场景:
- 30个目录节点 + 15个格式文档
- 混合匹配策略

预期性能:
- 总耗时 < 10秒
- 内存占用 < 100MB
- 数据库查询 < 10次
```

---

## 🔮 未来扩展

### 扩展1: 智能内容生成

当格式文档未提供时，根据节点标题自动生成模板内容：

```python
async def generate_template_content(node: DirectoryNode) -> str:
    """
    基于节点标题生成模板内容
    
    示例:
    - 节点: "投标函"
    - 生成: 标准投标函模板（包含常见字段占位符）
    """
    prompt = f"""
请生成「{node.title}」的标准格式模板。

要求:
1. 符合招投标规范
2. 包含必要的字段占位符
3. 格式规范，易于填写

只返回模板内容，不要其他说明。
"""
    
    content = await llm.chat(...)
    return content
```

### 扩展2: 多版本管理

支持保存多个版本的正文内容：

```sql
CREATE TABLE directory_node_body_versions (
  id TEXT PRIMARY KEY,
  node_id TEXT NOT NULL,
  version INT NOT NULL,
  body TEXT,
  source VARCHAR(50),  -- 'auto', 'manual', 'generated'
  created_at TIMESTAMP,
  created_by TEXT
);
```

### 扩展3: 协同编辑

支持多人同时编辑目录正文，实时同步：

```typescript
// 使用 WebSocket 或 Yjs 实现
const { provider, doc } = useCollaboration(nodeId);
```

---

## ✅ 推荐方案

**建议采用「方案C：混合方案」**

**理由**:
1. ✅ 准确率高（90%+）
2. ✅ 成本低（$0.002/项目）
3. ✅ 速度快（< 10秒）
4. ✅ 可靠性好（规则 + LLM双保险）
5. ✅ 易于维护（规则覆盖常见cases，LLM处理边缘cases）

**实施优先级**:
1. **P0 (必须)**: Phase 1 - 核心匹配功能
2. **P1 (重要)**: Phase 2 - 前端展示
3. **P2 (可选)**: Phase 3 - 优化扩展

**预期里程碑**:
- Week 1: 完成Phase 1（核心功能）
- Week 2: 完成Phase 2（前端展示）+ 测试
- Week 3: 完成Phase 3（优化扩展）+ 上线

---

**方案制定时间**: 2025-12-25  
**预计开发时间**: 2.5-5天  
**预期效果**: 节省60-75分钟/项目，准确率90%+
