# 申报书工作台重构 V2

## 修改说明

根据用户反馈，需要优化操作逻辑：

1. **项目管理改为弹窗式**
   - 右上角显示"新建项目"按钮
   - 点击后弹出新建项目表单（可折叠）
   - 项目列表以卡片网格形式展示

2. **点击项目进入项目详情**
   - 参照招投标的项目管理模式
   - 点击项目卡片后进入该项目的工作区
   - 显示该项目的完整工作流程

## 实现要点

### 布局结构
- 左侧：导航栏（只显示"项目管理"按钮）
- 中间：根据视图模式显示不同内容
  - `projectList` 视图：项目列表 + 新建表单
  - `projectDetail` 视图：项目详情 + 工作流程（Step1-4）

### 视图切换
```typescript
type ViewMode = 'projectList' | 'projectDetail';
const [viewMode, setViewMode] = useState<ViewMode>('projectList');
```

### 项目选择逻辑
```typescript
// 点击项目卡片
const handleSelectProject = (project) => {
  setCurrentProject(project);
  setViewMode('projectDetail'); // 切换到详情视图
  // 加载项目数据...
};

// 返回项目列表
const handleBackToList = () => {
  setViewMode('projectList');
  setCurrentProject(null);
};
```

## 需要修改的文件

- `frontend/src/components/DeclareWorkspace.tsx`

## 关键代码片段

参照 `TenderWorkspace.tsx` 的实现：
- 行 2187-2212：页面标题 + 新建项目按钮
- 行 2215-2264：可折叠的创建项目表单
- 行 2266-2322：项目卡片网格布局

## 注意事项

由于代码结构复杂，建议分步实施：
1. 先添加 viewMode 状态
2. 修改项目选择逻辑
3. 调整UI布局（参照TenderWorkspace）
4. 测试所有功能是否正常

## 当前状态

- ❌ 构建失败（JSX语法错误）
- 需要重新实现，更小心处理JSX结构

