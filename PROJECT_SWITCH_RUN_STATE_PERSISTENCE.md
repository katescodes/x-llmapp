# 项目切换Run状态持久化修复

**问题时间**: 2025-12-25  
**问题描述**: 切换项目后再切换回来，按钮变为"开始抽取"（可用），但后台实际还在运行抽取任务

---

## 🐛 问题根源

### 原始逻辑（有问题）

```typescript
const selectProject = (proj: TenderProject) => {
  // 停止轮询
  clearInterval(pollTimerRef.current);
  
  // 切换项目
  setCurrentProject(proj);
  
  // ❌ 清空所有run状态
  setInfoRun(null);
  setRiskRun(null);
  setDirRun(null);
  setReviewRun(null);
  
  // 清空数据
  setProjectInfo(null);
  // ...
};
```

### 问题场景

1. 项目A开始抽取 → `infoRun = { status: 'running', id: 'run-A-123' }`
2. 切换到项目B → `setInfoRun(null)` → 状态丢失 ❌
3. 切换回项目A → `infoRun = null` → 按钮显示"开始抽取" ❌
4. 但后台任务`run-A-123`还在运行 → 数据不一致 ❌

### 核心问题

**切换项目时清空了run状态，导致：**
- 切换回项目时，不知道该项目是否有正在运行的任务
- 按钮状态错误（显示可用，实际不可用）
- 轮询丢失（无法继续跟踪后台任务）
- 用户可能重复点击"开始抽取"，导致多个任务并行

---

## ✅ 解决方案

### 核心思路

**使用缓存保存每个项目的run状态，切换项目时不丢失**

### 实现步骤

#### 1. 添加run状态缓存

```typescript
// ✅ 使用useRef存储Map，避免重渲染
const projectRunsCacheRef = useRef<Map<string, {
  infoRun: TenderRun | null;
  riskRun: TenderRun | null;
  dirRun: TenderRun | null;
  reviewRun: TenderRun | null;
}>>(new Map());
```

**为什么用useRef而不是useState？**
- `useState`会触发重渲染，增加性能开销
- `useRef`仅用于缓存，不需要触发UI更新
- Map的修改不会导致组件重渲染

#### 2. 自动保存run状态

```typescript
const saveCurrentProjectRuns = useCallback(() => {
  if (!currentProject) return;
  projectRunsCacheRef.current.set(currentProject.id, {
    infoRun,
    riskRun,
    dirRun,
    reviewRun,
  });
  console.log('[saveCurrentProjectRuns] 已保存项目run状态:', currentProject.id);
}, [currentProject, infoRun, riskRun, dirRun, reviewRun]);

// ✅ 每次run状态变化时，自动保存
useEffect(() => {
  if (currentProject) {
    saveCurrentProjectRuns();
  }
}, [infoRun, riskRun, dirRun, reviewRun, currentProject, saveCurrentProjectRuns]);
```

#### 3. 恢复run状态

```typescript
const restoreProjectRuns = useCallback((projectId: string) => {
  const cached = projectRunsCacheRef.current.get(projectId);
  if (cached) {
    console.log('[restoreProjectRuns] 恢复项目run状态:', projectId, cached);
    setInfoRun(cached.infoRun);
    setRiskRun(cached.riskRun);
    setDirRun(cached.dirRun);
    setReviewRun(cached.reviewRun);
    return cached;
  } else {
    console.log('[restoreProjectRuns] 无缓存，清空run状态');
    setInfoRun(null);
    setRiskRun(null);
    setDirRun(null);
    setReviewRun(null);
    return null;
  }
}, []);
```

#### 4. 重构selectProject

```typescript
const selectProject = (proj: TenderProject) => {
  console.log('[selectProject] 切换项目:', { from: currentProject?.id, to: proj.id });
  
  // ✅ 1. 保存当前项目的run状态
  saveCurrentProjectRuns();
  
  // ✅ 2. 停止正在进行的轮询
  if (pollTimerRef.current) {
    clearInterval(pollTimerRef.current);
    pollTimerRef.current = null;
  }
  
  // ✅ 3. 更新当前项目
  setCurrentProject(proj);
  
  // ✅ 4. 清空数据状态（但不清空run状态）
  setProjectInfo(null);
  setRisks([]);
  // ...
  
  // ✅ 5. 恢复目标项目的run状态
  restoreProjectRuns(proj.id);
};
```

#### 5. 自动恢复轮询

```typescript
// ✅ 当项目切换且run状态恢复后，自动恢复running任务的轮询
useEffect(() => {
  if (!currentProject) return;
  
  const projectId = currentProject.id;
  
  // 恢复各个running任务的轮询
  if (infoRun?.status === 'running' && infoRun.id) {
    console.log('[useEffect] 恢复项目信息抽取轮询:', infoRun.id);
    pollRun(infoRun.id, projectId, () => loadProjectInfo(projectId));
  }
  
  if (riskRun?.status === 'running' && riskRun.id) {
    console.log('[useEffect] 恢复风险识别轮询:', riskRun.id);
    pollRun(riskRun.id, projectId, () => loadRisks(projectId));
  }
  
  if (dirRun?.status === 'running' && dirRun.id) {
    console.log('[useEffect] 恢复目录生成轮询:', dirRun.id);
    pollRun(dirRun.id, projectId, async () => {
      const nodes = await loadDirectory(projectId);
      if (nodes.length > 0) {
        await loadBodiesForAllNodes(nodes);
      }
      await loadSampleFragments();
    });
  }
  
  if (reviewRun?.status === 'running' && reviewRun.id) {
    console.log('[useEffect] 恢复审核轮询:', reviewRun.id);
    pollRun(reviewRun.id, projectId, () => loadReview(projectId));
  }
}, [currentProject, infoRun?.id, riskRun?.id, dirRun?.id, reviewRun?.id]);
```

**为什么只监听run的id？**
- 避免监听整个run对象（如`infoRun`），否则每次status/progress变化都会触发
- 只监听`id`变化，即只在切换项目或启动新任务时触发
- 减少不必要的重复恢复轮询

---

## 📋 修改清单

### 修改的文件

**文件**: `frontend/src/components/TenderWorkspace.tsx`

### 新增内容

1. ✅ `projectRunsCacheRef` - run状态缓存（useRef + Map）
2. ✅ `saveCurrentProjectRuns()` - 保存当前项目run状态
3. ✅ `restoreProjectRuns(projectId)` - 恢复指定项目run状态
4. ✅ `useEffect` - 自动保存run状态
5. ✅ `useEffect` - 自动恢复轮询

### 修改内容

6. ✅ `selectProject()` - 切换项目时保存&恢复状态，不再清空run

---

## 🔄 工作流程

### 完整流程图

```
1. 用户在项目A点击"开始抽取"
   → infoRun = { status: 'running', id: 'run-A-123' }
   → pollRun启动
   → 自动保存到cache: Map { 'A' => { infoRun: {...} } }

2. 用户切换到项目B
   → selectProject(B)
   → saveCurrentProjectRuns() // 保存A的状态
   → clearInterval(pollTimerRef) // 停止A的轮询
   → setCurrentProject(B)
   → restoreProjectRuns('B') // 恢复B的状态（可能为null）
   → setInfoRun(null) // B之前没有任务
   → useEffect触发：无running任务，不恢复轮询

3. 用户切换回项目A
   → selectProject(A)
   → saveCurrentProjectRuns() // 保存B的状态（null）
   → clearInterval(pollTimerRef) // 停止（实际没有）
   → setCurrentProject(A)
   → restoreProjectRuns('A') // ✅ 恢复A的状态
   → setInfoRun({ status: 'running', id: 'run-A-123' })
   → useEffect触发：检测到running，恢复轮询
   → pollRun('run-A-123', 'A', ...)
   → ✅ 按钮显示"抽取中..."，轮询继续

4. 项目A的任务完成
   → pollRun检测到status='success'
   → setInfoRun({ status: 'success', id: 'run-A-123' })
   → 自动保存到cache
   → ✅ 按钮变为可用，显示"开始抽取"

5. 用户再次切换到项目A
   → restoreProjectRuns('A')
   → setInfoRun({ status: 'success', id: 'run-A-123' })
   → useEffect触发：status≠'running'，不恢复轮询
   → ✅ 按钮显示"开始抽取"（正确，因为已完成）
```

---

## 🎯 关键改进

| 改进点 | 修复前 | 修复后 |
|--------|--------|--------|
| **状态持久化** | ❌ 切换项目丢失run状态 | ✅ 缓存保存，永不丢失 |
| **轮询恢复** | ❌ 切换回来轮询停止 | ✅ 自动恢复running任务轮询 |
| **按钮状态** | ❌ 显示错误（可用/不可用） | ✅ 始终正确 |
| **数据污染** | ✅ 已通过前一次修复解决 | ✅ 保持解决 |
| **用户体验** | ❌ 困惑（看起来可以操作，实际不行） | ✅ 清晰（状态一致） |

---

## 🧪 测试场景

### 场景1: 正常切换（无任务）
1. 项目A（无任务）
2. 切换到项目B
3. 切换回项目A
4. ✅ 按钮显示"开始抽取"

### 场景2: 切换后恢复（running）
1. 项目A开始抽取（running）
2. 切换到项目B
3. 切换回项目A
4. ✅ 按钮显示"抽取中..."
5. ✅ 轮询自动恢复
6. ✅ 数据增量更新

### 场景3: 切换后恢复（success）
1. 项目A抽取完成（success）
2. 切换到项目B
3. 切换回项目A
4. ✅ 按钮显示"开始抽取"
5. ✅ 不恢复轮询（因为已完成）

### 场景4: 多次切换
1. 项目A开始抽取
2. 切换到项目B
3. 项目B开始抽取
4. 切换到项目C
5. 切换回项目A → ✅ 显示A的状态
6. 切换到项目B → ✅ 显示B的状态
7. ✅ 每个项目状态独立且正确

### 场景5: 重复启动防护
1. 项目A开始抽取
2. 切换到项目B
3. 切换回项目A
4. ✅ 按钮禁用（因为running）
5. ❌ 无法重复点击

---

## 💡 设计原则

1. **状态与UI一致**: 按钮状态始终反映真实的任务状态
2. **自动化优先**: 自动保存、自动恢复，无需手动操作
3. **缓存轻量**: 使用useRef+Map，避免不必要的重渲染
4. **日志完善**: 所有关键操作都有日志，便于调试
5. **向后兼容**: 现有功能不受影响，仅增强切换逻辑

---

## 🔍 调试方法

### 查看缓存内容

在浏览器控制台：
```javascript
// 注意：projectRunsCacheRef是私有的，但可以通过React DevTools查看
// 或者在代码中添加临时调试：
console.log('缓存内容:', Array.from(projectRunsCacheRef.current.entries()));
```

### 关键日志

- `[saveCurrentProjectRuns] 已保存项目run状态`
- `[restoreProjectRuns] 恢复项目run状态`
- `[restoreProjectRuns] 无缓存，清空run状态`
- `[useEffect] 恢复项目信息抽取轮询`
- `[selectProject] 切换项目`

---

## ✨ 总结

**问题**: 切换项目时清空run状态，导致切换回来后状态丢失

**解决**: 
1. 添加run状态缓存（useRef + Map）
2. 切换前自动保存
3. 切换后自动恢复
4. 自动恢复running任务的轮询

**效果**: 
- ✅ 项目状态完全隔离
- ✅ 切换项目无状态丢失
- ✅ 按钮状态始终正确
- ✅ 轮询自动恢复
- ✅ 用户体验流畅

---

**修复完成时间**: 2025-12-25
