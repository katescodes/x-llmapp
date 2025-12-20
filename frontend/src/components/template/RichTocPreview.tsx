/**
 * 富文本目录预览组件（Word 风格）
 * - 使用 iframe 进行样式隔离
 * - 支持层级缩进、点引导线、页码占位
 * - 应用模板样式：字体、字号、行距、底色等
 * - 不使用 table，纯 <p>/<div> 实现
 */
import React, { useRef, useEffect } from 'react';

export interface TocItem {
  id?: string;
  level: number;
  numbering: string;
  title: string;
  pageNo?: number | string;
}

export interface TemplateStyle {
  pageBackground?: string;
  fontFamily?: string;
  fontSize?: string;
  lineHeight?: number | string;
  tocIndent1?: string;
  tocIndent2?: string;
  tocIndent3?: string;
  tocIndent4?: string;
  // 可选：标题样式提示
  heading1Bold?: boolean;
  heading1Size?: string;
}

interface Props {
  items: TocItem[];
  templateStyle?: TemplateStyle;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * HTML 转义
 */
function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * 生成目录 HTML（Word 风格）
 */
function buildTocHtml(items: TocItem[], style: TemplateStyle): string {
  const {
    pageBackground = '#ffffff',
    fontFamily = 'SimSun, serif',
    fontSize = '14px',
    lineHeight = 1.6,
    tocIndent1 = '0px',
    tocIndent2 = '20px',
    tocIndent3 = '40px',
    tocIndent4 = '60px',
    heading1Bold = true,
    heading1Size,
  } = style;

  const cssVars = `
    --page-bg: ${pageBackground};
    --font-family: ${fontFamily};
    --font-size: ${fontSize};
    --line-height: ${lineHeight};
    --toc-indent-1: ${tocIndent1};
    --toc-indent-2: ${tocIndent2};
    --toc-indent-3: ${tocIndent3};
    --toc-indent-4: ${tocIndent4};
  `.trim();

  const itemsHtml = items
    .map((it) => {
      const displayText = it.numbering ? `${it.numbering} ${it.title}` : it.title;
      const pageText = it.pageNo !== undefined && it.pageNo !== '' ? String(it.pageNo) : '';
      
      // 层级样式
      let extraStyle = '';
      if (it.level === 1 && heading1Bold) {
        extraStyle += 'font-weight: 700;';
      }
      if (it.level === 1 && heading1Size) {
        extraStyle += `font-size: ${heading1Size};`;
      }

      return `
        <p class="toc-line lvl-${it.level}" style="${extraStyle}">
          <span class="toc-text">${escapeHtml(displayText)}</span>
          <span class="toc-leader"></span>
          <span class="toc-page">${escapeHtml(pageText)}</span>
        </p>
      `;
    })
    .join('');

  return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    
    :root {
      ${cssVars}
    }
    
    body {
      margin: 0;
      padding: 0;
      background: transparent;
    }
    
    .doc-page {
      background: var(--page-bg);
      padding: 32px 40px;
      border-radius: 6px;
      box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.06);
      min-height: 100%;
    }
    
    .toc {
      font-family: var(--font-family);
      font-size: var(--font-size);
      line-height: var(--line-height);
    }
    
    .toc-line {
      display: flex;
      align-items: baseline;
      margin: 6px 0;
      min-height: 1.4em;
    }
    
    .toc-text {
      white-space: pre-wrap;
      flex-shrink: 0;
    }
    
    .toc-leader {
      flex: 1;
      margin: 0 8px;
      border-bottom: 1px dotted rgba(0, 0, 0, 0.35);
      transform: translateY(-3px);
      min-width: 20px;
    }
    
    .toc-page {
      min-width: 28px;
      text-align: right;
      flex-shrink: 0;
    }
    
    /* 层级缩进 */
    .lvl-1 { padding-left: var(--toc-indent-1); }
    .lvl-2 { padding-left: var(--toc-indent-2); }
    .lvl-3 { padding-left: var(--toc-indent-3); }
    .lvl-4 { padding-left: var(--toc-indent-4); }
    .lvl-5 { padding-left: calc(var(--toc-indent-4) + 20px); }
    .lvl-6 { padding-left: calc(var(--toc-indent-4) + 40px); }
  </style>
</head>
<body>
  <div class="doc-page">
    <div class="toc">
      ${itemsHtml}
    </div>
  </div>
</body>
</html>
  `.trim();
}

export default function RichTocPreview({ items, templateStyle = {}, className, style }: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    const html = buildTocHtml(items, templateStyle);
    
    const doc = iframe.contentDocument || iframe.contentWindow?.document;
    if (doc) {
      doc.open();
      doc.write(html);
      doc.close();
    }
  }, [items, templateStyle]);

  return (
    <iframe
      ref={iframeRef}
      className={className}
      style={{
        width: '100%',
        height: '100%',
        minHeight: '400px',
        border: 'none',
        borderRadius: '6px',
        ...style,
      }}
      title="目录预览"
    />
  );
}
