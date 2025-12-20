import React, { useMemo, useState } from "react";

type Props = {
  info: Record<string, any>;
  onEvidence?: (chunkIds: string[]) => void;
};

const BASIC_FIELDS: Array<{ k: string; label: string }> = [
  { k: "projectName", label: "项目名称" },
  { k: "ownerName", label: "招标人/业主" },
  { k: "agencyName", label: "代理机构" },
  { k: "bidDeadline", label: "投标截止时间" },
  { k: "bidOpeningTime", label: "开标时间" },
  { k: "budget", label: "预算金额" },
  { k: "maxPrice", label: "最高限价" },
  { k: "bidBond", label: "投标保证金" },
  { k: "schedule", label: "工期要求" },
  { k: "quality", label: "质量要求" },
  { k: "location", label: "地点/交付" },
  { k: "contact", label: "联系人" },
];

function asArray(v: any): any[] {
  if (!v) return [];
  if (Array.isArray(v)) return v;
  return [];
}

export default function ProjectInfoView({ info, onEvidence }: Props) {
  const [showRaw, setShowRaw] = useState(false);

  // 从 data_json 中提取数据（兼容新旧格式）
  const dataJson = info?.data_json || info || {};
  const baseInfo = dataJson?.base || dataJson;

  const technical = useMemo(() => {
    const arr = asArray(dataJson?.technical_parameters || dataJson?.technicalParameters);
    return arr.map((x, idx) => ({
      category: String(x?.category || ""),
      item: String(x?.item || ""),
      requirement: String(x?.requirement || ""),
      parameters: asArray(x?.parameters),
      evidence: asArray(x?.evidence_chunk_ids),
      _idx: idx,
    }));
  }, [dataJson]);

  const business = useMemo(() => {
    const arr = asArray(dataJson?.business_terms || dataJson?.businessTerms);
    return arr.map((x, idx) => ({
      term: String(x?.term || ""),
      requirement: String(x?.requirement || ""),
      evidence: asArray(x?.evidence_chunk_ids),
      _idx: idx,
    }));
  }, [dataJson]);

  const scoring = useMemo(() => {
    const sc = dataJson?.scoring_criteria || dataJson?.scoringCriteria || {};
    const items = asArray(sc?.items).map((x, idx) => ({
      category: String(x?.category || ""),
      item: String(x?.item || ""),
      score: String(x?.score || ""),
      rule: String(x?.rule || ""),
      evidence: asArray(x?.evidence_chunk_ids),
      _idx: idx,
    }));
    return {
      evaluationMethod: String(sc?.evaluationMethod || ""),
      items,
    };
  }, [dataJson]);

  const showEvidenceBtn = (ids: any[]) =>
    onEvidence && ids && ids.length > 0 ? (
      <button className="link-button" onClick={() => onEvidence(ids)}>
        证据({ids.length})
      </button>
    ) : null;

  return (
    <div>
      {/* 基本信息 */}
      <div className="source-card" style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontWeight: 700 }}>项目信息</div>
          <button className="link-button" onClick={() => setShowRaw((v) => !v)}>
            {showRaw ? "隐藏原始JSON" : "查看原始JSON"}
          </button>
        </div>

        {!showRaw ? (
          <div className="tender-kv-grid" style={{ marginTop: 12 }}>
            {BASIC_FIELDS.map((f) => {
              const v = baseInfo?.[f.k];
              const text = (v === null || v === undefined || String(v).trim() === "") ? "—" : String(v);
              return (
                <div key={f.k} className="tender-kv-item">
                  <div className="tender-kv-label">{f.label}</div>
                  <div className="tender-kv-value">{text}</div>
                </div>
              );
            })}
          </div>
        ) : (
          <pre className="md-pre" style={{ marginTop: 12 }}>
            <code>{JSON.stringify(info || {}, null, 2)}</code>
          </pre>
        )}
      </div>

      {/* 技术参数 */}
      <div className="source-card" style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontWeight: 700 }}>技术参数（功能/指标）</div>
          <div className="kb-doc-meta">条目：{technical.length}</div>
        </div>

        {technical.length === 0 ? (
          <div className="kb-empty" style={{ marginTop: 10 }}>未抽取到技术参数</div>
        ) : (
          <div className="tender-table-wrap" style={{ marginTop: 10 }}>
            <table className="tender-table">
              <thead>
                <tr>
                  <th style={{ width: 140 }}>分类</th>
                  <th style={{ width: 220 }}>功能/条目</th>
                  <th>要求</th>
                  <th style={{ width: 220 }}>参数</th>
                  <th style={{ width: 120 }}>证据</th>
                </tr>
              </thead>
              <tbody>
                {technical.map((t) => (
                  <tr key={t._idx}>
                    <td>{t.category || "—"}</td>
                    <td>{t.item || "—"}</td>
                    <td className="tender-cell">{t.requirement || "—"}</td>
                    <td className="tender-cell">
                      {t.parameters.length === 0 ? (
                        "—"
                      ) : (
                        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                          {t.parameters.slice(0, 6).map((p: any, i: number) => (
                            <div key={i} className="kb-doc-meta">
                              {String(p?.name || "参数")}：{String(p?.value || "")}
                              {p?.unit ? ` ${p.unit}` : ""}
                              {p?.remark ? `（${p.remark}）` : ""}
                            </div>
                          ))}
                          {t.parameters.length > 6 && <div className="kb-doc-meta">…还有 {t.parameters.length - 6} 条</div>}
                        </div>
                      )}
                    </td>
                    <td>{showEvidenceBtn(t.evidence)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 商务条款 */}
      <div className="source-card" style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontWeight: 700 }}>商务条款</div>
          <div className="kb-doc-meta">条目：{business.length}</div>
        </div>

        {business.length === 0 ? (
          <div className="kb-empty" style={{ marginTop: 10 }}>未抽取到商务条款</div>
        ) : (
          <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 10 }}>
            {business.map((b) => (
              <div key={b._idx} className="kb-doc-card">
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                  <div className="kb-doc-title">{b.term || "条款"}</div>
                  {showEvidenceBtn(b.evidence)}
                </div>
                <div className="tender-cell" style={{ marginTop: 6 }}>{b.requirement || "—"}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 评分标准 */}
      <div className="source-card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <div style={{ fontWeight: 700 }}>评分标准</div>
          <div className="kb-doc-meta">条目：{scoring.items.length}</div>
        </div>

        {scoring.evaluationMethod && (
          <div className="kb-doc-meta" style={{ marginTop: 8 }}>
            评标办法：{scoring.evaluationMethod}
          </div>
        )}

        {scoring.items.length === 0 ? (
          <div className="kb-empty" style={{ marginTop: 10 }}>未抽取到评分细则</div>
        ) : (
          <div className="tender-table-wrap" style={{ marginTop: 10 }}>
            <table className="tender-table">
              <thead>
                <tr>
                  <th style={{ width: 160 }}>大项</th>
                  <th>细则</th>
                  <th style={{ width: 90 }}>分值</th>
                  <th style={{ width: 120 }}>证据</th>
                </tr>
              </thead>
              <tbody>
                {scoring.items.map((s) => (
                  <tr key={s._idx}>
                    <td>{s.category || "—"}</td>
                    <td className="tender-cell">
                      <div style={{ fontWeight: 600 }}>{s.item || "—"}</div>
                      {s.rule ? <div className="kb-doc-meta" style={{ marginTop: 6 }}>{s.rule}</div> : null}
                    </td>
                    <td>{s.score || "—"}</td>
                    <td>{showEvidenceBtn(s.evidence)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
