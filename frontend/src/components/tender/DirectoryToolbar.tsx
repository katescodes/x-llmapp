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
  generationMode?: string;  // "fast" | "llm" | "hybrid"
  fastStats?: any;
  refinementStats?: any;  // 规则细化统计
  bracketParsingStats?: any;  // 括号解析统计
  templateMatchingStats?: any;  // ✨ 新增：范本填充统计
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
  generationMode,
  fastStats,
  refinementStats,
  bracketParsingStats,
  templateMatchingStats,  // ✨ 新增
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
        <div style={{ marginBottom: 6 }}>
          <strong>说明：</strong>生成目录成功后，下方区域会原地切换为"一页模式（目录+正文）"。正文为自动保存。套用格式后可切换到"格式预览"查看整体效果。
        </div>
        <div style={{ padding: '6px 10px', background: 'rgba(59, 130, 246, 0.08)', borderRadius: 4, fontSize: '12px', color: '#475569', lineHeight: '1.6' }}>
          💡 <strong>目录生成策略：</strong>
          <br/>
          • 优先从招标书的"投标文件格式"章节精确提取（规则方法，保持原样）
          <br/>
          • 如无标准格式章节，则基于招标要求由AI智能生成（LLM方法）
          <br/>
          • 两种方法互为补充，确保目录完整性和准确性
        </div>
        {generationMode && (
          <div style={{ marginTop: 4, padding: '6px 10px', background: 'rgba(16, 185, 129, 0.1)', borderRadius: 4, fontSize: '13px' }}>
            {generationMode === 'fast' && (
              <span style={{ color: '#10b981' }}>
                ⚡ 快速生成模式：基于已提取的项目信息构建骨架
                {fastStats && ` (${fastStats.total_nodes}个节点，其中${fastStats.from_project_info}个来自项目信息)`}
              </span>
            )}
            {generationMode === 'llm' && (
              <span style={{ color: '#6366f1' }}>
                🤖 LLM生成模式：通过检索招标书全文生成目录
              </span>
            )}
            {generationMode === 'hybrid' && (
              <span style={{ color: '#f59e0b' }}>
                🔀 混合模式：基础骨架来自项目信息，细节由LLM补充
                {fastStats && ` (快速生成${fastStats.from_project_info}个节点)`}
              </span>
            )}
          </div>
        )}
        {/* ✨ 新增：细化统计 */}
        {refinementStats && refinementStats.enabled && (
          <div style={{ marginTop: 4, padding: '6px 10px', background: 'rgba(147, 51, 234, 0.1)', borderRadius: 4, fontSize: '12px' }}>
            <span style={{ color: '#9333ea', fontWeight: 500 }}>
              ✨ 规则细化：
            </span>
            <span style={{ color: '#7c3aed' }}>
              {refinementStats.new_nodes > 0 ? (
                <>
                  从招标要求中提取了 <strong>{refinementStats.new_nodes}</strong> 个细分节点
                  {refinementStats.refinable_nodes && ` (细化了 ${refinementStats.refinable_nodes} 个父节点)`}
                  {/* 示例：评分标准 → 5个评分项子节点 */}
                </>
              ) : (
                '未发现可细化的节点'
              )}
            </span>
          </div>
        )}
        {/* ✨ 新增：括号解析统计 */}
        {bracketParsingStats && bracketParsingStats.enabled && (
          <div style={{ marginTop: 4, padding: '6px 10px', background: 'rgba(59, 130, 246, 0.1)', borderRadius: 4, fontSize: '12px' }}>
            <span style={{ color: '#3b82f6', fontWeight: 500 }}>
              🔍 LLM括号解析：
            </span>
            <span style={{ color: '#2563eb' }}>
              {bracketParsingStats.new_l4_nodes > 0 ? (
                <>
                  从括号说明中提取了 <strong>{bracketParsingStats.new_l4_nodes}</strong> 个L4子节点
                  {bracketParsingStats.split_count > 0 && ` (解析了 ${bracketParsingStats.split_count}/${bracketParsingStats.bracket_candidates} 个括号)`}
                </>
              ) : (
                `检查了${bracketParsingStats.bracket_candidates || 0}个括号，未发现需要拆分的列表项`
              )}
            </span>
          </div>
        )}
        {/* ✨ 新增：范本填充统计 */}
        {templateMatchingStats && templateMatchingStats.enabled && (
          <div style={{ marginTop: 4, padding: '6px 10px', background: 'rgba(236, 72, 153, 0.1)', borderRadius: 4, fontSize: '12px' }}>
            <span style={{ color: '#ec4899', fontWeight: 500 }}>
              📄 格式范本填充：
            </span>
            <span style={{ color: '#db2777' }}>
              {templateMatchingStats.filled_count > 0 ? (
                <>
                  自动填充了 <strong>{templateMatchingStats.filled_count}</strong> 个节点的格式范本
                  {templateMatchingStats.filled_nodes && templateMatchingStats.filled_nodes.length > 0 && (
                    <span style={{ fontSize: '10px', marginLeft: '4px' }}>
                      ({templateMatchingStats.filled_nodes.slice(0, 3).join('、')}{templateMatchingStats.filled_nodes.length > 3 && '...'})
                    </span>
                  )}
                </>
              ) : (
                templateMatchingStats.matches_count > 0 
                  ? `发现${templateMatchingStats.matches_count}个匹配但填充失败`
                  : '未发现可匹配的格式范本'
              )}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
