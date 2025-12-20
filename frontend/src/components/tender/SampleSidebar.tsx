import React, { useMemo, useState } from "react";
import type { SampleFragment, SampleFragmentPreview } from "../../types/tender";

export type SamplePreviewState = {
  loading?: boolean;
  data?: SampleFragmentPreview;
  error?: string;
};

type Props = {
  open: boolean;
  onToggle: () => void;
  fragments: SampleFragment[];
  previewById: Record<string, SamplePreviewState | undefined>;
  onLoadPreview: (fragmentId: string) => void;
};

function pct(conf?: number): string {
  if (conf == null || Number.isNaN(conf)) return "";
  const v = Math.max(0, Math.min(1, conf));
  return `${Math.round(v * 100)}%`;
}

export default function SampleSidebar({ open, onToggle, fragments, previewById, onLoadPreview }: Props) {
  const [expandedIds, setExpandedIds] = useState<Record<string, boolean>>({});

  const count = fragments?.length || 0;
  const title = useMemo(() => `范本原文（${count}）`, [count]);

  if (!open) {
    return (
      <div
        style={{
          width: 40,
          flex: "0 0 40px",
          borderLeft: "1px solid rgba(148, 163, 184, 0.25)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 10,
          padding: "10px 6px",
          color: "#cbd5e1",
        }}
      >
        <button
          onClick={onToggle}
          title="展开范本原文"
          style={{
            background: "rgba(15, 23, 42, 0.6)",
            border: "1px solid rgba(148, 163, 184, 0.25)",
            color: "#e2e8f0",
            borderRadius: 8,
            padding: "6px 8px",
            cursor: "pointer",
          }}
        >
          ◀
        </button>
        <div style={{ writingMode: "vertical-rl", fontSize: 12, opacity: 0.85 }}>范本原文</div>
      </div>
    );
  }

  return (
    <div
      style={{
        width: 380,
        flex: "0 0 380px",
        borderLeft: "1px solid rgba(148, 163, 184, 0.25)",
        minHeight: 0,
        display: "flex",
        flexDirection: "column",
        background: "rgba(15, 23, 42, 0.35)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          padding: "10px 12px",
          borderBottom: "1px solid rgba(148, 163, 184, 0.18)",
          color: "#e2e8f0",
          fontWeight: 700,
        }}
      >
        <div style={{ fontSize: 14 }}>{title}</div>
        <button
          onClick={onToggle}
          style={{
            background: "transparent",
            border: "1px solid rgba(148, 163, 184, 0.25)",
            color: "#e2e8f0",
            borderRadius: 8,
            padding: "6px 10px",
            cursor: "pointer",
            fontSize: 12,
          }}
        >
          收起
        </button>
      </div>

      <div style={{ overflowY: "auto", minHeight: 0, padding: 10 }}>
        {count === 0 ? (
          <div
            style={{
              background: "rgba(30, 41, 59, 0.6)",
              border: "1px solid rgba(148, 163, 184, 0.18)",
              borderRadius: 10,
              padding: 12,
              color: "#cbd5e1",
              fontSize: 13,
              lineHeight: 1.6,
            }}
          >
            <div style={{ fontWeight: 700, color: "#e2e8f0", marginBottom: 6 }}>未抽取到范本</div>
            <div style={{ marginBottom: 8 }}>
              常见原因：范本是图片扫描/无可复制文字；标题在表格中未被识别；标题不是 Heading 样式导致定位不稳。
            </div>
            <div>建议：上传可编辑的 docx；或开启 LLM span 定位；必要时手动确认招标书里“投标文件格式/样表/范本”所在位置。</div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {fragments.map((f) => {
              const expanded = !!expandedIds[f.id];
              const st = previewById?.[f.id];
              const conf = pct(f.confidence);
              return (
                <div
                  key={f.id}
                  style={{
                    border: "1px solid rgba(148, 163, 184, 0.18)",
                    borderRadius: 10,
                    overflow: "hidden",
                    background: "rgba(30, 41, 59, 0.55)",
                  }}
                >
                  <button
                    onClick={() => {
                      setExpandedIds((prev) => {
                        const next = { ...prev, [f.id]: !prev[f.id] };
                        return next;
                      });
                      if (!expanded) onLoadPreview(f.id);
                    }}
                    style={{
                      width: "100%",
                      textAlign: "left",
                      cursor: "pointer",
                      background: "transparent",
                      border: "none",
                      color: "#e2e8f0",
                      padding: "10px 10px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 10,
                    }}
                    title="展开/收起预览"
                  >
                    <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
                      <div style={{ fontWeight: 700, fontSize: 13, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {f.title || "(无标题)"}
                      </div>
                      <div style={{ fontSize: 12, color: "rgba(226, 232, 240, 0.7)" }}>
                        {f.fragment_type}
                        {conf ? ` · 置信度 ${conf}` : ""}
                      </div>
                    </div>
                    <div style={{ fontSize: 12, color: "rgba(226, 232, 240, 0.7)" }}>{expanded ? "▲" : "▼"}</div>
                  </button>

                  {expanded && (
                    <div style={{ padding: 10, background: "rgba(15, 23, 42, 0.25)" }}>
                      {st?.loading ? (
                        <div style={{ color: "#cbd5e1", fontSize: 13 }}>预览加载中…</div>
                      ) : st?.error ? (
                        <div style={{ color: "#fca5a5", fontSize: 13 }}>预览加载失败：{st.error}</div>
                      ) : st?.data ? (
                        <>
                          {Array.isArray(st.data.warnings) && st.data.warnings.length > 0 && (
                            <div style={{ color: "rgba(226, 232, 240, 0.75)", fontSize: 12, marginBottom: 8 }}>
                              提示：{st.data.warnings.slice(0, 3).join("；")}
                              {st.data.warnings.length > 3 ? "…" : ""}
                            </div>
                          )}
                          <div
                            style={{
                              background: "#ffffff",
                              borderRadius: 8,
                              padding: "10px 10px",
                              color: "#0f172a",
                              fontSize: 13,
                              lineHeight: 1.65,
                              overflowX: "auto",
                              wordBreak: "break-word",
                            }}
                            dangerouslySetInnerHTML={{ __html: st.data.preview_html }}
                          />
                        </>
                      ) : (
                        <div style={{ color: "#cbd5e1", fontSize: 13 }}>点击加载预览</div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}


