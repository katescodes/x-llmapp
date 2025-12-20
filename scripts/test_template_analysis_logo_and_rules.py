#!/usr/bin/env python3
"""
Self-test: template analysis should
- detect header/footer images (logo_detected)
- force base_policy.mode == KEEP_ALL when logo_detected=true
- produce executable style_rules (at least body + heading1)
- keep style_hints.heading1_style non-empty

Usage
- (preferred) API mode (requires backend running):
    BASE_URL=http://localhost:8000 TEMPLATE_ID=... DOCX_PATH=... python3 scripts/test_template_analysis_logo_and_rules.py
  Optional: AUTH_TOKEN=...

- (fallback) local mode (no server): just run extractor+analyzer in-process
    DOCX_PATH=... python3 scripts/test_template_analysis_logo_and_rules.py --local
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip()
    return v or default


def _fail(msg: str) -> None:
    print("FAIL:", msg)
    raise SystemExit(1)


def _pass(msg: str) -> None:
    print("PASS:", msg)
    raise SystemExit(0)


def _pick_docx_with_logo(candidates: List[Path]) -> Tuple[Path, Dict[str, Any]]:
    from app.services.template.docx_extractor import DocxBlockExtractor

    ex = DocxBlockExtractor()
    for p in candidates:
        try:
            b = p.read_bytes()
            r = ex.extract(b, max_blocks=120, max_chars_per_block=200)
            hfm = getattr(r, "header_footer_media", {}) or {}
            if isinstance(hfm, dict) and hfm.get("logo_detected"):
                return p, hfm
        except Exception:
            continue
    _fail("No candidate docx has header/footer images (logo_detected=false for all). Set DOCX_PATH.")
    raise AssertionError("unreachable")


def _default_candidates(repo_root: Path) -> List[Path]:
    # keep it small & deterministic
    cands: List[Path] = []
    for rel in [
        "data/tender_assets",
        "storage/attachments",
    ]:
        base = repo_root / rel
        if not base.exists():
            continue
        cands.extend(sorted(base.rglob("*.docx")))
    return cands[:30]


def _headers(auth_token: Optional[str]) -> Dict[str, str]:
    h: Dict[str, str] = {"Accept": "application/json"}
    if auth_token:
        h["Authorization"] = f"Bearer {auth_token}"
    return h


def _json_get(client, url: str, auth_token: Optional[str]) -> Any:
    r = client.get(url, headers=_headers(auth_token))
    if r.status_code in (401, 403):
        _fail(f"Auth failed for GET {url}: {r.status_code} (set AUTH_TOKEN)")
    r.raise_for_status()
    return r.json()


def _pick_template_id(client, base_url: str, auth_token: Optional[str], env_template_id: Optional[str]) -> str:
    if env_template_id:
        return env_template_id
    rows = _json_get(client, f"{base_url}/api/apps/tender/format-templates", auth_token)
    if not isinstance(rows, list) or not rows:
        _fail("No format templates found via GET /api/apps/tender/format-templates (set TEMPLATE_ID)")
    tid = str(rows[0].get("id") or "")
    if not tid:
        _fail("First format template has empty id")
    return tid


def _assert_spec(spec: Dict[str, Any], expect_keep_all: bool) -> None:
    if not isinstance(spec, dict):
        _fail("spec is not a JSON object")

    bp = spec.get("base_policy") or {}
    mode = (bp.get("mode") or "").strip()
    if expect_keep_all and mode != "KEEP_ALL":
        _fail(f"expected base_policy.mode=KEEP_ALL when logo_detected=true, got: {mode!r}")

    hints = spec.get("style_hints") or {}
    h1 = (hints.get("heading1_style") or "").strip()
    if not h1:
        _fail("spec.style_hints.heading1_style empty")

    rules = spec.get("style_rules") or []
    if not isinstance(rules, list):
        _fail("spec.style_rules not a list")
    targets = {str(r.get("target")) for r in rules if isinstance(r, dict) and r.get("target")}
    if "body" not in targets or "heading1" not in targets:
        _fail(f"spec.style_rules must include targets body + heading1, got: {sorted(targets)}")

    diag = spec.get("diagnostics") or {}
    if "confidence" not in diag:
        _fail("spec.diagnostics.confidence missing")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="run extractor+analyzer in-process (no HTTP server)")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    docx_path = _env("DOCX_PATH")

    if docx_path:
        p = Path(docx_path)
        if not p.exists():
            _fail(f"DOCX_PATH not found: {p}")
        candidates = [p]
    else:
        candidates = _default_candidates(repo_root)
        if not candidates:
            _fail("No default docx candidates found. Set DOCX_PATH.")

    chosen_docx, hfm = _pick_docx_with_logo(candidates)
    expect_keep_all = bool(hfm.get("logo_detected"))
    print(f"[info] using docx: {chosen_docx} (logo_detected={expect_keep_all})")

    if args.local:
        import asyncio
        from app.services.template.docx_extractor import DocxBlockExtractor
        from app.services.template.llm_analyzer import TemplateLlmAnalyzer

        b = chosen_docx.read_bytes()
        ex = DocxBlockExtractor()
        extract_result = ex.extract(b, max_blocks=220, max_chars_per_block=260)
        analyzer = TemplateLlmAnalyzer()

        spec_obj = asyncio.run(analyzer.analyze(extract_result))
        spec = spec_obj.to_dict()
        _assert_spec(spec, expect_keep_all=expect_keep_all)
        _pass("local analyzer: KEEP_ALL + style_rules OK")

    # API mode
    try:
        import httpx
    except Exception:
        _fail("httpx not installed; run with --local or install httpx")

    base_url = _env("BASE_URL", "http://localhost:8000")
    auth_token = _env("AUTH_TOKEN")
    with httpx.Client(timeout=120) as client:
        template_id = _pick_template_id(client, base_url, auth_token, _env("TEMPLATE_ID"))

        # Force analyze with selected docx
        files = {"file": (chosen_docx.name, chosen_docx.read_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        r = client.post(
            f"{base_url}/api/apps/tender/format-templates/{template_id}/analyze",
            params={"force": "true"},
            files=files,
            headers=_headers(auth_token),
        )
        if r.status_code in (401, 403):
            _fail(f"Auth failed for POST analyze: {r.status_code} (set AUTH_TOKEN)")
        r.raise_for_status()

        # Fetch spec + summary
        spec = _json_get(client, f"{base_url}/api/apps/tender/format-templates/{template_id}/spec", auth_token)
        summary = _json_get(client, f"{base_url}/api/apps/tender/format-templates/{template_id}/analysis-summary", auth_token)
        if not isinstance(summary, dict):
            _fail("analysis-summary not dict")
        if summary.get("base_policy_mode") != "KEEP_ALL" and expect_keep_all:
            _fail(f"analysis-summary base_policy_mode expected KEEP_ALL, got: {summary.get('base_policy_mode')!r}")

        _assert_spec(spec, expect_keep_all=expect_keep_all)
        _pass("API analyzer: KEEP_ALL + style_rules OK")


if __name__ == "__main__":
    main()


