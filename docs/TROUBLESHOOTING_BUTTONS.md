# 招投标自定义规则和用户文档按钮显示问题排查

## 问题描述
在招投标工作台左侧边栏看不到"自定义规则"和"用户文档"按钮。

## 排查步骤

### 1. 确认前端代码已更新
```bash
cd /aidata/x-llmapp1/frontend
git status
# 查看 TenderWorkspace.tsx 是否有修改
```

### 2. 重新编译前端
```bash
cd /aidata/x-llmapp1/frontend

# 开发模式（推荐）
npm start

# 或者生产构建
npm run build
```

### 3. 清除浏览器缓存
- **Chrome/Edge**: Ctrl + Shift + Delete → 清除缓存
- **强制刷新**: Ctrl + Shift + R (Windows) 或 Cmd + Shift + R (Mac)

### 4. 检查控制台错误
1. 打开浏览器开发者工具 (F12)
2. 切换到 Console 标签
3. 刷新页面，查看是否有红色错误信息
4. 特别关注：
   - `Cannot find module 'CustomRulesPage'`
   - `Cannot find module 'UserDocumentsPage'`
   - React 组件加载错误

### 5. 验证文件存在
```bash
# 检查组件文件是否存在
ls -la /aidata/x-llmapp1/frontend/src/components/CustomRulesPage.tsx
ls -la /aidata/x-llmapp1/frontend/src/components/UserDocumentsPage.tsx
```

### 6. 检查访问路径
确认你访问的是正确的页面：
- ✅ 正确：`http://localhost:3000` → 导航栏点击"招投标"
- ❌ 错误：其他知识库或文档管理页面

### 7. 查看按钮位置
按钮应该在：
```
招投标工作台
├── [左侧边栏顶部]
│   ├── 📋 格式模板 (紫色)
│   ├── ⚙️ 自定义规则 (粉色)
│   └── 📁 用户文档 (橙色)
├── [新建项目表单]
└── [项目列表]
```

### 8. 检查 CSS 样式
在浏览器开发者工具中：
1. 按 F12 打开开发者工具
2. 点击左上角的"选择元素"图标
3. 查看左侧边栏，看是否有隐藏的按钮
4. 检查 CSS 属性：
   - `display: none`
   - `visibility: hidden`
   - `opacity: 0`

### 9. 手动验证按钮代码
在浏览器控制台执行：
```javascript
// 检查组件是否加载
console.log('CustomRulesPage:', typeof CustomRulesPage);
console.log('UserDocumentsPage:', typeof UserDocumentsPage);

// 检查 viewMode 状态
console.log('Current viewMode:', window.location.pathname);
```

### 10. 检查网络请求
1. 打开开发者工具 → Network 标签
2. 刷新页面
3. 查看是否有 JavaScript 加载失败（404 错误）

## 临时解决方案

### 方案1: 直接访问组件（测试用）
如果按钮不显示，可以暂时修改代码强制显示：

1. 打开浏览器控制台 (F12)
2. 在 Console 中执行：
```javascript
// 强制切换到自定义规则视图
setViewMode("customRules");

// 或者强制切换到用户文档视图
setViewMode("userDocuments");
```

### 方案2: 检查 React DevTools
1. 安装 React Developer Tools 浏览器插件
2. 打开插件，查看组件树
3. 搜索 `TenderWorkspace` 组件
4. 查看 `viewMode` 状态值
5. 查看按钮是否在 DOM 树中

## 预期结果

正常情况下，应该看到：

```
┌─────────────────────────────┐
│   招投标工作台               │
│   项目管理 + 风险识别 + ...  │
│                             │
│  ┌───────────────────────┐  │
│  │ 📋 格式模板           │  │  ← 紫色渐变按钮
│  └───────────────────────┘  │
│                             │
│  ┌───────────────────────┐  │
│  │ ⚙️ 自定义规则         │  │  ← 粉色渐变按钮
│  └───────────────────────┘  │
│                             │
│  ┌───────────────────────┐  │
│  │ 📁 用户文档           │  │  ← 橙色渐变按钮
│  └───────────────────────┘  │
│                             │
│  [新建项目表单]             │
│  [项目列表]                 │
└─────────────────────────────┘
```

## 常见问题

### Q1: 按钮点击没反应
**A**: 检查是否已选择项目。"自定义规则"和"用户文档"需要先选择项目。

### Q2: 只看到"格式模板"按钮
**A**: 检查前端代码是否最新，确认已包含最新的修改。

### Q3: 控制台报错 "Cannot read property 'id' of null"
**A**: 这是正常的，因为按钮要求先选择项目。选择一个项目后再点击。

### Q4: 按钮样式不对
**A**: 清除浏览器缓存，重新加载 CSS 文件。

## 联系支持

如果以上步骤都无法解决问题，请提供：
1. 浏览器控制台的完整错误信息（截图）
2. 前端构建日志
3. 访问的完整URL
4. 浏览器版本信息

## 快速验证命令

一键执行所有检查：
```bash
#!/bin/bash
echo "=== 检查文件存在性 ==="
ls -la /aidata/x-llmapp1/frontend/src/components/CustomRulesPage.tsx
ls -la /aidata/x-llmapp1/frontend/src/components/UserDocumentsPage.tsx

echo -e "\n=== 检查导入语句 ==="
grep -n "CustomRulesPage\|UserDocumentsPage" /aidata/x-llmapp1/frontend/src/components/TenderWorkspace.tsx

echo -e "\n=== 检查按钮代码 ==="
grep -n "自定义规则\|用户文档" /aidata/x-llmapp1/frontend/src/components/TenderWorkspace.tsx

echo -e "\n=== 检查前端进程 ==="
ps aux | grep "react-scripts\|npm"

echo -e "\n=== 完成 ==="
```

