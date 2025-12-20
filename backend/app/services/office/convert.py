"""
Office 文档转换工具
使用 LibreOffice 进行文档格式转换
"""
from __future__ import annotations
import subprocess
import tempfile
import uuid
from pathlib import Path


def docx_to_pdf(docx_path: str) -> str:
    """
    将 DOCX 转换为 PDF
    
    Args:
        docx_path: DOCX 文件路径
        
    Returns:
        生成的 PDF 文件路径
        
    Raises:
        RuntimeError: 转换失败时抛出
    """
    run_id = uuid.uuid4().hex[:10]
    outdir = Path(tempfile.gettempdir()) / "tender_render_pdf" / run_id
    outdir.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            "soffice", "--headless", "--nologo", "--nolockcheck",
            "--convert-to", "pdf",
            "--outdir", str(outdir),
            docx_path
        ],
        check=True,
        capture_output=True,
    )
    
    pdfs = list(outdir.glob("*.pdf"))
    if not pdfs:
        raise RuntimeError(f"DOCX 转 PDF 失败：未生成 PDF 文件，outdir={outdir}")
    
    # 如果有多个 PDF，返回最新的
    if len(pdfs) > 1:
        pdfs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    
    return str(pdfs[0])


def pdf_to_docx(pdf_path: str) -> str:
    """
    将 PDF 转换为 DOCX（用于范本提取）
    
    Args:
        pdf_path: PDF 文件路径
        
    Returns:
        生成的 DOCX 文件路径
        
    Raises:
        RuntimeError: 转换失败时抛出
    """
    run_id = uuid.uuid4().hex[:10]
    outdir = Path(tempfile.gettempdir()) / "tender_pdf2docx" / run_id
    outdir.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            "soffice", "--headless", "--nologo", "--nolockcheck",
            "--convert-to", "docx",
            "--outdir", str(outdir),
            pdf_path
        ],
        check=True,
    )

    docx_files = list(outdir.glob("*.docx"))
    if not docx_files:
        raise RuntimeError(f"PDF 转 DOCX 失败：未生成 DOCX 文件，outdir={outdir}")
    
    if len(docx_files) > 1:
        docx_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    
    return str(docx_files[0])

