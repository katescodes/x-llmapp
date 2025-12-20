/**
 * RichTocPreview 使用示例
 * 
 * 这个组件用于在 Step3 展示 Word 风格的富文本目录预览
 */

import React from 'react';
import RichTocPreview, { TocItem, TemplateStyle } from './components/template/RichTocPreview';

// 示例 1: 基础使用（默认样式）
export function Example1() {
  const items: TocItem[] = [
    { level: 1, numbering: '第一卷', title: '商务标', pageNo: 1 },
    { level: 2, numbering: '1.1', title: '投标函', pageNo: 2 },
    { level: 3, numbering: '1.1.1', title: '投标函附录', pageNo: 3 },
    { level: 2, numbering: '1.2', title: '法定代表人身份证明', pageNo: 5 },
    { level: 1, numbering: '第二卷', title: '技术标', pageNo: 10 },
    { level: 2, numbering: '2.1', title: '技术方案', pageNo: 11 },
  ];

  return (
    <div style={{ width: '100%', height: '600px' }}>
      <RichTocPreview items={items} />
    </div>
  );
}

// 示例 2: 应用自定义模板样式
export function Example2() {
  const items: TocItem[] = [
    { level: 1, numbering: '1', title: '项目概述', pageNo: 1 },
    { level: 2, numbering: '1.1', title: '项目背景', pageNo: 2 },
    { level: 2, numbering: '1.2', title: '项目目标', pageNo: 5 },
  ];

  const customStyle: TemplateStyle = {
    pageBackground: '#f8f9fa',      // 浅灰底色
    fontFamily: 'Microsoft YaHei',  // 微软雅黑
    fontSize: '16px',               // 较大字号
    lineHeight: '1.8',              // 较大行距
    tocIndent1: '0px',
    tocIndent2: '30px',             // 更大的缩进
    tocIndent3: '60px',
    tocIndent4: '90px',
    heading1Bold: true,
    heading1Size: '18px',           // 一级标题更大
  };

  return (
    <div style={{ width: '100%', height: '600px' }}>
      <RichTocPreview items={items} templateStyle={customStyle} />
    </div>
  );
}

// 示例 3: 在 TenderWorkspace 中的实际使用
export function Example3_TenderWorkspaceIntegration() {
  /*
  在 TenderWorkspace.tsx 中的使用：

  {previewOpen && previewNodes && previewNodes.length > 0 && (
    <div style={{ flex: 1, minHeight: 0 }}>
      <RichTocPreview
        items={previewNodes.map((n): TocItem => ({
          id: n.id,
          level: n.level,
          numbering: n.numbering,
          title: n.title,
          pageNo: undefined, // 页码暂时留空
        }))}
        templateStyle={currentTemplateStyle}
        style={{ minHeight: '500px' }}
      />
    </div>
  )}
  */

  return null; // 仅用于文档说明
}

// 示例 4: 无页码的目录（常见场景）
export function Example4() {
  const items: TocItem[] = [
    { level: 1, numbering: 'Chapter 1', title: 'Introduction' },
    { level: 2, numbering: '1.1', title: 'Background' },
    { level: 2, numbering: '1.2', title: 'Objectives' },
    { level: 1, numbering: 'Chapter 2', title: 'Methodology' },
  ];

  return (
    <div style={{ width: '100%', height: '400px' }}>
      <RichTocPreview
        items={items}
        templateStyle={{
          pageBackground: '#ffffff',
          fontFamily: 'Times New Roman, serif',
          fontSize: '12pt',
          lineHeight: '1.5',
        }}
      />
    </div>
  );
}
