import React from "react";
import { Source } from "../types";

interface SourcePanelProps {
  sources: Source[];
  collapsed: boolean;
  onToggle: () => void;
}

const SourcePanel: React.FC<SourcePanelProps> = ({
  sources,
  collapsed,
  onToggle
}) => {
  if (collapsed) {
    return (
      <div className="source-panel-collapsed">
        <button
          className="source-toggle collapsed"
          onClick={onToggle}
          title="展开参考资料"
        >
          ◀
        </button>
        <span className="source-collapsed-label">参考资料</span>
      </div>
    );
  }

  return (
    <div className="source-panel-body">
      <div className="source-title-row">
        <div className="source-title">参考资料</div>
        <button className="source-toggle" onClick={onToggle}>
          收起
        </button>
      </div>
      {sources.length === 0 && (
        <div className="source-empty">
          暂无引用资料。当你启用联网或知识库检索时，这里会展示引用的内容。
        </div>
      )}
      {sources.map((s) => (
        <div key={s.id} className="source-card">
          <div className="source-card-title">
            [{s.id}] {s.kb_name || "知识库"} / {s.doc_name || s.title || "未命名"}
          </div>
          <div className="source-card-url">{s.title}</div>
          {s.url ? (
            <a
              className="source-card-url"
              href={s.url}
              target="_blank"
              rel="noreferrer"
            >
              {s.url}
            </a>
          ) : (
            <div className="source-card-snippet">(no url)</div>
          )}
          <div className="source-card-snippet">{s.snippet}</div>
        </div>
      ))}
    </div>
  );
};

export default SourcePanel;
