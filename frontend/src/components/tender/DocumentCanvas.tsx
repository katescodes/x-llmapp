import React, { useCallback, useMemo, useRef } from "react";

export type OutlineNode = {
  id: string;
  title: string;
  level: number;
  numbering?: string;
  bodyMeta?: any;
};

type Props = {
  outlineFlat: OutlineNode[];
  tocStyleVars?: any;
  bodyByNodeId: Record<string, string>; // nodeId -> html
  bodyMetaByNodeId?: Record<string, any>;
  onNodeClick?: (nodeId: string) => void; // 点击目录节点时的回调
  projectId?: string; // 项目ID（用于删除挂载）
  onTemplateMountRemoved?: () => void; // 删除挂载后的回调
};

function indentForLevel(lvl: number, vars?: any): number {
  if (!vars) return Math.max(0, (lvl - 1) * 18);
  if (lvl <= 1) return vars.indent1Px ?? 0;
  if (lvl === 2) return vars.indent2Px ?? (vars.indent1Px ?? 0) + 18;
  if (lvl === 3) return vars.indent3Px ?? (vars.indent2Px ?? 0) + 18;
  return (vars.indent3Px ?? vars.indent2Px ?? 0) + (lvl - 3) * 18;
}

export default function DocumentCanvas({
  outlineFlat,
  tocStyleVars,
  bodyByNodeId,
  bodyMetaByNodeId,
  onNodeClick,
  projectId,
  onTemplateMountRemoved,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // 删除范本挂载
  const handleRemoveTemplateMount = async (nodeId: string) => {
    if (!projectId) return;
    
    if (!confirm('确定要删除此章节的范本挂载吗？')) return;
    
    try {
      const response = await fetch(`/api/apps/tender/projects/${projectId}/directory/${nodeId}/template-mount`, {
        method: 'DELETE',
      });
      
      const data = await response.json();
      
      if (data.success) {
        alert('范本挂载已删除');
        onTemplateMountRemoved?.();
      } else {
        alert(data.message || '删除失败');
      }
    } catch (error) {
      console.error('删除范本挂载失败:', error);
      alert('删除失败，请稍后重试');
    }
  };

  const paperStyle: React.CSSProperties = useMemo(() => {
    const fontFamily = tocStyleVars?.fontFamily;
    const fontSizePx = tocStyleVars?.fontSizePx;
    const lineHeight = tocStyleVars?.lineHeight;
    return {
      maxWidth: 920,
      margin: "0 auto",
      background: "#ffffff",
      borderRadius: 10,
      boxShadow: "0 0 0 1px rgba(15, 23, 42, 0.12), 0 20px 40px rgba(15, 23, 42, 0.12)",
      padding: "28px 36px",
      fontFamily: fontFamily || undefined,
      fontSize: fontSizePx ? `${fontSizePx}px` : undefined,
      lineHeight: lineHeight || undefined,
    };
  }, [tocStyleVars]);

  const scrollToNode = useCallback((nodeId: string) => {
    const container = scrollRef.current;
    if (!container) return;
    const el = container.querySelector(`#sec-${CSS.escape(nodeId)}`) as HTMLElement | null;
    if (!el) return;
    // 同一滚动容器内定位
    container.scrollTo({
      top: el.offsetTop - 16,
      behavior: "smooth",
    });
  }, []);

  return (
    <div
      data-testid="document-canvas"
      ref={scrollRef}
      style={{
        flex: 1,
        minHeight: 0,
        overflowY: "auto",
        padding: "18px 0",
      }}
    >
      <div style={paperStyle}>
        {/* TOC */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ fontWeight: 800, marginBottom: 10 }}>目录</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {outlineFlat.map((n) => (
              <div
                key={n.id}
                onClick={() => {
                  scrollToNode(n.id);
                  onNodeClick?.(n.id);
                }}
                style={{
                  cursor: "pointer",
                  color: "#0f172a",
                  paddingLeft: indentForLevel(n.level, tocStyleVars),
                  fontWeight: n.level === 1 && tocStyleVars?.lvl1Bold ? 700 : 500,
                  fontSize:
                    n.level === 1 && tocStyleVars?.lvl1FontSizePx
                      ? `${tocStyleVars.lvl1FontSizePx}px`
                      : undefined,
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <span style={{ flex: 1, minWidth: 0 }}>
                  {n.numbering ? `${n.numbering} ` : ""}
                  {n.title}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ height: 1, background: "rgba(15, 23, 42, 0.12)", margin: "18px 0" }} />

        {/* Sections */}
        <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
          {outlineFlat.map((n) => {
            const meta = bodyMetaByNodeId?.[n.id] ?? n.bodyMeta;
            const html = bodyByNodeId[n.id] || "";
            const empty = !html || !html.trim();

            return (
              <div key={n.id} id={`sec-${n.id}`} style={{ scrollMarginTop: 12 }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "baseline",
                    justifyContent: "space-between",
                    gap: 12,
                    marginBottom: 10,
                  }}
                >
                  <div
                    style={{
                      fontWeight: n.level === 1 ? 800 : 700,
                      fontSize:
                        n.level === 1 && tocStyleVars?.lvl1FontSizePx
                          ? `${tocStyleVars.lvl1FontSizePx}px`
                          : n.level === 2
                          ? "18px"
                          : "16px",
                    }}
                  >
                    {n.numbering ? `${n.numbering} ` : ""}
                    {n.title}
                  </div>

                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {/* 仅保留范本提示（在下方渲染） */}
                  </div>
                </div>

                <div
                  style={{
                    background: "#ffffff",
                    borderRadius: 6,
                    padding: "10px 0",
                  }}
                >
                  {empty ? (
                    <div style={{ color: "rgba(15, 23, 42, 0.55)", fontSize: 13 }}>
                      （本章节暂无正文；点击“自动填充范本”后会显示对应范本内容）
                    </div>
                  ) : (
                    <div
                      className="doc-html"
                      style={{
                        color: "#0f172a",
                        fontSize: "14px",
                        lineHeight: tocStyleVars?.lineHeight || 1.7,
                        wordBreak: "break-word",
                      }}
                      dangerouslySetInnerHTML={{ __html: html }}
                    />
                  )}
                </div>

                {meta?.source === "TEMPLATE_SAMPLE" && (
                  <div
                    style={{
                      marginTop: 10,
                      padding: 10,
                      background: "rgba(251, 191, 36, 0.12)",
                      borderRadius: 6,
                      color: "#92400e",
                      fontSize: 12,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 12,
                    }}
                  >
                    <div style={{ flex: 1 }}>
                      📄 该章节已挂载范本，导出时将保真拷贝源文档格式
                    </div>
                    {projectId && (
                      <button
                        onClick={() => handleRemoveTemplateMount(n.id)}
                        style={{
                          padding: "4px 12px",
                          background: "#dc2626",
                          color: "#ffffff",
                          border: "none",
                          borderRadius: 4,
                          cursor: "pointer",
                          fontSize: 11,
                          fontWeight: 600,
                          whiteSpace: "nowrap",
                        }}
                        title="删除范本挂载"
                      >
                        🗑️ 删除挂载
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}


