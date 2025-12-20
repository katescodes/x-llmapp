#!/usr/bin/env python3
"""
E2E: 自动填充范本（docker 内一键 PASS/FAIL）

Checks
1) 调 POST /directory/auto-fill-samples
2) 若 ok=false：直接 FAIL 并打印 warnings、needs_reupload、tender_storage_path
3) 若 ok=true：断言 attached_sections >= 1

Run (docker):
  docker-compose exec backend python /app/scripts/test_auto_fill_samples_e2e.py

Env
- BASE_URL: default http://localhost:8000
- PROJECT_ID: optional（不传则取第一个项目）
- AUTH_TOKEN: optional
- USERNAME/PASSWORD: optional（不传则默认 admin/admin123）
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx


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


def _headers(token: Optional[str]) -> Dict[str, str]:
    h = {"Accept": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _login(client: httpx.Client, base_url: str, username: str, password: str) -> Optional[str]:
    try:
        r = client.post(f"{base_url}/api/auth/login", json={"username": username, "password": password})
        if r.status_code != 200:
            return None
        data = r.json()
        return str(data.get("access_token") or "").strip() or None
    except Exception:
        return None


def _json_get(client: httpx.Client, url: str, token: Optional[str]) -> Any:
    r = client.get(url, headers=_headers(token))
    if r.status_code in (401, 403):
        _fail(f"Auth failed for GET {url}: {r.status_code} {r.text}")
    r.raise_for_status()
    return r.json()


def _json_post(client: httpx.Client, url: str, payload: Any, token: Optional[str]) -> Any:
    r = client.post(url, headers=_headers(token), json=payload)
    if r.status_code in (401, 403):
        _fail(f"Auth failed for POST {url}: {r.status_code} {r.text}")
    r.raise_for_status()
    return r.json()


def _pick_project_id(client: httpx.Client, base_url: str, token: str, env_project_id: Optional[str]) -> str:
    if env_project_id:
        return env_project_id
    projects = _json_get(client, f"{base_url}/api/apps/tender/projects", token)
    if not isinstance(projects, list) or not projects:
        _fail("No projects found")
    pid = str((projects[0] or {}).get("id") or "")
    if not pid:
        _fail("First project has empty id")
    return pid


def main() -> None:
    base_url = _env("BASE_URL", "http://localhost:8000")
    project_id = _env("PROJECT_ID")
    token = _env("AUTH_TOKEN")
    username = _env("USERNAME", "admin")
    password = _env("PASSWORD", "admin123")

    with httpx.Client(timeout=90.0, trust_env=False) as client:
        if not token:
            token = _login(client, base_url, username, password)
        if not token:
            _fail("Not authenticated (set AUTH_TOKEN or USERNAME/PASSWORD)")

        pid = _pick_project_id(client, base_url, token, project_id)
        resp = _json_post(
            client,
            f"{base_url}/api/apps/tender/projects/{pid}/directory/auto-fill-samples",
            {},
            token,
        )

        if not isinstance(resp, dict):
            _fail(f"auto-fill-samples resp not object: {type(resp).__name__}")

        ok = bool(resp.get("ok", False))
        warnings = resp.get("warnings") or []
        needs_reupload = bool(resp.get("needs_reupload", False))
        tender_storage_path = resp.get("tender_storage_path")
        extracted = int(resp.get("tender_fragments_upserted") or resp.get("extracted_fragments") or 0)
        attached_tpl = int(resp.get("attached_sections_template_sample") or 0)
        attached_builtin = int(resp.get("attached_sections_builtin") or 0)
        attached = int((attached_tpl + attached_builtin) or (resp.get("attached_sections") or 0))

        if not ok:
            _fail(
                f"ok=false. project_id={pid} needs_reupload={needs_reupload} "
                f"tender_storage_path={tender_storage_path} warnings={warnings}"
            )

        if attached < 1:
            _fail(f"ok=true but attached_sections < 1. project_id={pid} extracted={extracted} attached={attached}")

        if needs_reupload:
            # 允许 PASS，但必须给出明确提示
            note = "NOTE: needs_reupload=true (likely using builtin samples; re-upload tender docx for faithful extraction)"
            print(note)
            if isinstance(warnings, list) and warnings:
                print("warnings[0]:", warnings[0])

        _pass(f"project_id={pid} extracted_fragments={extracted} attached_sections={attached} needs_reupload={needs_reupload}")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPError as e:
        _fail(f"HTTP error: {type(e).__name__}: {e}")

