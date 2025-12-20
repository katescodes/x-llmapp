/**
 * 模板相关 API 调用
 */
import { api } from '../../config/api';
import { TemplateStyle } from './RichTocPreview';

export interface TemplateSpec {
  version?: string;
  language?: string;
  base_policy?: any;
  style_hints?: {
    heading1_style?: string;
    heading2_style?: string;
    heading3_style?: string;
    heading4_style?: string;
    heading5_style?: string;
    body_style?: string;
    table_style?: string;
    page_background?: string;
    font_family?: string;
    font_size?: string;
    line_height?: string;
    toc_indent_1?: string;
    toc_indent_2?: string;
    toc_indent_3?: string;
    toc_indent_4?: string;
    [key: string]: any;
  };
  outline?: any[];
  merge_policy?: any;
  diagnostics?: any;
  metadata?: any;
}

/**
 * 获取模板规格
 */
export async function getTemplateSpec(templateAssetId: string): Promise<TemplateSpec | null> {
  try {
    // 注意：这里使用 tender asset ID，后端需要支持通过 asset ID 查询 spec
    // 如果后端尚未支持，我们先用默认值
    const spec = await api.get(`/api/apps/tender/format-templates/${templateAssetId}/spec`);
    return spec;
  } catch (err) {
    console.warn('Failed to load template spec:', err);
    return null;
  }
}

/**
 * 将 TemplateSpec 转换为 TemplateStyle（供前端预览使用）
 */
export function convertSpecToStyle(spec: TemplateSpec | null): TemplateStyle {
  const hints = spec?.style_hints || {};
  
  return {
    pageBackground: hints.page_background || '#ffffff',
    fontFamily: hints.font_family || 'SimSun, serif',
    fontSize: hints.font_size || '14px',
    lineHeight: hints.line_height || '1.6',
    tocIndent1: hints.toc_indent_1 || '0px',
    tocIndent2: hints.toc_indent_2 || '20px',
    tocIndent3: hints.toc_indent_3 || '40px',
    tocIndent4: hints.toc_indent_4 || '60px',
    heading1Bold: true,
    heading1Size: hints.heading1_style ? '16px' : undefined,
  };
}

/**
 * 获取默认模板样式（无模板时使用）
 */
export function getDefaultTemplateStyle(): TemplateStyle {
  return {
    pageBackground: '#ffffff',
    fontFamily: 'SimSun, serif',
    fontSize: '14px',
    lineHeight: '1.6',
    tocIndent1: '0px',
    tocIndent2: '20px',
    tocIndent3: '40px',
    tocIndent4: '60px',
    heading1Bold: true,
  };
}
