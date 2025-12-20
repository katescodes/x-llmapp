/**
 * 模块化答案组件（平铺展示版本）
 * 
 * 用于渲染编排器生成的结构化答案：
 * - 平铺展示所有模块（无折叠交互）
 * - Markdown 渲染
 * - 可选补充信息提示
 */

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ChatSection } from '../types/orchestrator';

interface ModularAnswerProps {
  sections: ChatSection[];
  followups?: string[];
  className?: string;
}

export const ModularAnswer: React.FC<ModularAnswerProps> = ({
  sections,
  followups,
  className = '',
}) => {
  if (!sections || sections.length === 0) {
    return null;
  }

  return (
    <div className={`modular-answer ${className}`}>
      {sections.map((section) => (
        <div
          key={section.id}
          className="answer-section"
          style={{
            marginBottom: '1.5rem',
          }}
        >
          {/* 模块标题（纯展示，无交互） */}
          <h3
            style={{
              margin: '0 0 0.75rem 0',
              fontSize: '1.125rem',
              fontWeight: 600,
              color: '#e5e7eb',
              borderBottom: '2px solid rgba(148, 163, 184, 0.3)',
              paddingBottom: '0.5rem',
            }}
          >
            {section.title}
          </h3>

          {/* 模块内容（Markdown 渲染） */}
          <div
            className="section-content"
            style={{
              paddingLeft: '0.5rem',
            }}
          >
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                // 自定义样式
                h1: ({ node, ...props }) => (
                  <h1
                    style={{
                      fontSize: '1.5rem',
                      fontWeight: 700,
                      marginTop: '1rem',
                      marginBottom: '0.5rem',
                      color: '#e5e7eb',
                    }}
                    {...props}
                  />
                ),
                h2: ({ node, ...props }) => (
                  <h2
                    style={{
                      fontSize: '1.25rem',
                      fontWeight: 600,
                      marginTop: '0.75rem',
                      marginBottom: '0.5rem',
                      color: '#e5e7eb',
                    }}
                    {...props}
                  />
                ),
                h3: ({ node, ...props }) => (
                  <h3
                    style={{
                      fontSize: '1.125rem',
                      fontWeight: 600,
                      marginTop: '0.5rem',
                      marginBottom: '0.5rem',
                      color: '#e5e7eb',
                    }}
                    {...props}
                  />
                ),
                p: ({ node, ...props }) => (
                  <p
                    style={{
                      marginBottom: '0.75rem',
                      lineHeight: '1.6',
                      color: '#e5e7eb',
                    }}
                    {...props}
                  />
                ),
                ul: ({ node, ...props }) => (
                  <ul
                    style={{
                      marginLeft: '1.5rem',
                      marginBottom: '0.75rem',
                      listStyleType: 'disc',
                      color: '#e5e7eb',
                    }}
                    {...props}
                  />
                ),
                ol: ({ node, ...props }) => (
                  <ol
                    style={{
                      marginLeft: '1.5rem',
                      marginBottom: '0.75rem',
                      listStyleType: 'decimal',
                      color: '#e5e7eb',
                    }}
                    {...props}
                  />
                ),
                li: ({ node, ...props }) => (
                  <li
                    style={{
                      marginBottom: '0.25rem',
                      color: '#e5e7eb',
                    }}
                    {...props}
                  />
                ),
                table: ({ node, ...props }) => (
                  <div style={{ overflowX: 'auto', marginBottom: '0.75rem' }}>
                    <table
                      style={{
                        width: '100%',
                        borderCollapse: 'collapse',
                        border: '1px solid rgba(148, 163, 184, 0.3)',
                      }}
                      {...props}
                    />
                  </div>
                ),
                th: ({ node, ...props }) => (
                  <th
                    style={{
                      padding: '0.5rem',
                      backgroundColor: 'rgba(51, 65, 85, 0.5)',
                      border: '1px solid rgba(148, 163, 184, 0.3)',
                      fontWeight: 600,
                      textAlign: 'left',
                      color: '#e5e7eb',
                    }}
                    {...props}
                  />
                ),
                td: ({ node, ...props }) => (
                  <td
                    style={{
                      padding: '0.5rem',
                      border: '1px solid rgba(148, 163, 184, 0.3)',
                      color: '#e5e7eb',
                    }}
                    {...props}
                  />
                ),
                code: ({ node, inline, ...props }: any) =>
                  inline ? (
                    <code
                      style={{
                        backgroundColor: 'rgba(51, 65, 85, 0.5)',
                        padding: '0.125rem 0.25rem',
                        borderRadius: '0.25rem',
                        fontSize: '0.875rem',
                        fontFamily: 'monospace',
                        color: '#f9fafb',
                      }}
                      {...props}
                    />
                  ) : (
                    <code
                      style={{
                        display: 'block',
                        backgroundColor: '#1f2937',
                        color: '#f9fafb',
                        padding: '1rem',
                        borderRadius: '0.5rem',
                        fontSize: '0.875rem',
                        fontFamily: 'monospace',
                        overflowX: 'auto',
                        marginBottom: '0.75rem',
                      }}
                      {...props}
                    />
                  ),
                blockquote: ({ node, ...props }) => (
                  <blockquote
                    style={{
                      borderLeft: '4px solid rgba(148, 163, 184, 0.5)',
                      paddingLeft: '1rem',
                      color: '#9ca3af',
                      fontStyle: 'italic',
                      marginBottom: '0.75rem',
                    }}
                    {...props}
                  />
                ),
              }}
            >
              {section.markdown}
            </ReactMarkdown>
          </div>
        </div>
      ))}

      {/* 可选补充信息提示 */}
      {followups && followups.length > 0 && (
        <div
          className="followups-section"
          style={{
            marginTop: '1.5rem',
            padding: '1rem',
            backgroundColor: 'rgba(254, 243, 199, 0.1)',
            border: '1px solid rgba(251, 191, 36, 0.3)',
            borderRadius: '0.5rem',
          }}
        >
          <h4
            style={{
              margin: '0 0 0.5rem 0',
              fontSize: '0.875rem',
              fontWeight: 600,
              color: '#fbbf24',
            }}
          >
            💡 可选补充信息（非必需）
          </h4>
          <ul
            style={{
              margin: 0,
              paddingLeft: '1.5rem',
              color: '#fbbf24',
              fontSize: '0.875rem',
            }}
          >
            {followups.map((question, idx) => (
              <li key={idx} style={{ marginBottom: '0.25rem' }}>
                {question}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
