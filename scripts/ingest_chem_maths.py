#!/usr/bin/env python3
"""
Ingest NCERT Chemistry and Mathematics content into knowledge_chunks.

Source: KadamParth/Ncert_dataset on HuggingFace
  - Contains NCERT chapters for Physics, Chemistry, Mathematics (Class 11 + 12)
  - Each row typically: { subject, class, chapter_name, chapter_number, content }

Embedding model: OpenAI text-embedding-3-small (1536-dim)
  — must match existing knowledge_chunks.embedding column.

Chunking strategy:
  - Split by logical sections (double-newlines / heading patterns)
  - Target ~300–400 tokens per chunk (measured via tiktoken cl100k_base)
  - Preserve chapter + section metadata per chunk

Resumability:
  - Tracks ingested (subject, chapter) pairs in a local JSON file:
      scripts/.ingest_chem_maths_progress.json
  - Re-running skips already-completed chapters (idempotent)

Usage:
    poetry run python scripts/ingest_chem_maths.py
    poetry run python scripts/ingest_chem_maths.py --dry-run        # preview only
    poetry run python scripts/ingest_chem_maths.py --reset-progress # start fresh
    poetry run python scripts/ingest_chem_maths.py --subject Chemistry
    poetry run python scripts/ingest_chem_maths.py --subject Maths
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Generator, List, Optional

import asyncpg
import tiktoken

# ── Setup paths ───────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT   = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

from app.config import settings

# ── Constants ─────────────────────────────────────────────────────────────────
PROGRESS_FILE   = SCRIPT_DIR / ".ingest_chem_maths_progress.json"
CHUNK_TARGET    = 350        # target tokens per chunk
CHUNK_MAX       = 500        # hard max before forced split
CHUNK_MIN       = 80         # discard chunks shorter than this
EMBED_BATCH     = 20         # OpenAI embeddings batch size
INSERT_BATCH    = 50         # DB insert batch size
EMBED_MODEL     = "text-embedding-3-small"
EMBED_DIM       = 1536

SUBJECTS_MAP = {
    # Exact subject strings found in KadamParth/Ncert_dataset
    # (confirmed via live run: Chemistry ✓, Physics ✓, no Mathematics column)
    "Chemistry":   "Chemistry",
    "chemistry":   "Chemistry",
    "Physics":     "Physics",
    "physics":     "Physics",
    # Aliases for Maths (used when sourcing from alternate datasets)
    "Maths":       "Maths",
    "maths":       "Maths",
    "Math":        "Maths",
    "math":        "Maths",
    "Mathematics": "Maths",
    "mathematics": "Maths",
    "MATHEMATICS": "Maths",
}

# Grades to include — JEE covers Class 11 & 12 only
TARGET_GRADES = {"11", "12"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── tiktoken tokenizer (cl100k_base — same as OpenAI embeddings) ──────────────
_tokenizer = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_tokenizer.encode(text))


# ── Progress tracking ─────────────────────────────────────────────────────────

def _load_progress() -> set[str]:
    """Return set of completed 'subject::chapter' keys."""
    if PROGRESS_FILE.exists():
        try:
            data = json.loads(PROGRESS_FILE.read_text())
            return set(data.get("completed", []))
        except Exception:
            pass
    return set()


def _save_progress(completed: set[str]) -> None:
    PROGRESS_FILE.write_text(json.dumps({"completed": sorted(completed)}, indent=2))


def _chapter_key(subject: str, chapter: str) -> str:
    return f"{subject}::{chapter}"


# ── Text chunking ─────────────────────────────────────────────────────────────

def _split_into_chunks(
    text: str,
    chapter: str,
    section_prefix: str = "",
) -> List[dict]:
    """
    Split chapter text into ~300–400 token chunks.

    Strategy:
    1. Split on double newlines (paragraph boundaries) or heading patterns.
    2. Accumulate paragraphs until token budget fills.
    3. If a single paragraph > CHUNK_MAX, split by sentence.

    Each chunk dict: { content, section, chunk_index }
    """
    # Normalise whitespace: collapse 3+ consecutive newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text.strip())

    # Detect headings (ALL CAPS lines, lines ending with colon, numbered headings)
    heading_pattern = re.compile(
        r"^(?:[A-Z][A-Z\s,\-]{4,}|(?:\d+\.)+\s+\S|\S[^\n]{0,60}:)\s*$",
        re.MULTILINE,
    )

    # Split text by double newlines first
    raw_paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: List[dict] = []
    current_parts: List[str] = []
    current_tokens = 0
    current_section = section_prefix or chapter
    chunk_index = 0

    def _flush() -> None:
        nonlocal current_parts, current_tokens, chunk_index, current_section
        joined = "\n\n".join(current_parts).strip()
        if _count_tokens(joined) >= CHUNK_MIN:
            label = f"Topic: {current_section}\n\n{joined}"
            chunks.append({
                "content":     label,
                "section":     current_section,
                "chunk_index": chunk_index,
            })
            chunk_index += 1
        current_parts = []
        current_tokens = 0

    for para in raw_paragraphs:
        # Detect new section heading → flush and update section label
        if heading_pattern.match(para) and len(para) < 120:
            if current_parts:
                _flush()
            current_section = para.strip(": ").strip()
            continue

        para_tokens = _count_tokens(para)

        # Single paragraph exceeds hard max — sentence-split it
        if para_tokens > CHUNK_MAX:
            if current_parts:
                _flush()
            sentences = re.split(r"(?<=[.?!])\s+", para)
            sent_parts: List[str] = []
            sent_tokens = 0
            for sent in sentences:
                t = _count_tokens(sent)
                if sent_tokens + t > CHUNK_TARGET and sent_parts:
                    label = f"Topic: {current_section}\n\n" + " ".join(sent_parts).strip()
                    if _count_tokens(label) >= CHUNK_MIN:
                        chunks.append({
                            "content":     label,
                            "section":     current_section,
                            "chunk_index": chunk_index,
                        })
                        chunk_index += 1
                    sent_parts = [sent]
                    sent_tokens = t
                else:
                    sent_parts.append(sent)
                    sent_tokens += t
            if sent_parts:
                label = f"Topic: {current_section}\n\n" + " ".join(sent_parts).strip()
                if _count_tokens(label) >= CHUNK_MIN:
                    chunks.append({
                        "content":     label,
                        "section":     current_section,
                        "chunk_index": chunk_index,
                    })
                    chunk_index += 1
            continue

        # Normal paragraph — accumulate
        if current_tokens + para_tokens > CHUNK_TARGET and current_parts:
            _flush()

        current_parts.append(para)
        current_tokens += para_tokens

    if current_parts:
        _flush()

    return chunks


# ── OpenAI embedding ──────────────────────────────────────────────────────────

def _embed_batch(texts: List[str]) -> List[List[float]]:
    """Embed a batch of texts using OpenAI text-embedding-3-small."""
    import openai
    client = openai.OpenAI(api_key=settings.openai_api_key, timeout=30.0, max_retries=3)
    cleaned = [t.replace("\n", " ") for t in texts]
    resp = client.embeddings.create(input=cleaned, model=EMBED_MODEL)
    return [item.embedding for item in resp.data]


# ── DB insertion ──────────────────────────────────────────────────────────────

async def _insert_chunks(
    pool: asyncpg.Pool,
    rows: List[dict],
    dry_run: bool = False,
) -> int:
    """Insert a batch of chunk rows. Returns count inserted."""
    if not rows:
        return 0
    if dry_run:
        logger.info("[DRY RUN] Would insert %d chunks", len(rows))
        return len(rows)

    # Build vec literal
    def _vec(emb: List[float]) -> str:
        return "[" + ",".join(f"{v:.8f}" for v in emb) + "]"

    async with pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO knowledge_chunks
                (id, source_file, subject, chapter, chunk_index, content, embedding, metadata)
            VALUES
                ($1, $2, $3, $4, $5, $6, $7::vector, $8::jsonb)
            ON CONFLICT DO NOTHING
            """,
            [
                (
                    uuid.uuid4(),
                    row["source_file"],
                    row["subject"],
                    row["chapter"],
                    row["chunk_index"],
                    row["content"],
                    _vec(row["embedding"]),
                    json.dumps(row["metadata"]),
                )
                for row in rows
            ],
        )
    return len(rows)


# ── Main ingestion logic ──────────────────────────────────────────────────────

async def ingest(
    target_subjects: Optional[List[str]] = None,
    dry_run: bool = False,
    reset_progress: bool = False,
) -> None:
    """
    Load NCERT Chemistry + Maths from HuggingFace and ingest into knowledge_chunks.
    """
    try:
        from datasets import load_dataset
    except ImportError:
        logger.error(
            "huggingface `datasets` library not installed. "
            "Run: poetry add datasets"
        )
        sys.exit(1)

    if reset_progress and PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()
        logger.info("Progress file reset.")

    completed = _load_progress()
    logger.info("Previously completed chapters: %d", len(completed))

    # ── Load dataset ──────────────────────────────────────────────────────────
    logger.info("Loading KadamParth/Ncert_dataset from HuggingFace …")
    try:
        # trust_remote_code removed — deprecated in recent datasets versions
        ds = load_dataset("KadamParth/Ncert_dataset", split="train")
    except Exception as exc:
        logger.warning("split='train' failed (%s), trying default split …", exc)
        try:
            ds_dict = load_dataset("KadamParth/Ncert_dataset")
            split_name = list(ds_dict.keys())[0]
            ds = ds_dict[split_name]
            logger.info("Loaded split: %s", split_name)
        except Exception as exc2:
            logger.error("Dataset load failed completely: %s", exc2)
            sys.exit(1)

    logger.info("Dataset loaded: %d rows, columns=%s", len(ds), ds.column_names)

    # ── Identify columns ──────────────────────────────────────────────────────
    # Actual KadamParth/Ncert_dataset schema (confirmed from live run):
    #   Topic, Explanation, Question, Answer, Difficulty, StudentLevel,
    #   QuestionType, QuestionComplexity, Prerequisites, EstimatedTime, subject, grade
    cols = ds.column_names

    col_subject = next(
        (c for c in ["subject", "Subject", "SUBJECT"] if c in cols), None
    )
    # Topic IS the chapter/section name in this dataset
    col_chapter = next(
        (c for c in ["Topic", "topic", "chapter_name", "chapter", "Chapter", "title"] if c in cols), None
    )
    # Explanation is the primary NCERT theory content
    col_explanation = next(
        (c for c in ["Explanation", "explanation", "content", "text", "passage"] if c in cols), None
    )
    # Question + Answer supplement the explanation for richer chunks
    col_question = next((c for c in ["Question", "question"] if c in cols), None)
    col_answer   = next((c for c in ["Answer",   "answer"]   if c in cols), None)
    col_class    = next(
        (c for c in ["grade", "Grade", "class", "Class"] if c in cols), None
    )

    logger.info(
        "Column mapping — subject=%s, chapter=%s, explanation=%s, "
        "question=%s, answer=%s, class=%s",
        col_subject, col_chapter, col_explanation, col_question, col_answer, col_class,
    )

    # col_explanation is required; col_chapter highly preferred
    col_content = col_explanation  # alias for rest of code
    if not col_content:
        logger.error(
            "Cannot find explanation/content column. Available columns: %s", cols
        )
        sys.exit(1)

    # ── Filter to target subjects ─────────────────────────────────────────────
    want_subjects = set(target_subjects) if target_subjects else {"Chemistry", "Maths"}
    logger.info("Target subjects: %s", want_subjects)

    # ── Connect to DB ─────────────────────────────────────────────────────────
    pool: asyncpg.Pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=5)

    total_chunks_inserted = 0
    total_chapters_processed = 0

    try:
        # Group rows by (subject, chapter)
        chapter_groups: dict[tuple[str, str], list] = {}

        for row in ds:
            # ── Grade filter: JEE only needs Class 11 & 12 ───────────────────
            class_label = str(row.get(col_class, "")).strip() if col_class else ""
            if class_label and class_label not in TARGET_GRADES:
                continue

            # Determine subject
            raw_subject = row.get(col_subject, "") if col_subject else ""
            db_subject = SUBJECTS_MAP.get(str(raw_subject).strip(), None)
            if db_subject is None or db_subject not in want_subjects:
                continue

            # Determine chapter — use Topic column (e.g. "Electrochemistry")
            chapter_name = str(row.get(col_chapter, "Unknown Chapter")).strip() if col_chapter else "Unknown Chapter"
            if class_label:
                chapter_name = f"Class {class_label} — {chapter_name}"

            key = (db_subject, chapter_name)
            if key not in chapter_groups:
                chapter_groups[key] = []
            chapter_groups[key].append(row)

        logger.info(
            "Found %d (subject, chapter) groups across %s",
            len(chapter_groups), want_subjects,
        )

        # ── Maths fallback: KadamParth dataset has no Mathematics subject. ────
        # Try alternate HuggingFace datasets if Maths was requested but 0 groups found.
        maths_groups_found = sum(1 for (s, _) in chapter_groups if s == "Maths")
        if "Maths" in want_subjects and maths_groups_found == 0:
            logger.info(
                "No Maths found in primary dataset — trying alternate Maths sources …"
            )
            maths_candidates = [
                ("Vivacem/NCERT_Maths",         "train"),
                ("anmolsingh1/ncert-maths",      "train"),
                ("pradipta-cloud/ncert-maths",   "train"),
                ("Matan1178/NCERT_maths",        "train"),
                ("iitjee/ncert-mathematics",     "train"),
            ]
            for ds_id, split_name in maths_candidates:
                try:
                    from datasets import load_dataset as _lds
                    logger.info("  Trying %s …", ds_id)
                    ds_maths = _lds(ds_id, split=split_name)
                    logger.info("  Loaded %s: %d rows, cols=%s", ds_id, len(ds_maths), ds_maths.column_names)
                    _m_cols = ds_maths.column_names
                    _m_chap = next((c for c in ["Topic","topic","chapter","Chapter","title","section"] if c in _m_cols), None)
                    _m_exp  = next((c for c in ["Explanation","explanation","content","text","passage"] if c in _m_cols), None)
                    _m_q    = next((c for c in ["Question","question"] if c in _m_cols), None)
                    _m_a    = next((c for c in ["Answer","answer"]     if c in _m_cols), None)
                    _m_g    = next((c for c in ["grade","Grade","class","Class"] if c in _m_cols), None)
                    if not _m_exp and not _m_q:
                        logger.warning("  No content column found in %s — skipping", ds_id)
                        continue
                    for row in ds_maths:
                        _g = str(row.get(_m_g, "")).strip() if _m_g else ""
                        if _g and _g not in TARGET_GRADES:
                            continue
                        _chap = str(row.get(_m_chap, "Unknown Chapter")).strip() if _m_chap else "Unknown Chapter"
                        if _g:
                            _chap = f"Class {_g} — {_chap}"
                        key = ("Maths", _chap)
                        if key not in chapter_groups:
                            chapter_groups[key] = []
                        chapter_groups[key].append({
                            col_explanation: str(row.get(_m_exp, "")) if _m_exp else "",
                            col_question:    str(row.get(_m_q, ""))   if _m_q else "",
                            col_answer:      str(row.get(_m_a, ""))   if _m_a else "",
                            col_class:       _g,
                            "_maths_source": ds_id,
                        })
                    maths_found = sum(1 for (s, _) in chapter_groups if s == "Maths")
                    if maths_found > 0:
                        logger.info("  ✅ Found %d Maths groups from %s", maths_found, ds_id)
                        break
                except Exception as exc:
                    logger.warning("  %s failed: %s", ds_id, exc)
            else:
                # ── Local seed fallback: load bundled ncert_maths_seed.json ──
                _seed_path = SCRIPT_DIR / "data" / "ncert_maths_seed.json"
                if _seed_path.exists():
                    logger.info("  📦 Loading local Maths seed from %s …", _seed_path)
                    try:
                        _seed_rows = json.loads(_seed_path.read_text())
                        for row in _seed_rows:
                            _g = str(row.get("grade", "")).strip()
                            if _g and _g not in TARGET_GRADES:
                                continue
                            _chap = str(row.get("Topic", "Unknown Chapter")).strip()
                            if _g:
                                _chap = f"Class {_g} — {_chap}"
                            key = ("Maths", _chap)
                            if key not in chapter_groups:
                                chapter_groups[key] = []
                            chapter_groups[key].append({
                                "Explanation": str(row.get("Explanation", "")),
                                "Question":    str(row.get("Question", "")),
                                "Answer":      str(row.get("Answer", "")),
                                "grade":       _g,
                                "_maths_source": "local_seed",
                            })
                        maths_found = sum(1 for (s, _) in chapter_groups if s == "Maths")
                        logger.info("  ✅ Loaded %d Maths groups from local seed", maths_found)
                    except Exception as exc:
                        logger.warning("  Local seed load failed: %s", exc)
                        logger.warning(
                            "No Maths NCERT dataset available. "
                            "Maths content will not be ingested this run."
                        )
                else:
                    logger.warning(
                        "No Maths NCERT dataset found on HuggingFace and no local seed at %s. "
                        "Maths content will not be ingested this run.", _seed_path
                    )
            logger.info(
                "After Maths fallback: %d total (subject, chapter) groups",
                len(chapter_groups),
            )

        # ── Process each chapter ──────────────────────────────────────────────
        for (db_subject, chapter_name), rows in sorted(chapter_groups.items()):
            prog_key = _chapter_key(db_subject, chapter_name)
            if prog_key in completed:
                logger.info("  ⏭  Skipping already-ingested: %s / %s", db_subject, chapter_name)
                continue

            # Assemble full chapter text from all Q&A rows for this topic.
            # Each row = one NCERT Q&A pair. Build richer content by combining:
            #   Explanation (primary theory text) + Question + Answer.
            parts: List[str] = []
            seen_explanations: set[str] = set()
            for r in rows:
                explanation = str(r.get(col_explanation, "")).strip() if col_explanation else ""
                question    = str(r.get(col_question, "")).strip()    if col_question    else ""
                answer      = str(r.get(col_answer,   "")).strip()    if col_answer      else ""
                # Deduplicate repeated explanations (same concept repeated for multiple Qs)
                exp_key = explanation[:120]
                if explanation and exp_key not in seen_explanations:
                    seen_explanations.add(exp_key)
                    parts.append(explanation)
                # Always append Q&A pairs (they're unique per row)
                if question and answer:
                    parts.append(f"Q: {question}\nA: {answer}")
                elif question:
                    parts.append(f"Q: {question}")
            full_text = "\n\n".join(parts).strip()

            if not full_text or len(full_text) < 100:
                logger.warning("  ⚠  Skipping empty/tiny chapter: %s / %s", db_subject, chapter_name)
                completed.add(prog_key)
                _save_progress(completed)
                continue

            logger.info(
                "  📖 Processing: %s / %s (%d chars)",
                db_subject, chapter_name, len(full_text),
            )

            # Split into chunks
            chunks = _split_into_chunks(full_text, chapter_name)
            logger.info("     → %d chunks", len(chunks))

            if not chunks:
                completed.add(prog_key)
                _save_progress(completed)
                continue

            # Embed in batches
            all_embeddings: List[List[float]] = []
            texts_to_embed = [c["content"] for c in chunks]

            for i in range(0, len(texts_to_embed), EMBED_BATCH):
                batch = texts_to_embed[i : i + EMBED_BATCH]
                logger.info(
                    "     Embedding batch %d–%d …",
                    i + 1, min(i + EMBED_BATCH, len(texts_to_embed)),
                )
                retries = 0
                while retries < 3:
                    try:
                        embs = _embed_batch(batch)
                        all_embeddings.extend(embs)
                        break
                    except Exception as exc:
                        retries += 1
                        logger.warning(
                            "Embedding batch failed (attempt %d/3): %s", retries, exc
                        )
                        time.sleep(2 ** retries)
                else:
                    logger.error("Embedding batch failed after 3 retries — aborting chapter.")
                    break

            if len(all_embeddings) != len(chunks):
                logger.error(
                    "Embedding count mismatch: expected %d, got %d. Skipping chapter.",
                    len(chunks), len(all_embeddings),
                )
                continue

            # Build DB rows
            db_rows = [
                {
                    "source_file":  f"ncert_{db_subject.lower()}_huggingface",
                    "subject":      db_subject,
                    "chapter":      chapter_name,
                    "chunk_index":  chunk["chunk_index"],
                    "content":      chunk["content"],
                    "embedding":    all_embeddings[idx],
                    "metadata": {
                        "section":    chunk["section"],
                        "source":     "KadamParth/Ncert_dataset",
                        "class":      class_label,
                        "chunk_total": len(chunks),
                    },
                }
                for idx, chunk in enumerate(chunks)
            ]

            # Insert in batches
            inserted = 0
            for i in range(0, len(db_rows), INSERT_BATCH):
                batch = db_rows[i : i + INSERT_BATCH]
                n = await _insert_chunks(pool, batch, dry_run=dry_run)
                inserted += n

            logger.info("     ✅ Inserted %d chunks for %s / %s", inserted, db_subject, chapter_name)
            total_chunks_inserted += inserted
            total_chapters_processed += 1

            # Mark chapter as done
            completed.add(prog_key)
            _save_progress(completed)

    finally:
        await pool.close()

    logger.info(
        "🎉 Ingestion complete. Chapters processed: %d | Total chunks inserted: %d",
        total_chapters_processed, total_chunks_inserted,
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest NCERT Chemistry + Maths from KadamParth/Ncert_dataset"
    )
    parser.add_argument(
        "--subject",
        choices=["Chemistry", "Maths", "both"],
        default="both",
        help="Which subject to ingest (default: both)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview chunking/embedding without writing to DB",
    )
    parser.add_argument(
        "--reset-progress",
        action="store_true",
        help="Delete the progress file and re-ingest everything",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    subjects: Optional[List[str]]
    if args.subject == "both":
        subjects = ["Chemistry", "Maths"]
    else:
        subjects = [args.subject]

    asyncio.run(
        ingest(
            target_subjects=subjects,
            dry_run=args.dry_run,
            reset_progress=args.reset_progress,
        )
    )
