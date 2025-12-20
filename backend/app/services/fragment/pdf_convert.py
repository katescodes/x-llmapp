import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path


def _pick_soffice() -> str:
    for c in ["soffice", "libreoffice"]:
        p = shutil.which(c)
        if p:
            return p
    return "/usr/bin/soffice"


def _run(cmd: list[str], env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _newest(outdir: Path, exts: tuple[str, ...]) -> Path | None:
    files = [p for p in outdir.iterdir() if p.is_file() and p.suffix.lower() in exts]
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


def pdf_to_docx(pdf_path: str) -> str:
    """
    稳定版 PDF->DOCX：
    - 使用独立 UserInstallation + HOME（避免并发/权限/首次启动问题）
    - 输入固定为 input.pdf（避免路径/文件名问题）
    - 优先 PDF->DOCX；失败则 PDF->ODT->DOCX（很多环境更稳）
    - 以"实际文件是否生成 + stderr 是否包含 impl_store failed"为准判定成功
    """
    src = Path(os.path.abspath(pdf_path))
    if not src.exists():
        raise RuntimeError(f"pdf_to_docx: pdf not found: {src}")

    base = Path(tempfile.gettempdir()) / "tender_pdf2docx" / uuid.uuid4().hex[:12]
    outdir = base / "out"
    profile = base / "lo_profile"
    base.mkdir(parents=True, exist_ok=True)
    outdir.mkdir(parents=True, exist_ok=True)
    profile.mkdir(parents=True, exist_ok=True)

    # 固定短文件名
    inp_pdf = base / "input.pdf"
    shutil.copyfile(str(src), str(inp_pdf))

    soffice = _pick_soffice()
    profile_uri = profile.resolve().as_uri()

    env = os.environ.copy()
    env["HOME"] = str(profile)          # LO 必须可写
    env["TMPDIR"] = str(base)
    env.setdefault("LANG", "C.UTF-8")
    env.setdefault("LC_ALL", "C.UTF-8")

    def has_store_error(stderr: str) -> bool:
        s = (stderr or "")
        return ("impl_store" in s and "failed" in s) or ("Error:" in s and "impl_store" in s)

    # --- 1) 直接 PDF -> DOCX
    cmd1 = [
        soffice,
        "--headless", "--nologo", "--nolockcheck", "--nodefault", "--norestore",
        "--nofirststartwizard",
        f"-env:UserInstallation={profile_uri}",
        "--infilter=writer_pdf_import",
        "--convert-to", 'docx:"MS Word 2007 XML"',
        "--outdir", str(outdir),
        str(inp_pdf),
    ]
    p1 = _run(cmd1, env)
    docx1 = _newest(outdir, (".docx",))
    if docx1 and docx1.exists() and (not has_store_error(p1.stderr)):
        return str(docx1)

    # --- 2) fallback：PDF -> ODT（writer8）
    cmd2 = [
        soffice,
        "--headless", "--nologo", "--nolockcheck", "--nodefault", "--norestore",
        "--nofirststartwizard",
        f"-env:UserInstallation={profile_uri}",
        "--infilter=writer_pdf_import",
        "--convert-to", 'odt:"writer8"',
        "--outdir", str(outdir),
        str(inp_pdf),
    ]
    p2 = _run(cmd2, env)
    odt = _newest(outdir, (".odt",))
    if (not odt) or (not odt.exists()) or has_store_error(p2.stderr):
        raise RuntimeError(
            "PDF 转 ODT 失败（用于二段式转换）。"
            f" outdir={outdir}\ncmd={' '.join(cmd2)}\ncode={p2.returncode}\n"
            f"stdout={p2.stdout}\n\nstderr={p2.stderr}\n"
            f"outdir_files={sorted([x.name for x in outdir.iterdir()])}\n"
        )

    # --- 3) ODT -> DOCX
    cmd3 = [
        soffice,
        "--headless", "--nologo", "--nolockcheck", "--nodefault", "--norestore",
        "--nofirststartwizard",
        f"-env:UserInstallation={profile_uri}",
        "--convert-to", 'docx:"MS Word 2007 XML"',
        "--outdir", str(outdir),
        str(odt),
    ]
    p3 = _run(cmd3, env)
    docx3 = _newest(outdir, (".docx",))
    if (not docx3) or (not docx3.exists()) or has_store_error(p3.stderr):
        raise RuntimeError(
            "PDF 二段式转换失败：ODT->DOCX 未生成可用文件。"
            f" outdir={outdir}\ncmd={' '.join(cmd3)}\ncode={p3.returncode}\n"
            f"stdout={p3.stdout}\n\nstderr={p3.stderr}\n"
            f"outdir_files={sorted([x.name for x in outdir.iterdir()])}\n"
        )

    return str(docx3)
