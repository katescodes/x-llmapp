# Step3 目录展示重构说明

## 改造目标

将 Step3 的目录展示统一改成一个只读富文本框（白底），支持按"是否选择格式模板"在同一框内切换样式。不再有单独预览区/表格展示。

## 已完成的修改

### 1. 新增组件：`RichTocBox`

**文件位置**：`frontend/src/components/step3/RichTocBox.tsx`

**功能特性**：
- ✅ 白底固定，不跟模板底色走
- ✅ 只读富文本展示（可复制文本）
- ✅ 使用 HTML 段落渲染目录行（缩进 + 点引导线）
- ✅ 通过 CSS 变量（`TocStyleVars`）切换样式
- ✅ 支持默认样式和模板样式的无缝切换

**类型定义**：
```typescript
export type TocItem = {
  id: string;
  level: number;      // 1,2,3...
  orderNo?: string;   // "1", "1.1"...
  title: string;
};

export type TocStyleVars = {
  fontFamily?: string;
  fontSizePx?: number;
  lineHeight?: number;
  lvl1Bold?: boolean;
  lvl1FontSizePx?: number;
  indent1Px?: number;
  indent2Px?: number;
  indent3Px?: number;
};
```

### 2. 修改 `DirectoryToolbar`

**文件位置**：`frontend/src/components/tender/DirectoryToolbar.tsx`

**修改内容**：
- ✅ 移除 `onPreview` 回调和"预览目录"按钮
- ✅ 下拉框第一项改为"（不使用格式）"
- ✅ 更新说明文案：强调实时样式切换

### 3. 修改 `TenderWorkspace` Step3 逻辑

**文件位置**：`frontend/src/components/TenderWorkspace.tsx`

**修改内容**：

#### 3.1 导入更新
```typescript
import RichTocBox, { TocItem as RichTocItem, TocStyleVars } from './step3/RichTocBox';
```

#### 3.2 状态管理
- ✅ 移除 `previewNodes` 和 `previewOpen` 状态
- ✅ 移除 `currentTemplateStyle` 状态
- ✅ 新增 `tocStyleVars` 状态（TocStyleVars | undefined）

#### 3.3 模板处理逻辑
- ✅ 新增 `handleTemplateChange` 函数：
  - 选择模板时：调用预览接口获取 `style_hints`，解析并映射为 `TocStyleVars`
  - 清空模板时：设置 `tocStyleVars` 为 `undefined`，回到默认样式
- ✅ 移除 `previewTemplate` 函数
- ✅ 更新 `applyTemplate` 函数：套用后重新加载样式

#### 3.4 渲染更新
- ✅ 移除预览面板的双栏布局
- ✅ 使用单一 `RichTocBox` 组件展示目录
- ✅ 目录数据映射：`DirectoryNode` → `RichTocItem`
- ✅ 传递 `tocStyleVars` 到 `RichTocBox`

## 功能验证点

### 自动生成目录
- [ ] 点击"从招标生成目录"
- [ ] 同一富文本框立即显示（默认样式：白底、默认字体、默认缩进）

### 选择模板
- [ ] 在下拉框选择任意模板
- [ ] 同一富文本框内字体/字号/缩进/加粗实时切换
- [ ] 白底保持不变

### 清空模板
- [ ] 选择"（不使用格式）"
- [ ] 同一富文本框立刻回到默认样式

### 套用模板
- [ ] 选择模板后点击"套用模板"
- [ ] 目录结构被替换为模板大纲
- [ ] 样式保持模板样式

### 导出 DOCX
- [ ] 导出功能正常工作
- [ ] 导出的文件包含正确的样式

## 技术亮点

1. **样式隔离**：富文本框固定白底，不受模板底色影响
2. **实时切换**：通过 CSS 变量实现样式的即时切换，无需重新渲染
3. **默认样式**：未选择模板时自动应用默认样式（宋体、14px、标准缩进）
4. **可复制**：`user-select: text` 支持用户复制目录内容
5. **无 table**：纯 `<p>` 标签实现，更符合 Word 目录的展示方式

## 后续建议

1. 如果需要支持页码显示，可在 `TocItem` 中添加 `pageNo` 字段
2. 如果需要更多层级（当前支持 lvl-1/2/3），可扩展 CSS 和 `TocStyleVars`
3. 可考虑添加"恢复默认样式"按钮，快速清空模板选择



