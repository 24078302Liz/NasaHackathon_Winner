"""一键接入语料：PDF（unstructured hi_res）/ docx / txt / md / html → 切片 → 写 Milvus + SQLite。

用法（在 backend/ 目录下）：
    python scripts/ingest.py --source data/sources
    python scripts/ingest.py --source data/saffire --investigation Saffire

- PDF：unstructured 路径（版面分析 → 过滤/表格/标题栈/清洗 → chunk_by_title 切片）
- 其他格式：loaders 抽文本 → chunker 分块
- 默认按文件名关键字自动识别调查；识别不了用 --investigation 显式指定
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

# 让 `python scripts/ingest.py` 也能 import app.*（把 backend/ 加入 sys.path）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ingestion.chunker import chunk_text
from app.ingestion.indexer import (
    ingest_experiment_table,
    insert_passages,
    seed_investigations,
    upsert_document,
)
from app.ingestion.loaders import extract_text
from app.ingestion.unstructured_pipeline import chunk_elements, chunk_to_passage, process_pdf
from app.retrieval.store import init_db

SUPPORTED_EXTS = {".pdf", ".docx", ".md", ".html", ".htm"}

# 文件名关键字 → investigation 映射（按顺序匹配，broadest 的 "bass" 放最后）。
SOURCE_KEYWORDS = {
    "Fire-Equipment": ["fire detector", "fireman", "air tanks", "fire attire"],
    "Fire-Incidents": ["apollo", "mir", "incident"],
    "Combustion-Guide": ["combustion", "iss-mini-book"],
    "Saffire": ["saffire"],
    "BASS-M": ["milliken", "bass-m", "bass_m", "bassm"],
    "BASS-II": ["bass-ii", "bass_ii", "bassii", "bass-2", "bass_2"],
    "BASS": ["bass"],
}

INVESTIGATION_IDS = {
    "BASS", "BASS-II", "BASS-M", "Saffire", "FLEX", "SAME-R", "Combustion-Guide",
    "Fire-Incidents", "Fire-Equipment",
}

# NASA PSI 实验编号 → 调查名 映射（PSI 顶层文件夹名如 PSI-117）
PSI_ID_MAP = {
    "psi-25": "BASS-II",
    "psi-69": "FLEX",
    "psi-98": "Saffire",
    "psi-101": "SAME-R",
}


def guess_investigation(name: str) -> str | None:
    """按名字（文件名或目录名）判断调查：PSI 编号映射 > 精确匹配调查名 > 关键字匹配。"""
    lower = name.lower().replace("_", " ")  # 下划线也当空格，统一匹配
    if lower in PSI_ID_MAP:
        return PSI_ID_MAP[lower]
    for inv in INVESTIGATION_IDS:
        if lower == inv.lower():
            return inv
    for investigation_id, keywords in SOURCE_KEYWORDS.items():
        if any(k in lower for k in keywords):
            return investigation_id
    return None


def guess_from_path(path: Path, source_dir: str) -> str | None:
    """优先用目录名判断调查（一个实验一个文件夹），兜底用文件名。"""
    try:
        rel = path.relative_to(source_dir)
    except ValueError:
        rel = path
    for part in rel.parts[:-1]:  # 目录部分（不含文件名）
        inv = guess_investigation(part)
        if inv:
            return inv
    return guess_investigation(path.name)


def _iter_files(source_dir: str, recursive: bool):
    p = Path(source_dir)
    pattern = "**/*" if recursive else "*"
    for path in sorted(p.glob(pattern)):
        if path.is_file() and not path.name.startswith("."):
            yield path


def _document_id(investigation_id: str, stem: str) -> str:
    return f"{investigation_id}-{stem[:32]}"


def _has_text_layer(path: Path) -> bool:
    """检查 PDF 是否有文本层（前 3 页有文字即视为有）。

    有文本层 → 本地 pypdf 快速提取（免费、快）；无文本层 → 扫描件，需 Transform hi_res OCR。
    """
    import fitz

    doc = fitz.open(str(path))
    try:
        for page in list(doc)[:3]:
            if page.get_text().strip():
                return True
        return False
    finally:
        doc.close()


def ingest_pdf(path: Path, investigation_id: str) -> tuple[int, str]:
    """PDF：unstructured 路径。返回 (写入 passage 数, document_id)。"""
    document_id = _document_id(investigation_id, path.stem)
    clean_elements = process_pdf(
        str(path),
        investigation_id=investigation_id,
        document_id=document_id,
        source_url="",
    )
    chunks = chunk_elements(clean_elements)
    passages = [
        chunk_to_passage(
            c, i,
            investigation_id=investigation_id,
            document_id=document_id,
            source_url="",
        )
        for i, c in enumerate(chunks)
    ]
    n = insert_passages(passages)
    return n, document_id


def ingest_plain(path: Path, investigation_id: str) -> tuple[int, str]:
    """docx/txt/md/html：loaders + chunker 路径。返回 (写入 passage 数, document_id)。"""
    document_id = _document_id(investigation_id, path.stem)
    text = extract_text(str(path))
    chunks = chunk_text(
        text,
        document_id=document_id,
        investigation_id=investigation_id,
        source_url="",
    )
    n = insert_passages(chunks)
    return n, document_id


def main(source_dir: str, investigation: str | None, recursive: bool) -> None:
    init_db()
    seed_investigations()

    count = 0
    for path in _iter_files(source_dir, recursive):
        fname = path.name
        ext = path.suffix.lower()

        investigation_id = investigation or guess_from_path(path, source_dir)
        if investigation_id is None:
            print(f"[skip] {fname} (cannot guess investigation; use --investigation)")
            continue

        if ext == ".csv":
            # 实验表 CSV → ExperimentalCondition（结构化数据，不写 Milvus）
            try:
                n = ingest_experiment_table(str(path), investigation_id=investigation_id)
                print(f"[experiment] {fname} -> {n} conditions")
            except Exception as exc:
                print(f"[error] {fname}: {exc}")
            continue

        if ext not in SUPPORTED_EXTS:
            print(f"[skip] {fname} (unsupported type {ext})")
            continue

        print(f"[ingest] {fname} -> {investigation_id}")
        try:
            if ext == ".pdf" and _has_text_layer(path):
                # 有文本层：本地 pypdf 快速提取（省 Transform API、快）
                n, document_id = ingest_plain(path, investigation_id)
            elif ext == ".pdf":
                # 扫描件/图纸：无文本层，超出 PRD 范围（非知识文档），跳过
                print(f"[skip] {fname} (扫描件/无文本层，跳过)")
                continue
            else:
                n, document_id = ingest_plain(path, investigation_id)
        except Exception as exc:
            print(f"[error] {fname}: {exc}")
            continue

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
