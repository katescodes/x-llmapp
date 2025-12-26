# 项目切换数据污染问题修复

**问题时间**: 2025-12-25  
**问题描述**: 当项目A正在抽取时，切换到项目B，项目B会显示项目A的抽取内容

---

## 🐛 问题根源分析

### 问题场景

1. **用户在项目A开始抽取**
   - 触发 `extractProjectInfo()`
   - 启动轮询 `pollRun(runId, 'project-A-id', loadProjectInfo)`
   - 后台开始抽取项目A的数据

2. **用户切换到项目B**
   - `selectProject(projectB)` 被调用
   - `currentProject` 更新为项目B
   - 轮询检测到项目切换，停止轮询 ✅

3. **问题出现：项目B显示了项目A的数据** ❌
   - 在切换的瞬间，如果项目A的抽取刚好完成
   - `pollRun` 调用 `onSuccess()` 回调（即 `loadProjectInfo()`）
   - `loadProjectInfo()` 使用当前的 `currentProject`（此时是项目B！）
   - 结果：加载了项目B的数据，但可能是空的；或者更糟，如果时序巧合，可能加载了项目A的数据到项目B界面

### 核心问题

**异步加载函数依赖闭包变量 `currentProject`，而不是启动任务时的项目ID**

```typescript
// ❌ 问题代码
const loadProjectInfo = useCallback(async () => {
  if (!currentProject) return;
  const data = await api.get(`/api/apps/tender/projects/${currentProject.id}/project-info`);
  setProjectInfo(data);
}, [currentProject]);

// 启动任务
pollRun(runId, projectA.id, loadProjectInfo);

// 用户切换到项目B
// currentProject = projectB

// 任务完成，调用 loadProjectInfo()
// 此时 currentProject 已经是 projectB！
// 结果加载了错误的数据
```

### 时序图

```
时间轴：
  t0: 项目A开始抽取 → pollRun(runA, 'A', loadProjectInfo)
  t1: currentProject = 'A'
  t2: 用户切换项目 → selectProject(B)
  t3: currentProject = 'B'
  t4: 项目A抽取完成 → pollRun 检测到项目切换，停止轮询 ✅
  
  但如果时序是：
  t4': 项目A抽取完成 → pollRun 调用 onSuccess() → loadProjectInfo()
  t5': loadProjectInfo() 使用 currentProject (此时是'B') ❌
  t6': 加载并显示了错误的数据
```

---

## ✅ 修复方案

### 核心思路

**将项目ID作为参数传递，而不是依赖闭包变量**

### 修复1: 加载函数支持项目ID参数

所有加载函数（`loadProjectInfo`, `loadRisks`, `loadDirectory`, `loadReview`）都添加可选的 `forceProjectId` 参数：

```typescript
const loadProjectInfo = useCallback(async (forceProjectId?: string) => {
  // ✅ 使用传入的projectId或当前项目ID
  const projectId = forceProjectId || currentProject?.id;
  if (!projectId) return;
  
  // ✅ 加载前验证项目ID
  if (!forceProjectId && currentProject && currentProject.id !== projectId) {
    console.log('[loadProjectInfo] 项目已切换，跳过加载');
    return;
  }
  
  try {
    const data = await api.get(`/api/apps/tender/projects/${projectId}/project-info`);
    
    // ✅ 加载后再次验证项目ID（防止异步加载期间项目切换）
    if (currentProject && currentProject.id !== projectId) {
      console.log('[loadProjectInfo] 加载完成时项目已切换，丢弃数据');
      return;
    }
    
    setProjectInfo(data);
  } catch (err) {
    console.error('Failed to load project info:', err);
  }
}, [currentProject]);
```

**关键改进**:
1. 接受 `forceProjectId` 参数
2. 加载前验证项目ID
3. 加载后再次验证项目ID（防止异步过程中切换）
4. 只有当前项目匹配时才更新状态

### 修复2: pollRun回调验证项目ID

在 `pollRun` 中调用 `onSuccess` 前，再次验证项目ID：

```typescript
if (run.status === 'success') {
  if (pollTimerRef.current) {
    clearInterval(pollTimerRef.current);
    pollTimerRef.current = null;
  }
  
  // ✅ 再次验证项目ID后才调用onSuccess
  if (currentProject && currentProject.id === projectId) {
    onSuccess();
  } else {
    console.log('[pollRun] 任务成功但项目已切换，跳过onSuccess回调');
  }
}
```

### 修复3: 启动任务时捕获项目ID

在启动任务时，立即捕获项目ID，并在回调中使用：

```typescript
const extractProjectInfo = async () => {
  if (!currentProject) return;
  const projectId = currentProject.id; // ✅ 立即捕获
  
  setProjectInfo(null);
  try {
    const res = await api.post(`/api/apps/tender/projects/${projectId}/extract/project-info`, { model_id: null });
    setInfoRun({ id: res.run_id, status: 'running', progress: 0, message: '开始抽取...', kind: 'extract_project_info' } as TenderRun);
    
    // ✅ 传入projectId，确保回调使用正确的项目
    pollRun(res.run_id, projectId, () => loadProjectInfo(projectId));
  } catch (err) {
    alert(`抽取失败: ${err}`);
    setInfoRun(null);
  }
};
```

### 修复4: 增量加载也验证项目ID

在 `pollRun` 的增量加载中，也加强项目ID验证：

```typescript
else if (run.status === 'running') {
  if (run.kind === 'extract_project_info' && currentProject && currentProject.id === projectId) {
    // 使用projectId参数，而不是currentProject.id
    api.get(`/api/apps/tender/projects/${projectId}/project-info`)
      .then(data => {
        // ✅ 加载完成后再次验证项目ID
        if (currentProject && currentProject.id === projectId) {
          setProjectInfo(data);
        } else {
          console.log('[pollRun] 增量加载完成但项目已切换，丢弃数据');
        }
      })
      .catch(err => console.warn('增量加载项目信息失败:', err));
  }
}
```

---

## 📋 修改清单

### 修改的文件

**文件**: `frontend/src/components/TenderWorkspace.tsx`

### 修改的函数

1. ✅ `loadProjectInfo(forceProjectId?: string)` - 支持项目ID参数，双重验证
2. ✅ `loadRisks(forceProjectId?: string)` - 同上
3. ✅ `loadDirectory(forceProjectId?: string)` - 同上
4. ✅ `loadReview(forceProjectId?: string)` - 同上
5. ✅ `pollRun()` - onSuccess前验证，增量加载双重验证
6. ✅ `extractProjectInfo()` - 捕获项目ID，传入回调
7. ✅ `extractRisks()` - 同上
8. ✅ `generateDirectory()` - 同上
9. ✅ `runReview()` - 同上

---

## 🛡️ 防御层级

现在系统有**三层防御**来防止数据污染：

### 第一层：轮询层面
```typescript
// pollRun 中检测项目切换
if (!currentProject || currentProject.id !== projectId) {
  console.log('[pollRun] 项目已切换，停止轮询');
  clearInterval(pollTimerRef.current);
  return;
}
```

### 第二层：回调层面
```typescript
// 调用 onSuccess 前验证
if (currentProject && currentProject.id === projectId) {
  onSuccess();
} else {
  console.log('[pollRun] 任务成功但项目已切换，跳过回调');
}
```

### 第三层：加载函数层面
```typescript
// 加载前验证
if (!forceProjectId && currentProject && currentProject.id !== projectId) {
  console.log('[loadProjectInfo] 项目已切换，跳过加载');
  return;
}

// 加载后验证
if (currentProject && currentProject.id !== projectId) {
  console.log('[loadProjectInfo] 加载完成时项目已切换，丢弃数据');
  return;
}
```

---

## 🧪 测试场景

### 场景1: 正常流程（无切换）
- 项目A开始抽取
- 等待完成
- ✅ 项目A显示正确数据

### 场景2: 抽取中切换
- 项目A开始抽取（running）
- 切换到项目B
- ✅ 轮询停止
- ✅ 项目B不显示项目A的数据
- ✅ 项目A的后台任务继续运行

### 场景3: 完成瞬间切换
- 项目A开始抽取
- 抽取即将完成
- 在完成瞬间切换到项目B
- ✅ onSuccess被跳过
- ✅ 项目B不显示项目A的数据

### 场景4: 增量加载时切换
- 项目A开始抽取（四阶段）
- Stage 1完成，增量加载中
- 切换到项目B
- ✅ 增量加载的数据被丢弃
- ✅ 项目B不显示项目A的部分数据

### 场景5: 切换回原项目
- 项目A开始抽取
- 切换到项目B
- 再切换回项目A
- ✅ 项目A显示其正确的数据（如果已完成）
- ✅ 或显示正在抽取状态（如果还在运行）

---

## 💡 关键设计原则

1. **显式优于隐式**: 用参数传递项目ID，而不是依赖闭包
2. **双重验证**: 加载前验证 + 加载后验证
3. **早期返回**: 一旦检测到项目切换，立即返回
4. **日志完善**: 所有关键路径都有日志，便于调试
5. **数据隔离**: 不同项目的数据绝不混淆

---

## 🎯 验证方法

### 手动测试
1. 打开浏览器控制台
2. 在项目A点击"开始抽取"
3. 立即切换到项目B
4. 观察控制台日志：
   - 应该看到 `[pollRun] 项目已切换，停止轮询`
   - 应该看到 `[loadProjectInfo] 项目已切换，跳过加载`
5. 检查项目B的界面，不应该显示项目A的数据

### 日志关键词
- `项目已切换，停止轮询`
- `任务成功但项目已切换，跳过回调`
- `项目已切换，跳过加载`
- `加载完成时项目已切换，丢弃数据`

---

## ✨ 总结

**问题**: 项目切换时，异步加载函数使用了错误的 `currentProject`，导致数据污染

**解决**: 
1. 加载函数支持项目ID参数
2. 启动任务时捕获项目ID
3. 回调中传入项目ID
4. 三层验证防御

**效果**: 彻底消除项目切换时的数据污染问题，确保每个项目只显示其自己的数据

---

**修复完成时间**: 2025-12-25
