import React, { useEffect, useMemo, useRef } from "react";

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

function escapeHtml(s: string) {
  return s
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function buildTocHtml(items: TocItem[]) {
  const lines = items.map((it) => {
    const text = `${it.orderNo ? it.orderNo + " " : ""}${it.title ?? ""}`;
    return `
      <p class="toc-line lvl-${it.level}">
        <span class="toc-text">${escapeHtml(text)}</span>
        <span class="toc-leader"></span>
      </p>
    `;
  });
  return `<div class="toc-root">${lines.join("")}</div>`;
}

export default function RichTocBox(props: {
  items: TocItem[];
  styleVars?: TocStyleVars; // 为空表示默认样式
}) {
  const { items, styleVars } = props;
  const ref = useRef<HTMLDivElement | null>(null);

  const html = useMemo(() => buildTocHtml(items), [items]);

  useEffect(() => {
    if (!ref.current) return;
    ref.current.innerHTML = html;
  }, [html]);

  const vars: Required<TocStyleVars> = {
    fontFamily: styleVars?.fontFamily ?? `"Microsoft YaHei", "PingFang SC", "SimSun", serif`,
    fontSizePx: styleVars?.fontSizePx ?? 14,
    lineHeight: styleVars?.lineHeight ?? 1.7,
    lvl1Bold: styleVars?.lvl1Bold ?? true,
    lvl1FontSizePx: styleVars?.lvl1FontSizePx ?? 16,
    indent1Px: styleVars?.indent1Px ?? 0,
    indent2Px: styleVars?.indent2Px ?? 22,
    indent3Px: styleVars?.indent3Px ?? 44,
  };

  return (
    <div
      style={{
        background: "#fff",              // ✅ 白底，固定不跟模板走
        borderRadius: 8,
        padding: "18px 20px",
        border: "1px solid rgba(0,0,0,0.08)",
        overflow: "auto",
      }}
    >
      <style>{`
        .toc-root{
          font-family: var(--toc-font);
          font-size: var(--toc-font-size);
          line-height: var(--toc-line-height);
          color: rgba(0,0,0,0.88);
          user-select: text;
        }
        .toc-line{
          display:flex;
          align-items: baseline;
          margin: 6px 0;
          white-space: nowrap;
        }
        .toc-text{
          white-space: pre-wrap;
        }
        .toc-leader{
          flex:1;
          margin: 0 10px;
          border-bottom: 1px dotted rgba(0,0,0,0.45);
          transform: translateY(-2px);
        }
        .lvl-1{ padding-left: var(--toc-indent-1); font-weight: var(--toc-lvl1-weight); font-size: var(--toc-lvl1-font-size); }
        .lvl-2{ padding-left: var(--toc-indent-2); }
        .lvl-3{ padding-left: var(--toc-indent-3); }
      `}</style>

      <div
        ref={ref}
        // ✅ 用 CSS 变量控制"模板样式切换"
        style={{
          ["--toc-font" as any]: vars.fontFamily,
          ["--toc-font-size" as any]: `${vars.fontSizePx}px`,
          ["--toc-line-height" as any]: String(vars.lineHeight),
          ["--toc-lvl1-weight" as any]: vars.lvl1Bold ? 700 : 400,
          ["--toc-lvl1-font-size" as any]: `${vars.lvl1FontSizePx}px`,
          ["--toc-indent-1" as any]: `${vars.indent1Px}px`,
          ["--toc-indent-2" as any]: `${vars.indent2Px}px`,
          ["--toc-indent-3" as any]: `${vars.indent3Px}px`,
        }}
      />
    </div>
  );
}



