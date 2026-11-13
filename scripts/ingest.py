"""一键接入语料：PDF / docx / txt / md / html → 分块 → 向量化 → 写 Milvus + SQLite。

用法（在 backend/ 目录下）：
    python scripts/ingest.py --source ../PRD_and_project_introduction/
    python scripts/ingest.py --source ../data/saffire --investigation Saffire

- 默认按文件名关键字自动识别调查（Saffire / BASS-M / BASS-II / BASS）。
- 无法识别时用 --investigation 显式指定，或改 SOURCE_KEYWORDS。
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

# 让 `python scripts/ingest.py` 也能 import app.*（把 backend/ 加入 sys.path）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ingestion.chunker import chunk_text
from app.ingestion.indexer import insert_passages, seed_investigations, upsert_document
from app.ingestion.loaders import extract_text
from app.retrieval.store import init_db

SUPPORTED_EXTS = {".pdf", ".docx", ".txt", ".md", ".html", ".htm"}

# 文件名关键字 → investigation 映射（按顺序匹配，broadest 的 "bass" 放最后）。
SOURCE_KEYWORDS = {
    "Saffire": ["saffire"],
    "BASS-M": ["milliken", "bass-m", "bass_m", "bassm"],
    "BASS-II": ["bass-ii", "bass_ii", "bassii", "bass-2", "bass_2"],
    "BASS": ["bass"],
}


def guess_investigation(fname: str) -> str | None:
    lower = fname.lower()
    for investigation_id, keywords in SOURCE_KEYWORDS.items():
        if any(k in lower for k in keywords):
            return investigation_id
    return None


def _iter_files(source_dir: str, recursive: bool):
    p = Path(source_dir)
    pattern = "**/*" if recursive else "*"
    for path in sorted(p.glob(pattern)):
        if path.is_file() and not path.name.startswith("."):
            yield path


def main(source_dir: str, investigation: str | None, recursive: bool) -> None:
    init_db()
    seed_investigations()

    count = 0
    for path in _iter_files(source_dir, recursive):
        fname = path.name
        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTS:
            print(f"[skip] {fname} (unsupported type {ext})")
            continue

        investigation_id = investigation or guess_investigation(fname)
        if investigation_id is None:
            print(f"[skip] {fname} (cannot guess investigation; use --investigation)")
            continue

        document_id = f"{investigation_id}-{path.stem[:32]}"
        print(f"[ingest] {fname} -> {investigation_id} (document={document_id})")

        try:
            text = extract_text(str(path))
        except Exception as exc:
            print(f"[error] {fname}: {exc}")
            continue

        chunks = chunk_text(
            text,
            document_id=document_id,
            investigation_id=investigation_id,
            source_url="",
        )
        n = insert_passages(chunks)
        upsert_document(
            document_id=document_id,
            investigation_id=investigation_id,
            title=fname,
            source_url="",
            local_filename=str(path),
            retrieval_date=date.today().isoformat(),
        )
        print(f"[ingest] {n} passages written")
        count += 1

    print(f"[ingest] done ({count} files)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest source documents into Milvus + SQLite")
    parser.add_argument("--source", required=True, help="Directory containing source files")
    parser.add_argument(
        "--investigation",
        default=None,
        help="Force all files to this investigation (BASS/BASS-II/BASS-M/Saffire); "
        "overrides filename guessing",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Do not recurse into subdirectories (default: recurse)",
    )
    args = parser.parse_args()
    main(args.source, args.investigation, recursive=not args.no_recursive)
