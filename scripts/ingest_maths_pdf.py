#!/usr/bin/env python3
"""
Ingest NCERT Maths Class 11 + 12 from official PDFs into knowledge_chunks.

Source: ncert.nic.in (public domain — free to use)
  - 16 Class 11 chapters  (kemh101.pdf … kemh116.pdf)
  - 13 Class 12 chapters  (lemh101.pdf … lemh113.pdf)

Embedding model : OpenAI text-embedding-3-small (1536-dim)
                  — must match existing knowledge_chunks.embedding column.

Chunking strategy:
  - 300–400 token target per chunk, 50-token overlap
  - Split on paragraph boundaries first, hard-split on token limit
  - Skip front-matter pages (copyright, index) via heuristic

Resumability:
  - Progress tracked in scripts/.ingest_maths_pdf_progress.json
  - Re-running skips already-completed chapters

Usage:
    poetry run python scripts/ingest_maths_pdf.py
    poetry run python scripts/ingest_maths_pdf.py --class 11
    poetry run python scripts/ingest_maths_pdf.py --class 12
    poetry run python scripts/ingest_maths_pdf.py --chapter kemh103
    poetry run python scripts/ingest_maths_pdf.py --reset-progress
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Generator, List, Optional, Tuple

import asyncpg
import httpx
import tiktoken

# ── paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT   = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

from app.config import settings

# ── constants ─────────────────────────────────────────────────────────────────
PROGRESS_FILE  = SCRIPT_DIR / ".ingest_maths_pdf_progress.json"
PDF_CACHE_DIR  = SCRIPT_DIR / ".pdf_cache"          # local cache — avoids re-downloading
CHUNK_TARGET   = 350    # target tokens
CHUNK_MAX      = 450    # hard split threshold
CHUNK_OVERLAP  = 50     # token overlap between consecutive chunks
CHUNK_MIN      = 60     # discard tiny chunks
EMBED_BATCH    = 20     # OpenAI embeddings batch size
INSERT_BATCH   = 50     # DB insert batch size
EMBED_MODEL    = "text-embedding-3-small"
EMBED_DIM      = 1536
HTTP_TIMEOUT   = 60     # seconds per PDF download

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

_tokenizer = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_tokenizer.encode(text))


# ── chapter catalogue ─────────────────────────────────────────────────────────

CHAPTERS: List[dict] = [
    # Class 11
    {"id": "kemh101", "grade": "Class 11", "name": "Sets",
     "url": "https://ncert.nic.in/textbook/pdf/kemh101.pdf"},
    {"id": "kemh102", "grade": "Class 11", "name": "Relations and Functions",
     "url": "https://ncert.nic.in/textbook/pdf/kemh102.pdf"},
    {"id": "kemh103", "grade": "Class 11", "name": "Trigonometric Functions",
     "url": "https://ncert.nic.in/textbook/pdf/kemh103.pdf"},
    {"id": "kemh104", "grade": "Class 11", "name": "Principle of Mathematical Induction",
     "url": "https://ncert.nic.in/textbook/pdf/kemh104.pdf"},
    {"id": "kemh105", "grade": "Class 11", "name": "Complex Numbers and Quadratic Equations",
     "url": "https://ncert.nic.in/textbook/pdf/kemh105.pdf"},
    {"id": "kemh106", "grade": "Class 11", "name": "Linear Inequalities",
     "url": "https://ncert.nic.in/textbook/pdf/kemh106.pdf"},
    {"id": "kemh107", "grade": "Class 11", "name": "Permutations and Combinations",
     "url": "https://ncert.nic.in/textbook/pdf/kemh107.pdf"},
    {"id": "kemh108", "grade": "Class 11", "name": "Binomial Theorem",
     "url": "https://ncert.nic.in/textbook/pdf/kemh108.pdf"},
    {"id": "kemh109", "grade": "Class 11", "name": "Sequences and Series",
     "url": "https://ncert.nic.in/textbook/pdf/kemh109.pdf"},
    {"id": "kemh110", "grade": "Class 11", "name": "Straight Lines",
     "url": "https://ncert.nic.in/textbook/pdf/kemh110.pdf"},
    {"id": "kemh111", "grade": "Class 11", "name": "Conic Sections",
     "url": "https://ncert.nic.in/textbook/pdf/kemh111.pdf"},
    {"id": "kemh112", "grade": "Class 11", "name": "Introduction to Three Dimensional Geometry",
     "url": "https://ncert.nic.in/textbook/pdf/kemh112.pdf"},
    {"id": "kemh113", "grade": "Class 11", "name": "Limits and Derivatives",
     "url": "https://ncert.nic.in/textbook/pdf/kemh113.pdf"},
    {"id": "kemh114", "grade": "Class 11", "name": "Mathematical Reasoning",
     "url": "https://ncert.nic.in/textbook/pdf/kemh114.pdf"},
    # Class 11 — Statistics/Probability use different NCERT prefix (kest/kesp)
    {"id": "kest101", "grade": "Class 11", "name": "Statistics",
     "url": "https://ncert.nic.in/textbook/pdf/kest101.pdf"},
    {"id": "kesp101", "grade": "Class 11", "name": "Probability",
     "url": "https://ncert.nic.in/textbook/pdf/kesp101.pdf"},
    # Class 12 Part 1 (Chapters 1–6)
    {"id": "lemh101", "grade": "Class 12", "name": "Relations and Functions",
     "url": "https://ncert.nic.in/textbook/pdf/lemh101.pdf"},
    {"id": "lemh102", "grade": "Class 12", "name": "Inverse Trigonometric Functions",
     "url": "https://ncert.nic.in/textbook/pdf/lemh102.pdf"},
    {"id": "lemh103", "grade": "Class 12", "name": "Matrices",
     "url": "https://ncert.nic.in/textbook/pdf/lemh103.pdf"},
    {"id": "lemh104", "grade": "Class 12", "name": "Determinants",
     "url": "https://ncert.nic.in/textbook/pdf/lemh104.pdf"},
    {"id": "lemh105", "grade": "Class 12", "name": "Continuity and Differentiability",
     "url": "https://ncert.nic.in/textbook/pdf/lemh105.pdf"},
    {"id": "lemh106", "grade": "Class 12", "name": "Application of Derivatives",
     "url": "https://ncert.nic.in/textbook/pdf/lemh106.pdf"},
    # Class 12 Part 2 (Chapters 7–13) — NCERT uses lemh2xx prefix for Part 2
    {"id": "lemh201", "grade": "Class 12", "name": "Integrals",
     "url": "https://ncert.nic.in/textbook/pdf/lemh201.pdf"},
    {"id": "lemh202", "grade": "Class 12", "name": "Application of Integrals",
     "url": "https://ncert.nic.in/textbook/pdf/lemh202.pdf"},
    {"id": "lemh203", "grade": "Class 12", "name": "Differential Equations",
     "url": "https://ncert.nic.in/textbook/pdf/lemh203.pdf"},
    {"id": "lemh204", "grade": "Class 12", "name": "Vector Algebra",
     "url": "https://ncert.nic.in/textbook/pdf/lemh204.pdf"},
    {"id": "lemh205", "grade": "Class 12", "name": "Three Dimensional Geometry",
     "url": "https://ncert.nic.in/textbook/pdf/lemh205.pdf"},
    {"id": "lemh206", "grade": "Class 12", "name": "Linear Programming",
     "url": "https://ncert.nic.in/textbook/pdf/lemh206.pdf"},
    {"id": "lemh207", "grade": "Class 12", "name": "Probability",
     "url": "https://ncert.nic.in/textbook/pdf/lemh207.pdf"},
]

CHAPTER_BY_ID = {c["id"]: c for c in CHAPTERS}


# ── progress tracking ─────────────────────────────────────────────────────────

def _load_progress() -> set[str]:
    if PROGRESS_FILE.exists():
        try:
            return set(json.loads(PROGRESS_FILE.read_text()).get("completed", []))
        except Exception:
            pass
    return set()


def _save_progress(completed: set[str]) -> None:
    PROGRESS_FILE.write_text(json.dumps({"completed": sorted(completed)}, indent=2))


# ── PDF download ──────────────────────────────────────────────────────────────

def _download_pdf(chapter_id: str, url: str) -> bytes:
    """Download PDF bytes, using local cache if available."""
    PDF_CACHE_DIR.mkdir(exist_ok=True)
    cache_path = PDF_CACHE_DIR / f"{chapter_id}.pdf"

    if cache_path.exists() and cache_path.stat().st_size > 1024:
        logger.info("  📂 Using cached PDF: %s", cache_path.name)
        return cache_path.read_bytes()

    logger.info("  ⬇️  Downloading %s …", url)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://ncert.nic.in/",
        "Accept": "application/pdf,*/*",
    }
    for attempt in range(3):
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.content
                cache_path.write_bytes(data)
                logger.info("  ✅ Downloaded %d KB", len(data) // 1024)
                return data
        except Exception as exc:
            logger.warning("  Download attempt %d/3 failed: %s", attempt + 1, exc)
            time.sleep(2 ** attempt)

    raise RuntimeError(f"Failed to download {url} after 3 attempts")


# ── PDF text extraction ───────────────────────────────────────────────────────

# Patterns that identify front-matter pages to skip
_FRONTMATTER_SIGNALS = re.compile(
    r"(?i)^\s*("
    r"foreword|preface|contents|acknowledgement|acknowledgment|"
    r"copyright|©\s*\d{4}|national council|ncert|"
    r"chapter\s+\d+\s*$|unit\s+\d+\s*$"
    r")\b",
    re.MULTILINE,
)

_PAGE_NUMBER_ONLY = re.compile(r"^\s*\d{1,3}\s*$")


def _is_frontmatter_page(text: str) -> bool:
    """Return True if a page looks like front matter (skip it)."""
    stripped = text.strip()
    if not stripped or len(stripped) < 50:
        return True
    # Mostly a page number or "Rationalised 2023-24" style header
    lines = [l.strip() for l in stripped.splitlines() if l.strip()]
    if len(lines) <= 3:
        return True
    # Copyright / TOC pages
    if _FRONTMATTER_SIGNALS.search(stripped[:400]):
        # But only skip if it's the first few pages (handled by caller)
        return True
    return False


def _clean_page_text(text: str) -> str:
    """Clean raw PDF-extracted text for a single page."""
    if not text:
        return ""
    # Remove running headers / footers (short lines at start/end)
    lines = text.splitlines()
    # Drop leading/trailing lines that are purely numeric (page numbers)
    while lines and _PAGE_NUMBER_ONLY.match(lines[0]):
        lines.pop(0)
    while lines and _PAGE_NUMBER_ONLY.match(lines[-1]):
        lines.pop()
    text = "\n".join(lines)
    # Collapse 3+ consecutive blank lines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove soft hyphens and ligature artifacts
    text = text.replace("\u00ad", "").replace("\ufb01", "fi").replace("\ufb02", "fl")
    # Normalise unicode minus/dash to ASCII hyphen in math contexts
    text = text.replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", " - ")
    return text.strip()


def _extract_text_pdfplumber(pdf_bytes: bytes, chapter_name: str) -> List[Tuple[int, str]]:
    """
    Extract (page_number, cleaned_text) pairs from PDF bytes using pdfplumber.
    Returns only content pages (skips front matter).
    """
    import pdfplumber  # imported here so the import error is localised

    pages: List[Tuple[int, str]] = []
    front_matter_budget = 8  # skip up to 8 pages of front matter

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        total = len(pdf.pages)
        logger.info("  📄 %d pages total", total)
        skipped = 0
        for page_obj in pdf.pages:
            pnum = page_obj.page_number
            raw = page_obj.extract_text(x_tolerance=2, y_tolerance=3) or ""
            cleaned = _clean_page_text(raw)

            # Skip front-matter pages using budget
            if skipped < front_matter_budget and _is_frontmatter_page(cleaned):
                skipped += 1
                continue

            if not cleaned or len(cleaned) < 40:
                continue  # blank / near-blank page

            pages.append((pnum, cleaned))

    logger.info("  📝 Extracted %d content pages (skipped %d front-matter)", len(pages), skipped)
    return pages


# ── chunking with overlap ─────────────────────────────────────────────────────

def _split_into_chunks(
    pages: List[Tuple[int, str]],
    chapter_name: str,
    grade: str,
) -> List[dict]:
    """
    Chunk page text into ~300–400 token chunks with 50-token overlap.
    Returns list of chunk dicts: {content, chapter, section, page, chunk_index, tokens}.
    """
    # First, concatenate all page texts into paragraphs with page markers
    all_paragraphs: List[Tuple[int, str]] = []   # (page_number, paragraph_text)
    for pnum, text in pages:
        for para in re.split(r"\n{2,}", text):
            para = para.strip()
            if para and _count_tokens(para) >= 10:
                all_paragraphs.append((pnum, para))

    chunks: List[dict] = []
    chunk_index = 0
    current_parts: List[str] = []
    current_tokens = 0
    current_page = pages[0][0] if pages else 1
    # Overlap buffer: last N tokens of previous chunk to prepend to next
    overlap_text = ""

    def _flush(force_page: int) -> None:
        nonlocal current_parts, current_tokens, chunk_index, overlap_text
        if not current_parts:
            return
        body = "\n\n".join(current_parts).strip()
        if _count_tokens(body) < CHUNK_MIN:
            # Too small — carry forward into next chunk
            return
        # Prepend chapter label for retrieval context
        label = f"Chapter: {chapter_name} ({grade})\n\n{body}"
        chunks.append({
            "content":      label,
            "chapter":      chapter_name,
            "grade":        grade,
            "page":         force_page,
            "chunk_index":  chunk_index,
            "tokens":       _count_tokens(label),
        })
        chunk_index += 1
        # Build overlap: last CHUNK_OVERLAP tokens of the flushed body
        tokens = _tokenizer.encode(body)
        overlap_tokens = tokens[-CHUNK_OVERLAP:] if len(tokens) > CHUNK_OVERLAP else tokens
        overlap_text = _tokenizer.decode(overlap_tokens)
        current_parts = []
        current_tokens = 0

    for pnum, para in all_paragraphs:
        para_tokens = _count_tokens(para)

        # Hard-split a very large paragraph
        if para_tokens > CHUNK_MAX:
            if current_parts:
                _flush(current_page)
            # Sentence-level split within oversized paragraph
            sentences = re.split(r"(?<=[.?!])\s+", para)
            sent_parts: List[str] = []
            sent_tokens = 0
            if overlap_text:
                sent_parts.append(overlap_text)
                sent_tokens = _count_tokens(overlap_text)
                overlap_text = ""
            for sent in sentences:
                st = _count_tokens(sent)
                if sent_tokens + st > CHUNK_TARGET and sent_parts:
                    body = "\n\n".join(sent_parts).strip()
                    if _count_tokens(body) >= CHUNK_MIN:
                        label = f"Chapter: {chapter_name} ({grade})\n\n{body}"
                        chunks.append({
                            "content":      label,
                            "chapter":      chapter_name,
                            "grade":        grade,
                            "page":         pnum,
                            "chunk_index":  chunk_index,
                            "tokens":       _count_tokens(label),
                        })
                        chunk_index += 1
                        # Build overlap
                        enc = _tokenizer.encode(body)
                        ov = enc[-CHUNK_OVERLAP:] if len(enc) > CHUNK_OVERLAP else enc
                        overlap_text = _tokenizer.decode(ov)
                    sent_parts = [overlap_text, sent] if overlap_text else [sent]
                    sent_tokens = _count_tokens(" ".join(sent_parts))
                    overlap_text = ""
                else:
                    sent_parts.append(sent)
                    sent_tokens += st
            if sent_parts:
                body = " ".join(sent_parts).strip()
                if _count_tokens(body) >= CHUNK_MIN:
                    label = f"Chapter: {chapter_name} ({grade})\n\n{body}"
                    chunks.append({
                        "content":      label,
                        "chapter":      chapter_name,
                        "grade":        grade,
                        "page":         pnum,
                        "chunk_index":  chunk_index,
                        "tokens":       _count_tokens(label),
                    })
                    chunk_index += 1
            continue

        # Normal paragraph accumulation
        if current_tokens + para_tokens > CHUNK_TARGET and current_parts:
            _flush(current_page)
            # Start next chunk with overlap
            if overlap_text:
                current_parts = [overlap_text]
                current_tokens = _count_tokens(overlap_text)
                overlap_text = ""
            else:
                current_parts = []
                current_tokens = 0

        current_parts.append(para)
        current_tokens += para_tokens
        current_page = pnum

    if current_parts:
        _flush(current_page)

    return chunks


# ── OpenAI embedding ──────────────────────────────────────────────────────────

def _embed_batch(texts: List[str]) -> List[List[float]]:
    import openai
    client = openai.OpenAI(api_key=settings.openai_api_key, timeout=30.0, max_retries=3)
    cleaned = [t.replace("\n", " ") for t in texts]
    resp = client.embeddings.create(input=cleaned, model=EMBED_MODEL)
    return [item.embedding for item in resp.data]


# ── DB insertion ──────────────────────────────────────────────────────────────

async def _insert_chunks(pool: asyncpg.Pool, rows: List[dict]) -> int:
    if not rows:
        return 0

    def _vec(emb: List[float]) -> str:
        return "[" + ",".join(f"{v:.8f}" for v in emb) + "]"

    async with pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO knowledge_chunks
                (id, source_file, subject, chapter, chunk_index, content, embedding, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7::vector, $8::jsonb)
            ON CONFLICT DO NOTHING
            """,
            [
                (
                    uuid.uuid4(),
                    r["source_file"],
                    "Maths",
                    r["chapter"],
                    r["chunk_index"],
                    r["content"],
                    _vec(r["embedding"]),
                    json.dumps(r["metadata"]),
                )
                for r in rows
            ],
        )
    return len(rows)


# ── main ingestion ────────────────────────────────────────────────────────────

async def ingest(
    filter_class: Optional[str] = None,
    filter_chapter: Optional[str] = None,
    reset_progress: bool = False,
) -> None:
    if reset_progress and PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()
        logger.info("Progress file reset.")

    completed = _load_progress()
    logger.info("Previously completed chapters: %d", len(completed))

    # Filter chapter list
    chapters = CHAPTERS
    if filter_class:
        chapters = [c for c in chapters if c["grade"] == f"Class {filter_class}"]
        logger.info("Filtered to Class %s: %d chapters", filter_class, len(chapters))
    if filter_chapter:
        chapters = [c for c in chapters if c["id"] == filter_chapter]
        if not chapters:
            logger.error("Unknown chapter id: %s", filter_chapter)
            sys.exit(1)

    pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=5)
    total_chunks = 0
    total_chapters = 0

    try:
        for chap in chapters:
            chap_id   = chap["id"]
            chap_name = chap["name"]
            grade     = chap["grade"]
            url       = chap["url"]

            if chap_id in completed:
                logger.info("⏭  Skipping already-ingested: %s — %s", grade, chap_name)
                continue

            logger.info("📖 Processing: %s — %s [%s]", grade, chap_name, chap_id)

            # 1. Download
            try:
                pdf_bytes = _download_pdf(chap_id, url)
            except Exception as exc:
                logger.error("  Download failed, skipping: %s", exc)
                continue

            # 2. Extract text
            try:
                pages = _extract_text_pdfplumber(pdf_bytes, chap_name)
            except ImportError:
                logger.error("pdfplumber not installed. Run: poetry add pdfplumber")
                sys.exit(1)
            except Exception as exc:
                logger.error("  PDF extraction failed: %s", exc)
                continue

            if not pages:
                logger.warning("  No content pages extracted — skipping")
                completed.add(chap_id)
                _save_progress(completed)
                continue

            total_text_chars = sum(len(t) for _, t in pages)
            logger.info(
                "  Extracted %d pages, ~%d chars total",
                len(pages), total_text_chars,
            )

            # 3. Chunk
            chunks = _split_into_chunks(pages, chap_name, grade)
            logger.info("  → %d chunks (avg %.0f tokens)", len(chunks),
                        sum(c["tokens"] for c in chunks) / max(len(chunks), 1))

            if not chunks:
                logger.warning("  No chunks produced — skipping")
                completed.add(chap_id)
                _save_progress(completed)
                continue

            # 4. Embed in batches
            texts = [c["content"] for c in chunks]
            all_embeddings: List[List[float]] = []

            for i in range(0, len(texts), EMBED_BATCH):
                batch = texts[i: i + EMBED_BATCH]
                logger.info(
                    "  Embedding batch %d–%d / %d …",
                    i + 1, min(i + EMBED_BATCH, len(texts)), len(texts),
                )
                for attempt in range(3):
                    try:
                        embs = _embed_batch(batch)
                        all_embeddings.extend(embs)
                        break
                    except Exception as exc:
                        logger.warning("  Embed attempt %d/3 failed: %s", attempt + 1, exc)
                        time.sleep(2 ** attempt)
                else:
                    logger.error("  Embedding failed after 3 retries — aborting chapter")
                    break

            if len(all_embeddings) != len(chunks):
                logger.error(
                    "  Embedding count mismatch: expected %d, got %d — skipping",
                    len(chunks), len(all_embeddings),
                )
                continue

            # 5. Build DB rows + insert
            db_rows = [
                {
                    "source_file": f"ncert_maths_{chap_id}",
                    "chapter":     f"{grade} — {chap_name}",
                    "chunk_index": chunk["chunk_index"],
                    "content":     chunk["content"],
                    "embedding":   all_embeddings[idx],
                    "metadata": {
                        "grade":       grade,
                        "chapter_id":  chap_id,
                        "chapter_name": chap_name,
                        "page":        chunk["page"],
                        "tokens":      chunk["tokens"],
                        "chunk_total": len(chunks),
                        "source_url":  url,
                        "source":      "NCERT official PDF",
                    },
                }
                for idx, chunk in enumerate(chunks)
            ]

            inserted = 0
            for i in range(0, len(db_rows), INSERT_BATCH):
                batch = db_rows[i: i + INSERT_BATCH]
                n = await _insert_chunks(pool, batch)
                inserted += n

            logger.info(
                "  ✅ Inserted %d chunks for %s — %s",
                inserted, grade, chap_name,
            )
            total_chunks += inserted
            total_chapters += 1

            completed.add(chap_id)
            _save_progress(completed)

            # Brief pause between chapters to be polite to ncert.nic.in
            time.sleep(1)

    finally:
        await pool.close()

    logger.info(
        "🎉 Done. Chapters ingested: %d / %d | Chunks inserted: %d",
        total_chapters, len(chapters), total_chunks,
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest NCERT Maths Class 11+12 PDFs into knowledge_chunks"
    )
    parser.add_argument(
        "--class", dest="cls",
        choices=["11", "12"],
        help="Restrict to a single class (default: both)",
    )
    parser.add_argument(
        "--chapter",
        help="Ingest a single chapter by ID, e.g. kemh103",
    )
    parser.add_argument(
        "--reset-progress",
        action="store_true",
        help="Delete progress file and re-ingest from scratch",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(
        ingest(
            filter_class=args.cls,
            filter_chapter=args.chapter,
            reset_progress=args.reset_progress,
        )
    )
