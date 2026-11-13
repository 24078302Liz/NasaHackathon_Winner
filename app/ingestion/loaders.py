"""语料解析：PDF / docx / HTML / txt 文本抽取。"""
from __future__ import annotations

import os


def extract_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return _extract_pdf(path)
    if ext == ".docx":
        return _extract_docx(path)
    if ext in (".html", ".htm"):
        return _extract_html(path)
    if ext in (".txt", ".md"):
        with open(path, encoding="utf-8") as f:
            return f.read()
    raise ValueError(f"Unsupported file type: {ext}")


def _extract_pdf(path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def _extract_docx(path: str) -> str:
    import docx

    document = docx.Document(path)
    return "\n".join(p.text for p in document.paragraphs)


def _extract_html(path: str) -> str:
    from bs4 import BeautifulSoup

    with open(path, encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    # 去掉非正文标签，避免导航/脚本/样式干扰检索
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text("\n")
