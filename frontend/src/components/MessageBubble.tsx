import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Role } from "../types";

interface MessageBubbleProps {
  role: Role;
  content: string;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ role, content }) => {
  const isUser = role === "user";

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
    } catch (err) {
      console.error("复制失败", err);
    }
  };

  return (
    <div className={"message-bubble " + (isUser ? "user" : "assistant")}>
      {!isUser && (
        <button className="bubble-copy-btn" onClick={handleCopy} title="复制内容">
          ⧉
        </button>
      )}
      <div className="message-content markdown-body">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            a({ node, children, href, ...props }) {
              return (
                <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
                  {children}
                </a>
              );
            },

            // ✅ pre 单独接管：避免嵌套 pre 导致间距和滚动异常
            pre({ node, children, ...props }) {
              return (
                <pre className="md-pre" {...props}>
                  {children}
                </pre>
              );
            },

            // ✅ inline / block code 分开：inline 不要被 code block 样式污染
            code({ node, inline, className, children, ...props }) {
              if (inline) {
                return (
                  <code className={"md-inline-code " + (className || "")} {...props}>
                    {children}
                  </code>
                );
              }
              return (
                <code className={className} {...props}>
                  {children}
                </code>
              );
            },

            // ✅ 表格：使用 class 而不是 inline style，便于统一控制宽度策略
            table({ node, children, ...props }) {
              return (
                <div className="md-table-wrap">
                  <table {...props}>{children}</table>
                </div>
              );
            },

            blockquote({ node, children, ...props }) {
              return (
                <blockquote className="md-quote" {...props}>
                  {children}
                </blockquote>
              );
            },

            hr() {
              return <hr className="md-hr" />;
            },
          }}
        >
          {content || ""}
        </ReactMarkdown>
      </div>
    </div>
  );
};

export default MessageBubble;
