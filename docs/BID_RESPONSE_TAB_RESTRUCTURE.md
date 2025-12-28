# 投标响应抽取Tab重构

## 概述

将"投标响应抽取"功能从审核Tab独立出来，作为一个独立的Tab⑤，放在"AI生成全文（预留）"之后、"审核"之前。

## 修改内容

### 1. Tab结构调整

**原Tab顺序：**
- Tab 1: 项目信息
- Tab 2: 风险识别
- Tab 3: 目录生成
- Tab 4: AI生成全文（预留）
- Tab 5: 审核

**新Tab顺序：**
- Tab 1: 项目信息
- Tab 2: 风险识别
- Tab 3: 目录生成
- Tab 4: AI生成全文（预留）
- **Tab 5: 投标响应抽取** ⭐ 新增
- Tab 6: 审核

### 2. 状态管理扩展

#### 2.1 接口定义

```typescript
// 投标响应数据接口
interface BidResponse {
  id: string;
  bidder_name: string;
  dimension: string;
  response_type: string;
  response_text: string;
  extracted_value_json: any;
  evidence_chunk_ids: string[];
  created_at: string;
}

interface BidResponseStats {
  bidder_name: string;
  dimension: string;
  count: number;
}
```

#### 2.2 ProjectState扩展

```typescript
interface ProjectState {
  // ... 其他字段
  bidResponses: BidResponse[];
  bidResponseStats: BidResponseStats[];
  
  runs: {
    info: TenderRun | null;
    risk: TenderRun | null;
    directory: TenderRun | null;
    bidResponse: TenderRun | null;  // 新增
    review: TenderRun | null;
  };
}
```

#### 2.3 新增状态Getter和Setter

```typescript
const bidResponses = state.bidResponses;
const setBidResponses = useCallback((value: BidResponse[]) => {...}, []);

const bidResponseStats = state.bidResponseStats;
const setBidResponseStats = useCallback((value: BidResponseStats[]) => {...}, []);

const bidResponseRun = state.runs.bidResponse;
const setBidResponseRun = useCallback((value: TenderRun | null) => {...}, []);
```

### 3. 核心功能函数

#### 3.1 loadBidResponses

从后端API加载投标响应数据：

```typescript
const loadBidResponses = useCallback(async (forceProjectId?: string) => {
  const projectId = forceProjectId || currentProject?.id;
  if (!projectId) return;
  
  // 项目切换验证
  if (!forceProjectId && currentProject && currentProject.id !== projectId) {
    console.log('[loadBidResponses] 项目已切换，跳过加载');
    return;
  }
  
  try {
    const selectedBidderName = state.selectedBidder;
    const params = selectedBidderName ? `?bidder_name=${encodeURIComponent(selectedBidderName)}` : '';
    const data = await api.get(`/api/apps/tender/projects/${projectId}/bid-responses${params}`);
    
    // 验证项目是否在加载期间切换
    if (currentProject && currentProject.id !== projectId) {
      console.log('[loadBidResponses] 加载完成时项目已切换，丢弃数据');
      return;
    }
    
    setBidResponses(data.responses || []);
    setBidResponseStats(data.stats || []);
  } catch (err) {
    console.error('Failed to load bid responses:', err);
    setBidResponses([]);
    setBidResponseStats([]);
  }
}, [currentProject, state.selectedBidder]);
```

#### 3.2 extractBidResponses

执行投标响应抽取：

```typescript
const extractBidResponses = useCallback(async () => {
  if (!currentProject) return;
  if (!state.selectedBidder) {
    alert('请先选择投标人');
    return;
  }
  
  const projectId = currentProject.id;
  const bidderName = state.selectedBidder;
  
  setBidResponseRun({
    id: 'temp',
    status: 'running',
    progress: 0,
    message: '开始抽取投标响应数据...',
    kind: 'extract_bid_responses',
  } as TenderRun);
  
  try {
    const res = await api.post(
      `/api/apps/tender/projects/${projectId}/extract-bid-responses?bidder_name=${encodeURIComponent(bidderName)}`,
      {}
    );
    
    if (res.success) {
      setBidResponseRun({...});
      await loadBidResponses(projectId);
      showToast('success', `抽取完成！共抽取 ${res.data?.total_responses || 0} 条投标响应数据`);
    } else {
      setBidResponseRun({...});
      showToast('error', `抽取失败: ${res.message || '未知错误'}`);
    }
  } catch (err: any) {
    setBidResponseRun({...});
    showToast('error', `抽取失败: ${err.message || err}`);
  }
}, [currentProject, state.selectedBidder, loadBidResponses]);
```

### 4. useEffect数据加载

在项目切换时自动加载投标响应数据：

```typescript
useEffect(() => {
  if (!currentProject) return;
  const projectId = currentProject.id;
  
  // 加载项目数据
  loadAssets(projectId);
  loadProjectInfo(projectId);
  loadRisks(projectId);
  loadDirectory(projectId);
  loadBidResponses(projectId);  // 新增
  loadReview(projectId);
  loadSampleFragments(projectId);
  
  // 从后端加载run状态
  const loadAndRestoreRuns = async () => {
    // ...
    const bidResponseRunData = data.extract_bid_responses || null;
    
    updateProjectState(projectId, {
      runs: {
        info: infoRunData,
        risk: riskRunData,
        directory: dirRunData,
        bidResponse: bidResponseRunData,  // 新增
        review: reviewRunData,
      }
    });
    
    // 恢复投标响应抽取轮询
    if (bidResponseRunData?.status === 'running') {
      console.log('[loadAndRestoreRuns] 恢复投标响应抽取轮询:', bidResponseRunData.id);
      startPolling(projectId, 'bidResponse', bidResponseRunData.id, () => loadBidResponses(projectId));
    }
  };
  
  loadAndRestoreRuns();
}, [currentProject?.id]);
```

### 5. Tab切换逻辑

```typescript
{[
  { id: 1, label: 'Step 1: 项目信息' },
  { id: 2, label: 'Step 2: 风险识别' },
  { id: 3, label: '③ 目录生成' },
  { id: 4, label: '④ AI生成全文（预留）' },
  { id: 5, label: '⑤ 投标响应抽取' },
  { id: 6, label: '⑥ 审核' },
].map(tab => (
  <button
    key={tab.id}
    onClick={() => {
      setActiveTab(tab.id);
      // 切换到审核Tab时加载规则包列表
      if (tab.id === 6) {
        loadRulePacks();
      }
      // 切换到投标响应抽取Tab时加载投标响应数据
      if (tab.id === 5) {
        loadBidResponses();
      }
    }}
    // ...
  >
    {tab.label}
  </button>
))}
```

### 6. Tab⑤投标响应抽取UI

```typescript
{activeTab === 5 && (
  <section className="kb-upload-section">
    {/* 标题和操作按钮 */}
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
      <h4>投标响应抽取</h4>
      <button 
        onClick={extractBidResponses} 
        className="kb-create-form" 
        style={{ width: 'auto', marginBottom: 0 }}
        disabled={bidResponseRun?.status === 'running' || !selectedBidder}
      >
        {bidResponseRun?.status === 'running' ? '抽取中...' : '开始抽取'}
      </button>
    </div>
    
    {/* Run状态显示 */}
    {bidResponseRun && (
      <div className="kb-import-results">
        <div className="kb-import-item">状态: {bidResponseRun.status}</div>
        {bidResponseRun.message && (
          <div className="kb-import-item">{bidResponseRun.message}</div>
        )}
      </div>
    )}
    
    {/* 说明信息 */}
    <div className="kb-doc-meta" style={{ marginBottom: '16px', padding: '12px', backgroundColor: '#e0f2fe', borderRadius: '4px' }}>
      💡 <strong>说明</strong>：从投标文件中抽取结构化响应数据，用于V3审核。操作前请先选择投标人。
    </div>
    
    {/* 投标人选择 */}
    <div className="kb-create-form">
      {bidderOptions.length > 0 && (
        <>
          <label className="sidebar-label">选择投标人:</label>
          <select
            value={selectedBidder}
            onChange={e => setSelectedBidder(e.target.value)}
            className="sidebar-select"
          >
            <option value="">-- 请选择 --</option>
            {bidderOptions.map(name => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
        </>
      )}
      
      {/* 抽取统计 */}
      {bidResponseStats.length > 0 && (
        <div style={{ marginTop: '16px' }}>
          <h5 style={{ marginBottom: '8px' }}>抽取统计</h5>
          <div className="kb-doc-meta">
            {bidResponseStats.map((stat, idx) => (
              <div key={idx} style={{ padding: '4px 0' }}>
                • {stat.bidder_name} - {stat.dimension}: {stat.count} 条
              </div>
            ))}
            <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid #e2e8f0', fontWeight: 500 }}>
              总计: {bidResponseStats.reduce((sum, s) => sum + s.count, 0)} 条投标响应数据
            </div>
          </div>
        </div>
      )}
      
      {/* 抽取详情 */}
      {bidResponses.length > 0 && (
        <div style={{ marginTop: '16px' }}>
          <h5 style={{ marginBottom: '8px' }}>抽取详情</h5>
          <div style={{ maxHeight: '400px', overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: '4px', padding: '8px' }}>
            {bidResponses.map((resp, idx) => (
              <div key={resp.id} className="kb-doc-meta" style={{ marginBottom: '8px', padding: '12px', backgroundColor: '#f8fafc', borderRadius: '4px' }}>
                <div style={{ fontWeight: 500, marginBottom: '4px', color: '#334155' }}>
                  {idx + 1}. {resp.dimension}
                </div>
                <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>
                  类型: {resp.response_type} | 投标人: {resp.bidder_name}
                </div>
                <div style={{ fontSize: '13px', color: '#475569', marginTop: '8px', maxHeight: '100px', overflowY: 'auto', whiteSpace: 'pre-wrap' }}>
                  {resp.response_text}
                </div>
                {resp.evidence_chunk_ids.length > 0 && (
                  <button
                    onClick={() => showEvidence(resp.evidence_chunk_ids)}
                    className="link-button"
                    style={{ marginTop: '8px', fontSize: '12px' }}
                  >
                    查看证据 ({resp.evidence_chunk_ids.length} 条)
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
      
      {!selectedBidder && (
        <div className="kb-empty" style={{ marginTop: '16px' }}>
          请先选择投标人，然后点击"开始抽取"
        </div>
      )}
    </div>
  </section>
)}
```

### 7. Tab⑥审核的简化

从审核Tab移除了：
- "抽取投标响应"按钮
- V3审核说明的警告框

保留了：
- 投标人选择
- 自定义规则包选择
- 自定义规则文件选择
- 开始审核按钮
- 审核结果展示

### 8. 轮询类型扩展

```typescript
// startPolling和stopPolling函数的taskType参数扩展
type PollingTaskType = 'info' | 'risk' | 'directory' | 'bidResponse' | 'review';

const startPolling = useCallback((
  projectId: string,
  taskType: PollingTaskType,
  runId: string,
  onSuccess: () => void
) => {...}, []);

const stopPolling = useCallback((
  projectId: string, 
  taskType?: PollingTaskType
) => {...}, []);
```

## API依赖

### 后端API

- `GET /api/apps/tender/projects/{project_id}/bid-responses`
  - 查询参数: `bidder_name` (可选)
  - 返回: `{ count, responses, stats }`

- `POST /api/apps/tender/projects/{project_id}/extract-bid-responses`
  - 查询参数: `bidder_name` (必需)
  - 返回: `{ success, message, data: { total_responses } }`

## 用户操作流程

1. **进入项目**：选择一个招投标项目
2. **上传文件**：
   - Step 0: 上传招标文件和投标文件
3. **项目信息抽取**：
   - Step 1: 抽取招标项目的基本信息
4. **风险识别**：
   - Step 2: 识别招标文件中的风险点
5. **目录生成**：
   - Step 3: 生成标书目录和正文
6. **AI生成全文**：
   - Step 4: （预留功能）
7. **投标响应抽取**：⭐ 新增
   - Step 5: 选择投标人 → 点击"开始抽取" → 查看抽取的投标响应数据
8. **审核**：
   - Step 6: 选择投标人 → 选择自定义规则包（可选）→ 点击"开始审核" → 查看审核结果

## 与V3审核的关系

- **投标响应抽取**（Tab⑤）是V3审核的前置步骤
- V3审核需要结构化的投标响应数据（存储在`tender_bid_response_items`表）
- 用户应该在执行审核前，先在Tab⑤抽取投标响应
- 如果没有抽取投标响应，V3审核会因缺少数据而失败

## 优势

1. **流程清晰**：每个Tab专注于一个任务，操作流程更加清晰
2. **数据可视化**：用户可以在Tab⑤查看抽取的投标响应详情，而不是等到审核失败才发现问题
3. **操作独立**：抽取和审核分开，可以多次抽取而不影响审核结果
4. **状态持久化**：每个项目的投标响应状态独立管理，切换项目不会丢失数据

## 测试建议

1. **正常流程测试**：
   - 创建新项目 → 上传招标和投标文件 → 项目信息抽取 → 投标响应抽取 → 审核
2. **项目切换测试**：
   - 在多个项目间切换，验证投标响应数据不会混乱
3. **抽取状态测试**：
   - 验证抽取中、成功、失败状态的正确显示
4. **数据展示测试**：
   - 验证统计信息和详情的正确展示
   - 验证"查看证据"功能
5. **无投标人测试**：
   - 未选择投标人时，按钮应该是禁用状态

## 文件修改

- `/aidata/x-llmapp1/frontend/src/components/TenderWorkspace.tsx`
  - 新增 `BidResponse` 和 `BidResponseStats` 接口
  - 扩展 `ProjectState` 接口
  - 新增 `loadBidResponses` 和 `extractBidResponses` 函数
  - 新增 Tab⑤投标响应抽取UI
  - 修改 Tab⑥审核UI（移除抽取按钮和警告）
  - 更新 useEffect 数据加载逻辑
  - 扩展轮询类型

## 总结

本次重构将投标响应抽取独立成一个Tab，使得用户操作更加清晰，数据可视化更好，同时保持了与V3审核的良好集成。

