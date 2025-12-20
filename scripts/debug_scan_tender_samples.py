#!/usr/bin/env python3
"""
Debug: 扫描招标书 docx 的 body 元素并打印“范本锚点”命中情况。

用法：
  python scripts/debug_scan_tender_samples.py <project_id>

输出：
- tender storage_path
- N（body 元素总数）
- 命中锚点的前 40 条（index + type + text前80字）

说明：
若 anchors=0，常见原因是“范本是图片/扫描件，docx 内无可读文本”，只能走内置范本或要求提供可编辑 docx。
"""

from __future__ import annotations

import sys
from typing import Dict, List, Optional


def _pick_latest_tender_asset(assets: List[Dict]) -> Optional[Dict]:
    tenders = [a for a in (assets or []) if (a or {}).get("kind") == "tender"]
    if not tenders:
        return None
    try:
        tenders_sorted = sorted(tenders, key=lambda x: str(x.get("created_at") or ""), reverse=True)
        return tenders_sorted[0]
    except Exception:
        return tenders[-1]


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/debug_scan_tender_samples.py <project_id>")
        raise SystemExit(2)

    project_id = sys.argv[1].strip()
    if not project_id:
        raise SystemExit(2)

    # 连接 DB（复用 backend 的连接池/配置）
    from app.services.db.postgres import init_db, _get_pool  # type: ignore
    from app.services.dao.tender_dao import TenderDAO
    from app.services.fragment.fragment_extractor import TenderSampleFragmentExtractor

    init_db()
    dao = TenderDAO(_get_pool())

    assets = dao.list_assets(project_id)
    tender = _pick_latest_tender_asset(assets)
    if not tender:
        print(f"[debug] project_id={project_id} no tender asset found")
        raise SystemExit(1)

    path = str((tender.get("storage_path") or "")).strip()
    print(f"[debug] project_id={project_id}")
    print(f"[debug] tender_asset_id={tender.get('id')} filename={tender.get('filename')!r}")
    print(f"[debug] tender_storage_path={path!r}")

    if not path:
        print("[debug] storage_path is empty -> cannot scan (need reupload)")
        raise SystemExit(1)

    import os

    if not os.path.exists(path):
        print("[debug] storage_path not exists on disk -> cannot scan (need reupload)")
        raise SystemExit(1)

    if not path.lower().endswith(".docx"):
        print("[debug] tender is not .docx -> cannot scan")
        raise SystemExit(1)

    from docx import Document
    from io import BytesIO

    with open(path, "rb") as f:
        b = f.read()
    doc = Document(BytesIO(b))
    n_total = len(list(doc.element.body))
    print(f"[debug] body_elements_total={n_total}")

    extractor = TenderSampleFragmentExtractor(dao)
    elements_meta, anchors = extractor._scan_body_elements(doc)  # noqa: SLF001 (debug use)
    print(f"[debug] elements_meta={len(elements_meta)} anchors_found={len(anchors)}")
    print("[debug] anchors top40:")
    for i in anchors[:40]:
        m = next((x for x in elements_meta if int(x.get("i")) == int(i)), None)
        if not m:
            continue
        txt = str(m.get("txt") or "").replace("\n", " ")
        print(f"  - i={m.get('i')} t={m.get('t')} txt={txt[:80]!r}")


if __name__ == "__main__":
    main()


