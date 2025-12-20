"""
TemplateLlmAnalyzer - 使用 LLM 理解模板意图
"""
from __future__ import annotations

import json
import re
import time
from typing import Optional

from app.config import get_settings
from app.services.llm_client import get_llm_client
from app.services.template.docx_extractor import DocxExtractResult, DocxBlock
from app.services.template.outline_fallback import build_outline_fallback
from app.services.template.template_spec import TemplateSpec, create_minimal_spec
from app.services.template.spec_validator import get_validator, SchemaValidationException
from app.services.template.style_hints_fallback import build_style_hints_fallback


class TemplateLlmAnalyzer:
    """模板 LLM 分析器"""

    def __init__(self):
        self.settings = get_settings()
        self.validator = get_validator()

    async def analyze(self, extract_result: DocxExtractResult) -> TemplateSpec:
        """
        分析提取结果，生成 TemplateSpec
        
        Args:
            extract_result: DocxExtractResult 结构化提取结果
            
        Returns:
            TemplateSpec: 模板规格
        """
        start_time = time.time()
        
        try:
            excluded_tags = {"TOC", "INSTRUCTION", "COLOR_SWATCH"}
            excluded_blocks = [
                b for b in (extract_result.blocks or [])
                if getattr(b, "tag", None) in excluded_tags
            ]
            kept_blocks = [
                b for b in (extract_result.blocks or [])
                if getattr(b, "tag", None) not in excluded_tags
            ]

            # 1. 构造 prompt
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(
                extract_result,
                kept_blocks=kept_blocks,
                excluded_block_ids_candidates=[b.id for b in excluded_blocks],
            )
            
            # 2. 调用 LLM
            llm_client = get_llm_client()
            model_id = self.settings.TEMPLATE_LLM_ANALYSIS_MODEL
            
            response = await llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=model_id,
                temperature=0.1,  # 低温度以获得更稳定输出
                max_tokens=8000
            )
            
            llm_output = response.get("content", "")
            
            # 3. 提取 JSON
            spec_json = self._extract_json(llm_output)
            
            # 4. 校验 Schema
            spec_dict = self.validator.validate(spec_json)
            
            # 5. 构造 TemplateSpec
            spec = TemplateSpec.from_dict(spec_dict)
            
            # 6. 补充诊断信息
            duration_ms = int((time.time() - start_time) * 1000)
            spec.diagnostics.analysis_duration_ms = duration_ms
            spec.diagnostics.llm_model = model_id

            # 7. postprocess：失败/空结果时 deterministic fallback + 强制 exclude
            spec = self._postprocess_spec(spec, extract_result, llm_failed=False)
            return spec
            
        except Exception as e:
            # Fallback: 返回最小规格
            error_msg = f"LLM analysis failed: {type(e).__name__}: {str(e)}"
            spec = create_minimal_spec(confidence=0.0, error_msg=error_msg)
            spec.diagnostics.analysis_duration_ms = int((time.time() - start_time) * 1000)
            return self._postprocess_spec(spec, extract_result, llm_failed=True)

    def _is_style_hints_empty(self, style_hints) -> bool:
        if style_hints is None:
            return True
        keys = [
            "heading1_style",
            "heading2_style",
            "heading3_style",
            "heading4_style",
            "heading5_style",
            "body_style",
            "table_style",
            "list_style",
            "numbering_candidate",
        ]
        return all(getattr(style_hints, k, None) in (None, {}, []) for k in keys)

    def _postprocess_spec(
        self,
        spec: TemplateSpec,
        extract_result: DocxExtractResult,
        llm_failed: bool,
    ) -> TemplateSpec:
        excluded_tags = {"TOC", "INSTRUCTION", "COLOR_SWATCH"}
        tagged_excluded_ids = [
            b.id for b in (extract_result.blocks or [])
            if getattr(b, "tag", None) in excluded_tags
        ]

        # LOGO/页眉页脚：如果 extractor 认为存在页眉/页脚图片，则强制优先 KEEP_ALL
        try:
            hfm = getattr(extract_result, "header_footer_media", None) or {}
            if isinstance(hfm, dict) and bool(hfm.get("logo_detected", False)):
                if getattr(spec, "base_policy", None):
                    # 这里用 KEEP_ALL 最保守，确保 tpl_doc 作为 base 且保留页眉页脚
                    from app.services.template.template_spec import BasePolicyMode
                    spec.base_policy.mode = BasePolicyMode.KEEP_ALL
                spec.diagnostics.warnings.append("logo_detected=true -> force base_policy.mode=KEEP_ALL")
        except Exception:
            pass

        # style_hints fallback
        try:
            if self._is_style_hints_empty(getattr(spec, "style_hints", None)):
                spec.style_hints = build_style_hints_fallback(extract_result)
                spec.diagnostics.warnings.append("style_hints empty -> deterministic fallback")
        except Exception:
            pass

        # style_rules fallback：尽量从 style_catalog 推导出可执行的 body/heading1
        try:
            if not (getattr(spec, "style_rules", None) or []):
                fallback_rules = self._build_style_rules_fallback(extract_result)
                if fallback_rules:
                    spec.style_rules = fallback_rules  # type: ignore[assignment]
                    spec.diagnostics.warnings.append("style_rules empty -> fallback from style_catalog/style_stats")
        except Exception:
            pass

        # 如果 style_hints 仍为空，给一组稳定的 AI_* 名称（配合导出时自动创建样式）
        try:
            hints = getattr(spec, "style_hints", None)
            if hints:
                if not getattr(hints, "heading1_style", None):
                    hints.heading1_style = "AI_H1"
                if not getattr(hints, "heading2_style", None):
                    hints.heading2_style = "AI_H2"
                if not getattr(hints, "heading3_style", None):
                    hints.heading3_style = "AI_H3"
                if not getattr(hints, "body_style", None):
                    hints.body_style = "AI_BODY"
        except Exception:
            pass

        # outline fallback
        try:
            if not (getattr(spec, "outline", None) or []):
                spec.outline = build_outline_fallback(extract_result)
                spec.diagnostics.warnings.append("outline empty -> deterministic fallback")
        except Exception:
            pass

        # exclude_block_ids 强制包含 extractor 标记的噪声块
        try:
            if llm_failed:
                spec.base_policy.exclude_block_ids = sorted(set(tagged_excluded_ids))
            else:
                existing = (spec.base_policy.exclude_block_ids or []) if spec.base_policy else []
                spec.base_policy.exclude_block_ids = sorted(set(existing + tagged_excluded_ids))
        except Exception:
            pass

        # diagnostics: 给前端/调试一个明确的 instruction 列表（可选）
        try:
            spec.diagnostics.ignored_as_instructions_block_ids = sorted(set(tagged_excluded_ids))
        except Exception:
            pass

        return spec

    def _build_system_prompt(self) -> str:
        """构造系统 prompt"""
        return """你是"招投标 Word 模板分析器"。你的任务是分析模板的结构和意图，输出严格的 JSON 格式规格。

要求：
1. 只输出符合 schema 的 JSON，不要任何解释文字
2. 识别哪些块是"格式说明/操作指引"，加入 exclude_block_ids
3. 判断底板正文范围：KEEP_ALL 或 KEEP_RANGE（优先保留模板页眉页脚/LOGO）
4. 抽取模板定义的卷/章/节骨架（outline），给出层级和 orderNo
5. 识别样式映射：heading1-5, body, table, numbering
6. 生成可执行格式 style_rules：把 instructions_text 中的格式要求转成结构化规则（heading1/2/3/body）
6. mergePolicy 固定：模板定义结构，AI 只补缺失项，不改顺序

硬规则（必须遵守）：
- 如果 header_footer_media.logo_detected == true：base_policy.mode 必须为 KEEP_ALL（保留页眉页脚 LOGO 底板）
- instructions_text 是“格式说明”，不能落到正文 outline；但其中的格式要求必须转成 style_rules
- style_hints 优先选择 style_catalog 中真实存在的 style_name；如果找不到合适样式名，使用 AI_H1/AI_H2/AI_H3/AI_BODY，并在 style_rules 给出字体/字号/加粗/颜色/行距/缩进/对齐等属性
- base_policy.exclude_block_ids 必须包含 excluded_block_ids_candidates 中全部 block_id

输出 JSON 结构：
{
  "version": "v1",
  "language": "zh-CN",
  "base_policy": {
    "mode": "KEEP_ALL" | "KEEP_RANGE" | "REBUILD",
    "range_anchor": { "start_text": "...", "end_text": "..." },
    "exclude_block_ids": ["block-id-1", "block-id-2"],
    "description": "说明"
  },
  "style_hints": {
    "heading1_style": "标题 1",
    "heading2_style": "标题 2",
    "heading3_style": "标题 3",
    "body_style": "正文",
    "table_style": "表格",
    "numbering_candidate": {},
    "page_background": "#ffffff",
    "font_family": "SimSun, serif",
    "font_size": "14px",
    "line_height": "1.6",
    "toc_indent_1": "0px",
    "toc_indent_2": "20px",
    "toc_indent_3": "40px",
    "toc_indent_4": "60px"
  },
  "style_rules": [
    {
      "target": "heading1",
      "font_family": "SimSun",
      "font_size_pt": 16,
      "bold": true,
      "color": "#000000",
      "line_spacing": "1.5",
      "first_line_indent_chars": 0,
      "alignment": "center"
    },
    {
      "target": "body",
      "font_family": "SimSun",
      "font_size_pt": 14,
      "bold": false,
      "color": "#000000",
      "line_spacing": "1.5",
      "first_line_indent_chars": 2,
      "alignment": "left"
    }
  ],
  "outline": [
    {
      "id": "node-1",
      "title": "第一卷 商务标",
      "level": 1,
      "order_no": 1,
      "required": true,
      "style_hint": "标题 1",
      "children": [
        {
          "id": "node-1-1",
          "title": "1. 投标函",
          "level": 2,
          "order_no": 1,
          "required": true,
          "style_hint": "标题 2",
          "children": []
        }
      ]
    }
  ],
  "merge_policy": {
    "template_defines_structure": true,
    "ai_only_fill_missing": true,
    "preserve_template_order": true,
    "ai_cannot_reorder": true,
    "allow_ai_add_siblings": false
  },
  "diagnostics": {
    "confidence": 0.95,
    "warnings": [],
    "ignored_as_instructions_block_ids": []
  }
}"""

    def _select_blocks_for_prompt(
        self,
        blocks: list[DocxBlock],
        max_blocks: int = 220,
        context_window: int = 30,
    ) -> list[DocxBlock]:
        if len(blocks) <= max_blocks:
            return blocks

        important = set()
        for i, b in enumerate(blocks):
            if b.outline_level is None:
                continue
            for j in range(max(0, i - context_window), min(len(blocks), i + context_window + 1)):
                important.add(j)

        # headings first, then context, then trim
        heading_idxs = [i for i in sorted(important) if blocks[i].outline_level is not None]
        ctx_idxs = [i for i in sorted(important) if blocks[i].outline_level is None]
        picked = (heading_idxs + ctx_idxs)[:max_blocks]
        picked_set = set(picked)

        # fill from head if still not enough (should be rare)
        if len(picked) < max_blocks:
            for i in range(len(blocks)):
                if i in picked_set:
                    continue
                picked.append(i)
                picked_set.add(i)
                if len(picked) >= max_blocks:
                    break

        return [blocks[i] for i in sorted(picked)]

    def _build_user_prompt(
        self,
        extract_result: DocxExtractResult,
        kept_blocks: Optional[list[DocxBlock]] = None,
        excluded_block_ids_candidates: Optional[list[str]] = None,
    ) -> str:
        """构造用户 prompt"""
        blocks = kept_blocks if kept_blocks is not None else (extract_result.blocks or [])
        blocks = self._select_blocks_for_prompt(blocks, max_blocks=220, context_window=30)

        style_stats = extract_result.style_stats or {}
        style_stats_short = {
            "heading_style_by_level": style_stats.get("heading_style_by_level") or {},
            "body_style_guess": style_stats.get("body_style_guess"),
            "has_table": style_stats.get("has_table", False),
            "top_styles": style_stats.get("top_styles") or [],
        }

        # 将 DocxExtractResult 转为 JSON
        extract_data = {
            "header_footer_media": getattr(extract_result, "header_footer_media", {}) or {},
            "instructions_text": getattr(extract_result, "instructions_text", "") or "",
            "style_catalog": getattr(extract_result, "style_catalog", {}) or {},
            "tags_by_block_id": getattr(extract_result, "tags_by_block_id", {}) or {},
            "blocks": [
                {
                    "id": block.id,
                    "type": block.type.value,
                    "text": block.text,
                    "tag": getattr(block, "tag", None),
                    "style_id": block.style_id,
                    "style_name": block.style_name,
                    "outline_level": block.outline_level,
                    "num_id": block.num_id,
                    "ilvl": block.ilvl,
                    "sequence": block.sequence,
                    "table_meta": block.table_meta
                }
                for block in blocks
            ],
            "excluded_block_ids_candidates": excluded_block_ids_candidates or [],
            "style_stats": style_stats_short,
            "numbering_stats": extract_result.numbering_stats,
            "header_footer_stats": extract_result.header_footer_stats
        }
        
        extract_json = json.dumps(extract_data, ensure_ascii=False, indent=2)
        
        prompt = f"""请分析以下模板提取结果，输出 TemplateSpec JSON：

{extract_json}

注意：
1. excluded_block_ids_candidates 中的 block_id 必须全部进入 base_policy.exclude_block_ids（它们属于 TOC/INSTRUCTION/COLOR_SWATCH 噪声块）
2. 如果 header_footer_media.logo_detected=true，优先使用 KEEP_ALL（保留页眉页脚 LOGO 底板）
3. instructions_text 是格式说明：不要进入正文 outline，但要把其中的格式要求转成 style_rules（heading1/2/3/body）
4. style_hints 优先选 style_catalog 里真实存在的样式名；若不存在则用 AI_H1/AI_H2/AI_H3/AI_BODY，并用 style_rules 给出具体属性
5. 如果模板前半部分是说明，正文在后半，且 header_footer_media.logo_detected=false，才考虑 KEEP_RANGE 模式
3. outline 不允许来自 TOC 行；只允许来自：tag=="NORMAL" 且 outline_level!=None 的段落块
4. 每个 outline 节点必须有唯一 id、title、level、order_no（同级从 1 递增）
5. style_hints 优先使用 style_stats.heading_style_by_level / body_style_guess 填充 heading1~5 / body；table 可为空但不要瞎猜
6. style_hints 中添加页面样式：page_background（默认 #ffffff）、font_family、font_size、line_height
7. style_hints 中添加目录缩进：toc_indent_1-4（如 0px, 20px, 40px, 60px）
8. confidence 评估为 0-1，如果模板结构清晰则 >0.8

现在输出 JSON："""
        
        return prompt

    def _build_style_rules_fallback(self, extract_result: DocxExtractResult):
        """
        当 LLM 未能产出 style_rules 时，尽量从 style_catalog/style_stats 推导出最小可用规则。
        目标：至少给出 body + heading1，便于导出时自动创建 AI_* 样式。
        """
        from app.services.template.template_spec import StyleRule

        style_catalog = getattr(extract_result, "style_catalog", None) or {}
        styles = style_catalog.get("paragraph_styles") if isinstance(style_catalog, dict) else None
        if not isinstance(styles, list) or not styles:
            return []

        style_stats = extract_result.style_stats or {}
        heading_by_level = style_stats.get("heading_style_by_level") or {}
        body_guess = style_stats.get("body_style_guess")

        def _find_by_name(name: Optional[str]):
            if not name:
                return None
            for s in styles:
                if isinstance(s, dict) and str(s.get("name") or "") == str(name):
                    return s
            return None

        def _find_heading1():
            cand = _find_by_name(heading_by_level.get("1"))
            if cand:
                return cand
            for nm in ("Heading 1", "标题 1", "标题1", "一级标题"):
                cand = _find_by_name(nm)
                if cand:
                    return cand
            # fuzzy: contains
            for s in styles:
                n = str((s or {}).get("name") or "")
                if "Heading 1" in n or "标题 1" in n or "标题1" in n:
                    return s
            return None

        def _find_body():
            cand = _find_by_name(body_guess)
            if cand:
                return cand
            for nm in ("正文", "Normal"):
                cand = _find_by_name(nm)
                if cand:
                    return cand
            # pick first non-heading-ish
            for s in styles:
                n = str((s or {}).get("name") or "").lower()
                if "heading" in n or "标题" in n:
                    continue
                return s
            return styles[0]

        def _to_rule(target: str, sdict: dict):
            font = (sdict.get("font") or {}) if isinstance(sdict.get("font"), dict) else {}
            para = (sdict.get("para") or {}) if isinstance(sdict.get("para"), dict) else {}
            return StyleRule(
                target=target,
                font_family=font.get("name"),
                font_size_pt=font.get("size_pt"),
                bold=font.get("bold"),
                color=font.get("color"),
                line_spacing=para.get("line_spacing"),
                first_line_indent_chars=para.get("first_line_indent_chars"),
                alignment=para.get("alignment"),
                space_before_pt=para.get("space_before_pt"),
                space_after_pt=para.get("space_after_pt"),
            )

        out = []
        h1 = _find_heading1()
        body = _find_body()
        if isinstance(h1, dict):
            out.append(_to_rule("heading1", h1))
        if isinstance(body, dict):
            out.append(_to_rule("body", body))
        return out

    def _extract_json(self, text: str) -> str:
        """
        从 LLM 输出中容错提取 JSON
        支持 markdown code fence 包裹
        """
        if not text:
            raise ValueError("Empty LLM output")
        
        # 1. 尝试提取 markdown code fence 中的内容
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if m:
            text = m.group(1).strip()
        
        # 2. 尝试提取第一个完整的 JSON 对象
        # 找到第一个 { 和最后一个 }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        
        if first_brace == -1 or last_brace == -1 or first_brace >= last_brace:
            raise ValueError("No valid JSON object found in LLM output")
        
        json_text = text[first_brace:last_brace + 1]
        
        # 3. 验证是否为合法 JSON
        try:
            json.loads(json_text)
            return json_text
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")


class TemplateAnalysisCache:
    """模板分析缓存（基于 SHA256）"""

    def __init__(self):
        self._cache: dict[str, str] = {}  # key: sha256+version, value: spec_json

    def get_cache_key(self, sha256: str, analyzer_version: str, model: str) -> str:
        """生成缓存键"""
        return f"{sha256}:{analyzer_version}:{model}"

    def get(self, sha256: str, analyzer_version: str, model: str) -> Optional[str]:
        """获取缓存"""
        key = self.get_cache_key(sha256, analyzer_version, model)
        return self._cache.get(key)

    def set(self, sha256: str, analyzer_version: str, model: str, spec_json: str):
        """设置缓存"""
        key = self.get_cache_key(sha256, analyzer_version, model)
        self._cache[key] = spec_json

    def clear(self):
        """清空缓存"""
        self._cache.clear()


# 全局缓存实例
_cache_instance: Optional[TemplateAnalysisCache] = None


def get_analysis_cache() -> TemplateAnalysisCache:
    """获取缓存单例"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = TemplateAnalysisCache()
    return _cache_instance
