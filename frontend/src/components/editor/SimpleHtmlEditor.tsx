/**
 * 简单HTML编辑器 - 用于编辑章节正文
 * 支持基本格式：加粗、斜体、列表
 */
import React, { useEffect, useRef, useState } from "react";

interface SimpleHtmlEditorProps {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
  readonly?: boolean;
}

export default function SimpleHtmlEditor({
  value,
  onChange,
  placeholder = "请输入内容...",
  readonly = false,
}: SimpleHtmlEditorProps) {
  const editorRef = useRef<HTMLDivElement>(null);
  const [isFocused, setIsFocused] = useState(false);

  // 初始化内容
  useEffect(() => {
    if (editorRef.current && editorRef.current.innerHTML !== value) {
      editorRef.current.innerHTML = value || "";
    }
  }, [value]);

  // 处理内容变化
  const handleInput = () => {
    if (editorRef.current && onChange) {
      onChange(editorRef.current.innerHTML);
    }
  };

  // 执行格式化命令
  const execCommand = (command: string, value?: string) => {
    document.execCommand(command, false, value);
    editorRef.current?.focus();
    handleInput();
  };

  return (
    <div style={{ border: "1px solid #d9d9d9", borderRadius: 4, background: "#fff" }}>
      {/* 工具栏 */}
      {!readonly && (
        <div
          style={{
            borderBottom: "1px solid #d9d9d9",
            padding: "8px",
            display: "flex",
            gap: "8px",
            background: "#fafafa",
          }}
        >
          <button
            type="button"
            onClick={() => execCommand("bold")}
            style={{
              padding: "4px 12px",
              border: "1px solid #d9d9d9",
              borderRadius: 4,
              background: "#fff",
              cursor: "pointer",
            }}
            title="加粗"
          >
            <strong>B</strong>
          </button>
          <button
            type="button"
            onClick={() => execCommand("italic")}
            style={{
              padding: "4px 12px",
              border: "1px solid #d9d9d9",
              borderRadius: 4,
              background: "#fff",
              cursor: "pointer",
            }}
            title="斜体"
          >
            <em>I</em>
          </button>
          <button
            type="button"
            onClick={() => execCommand("underline")}
            style={{
              padding: "4px 12px",
              border: "1px solid #d9d9d9",
              borderRadius: 4,
              background: "#fff",
              cursor: "pointer",
            }}
            title="下划线"
          >
            <u>U</u>
          </button>
          <div style={{ width: 1, background: "#d9d9d9", margin: "0 4px" }} />
          <button
            type="button"
            onClick={() => execCommand("insertUnorderedList")}
            style={{
              padding: "4px 12px",
              border: "1px solid #d9d9d9",
              borderRadius: 4,
              background: "#fff",
              cursor: "pointer",
            }}
            title="无序列表"
          >
            • 列表
          </button>
        </div>
      )}

      {/* 编辑区域 */}
      <div
        ref={editorRef}
        contentEditable={!readonly}
        onInput={handleInput}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        style={{
          minHeight: 200,
          padding: 16,
          outline: "none",
          fontSize: 14,
          lineHeight: 1.6,
          color: "#333",
        }}
        data-placeholder={placeholder}
      >
        {/* 内容通过 innerHTML 注入 */}
      </div>

      <style>{`
        [contenteditable]:empty:before {
          content: attr(data-placeholder);
          color: #999;
        }
      `}</style>
    </div>
  );
}
