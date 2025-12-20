import React, { useMemo, useState } from "react";

export type DirectoryNode = {
  id: string;
  parent_id?: string | null;
  order_no: number;
  numbering: string;
  level: number;
  title: string;
  required: boolean;
  source?: string;
  notes?: string;
  volume?: string;
  evidence_chunk_ids: string[];
};

type Props = {
  nodes: DirectoryNode[];
  onOpenEvidence: (chunkIds: string[]) => void;
  selectedId?: string | null;
  onSelect?: (id: string) => void;
};

export default function DirectoryTree({ nodes, onOpenEvidence, selectedId, onSelect }: Props) {
  const byParent = useMemo(() => {
    const m = new Map<string, DirectoryNode[]>();
    for (const n of nodes) {
      const pid = n.parent_id || "__root__";
      if (!m.has(pid)) m.set(pid, []);
      m.get(pid)!.push(n);
    }
    for (const [k, arr] of m.entries()) {
      arr.sort((a, b) => (a.order_no ?? 0) - (b.order_no ?? 0));
      m.set(k, arr);
    }
    return m;
  }, [nodes]);

  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const render = (pid: string, depth: number): React.ReactNode[] => {
    const children = byParent.get(pid) || [];
    return children.map((n) => {
      const hasKids = (byParent.get(n.id) || []).length > 0;
      const isCol = !!collapsed[n.id];
      return (
        <div key={n.id}>
          <div
            className={`tender-tree-row kb-doc-card ${selectedId === n.id ? "active" : ""}`}
            style={{ paddingLeft: 12 + depth * 14, marginBottom: 8, cursor: onSelect ? 'pointer' : 'default' }}
            onClick={() => onSelect?.(n.id)}
          >
            <div className="tender-tree-main">
              {hasKids ? (
                <button
                  className="link-button"
                  style={{ marginRight: 8 }}
                  onClick={(e) => {
                    e.stopPropagation();
                    setCollapsed((p) => ({ ...p, [n.id]: !p[n.id] }));
                  }}
                  title={isCol ? "展开" : "收起"}
                >
                  {isCol ? "▶" : "▼"}
                </button>
              ) : (
                <span style={{ width: 18, display: "inline-block" }} />
              )}

              <div className="kb-doc-title" style={{ margin: 0 }}>
                <span className="tender-dir-number">{n.numbering}</span>
                <span style={{ marginLeft: 8 }}>{n.title}</span>
                {n.required && <span className="tender-badge required">必填</span>}
                {n.source && n.source !== "tender" && <span className="tender-badge">{n.source}</span>}
              </div>
            </div>

            {(n.notes || "").trim() && <div className="kb-doc-meta">{n.notes}</div>}

            {n.evidence_chunk_ids?.length > 0 && (
              <button
                className="link-button"
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenEvidence(n.evidence_chunk_ids);
                }}
              >
                查看证据 ({n.evidence_chunk_ids.length})
              </button>
            )}
          </div>

          {!isCol && hasKids && render(n.id, depth + 1)}
        </div>
      );
    });
  };

  return <div>{render("__root__", 0)}</div>;
}
