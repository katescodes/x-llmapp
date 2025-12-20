import React from "react";

interface HeaderBarProps {
  pending: boolean;
  activeLLMName?: string;
}

const HeaderBar: React.FC<HeaderBarProps> = ({ pending, activeLLMName }) => {
  return (
    <div className="header-bar">
      <div className="header-title">对话</div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {activeLLMName && (
          <div style={{ fontSize: 12, color: "#9ca3af" }}>
            模型: {activeLLMName}
          </div>
        )}
        <div className="header-tag">{pending ? "思考中…" : "就绪"}</div>
      </div>
    </div>
  );
};

export default HeaderBar;
