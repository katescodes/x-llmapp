import type { TocItem, TemplateStyle } from "./RichTocPreview";

type OutlineNodeLike = {
  title?: string;
  level?: number;
  order_no?: number;
  orderNo?: number;
  children?: OutlineNodeLike[];
};

function asArray<T>(v: any): T[] {
  return Array.isArray(v) ? (v as T[]) : [];
}

function sortByOrderNo(nodes: OutlineNodeLike[]): OutlineNodeLike[] {
  return [...nodes].sort((a, b) => {
    const ao = Number(a?.order_no ?? a?.orderNo ?? 0);
    const bo = Number(b?.order_no ?? b?.orderNo ?? 0);
    return ao - bo;
  });
}

/**
 * 将 TemplateSpec（后端 /format-templates/{id}/spec 返回）转换为 RichTocPreview 所需 items。
 * 规则：按 outline 的层级生成类似 1 / 1.1 / 1.1.1 的编号。
 */
export function templateSpecToTocItems(spec: any): TocItem[] {
  const outline = asArray<OutlineNodeLike>(spec?.outline);
  const counters: number[] = [];
  const items: TocItem[] = [];

  const walk = (nodes: OutlineNodeLike[], depth: number) => {
    for (const node of sortByOrderNo(nodes)) {
      const lvl = Math.max(1, Math.min(9, Number(node?.level ?? depth) || depth || 1));

      while (counters.length < lvl) counters.push(0);
      while (counters.length > lvl) counters.pop();
      counters[lvl - 1] += 1;
      for (let i = lvl; i < counters.length; i++) counters[i] = 0;

      const numbering = counters.filter((n) => n > 0).join(".");
      items.push({
        level: lvl,
        numbering,
        title: String(node?.title || ""),
      });

      const children = asArray<OutlineNodeLike>(node?.children);
      if (children.length) walk(children, lvl + 1);
    }
  };

  walk(outline, 1);
  if (items.length > 0) {
    return items;
  }

  // 如果 outline 为空，也渲染一个固定示例，避免“预览空白页”
  return [
    { level: 1, numbering: "1", title: "示例：项目概述" },
    { level: 2, numbering: "1.1", title: "示例：项目背景" },
    { level: 2, numbering: "1.2", title: "示例：项目目标" },
    { level: 1, numbering: "2", title: "示例：技术方案" },
    { level: 2, numbering: "2.1", title: "示例：总体架构" },
  ];
}

/**
 * 将 TemplateSpec.style_hints 转为 RichTocPreview 的 TemplateStyle（驼峰）。
 */
export function templateSpecToTemplateStyle(spec: any): TemplateStyle {
  const hints = (spec?.style_hints || spec?.styleHints || {}) as Record<string, any>;
  return {
    pageBackground: hints.page_background,
    fontFamily: hints.font_family,
    fontSize: hints.font_size,
    lineHeight: hints.line_height,
    tocIndent1: hints.toc_indent_1,
    tocIndent2: hints.toc_indent_2,
    tocIndent3: hints.toc_indent_3,
    tocIndent4: hints.toc_indent_4,
    heading1Bold: true,
    heading1Size: hints.font_size,
  };
}


