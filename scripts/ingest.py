"""Import document passages into Milvus and structured records into SQLite.

Usage from the repository root:
    python scripts/ingest.py --source data/sources
    python scripts/ingest.py --source data/saffire --investigation Saffire

- The optional PDF helper performs layout analysis and title-aware chunking.
- Other supported documents use the plain-text loaders and chunker.
- Infer investigations from paths, or specify --investigation explicitly.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

# Allow this CLI to import app modules from the repository root.
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

# Match specific investigation keywords before the broader bass keyword.
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

# Map NASA PSI directory identifiers to investigation names.
PSI_ID_MAP = {
    "psi-25": "BASS-II",
    "psi-69": "FLEX",
    "psi-98": "Saffire",
    "psi-101": "SAME-R",
}


def guess_investigation(name: str) -> str | None:
    """Identify an investigation by PSI identifier, exact name, then keywords."""
    lower = name.lower().replace("_", " ")  # Normalize underscores to spaces.
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
    """Prefer parent directory names, then fall back to the filename."""
    try:
        rel = path.relative_to(source_dir)
    except ValueError:
        rel = path
    for part in rel.parts[:-1]:  # Directory components, excluding the filename.
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
    """Check the first three PDF pages for extractable text.

    Text PDFs use local pypdf extraction; scanned documents need OCR processing.
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
    """Process PDF layout and return the passage count and document ID."""
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
    """Extract plain document text and return the passage count and document ID."""
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
            # Import experiment CSV rows into SQLite rather than the vector index.
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
                # Extract searchable PDFs locally without hosted layout analysis.
                n, document_id = ingest_plain(path, investigation_id)
            elif ext == ".pdf":
                # Skip scanned documents that have no searchable text layer.
                print(f"[skip] {fname} (scanned PDF or missing text layer)")
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
