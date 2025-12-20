import React from "react";

type FormatTemplateOption = { id: string; name: string };

type Props = {
  hasDirectory: boolean;
  onGenerate: () => void | Promise<void>;
  formatTemplates?: FormatTemplateOption[];
  selectedFormatTemplateId?: string;
  onChangeFormatTemplateId?: (id: string) => void;
  onApplyFormatTemplate?: () => void | Promise<void>;
  onAutoFillSamples?: () => void | Promise<void>;
  applyingFormat?: boolean;
  autoFillingSamples?: boolean;
  busy?: boolean;
};

export default function DirectoryToolbar({
  hasDirectory,
  onGenerate,
  formatTemplates,
  selectedFormatTemplateId,
  onChangeFormatTemplateId,
  onApplyFormatTemplate,
  onAutoFillSamples,
  applyingFormat,
  autoFillingSamples,
  busy,
}: Props) {
  return (
    <div className="source-card" style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <button className="kb-create-form" style={{ width: "auto", marginBottom: 0 }} onClick={onGenerate} disabled={busy}>
          {busy ? "生成中..." : hasDirectory ? "重新生成目录" : "生成目录"}
        </button>

        {onChangeFormatTemplateId && (
          <select
            value={selectedFormatTemplateId || ""}
            onChange={(e) => onChangeFormatTemplateId(e.target.value)}
            className="sidebar-select"
            style={{ width: "auto", marginBottom: 0 }}
            disabled={busy}
            title="选择格式模板（用于套用样式/结构）"
          >
            <option value="">选择格式模板…</option>
            {(formatTemplates || []).map((tpl) => (
              <option key={tpl.id} value={tpl.id}>
                {tpl.name}
              </option>
            ))}
          </select>
        )}

        {onApplyFormatTemplate && (
          <button
            className="kb-create-form"
            style={{ width: "auto", marginBottom: 0 }}
            onClick={onApplyFormatTemplate}
            disabled={busy || applyingFormat || !selectedFormatTemplateId}
            title={!selectedFormatTemplateId ? "请先选择格式模板" : "将所选格式模板应用到目录/样式"}
          >
            {applyingFormat ? "套用中..." : "自动套用格式"}
          </button>
        )}

        {onAutoFillSamples && (
          <button
            className="kb-create-form"
            style={{ width: "auto", marginBottom: 0 }}
            onClick={onAutoFillSamples}
            disabled={busy || autoFillingSamples || !hasDirectory}
            title={!hasDirectory ? "请先生成目录" : "从招标书抽取范本并自动挂载到章节正文"}
          >
            {autoFillingSamples ? "填充中..." : "自动填充范本（投标函/授权书/报价单…）"}
          </button>
        )}
      </div>

      <div className="kb-doc-meta" style={{ marginTop: 8 }}>
        说明：生成目录成功后，下方区域会原地切换为"一页模式（目录+正文）"。正文为自动保存。套用格式后可切换到"格式预览"查看整体效果。
      </div>
    </div>
  );
}
