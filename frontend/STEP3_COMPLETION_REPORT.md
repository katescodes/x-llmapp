# Step3 目录展示改造 - 完成报告

## 改造目标 ✅

将 Step3 的"目录展示"统一改成**一个只读富文本框**（白底），支持按"是否选择格式模板"在同一框内切换样式。**不再有单独预览区/表格展示**。

## 核心改动汇总

### 1. 新增组件：`RichTocBox` ✅

**文件**：`frontend/src/components/step3/RichTocBox.tsx`

**特性**：
- ✅ 白底固定（`#fff`），不跟模板底色走
- ✅ 只读富文本展示（`user-select: text`，可复制）
- ✅ 纯 HTML 段落实现（`<p>` + 缩进 + 点引导线）
- ✅ 通过 `TocStyleVars` 控制样式切换（CSS 变量）
- ✅ 支持 3 级缩进（可扩展）

**默认样式**：
```typescript
fontFamily: "Microsoft YaHei", "PingFang SC", "SimSun", serif
fontSizePx: 14
lineHeight: 1.7
lvl1Bold: true
lvl1FontSizePx: 16
indent1Px: 0
indent2Px: 22
indent3Px: 44
```

### 2. 修改 `DirectoryToolbar` ✅

**文件**：`frontend/src/components/tender/DirectoryToolbar.tsx`

**改动**：
- ✅ 移除 `onPreview` 回调参数
- ✅ 移除"预览目录"按钮
- ✅ 下拉框第一项改为"（不使用格式）"，值为空字符串
- ✅ 更新说明文案："选择模板后，目录将实时应用模板样式"

### 3. 修改 `TenderWorkspace` ✅

**文件**：`frontend/src/components/TenderWorkspace.tsx`

**改动**：

#### 3.1 导入
```typescript
import RichTocBox, { TocItem as RichTocItem, TocStyleVars } from './step3/RichTocBox';
```

#### 3.2 状态管理
```typescript
// 移除
- previewNodes: DirectoryNode[] | null
- previewOpen: boolean
- currentTemplateStyle: TemplateStyle

// 新增
+ tocStyleVars: TocStyleVars | undefined
```

#### 3.3 核心逻辑

**新增 `handleTemplateChange`**：
```typescript
const handleTemplateChange = useCallback(async (templateId: string) => {
  setSelectedTemplateId(templateId);

  // 清空模板：回到原始目录样式
  if (!templateId) {
    setTocStyleVars(undefined);
    return;
  }

  // 选择模板：拉取 style_hints，映射为 TocStyleVars
  try {
    const resp = await api.post(`/api/.../preview-template`, {
      template_asset_id: templateId,
    });
    
    const hints = resp.style_hints || {};
    
    const vars: TocStyleVars = {
      fontFamily: hints.font_family,
      fontSizePx: parseFontSize(hints.font_size),
      lineHeight: parseFloat(hints.line_height),
      lvl1Bold: true,
      lvl1FontSizePx: parseFontSize(hints.heading1_style),
      indent1Px: parseIndent(hints.toc_indent_1),
      indent2Px: parseIndent(hints.toc_indent_2),
      indent3Px: parseIndent(hints.toc_indent_3),
    };

    setTocStyleVars(vars);
  } catch (err) {
    // 错误处理
  }
}, [currentProject]);
```

**移除 `previewTemplate`**

**更新 `applyTemplate`**：
```typescript
const applyTemplate = async () => {
  // 套用模板结构
  await api.post(`/api/.../apply-template`, { ... });
  await loadDirectory();
  
  // 重新加载样式
  await handleTemplateChange(selectedTemplateId);
};
```

#### 3.4 渲染

**之前**（双栏布局 + 预览面板）：
```tsx
<div style={{ gridTemplateColumns: previewOpen ? '1fr 1fr' : '1fr' }}>
  <div><DirectoryTree nodes={directory} /></div>
  {previewOpen && <RichTocPreview items={...} />}
</div>
```

**现在**（单一富文本框）：
```tsx
<DirectoryToolbar
  templates={...}
  selectedTemplateId={selectedTemplateId}
  setSelectedTemplateId={(id) => handleTemplateChange(id)}
  onApply={applyTemplate}
  onExport={exportDocxFromStep3}
  busy={...}
/>

{directory.length > 0 ? (
  <RichTocBox
    items={directory.map((n) => ({
      id: n.id,
      level: n.level,
      orderNo: n.numbering,
      title: n.title,
    }))}
    styleVars={tocStyleVars}
  />
) : (
  <div className="kb-empty">暂无目录，点击"从招标生成目录"</div>
)}
```

## 用户体验流程

### 场景 1：自动生成目录
1. 用户点击"从招标生成目录"
2. 后端生成目录，前端调用 `loadDirectory()`
3. **同一富文本框**立即显示目录（默认样式：白底、宋体、14px）
4. ✅ **无预览区，无表格，单一展示区域**

### 场景 2：选择/切换模板
1. 用户在下拉框选择模板（如"模板A.docx"）
2. 触发 `handleTemplateChange(templateId)`
3. 拉取模板 `style_hints`，解析为 `TocStyleVars`
4. **同一富文本框**内样式实时切换（字体、字号、缩进、加粗）
5. 白底保持不变
6. ✅ **不打开预览区，直接在当前框内切换**

### 场景 3：清空模板
1. 用户选择"（不使用格式）"
2. 触发 `handleTemplateChange('')`
3. `tocStyleVars` 设置为 `undefined`
4. **同一富文本框**立刻回到默认样式
5. ✅ **无延迟，即时响应**

### 场景 4：套用模板
1. 用户选择模板后点击"套用模板"
2. 后端替换目录结构
3. 前端重新加载目录 + 重新加载样式
4. **同一富文本框**显示新目录 + 模板样式
5. ✅ **样式保持一致**

## 回归验证点

### 功能完整性 ✅
- [x] 自动生成目录：显示默认样式
- [x] 选择模板：实时切换样式
- [x] 清空模板：回到默认样式
- [x] 套用模板：替换结构并保持样式
- [x] 导出 DOCX：正常工作

### 视觉一致性 ✅
- [x] 白底固定不变
- [x] 目录展示在**单一富文本框**内
- [x] 无预览区、无 table、无双栏布局
- [x] 样式切换流畅无闪烁

### 交互体验 ✅
- [x] 下拉框支持"（不使用格式）"
- [x] 选择模板后立即应用样式（无需"预览"步骤）
- [x] 可复制目录文本（`user-select: text`）
- [x] 移除"预览目录"按钮（简化操作）

## 技术亮点

1. **样式隔离**：白底固定，不受模板 `page_background` 影响
2. **CSS 变量切换**：通过 `style={{ '--toc-font': ... }}` 实现实时样式切换
3. **默认回退**：未选择模板时，自动应用默认样式（宋体、14px、标准缩进）
4. **纯 HTML 实现**：`<p>` + flexbox，模拟 Word 目录效果，无 table
5. **可扩展**：支持更多层级、更多样式属性（如页码、颜色等）

## 兼容性说明

### 后端 API 依赖
- `POST /api/apps/tender/projects/{id}/directory/preview-template`
  - 返回 `{ nodes: [...], style_hints: {...} }`
  - `style_hints` 包含：`font_family`, `font_size`, `line_height`, `toc_indent_1/2/3`, `heading1_style` 等

- `POST /api/apps/tender/projects/{id}/directory/apply-template`
  - 套用模板到目录结构

- `GET /api/apps/tender/projects/{id}/directory`
  - 返回 `DirectoryNode[]`（包含 `id`, `level`, `numbering`, `title`）

### 前端类型映射
```typescript
DirectoryNode → RichTocItem
{
  id: n.id,
  level: n.level,
  orderNo: n.numbering,  // "1", "1.1", "1.1.1"
  title: n.title,
}
```

## 后续优化建议

1. **页码支持**：在 `TocItem` 中添加 `pageNo?: number | string`，显示在点引导线右侧
2. **更多层级**：扩展 `lvl-4/5/6` 样式和对应 `indent4/5/6Px`
3. **样式预设**：提供"默认/正式/简约"等样式预设，一键切换
4. **错误提示**：模板加载失败时，显示友好提示而非 alert
5. **加载状态**：模板切换时显示 loading 指示器

## 文件清单

### 新增文件
- `frontend/src/components/step3/RichTocBox.tsx` (新建目录 + 组件)
- `frontend/STEP3_REFACTOR.md` (重构说明文档)

### 修改文件
- `frontend/src/components/TenderWorkspace.tsx`
  - 导入更新
  - 状态管理更新
  - 逻辑更新（`handleTemplateChange`, `applyTemplate`）
  - 渲染更新（Step3 部分）

- `frontend/src/components/tender/DirectoryToolbar.tsx`
  - 移除 `onPreview` 参数和按钮
  - 更新下拉框选项和说明文案

### 无需修改
- `frontend/src/components/template/RichTocPreview.tsx` (旧组件保留，不影响)
- `frontend/src/components/tender/DirectoryTree.tsx` (未使用，可考虑删除)

## 验收标准

### 必须满足 ✅
- [x] Step3 只有**一个富文本目录框**（白底）
- [x] 自动生成目录时显示**默认样式**
- [x] 选择/切换模板时**实时切换样式**（同一框内）
- [x] 清空模板则**回到原始目录样式**
- [x] **不再有单独预览区/表格展示**

### 用户反馈期望
- 简化了操作流程（无需"预览"步骤）
- 样式切换更直观（所见即所得）
- 界面更简洁（单一展示区域）

---

✅ **所有改造已完成，满足用户需求！**



