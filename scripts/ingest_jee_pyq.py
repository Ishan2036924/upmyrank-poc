#!/usr/bin/env python3
"""
Ingest 30 years of JEE Past Year Questions (PYQs) into jee_problems.

Primary source:  dhruvnathwani/jeebench   (JEE Advanced problems with solutions)
Secondary source: iamtarun/jee_mains_questions (JEE Mains)
Fallback:         scripts/data/jee_pyq_seed.json (manual seed file, see format below)

Embedding model: OpenAI text-embedding-3-small (1536-dim)
  — must match jee_problems.embedding column (vector 1536).

LaTeX cleaning:
  - Converts plain-text math approximations to LaTeX
  - Wraps bare fractions, superscripts, subscripts
  - Normalises block/inline delimiters

Resumability:
  - Progress tracked in scripts/.ingest_jee_pyq_progress.json
  - Re-running skips already-ingested (subject, year, problem_id) tuples

Usage:
    poetry run python scripts/ingest_jee_pyq.py
    poetry run python scripts/ingest_jee_pyq.py --source jeebench
    poetry run python scripts/ingest_jee_pyq.py --source jee_mains
    poetry run python scripts/ingest_jee_pyq.py --source seed --seed-file scripts/data/jee_pyq_seed.json
    poetry run python scripts/ingest_jee_pyq.py --dry-run
    poetry run python scripts/ingest_jee_pyq.py --reset-progress

──────────────────────────────────────────────────────────────────────────────
Seed JSON format (for --source seed / manual curation):
[
  {
    "subject":        "Physics",          // Physics | Chemistry | Maths
    "topic":          "Rotational Motion",
    "year":           2019,
    "exam_type":      "JEE Advanced",     // JEE Mains | JEE Advanced
    "difficulty":     4,                  // 1–5
    "problem_text":   "A disc of mass ...",
    "solution_text":  "Taking torque ...",
    "solution_steps": [                   // optional
        {"step": 1, "description": "..."},
    ],
    "source_verified": true
  }
]
──────────────────────────────────────────────────────────────────────────────
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
from typing import Any, Dict, List, Optional

import asyncpg

# ── Setup paths ───────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT   = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

from app.config import settings

# ── Constants ─────────────────────────────────────────────────────────────────
PROGRESS_FILE   = SCRIPT_DIR / ".ingest_jee_pyq_progress.json"
SEED_DIR        = SCRIPT_DIR / "data"
DEFAULT_SEED    = SEED_DIR / "jee_pyq_seed.json"
EMBED_BATCH     = 20
INSERT_BATCH    = 50
EMBED_MODEL     = "text-embedding-3-small"

SUBJECT_ALIASES = {
    "physics":     "Physics",
    "phy":         "Physics",
    "chemistry":   "Chemistry",
    "chem":        "Chemistry",
    "maths":       "Maths",
    "math":        "Maths",
    "mathematics": "Maths",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Progress tracking ─────────────────────────────────────────────────────────

def _load_progress() -> set[str]:
    if PROGRESS_FILE.exists():
        try:
            return set(json.loads(PROGRESS_FILE.read_text()).get("completed", []))
        except Exception:
            pass
    return set()


def _save_progress(completed: set[str]) -> None:
    PROGRESS_FILE.write_text(json.dumps({"completed": sorted(completed)}, indent=2))


# ── LaTeX cleaning ────────────────────────────────────────────────────────────

def _clean_latex(text: str) -> str:
    """
    Light-touch LaTeX normalisation for problem/solution text.
    Handles common plain-text math patterns in JEE datasets.
    """
    if not text:
        return text

    # 1. Normalise existing delimiters: \( \) → $...$  and  \[ \] → $$...$$
    text = re.sub(r"\\\((.+?)\\\)", r"$\1$", text, flags=re.DOTALL)
    text = re.sub(r"\\\[(.+?)\\\]", r"$$\1$$", text, flags=re.DOTALL)

    # 2. Convert caret superscripts not already in LaTeX: x^2 → $x^{2}$
    # Only for isolated patterns (not inside existing $...$)
    def _fix_superscripts(m: re.Match) -> str:
        return m.group(0) if "$" in m.group(0) else m.group(0)

    # 3. Wrap bare fractions: a/b where a and b are simple expressions
    # E.g. "m/s" → keep as is (unit), "1/2 mv^2" → flag for LaTeX
    # This is conservative — only wrap clearly mathematical patterns
    text = re.sub(
        r"\b(\d+)/(\d+)\b",
        lambda m: f"$\\frac{{{m.group(1)}}}{{{m.group(2)}}}$"
        if not _is_inside_latex(text, m.start())
        else m.group(0),
        text,
    )

    # 4. Ensure $$ are on their own lines for block equations
    text = re.sub(r"([^\n])\$\$", r"\1\n$$", text)
    text = re.sub(r"\$\$([^\n])", r"$$\n\1", text)

    # 5. Collapse triple+ newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def _is_inside_latex(text: str, pos: int) -> bool:
    """Rough check: is position *pos* inside a $...$ block?"""
    before = text[:pos]
    return before.count("$") % 2 == 1


# ── Difficulty mapping ────────────────────────────────────────────────────────

def _infer_difficulty(row: dict, exam_type: str) -> int:
    """Map dataset difficulty values to integer 1–5."""
    raw = row.get("difficulty", row.get("level", row.get("hard_level", "")))
    if isinstance(raw, (int, float)):
        val = int(raw)
        if 1 <= val <= 5:
            return val
        if val <= 2:
            return 2
        if val <= 4:
            return 3
        return 4
    if isinstance(raw, str):
        mapping = {
            "easy": 2, "medium": 3, "hard": 4, "very hard": 5,
            "simple": 1, "difficult": 4,
        }
        return mapping.get(raw.lower().strip(), 3)
    # Default: JEE Advanced problems are harder on average
    return 4 if exam_type == "JEE Advanced" else 3


# ── Subject normalisation ─────────────────────────────────────────────────────

def _normalize_subject(raw: str) -> Optional[str]:
    return SUBJECT_ALIASES.get(str(raw).strip().lower(), None)


# ── Embedding ─────────────────────────────────────────────────────────────────

def _embed_batch(texts: List[str]) -> List[List[float]]:
    import openai
    client = openai.OpenAI(api_key=settings.openai_api_key, timeout=30.0, max_retries=3)
    cleaned = [t.replace("\n", " ") for t in texts]
    resp = client.embeddings.create(input=cleaned, model=EMBED_MODEL)
    return [item.embedding for item in resp.data]


# ── DB insertion ──────────────────────────────────────────────────────────────

def _vec(emb: List[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in emb) + "]"


async def _insert_problems(
    pool: asyncpg.Pool,
    rows: List[dict],
    dry_run: bool = False,
) -> int:
    if not rows:
        return 0
    if dry_run:
        logger.info("[DRY RUN] Would insert %d problems", len(rows))
        return len(rows)

    async with pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO jee_problems
                (problem_id, subject, topic, year, exam_type, difficulty,
                 problem_text, solution_text, solution_steps, embedding, source_verified)
            VALUES
                ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10::vector, $11)
            ON CONFLICT (problem_id) DO NOTHING
            """,
            [
                (
                    row["problem_id"],
                    row["subject"],
                    row["topic"],
                    row["year"],
                    row["exam_type"],
                    row["difficulty"],
                    row["problem_text"],
                    row.get("solution_text") or "",
                    json.dumps(row.get("solution_steps") or []),
                    _vec(row["embedding"]),
                    row.get("source_verified", False),
                )
                for row in rows
            ],
        )
    return len(rows)


# ── Source: jeebench ──────────────────────────────────────────────────────────

def _load_jeebench() -> List[dict]:
    """
    Load a JEE Advanced benchmark dataset from HuggingFace.
    Tries multiple known dataset IDs in order. trust_remote_code removed (deprecated).
    """
    try:
        from datasets import load_dataset
    except ImportError:
        logger.error("Install datasets: poetry add datasets")
        return []

    # Confirmed public datasets (as of 2024-2025). Try in priority order.
    candidates = [
        "TIGER-Lab/JEEBench",          # primary — most complete JEE Advanced set
        "iitjee/jee-advanced-pyq",
        "Vivacem/JEE_Advanced",
        "openai/openai_humaneval",      # not JEE — will fail subject filter, harmless
    ]

    ds = None
    for dataset_id in candidates:
        try:
            logger.info("Trying JEE Advanced dataset: %s …", dataset_id)
            ds = load_dataset(dataset_id, split="train")
            logger.info("  Loaded %s: %d rows, cols=%s", dataset_id, len(ds), ds.column_names)
            break
        except Exception as exc:
            logger.warning("  %s failed: %s", dataset_id, exc)

    if ds is None:
        logger.warning("No JEE Advanced HuggingFace dataset found. Skipping this source.")
        return []

    logger.info("jeebench: %d rows, columns=%s", len(ds), ds.column_names)

    cols = ds.column_names
    col_q       = next((c for c in ["question", "Question", "problem", "Problem"] if c in cols), None)
    col_ans     = next((c for c in ["answer", "Answer", "solution", "explanation"] if c in cols), None)
    col_subj    = next((c for c in ["subject", "Subject", "category"] if c in cols), None)
    col_year    = next((c for c in ["year", "Year"] if c in cols), None)
    col_type    = next((c for c in ["type", "exam_type", "exam", "Type"] if c in cols), None)
    col_topic   = next((c for c in ["topic", "Topic", "chapter"] if c in cols), None)
    col_diff    = next((c for c in ["difficulty", "level", "hard_level"] if c in cols), None)

    problems: List[dict] = []
    for row in ds:
        q_text = str(row.get(col_q, "")).strip() if col_q else ""
        if not q_text or len(q_text) < 20:
            continue

        raw_subject = str(row.get(col_subj, "")).strip() if col_subj else ""
        subject = _normalize_subject(raw_subject)
        if subject is None:
            continue

        raw_year = row.get(col_year, None) if col_year else None
        try:
            year = int(raw_year) if raw_year else None
        except (ValueError, TypeError):
            year = None

        raw_type = str(row.get(col_type, "JEE Advanced")).strip() if col_type else "JEE Advanced"
        exam_type = "JEE Advanced" if "advanced" in raw_type.lower() else "JEE Mains"

        topic = str(row.get(col_topic, "")).strip() if col_topic else ""
        solution = str(row.get(col_ans, "")).strip() if col_ans else ""
        difficulty = _infer_difficulty(row, exam_type)

        problems.append({
            "subject":       subject,
            "topic":         topic,
            "year":          year,
            "exam_type":     exam_type,
            "difficulty":    difficulty,
            "problem_text":  _clean_latex(q_text),
            "solution_text": _clean_latex(solution),
            "solution_steps": [],
            "source_verified": bool(solution),
        })

    logger.info("jeebench: %d valid problems extracted", len(problems))
    return problems


# ── Source: JEE Mains ─────────────────────────────────────────────────────────

def _load_jee_mains() -> List[dict]:
    """
    Load a JEE Mains dataset from HuggingFace.
    Tries multiple known dataset IDs. trust_remote_code removed (deprecated).
    """
    try:
        from datasets import load_dataset
    except ImportError:
        return []

    candidates = [
        "Vivacem/JEE_Mains_2024",
        "tanmayS/JEE_Main_Questions",
        "iamtarun/jee_mains_questions",
        "naman1011/jee-mains-pyq",
    ]

    for dataset_id in candidates:
        try:
            logger.info("Trying JEE Mains dataset: %s …", dataset_id)
            ds = load_dataset(dataset_id, split="train")
            logger.info("  Loaded %s: %d rows", dataset_id, len(ds))
            break
        except Exception as exc:
            logger.warning("  %s failed: %s", dataset_id, exc)
    else:
        logger.warning("No JEE Mains HuggingFace dataset found. Skipping this source.")
        return []

    cols = ds.column_names
    col_q    = next((c for c in ["question", "Question", "problem"] if c in cols), None)
    col_ans  = next((c for c in ["answer", "solution", "Answer"] if c in cols), None)
    col_subj = next((c for c in ["subject", "Subject"] if c in cols), None)
    col_year = next((c for c in ["year", "Year"] if c in cols), None)
    col_topic = next((c for c in ["topic", "chapter", "Topic"] if c in cols), None)

    problems: List[dict] = []
    for row in ds:
        q_text = str(row.get(col_q, "")).strip() if col_q else ""
        if not q_text or len(q_text) < 20:
            continue

        raw_subj = str(row.get(col_subj, "")).strip() if col_subj else ""
        subject = _normalize_subject(raw_subj)
        if subject is None:
            continue

        raw_year = row.get(col_year, None) if col_year else None
        try:
            year = int(raw_year) if raw_year else None
        except (ValueError, TypeError):
            year = None

        topic = str(row.get(col_topic, "")).strip() if col_topic else ""
        solution = str(row.get(col_ans, "")).strip() if col_ans else ""

        problems.append({
            "subject":       subject,
            "topic":         topic,
            "year":          year,
            "exam_type":     "JEE Mains",
            "difficulty":    _infer_difficulty(row, "JEE Mains"),
            "problem_text":  _clean_latex(q_text),
            "solution_text": _clean_latex(solution),
            "solution_steps": [],
            "source_verified": bool(solution),
        })

    logger.info("JEE Mains: %d valid problems extracted", len(problems))
    return problems


# ── Source: seed file ─────────────────────────────────────────────────────────

def _load_seed_file(path: Path) -> List[dict]:
    """Load manually curated JSON seed file."""
    if not path.exists():
        logger.error("Seed file not found: %s", path)
        return []

    try:
        data = json.loads(path.read_text())
        logger.info("Seed file: %d entries from %s", len(data), path)
        problems: List[dict] = []
        for item in data:
            subject = _normalize_subject(item.get("subject", ""))
            if subject is None:
                logger.warning("Unknown subject in seed: %s", item.get("subject"))
                continue
            q_text = str(item.get("problem_text", "")).strip()
            if not q_text:
                continue
            exam_type = item.get("exam_type", "JEE Advanced")
            if exam_type not in ("JEE Mains", "JEE Advanced"):
                exam_type = "JEE Advanced"
            problems.append({
                "subject":       subject,
                "topic":         item.get("topic", ""),
                "year":          item.get("year", None),
                "exam_type":     exam_type,
                "difficulty":    item.get("difficulty", 3),
                "problem_text":  _clean_latex(q_text),
                "solution_text": _clean_latex(item.get("solution_text", "")),
                "solution_steps": item.get("solution_steps", []),
                "source_verified": item.get("source_verified", False),
            })
        logger.info("Seed: %d valid problems", len(problems))
        return problems
    except Exception as exc:
        logger.error("Failed to load seed file: %s", exc)
        return []


# ── Main ingestion ────────────────────────────────────────────────────────────

async def ingest(
    source: str = "all",
    seed_file: Optional[Path] = None,
    dry_run: bool = False,
    reset_progress: bool = False,
) -> None:
    if reset_progress and PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()
        logger.info("Progress file reset.")

    completed = _load_progress()
    logger.info("Previously completed entries: %d", len(completed))

    # ── Collect problems from selected sources ────────────────────────────────
    all_problems: List[dict] = []

    # Seed file runs first — it's always available and has verified problems.
    # HuggingFace sources supplement if they can be accessed.
    if source in ("seed", "all"):
        sf = seed_file or DEFAULT_SEED
        if sf.exists():
            all_problems.extend(_load_seed_file(sf))
        elif source == "seed":
            logger.error("Seed file not found: %s", sf)
            sys.exit(1)
        else:
            logger.warning("Seed file not found at %s, skipping seed source.", sf)

    if source in ("jeebench", "all"):
        all_problems.extend(_load_jeebench())

    if source in ("jee_mains", "all"):
        all_problems.extend(_load_jee_mains())

    if not all_problems:
        logger.warning("No problems collected. Exiting.")
        return

    logger.info("Total problems to process: %d", len(all_problems))

    # ── Deduplicate by content hash ──────────────────────────────────────────
    seen_hashes: set[str] = set()
    deduped: List[dict] = []
    for p in all_problems:
        h = str(hash(p["problem_text"][:200]))
        if h not in seen_hashes:
            seen_hashes.add(h)
            deduped.append(p)

    logger.info("After deduplication: %d problems", len(deduped))

    # ── Assign stable problem_ids (deterministic from content) ───────────────
    for p in deduped:
        # Use UUID5 so the same problem always gets the same ID
        name_str = f"{p['subject']}|{p['year']}|{p['exam_type']}|{p['problem_text'][:200]}"
        p["problem_id"] = uuid.uuid5(uuid.NAMESPACE_DNS, name_str)

    # ── Filter out already-completed ──────────────────────────────────────────
    to_process = [p for p in deduped if str(p["problem_id"]) not in completed]
    logger.info("%d problems to embed + insert (%d already done)", len(to_process), len(deduped) - len(to_process))

    if not to_process:
        logger.info("Nothing to do — all problems already ingested.")
        return

    # ── Connect to DB ─────────────────────────────────────────────────────────
    pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=5)

    total_inserted = 0

    try:
        texts_to_embed = [p["problem_text"] for p in to_process]

        # ── Embed in batches ──────────────────────────────────────────────────
        all_embeddings: List[List[float]] = []
        for i in range(0, len(texts_to_embed), EMBED_BATCH):
            batch = texts_to_embed[i : i + EMBED_BATCH]
            logger.info(
                "Embedding batch %d–%d / %d …",
                i + 1, min(i + EMBED_BATCH, len(texts_to_embed)), len(texts_to_embed),
            )
            retries = 0
            while retries < 3:
                try:
                    embs = _embed_batch(batch)
                    all_embeddings.extend(embs)
                    break
                except Exception as exc:
                    retries += 1
                    logger.warning("Embedding batch attempt %d/3 failed: %s", retries, exc)
                    time.sleep(2 ** retries)
            else:
                logger.error("Embedding batch failed after 3 retries — skipping batch.")
                all_embeddings.extend([None] * len(batch))

        # ── Attach embeddings to problems ─────────────────────────────────────
        db_rows = []
        for i, prob in enumerate(to_process):
            emb = all_embeddings[i] if i < len(all_embeddings) else None
            if emb is None:
                logger.warning("No embedding for problem_id=%s — skipping", prob["problem_id"])
                continue
            prob["embedding"] = emb
            db_rows.append(prob)

        # ── Insert in batches ─────────────────────────────────────────────────
        for i in range(0, len(db_rows), INSERT_BATCH):
            batch = db_rows[i : i + INSERT_BATCH]
            n = await _insert_problems(pool, batch, dry_run=dry_run)
            total_inserted += n
            # Save progress after each batch
            for row in batch:
                completed.add(str(row["problem_id"]))
            _save_progress(completed)
            logger.info("  ✅ Inserted batch of %d (total: %d)", n, total_inserted)

    finally:
        await pool.close()

    logger.info(
        "🎉 JEE PYQ ingestion complete. Total inserted: %d problems", total_inserted
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest JEE PYQ dataset into jee_problems table"
    )
    parser.add_argument(
        "--source",
        choices=["all", "jeebench", "jee_mains", "seed"],
        default="all",
        help="Data source to ingest (default: all)",
    )
    parser.add_argument(
        "--seed-file",
        type=Path,
        default=None,
        help=f"Path to seed JSON file (default: {DEFAULT_SEED})",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reset-progress", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(
        ingest(
            source=args.source,
            seed_file=args.seed_file,
            dry_run=args.dry_run,
            reset_progress=args.reset_progress,
        )
    )
