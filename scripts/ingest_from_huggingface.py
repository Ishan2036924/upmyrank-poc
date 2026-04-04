"""
Ingest Physics (Class 11 + 12) content into Postgres knowledge_chunks and problems tables.

Strategy:
  1. Load KadamParth/Ncert_dataset from HuggingFace.
  2. Filter for subject == 'Physics', grades 11 and 12.
  3. Embed with all-MiniLM-L6-v2 and insert into knowledge_chunks + problems.
  4. Rebuild HNSW indexes.
  5. Run similarity-search test queries.

Usage:
    poetry run python scripts/ingest_from_huggingface.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse as _up
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
import psycopg2.extras
from datasets import load_dataset
from tqdm import tqdm

from app.config import settings
from app.services.rag.embeddings import embed_single, embed_texts

# ── Physics concept ID mapping ───────────────────────────────────────────────
# Maps keyword patterns in Topic/subtopic strings → physics concept IDs
CONCEPT_MAP: list[tuple[list[str], str]] = [
    # Class 11
    (["physical world", "nature of physics"],          "physics.11.physical_world"),
    (["si unit", "dimension", "measurement"],          "physics.11.units_measurements"),
    (["dimensional analys"],                           "physics.11.dimensional_analysis"),
    (["significant figure", "error analys"],           "physics.11.significant_figures"),
    (["distance", "displacement"],                     "physics.11.distance_displacement"),
    (["speed", "velocity"],                            "physics.11.speed_velocity"),
    (["acceleration", "equation of motion"],           "physics.11.acceleration"),
    (["graphical analys", "position-time", "v-t graph"], "physics.11.graphical_analysis"),
    (["vector"],                                       "physics.11.vectors"),
    (["projectile"],                                   "physics.11.projectile_motion"),
    (["circular motion", "centripetal"],               "physics.11.circular_motion"),
    (["first law", "inertia"],                         "physics.11.newtons_first_law"),
    (["second law", "f=ma", "f = ma", "force and mass"], "physics.11.newtons_second_law"),
    (["third law", "action reaction"],                 "physics.11.newtons_third_law"),
    (["friction", "static friction", "kinetic friction"], "physics.11.friction"),
    (["work done", "work by"],                         "physics.11.work"),
    (["kinetic energy", "work-energy"],                "physics.11.kinetic_energy"),
    (["potential energy", "elastic energy"],           "physics.11.potential_energy"),
    (["conservation of energy"],                       "physics.11.conservation_energy"),
    (["power", "collision", "elastic collision"],      "physics.11.power"),
    (["centre of mass", "center of mass"],             "physics.11.centre_of_mass"),
    (["moment of inertia"],                            "physics.11.moment_of_inertia"),
    (["torque", "angular momentum"],                   "physics.11.torque"),
    (["rotational", "rolling"],                        "physics.11.rotational_dynamics"),
    (["gravitation", "newton's law of gravitation"],   "physics.11.universal_gravitation"),
    (["gravitational field", "gravitational potential"], "physics.11.gravitational_field"),
    (["satellite", "orbital"],                         "physics.11.orbital_motion"),
    (["escape velocity", "kepler"],                    "physics.11.escape_velocity"),
    (["stress", "strain", "elastic moduli", "young's modulus"], "physics.11.stress_strain"),
    (["hooke"],                                        "physics.11.hookes_law"),
    (["pressure", "pascal"],                           "physics.11.pressure_fluids"),
    (["bernoulli", "viscosity"],                       "physics.11.bernoulli"),
    (["surface tension", "capillar"],                  "physics.11.surface_tension"),
    (["temperature", "thermal expansion", "thermometer"], "physics.11.temperature_heat"),
    (["calorimetry", "specific heat", "latent heat"],  "physics.11.calorimetry"),
    (["conduction", "convection", "radiation", "heat transfer"], "physics.11.heat_transfer"),
    (["first law of thermo", "internal energy"],       "physics.11.first_law_thermo"),
    (["second law", "heat engine", "carnot", "efficiency"], "physics.11.second_law_thermo"),
    (["entropy", "carnot cycle"],                      "physics.11.carnot_cycle"),
    (["kinetic theory", "rms speed"],                  "physics.11.kinetic_theory_gases"),
    (["gas law", "ideal gas", "boyle", "charles"],     "physics.11.gas_laws"),
    (["simple harmonic", "shm"],                       "physics.11.shm"),
    (["energy in shm", "damped", "damping"],           "physics.11.shm_energy"),
    (["pendulum", "forced oscillation"],               "physics.11.pendulum"),
    (["wave", "transverse", "longitudinal", "wave motion"], "physics.11.wave_motion"),
    (["superposition", "standing wave", "resonance"],  "physics.11.superposition"),
    (["doppler"],                                      "physics.11.doppler_effect"),
    # Class 12
    (["coulomb", "electric charge"],                   "physics.12.electric_charge"),
    (["electric field", "field line"],                 "physics.12.electric_field"),
    (["gauss"],                                        "physics.12.gauss_law"),
    (["electric potential", "potential energy"],       "physics.12.electric_potential"),
    (["capacitor", "capacitance"],                     "physics.12.capacitance"),
    (["dielectric"],                                   "physics.12.dielectrics"),
    (["ohm", "resistance", "resistivity"],             "physics.12.ohms_law"),
    (["kirchhoff", "circuit"],                         "physics.12.kirchhoffs_laws"),
    (["wheatstone", "potentiometer"],                  "physics.12.wheatstone_bridge"),
    (["magnetic force", "lorentz"],                    "physics.12.magnetic_force"),
    (["biot-savart", "biot savart", "ampere"],         "physics.12.biot_savart"),
    (["solenoid", "toroid"],                           "physics.12.solenoid_toroid"),
    (["magnetic property", "ferromagnetic", "diamagnetic"], "physics.12.magnetism_matter"),
    (["earth's magnet", "earth magnetism"],            "physics.12.earth_magnetism"),
    (["faraday", "lenz", "electromagnetic induction"], "physics.12.faradays_law"),
    (["inductance", "inductor"],                       "physics.12.inductance"),
    (["eddy current"],                                 "physics.12.eddy_currents"),
    (["ac circuit", "lcr", "resonance"],               "physics.12.ac_circuits"),
    (["transformer"],                                  "physics.12.transformers"),
    (["electromagnetic wave", "em wave", "spectrum"],  "physics.12.em_waves"),
    (["em propagation", "wave propagation"],           "physics.12.em_wave_propagation"),
    (["reflection", "refraction", "snell"],            "physics.12.reflection_refraction"),
    (["lens", "mirror", "image formation"],            "physics.12.lenses_mirrors"),
    (["microscope", "telescope", "optical instrument"], "physics.12.optical_instruments"),
    (["interference", "young", "double slit"],         "physics.12.interference"),
    (["diffraction", "polarization"],                  "physics.12.diffraction"),
    (["photoelectric"],                                "physics.12.photoelectric"),
    (["de broglie", "wave-particle", "matter wave"],   "physics.12.wave_particle_duality"),
    (["bohr", "hydrogen spectrum", "atomic model"],    "physics.12.atomic_models"),
    (["atomic spectra", "energy level"],               "physics.12.atomic_spectra"),
    (["nuclear", "binding energy"],                    "physics.12.nuclear_structure"),
    (["radioactivity", "radioactive", "half-life"],    "physics.12.radioactivity"),
    (["fission", "fusion", "nuclear reaction"],        "physics.12.nuclear_fission_fusion"),
    (["semiconductor", "p-n junction"],                "physics.12.semiconductors"),
    (["diode", "led", "photodiode"],                   "physics.12.diodes"),
    (["transistor", "logic gate"],                     "physics.12.transistors"),
]


def map_concepts(topic: str, explanation: str = "") -> list[str]:
    """Map a topic string to a list of physics concept IDs."""
    text = (topic + " " + explanation).lower()
    matched, seen = [], set()
    for keywords, cid in CONCEPT_MAP:
        if any(kw in text for kw in keywords) and cid not in seen:
            matched.append(cid)
            seen.add(cid)
            break  # one concept per match pass
    # If nothing matched, try each keyword list in order (broader scan)
    if not matched:
        for keywords, cid in CONCEPT_MAP:
            if any(kw in text for kw in keywords) and cid not in seen:
                matched.append(cid)
                seen.add(cid)
    return matched or ["physics.11.physical_world"]


def main() -> None:
    # ── 1. Load & inspect dataset ────────────────────────────────────────────
    print("\n[1/6] Loading KadamParth/Ncert_dataset from HuggingFace...")
    ds = load_dataset("KadamParth/Ncert_dataset")
    train = ds["train"]
    print(f"      Total rows  : {len(train)}")
    print(f"      Columns     : {train.column_names}")

    subjects = Counter(r["subject"] for r in train)
    print(f"\n      All subjects in dataset:")
    for subj, cnt in subjects.most_common():
        print(f"        {subj!r}: {cnt}")

    grades_all = Counter(str(r.get("grade", "?")) for r in train)
    print(f"      All grades  : {dict(grades_all.most_common())}")

    # ── Filter for Physics, grades 11 and 12 ─────────────────────────────────
    physics_rows = [
        r for r in train
        if str(r.get("subject", "")).strip().lower() == "physics"
        and r.get("grade") in [11, 12, "11", "12"]
    ]

    if not physics_rows:
        # Try broader filter (subject contains 'physics')
        physics_rows = [
            r for r in train
            if "physics" in str(r.get("subject", "")).strip().lower()
        ]
        print(f"\n      Broad filter found {len(physics_rows)} Physics rows")
    else:
        print(f"\n      Physics rows (grades 11+12): {len(physics_rows)}")

    if not physics_rows:
        print("      ⚠  No Physics rows found! Inspect dataset columns:")
        sample = train[0] if len(train) > 0 else {}
        for k, v in sample.items():
            print(f"        {k}: {v!r}")
        # Try any Physics subject
        all_phys = [r for r in train if "phys" in str(r.get("subject","")).lower()]
        print(f"      'phys' rows: {len(all_phys)}")
        if all_phys:
            physics_rows = all_phys[:3000]

    print(f"\n      Will ingest: {len(physics_rows)} rows")
    if len(physics_rows) > 0:
        print(f"      Sample row columns: {list(physics_rows[0].keys())}")
        print(f"      Sample subject: {physics_rows[0].get('subject', '?')!r}")
        print(f"      Sample grade: {physics_rows[0].get('grade', '?')!r}")

    grade_dist = Counter(str(r.get("grade", "?")) for r in physics_rows)
    topic_dist = Counter(r.get("Topic", r.get("topic", "?")) for r in physics_rows)
    print(f"\n      Grade distribution: {dict(grade_dist.most_common())}")
    print(f"      Unique topics: {len(topic_dist)}")
    print(f"      Top topics:")
    for t, cnt in topic_dist.most_common(10):
        print(f"        {t!r}: {cnt}")

    # ── 2. Connect to Postgres ───────────────────────────────────────────────
    print("\n[2/6] Connecting to Postgres...")
    dsn = settings.database_url
    if "supabase.com" in dsn:
        parsed = _up.urlparse(dsn)
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            dbname=parsed.path.lstrip("/"),
            user=parsed.username,
            password=_up.unquote(parsed.password or ""),
            sslmode="require",
        )
    else:
        conn = psycopg2.connect(dsn)
    conn.autocommit = False
    cur = conn.cursor()
    print("      Connected.")

    # Clear previous Physics rows
    cur.execute("DELETE FROM knowledge_chunks WHERE source_file LIKE '%physics%' OR source_file LIKE '%Physics%'")
    cur.execute("DELETE FROM problems WHERE source = 'NCERT_Physics_HF'")
    conn.commit()
    print("      Cleared previous Physics rows (if any).")

    # ── 3. Build records ─────────────────────────────────────────────────────
    print(f"\n[3/6] Preparing {len(physics_rows)} Physics rows...")

    # Detect column names (dataset might use different capitalisation)
    sample = physics_rows[0] if physics_rows else {}
    topic_col   = next((k for k in sample if k.lower() == "topic"), "Topic")
    expl_col    = next((k for k in sample if k.lower() in ("explanation", "content", "text")), "Explanation")
    q_col       = next((k for k in sample if k.lower() == "question"), "Question")
    a_col       = next((k for k in sample if k.lower() == "answer"), "Answer")
    grade_col   = next((k for k in sample if k.lower() == "grade"), "grade")
    cmplx_col   = next((k for k in sample if "complex" in k.lower()), None)
    print(f"      Column mapping: topic={topic_col!r} expl={expl_col!r} q={q_col!r} a={a_col!r}")

    chunk_texts, problem_texts, meta_list = [], [], []
    skipped = 0
    for row in physics_rows:
        topic    = str(row.get(topic_col, "") or "").strip()
        expl     = str(row.get(expl_col, "") or "").strip()
        question = str(row.get(q_col, "") or "").strip()
        answer   = str(row.get(a_col, "") or "").strip()
        grade    = row.get(grade_col, 11)
        complexity = int(row.get(cmplx_col, 5)) if cmplx_col and row.get(cmplx_col) is not None else 5

        if not question or not answer:
            skipped += 1
            continue

        content = f"Topic: {topic}\n\n{expl}\n\nQ: {question}\nA: {answer}"
        chunk_texts.append(content)
        problem_texts.append(question)
        meta_list.append({
            "difficulty":     round(complexity / 10.0, 2),
            "student_level":  f"Class {grade}",
            "question_type":  "short_answer",
            "complexity":     str(complexity),
            "prerequisites":  None,
            "estimated_time": f"{max(2, complexity)} min",
            "grade":          grade,
        })

    print(f"      Valid rows: {len(chunk_texts)}  (skipped {skipped} with missing Q/A)")

    if not chunk_texts:
        print("      ⚠  Nothing to ingest! Exiting.")
        cur.close(); conn.close(); return

    # ── 4. Embed in batches ──────────────────────────────────────────────────
    print("\n[4/6] Embedding chunks and questions (this may take a few minutes)...")
    BATCH = 64
    chunk_embeddings, problem_embeddings = [], []

    for i in tqdm(range(0, len(chunk_texts), BATCH), desc="Chunk embeddings"):
        chunk_embeddings.extend(embed_texts(chunk_texts[i : i + BATCH]))

    for i in tqdm(range(0, len(problem_texts), BATCH), desc="Problem embeddings"):
        problem_embeddings.extend(embed_texts(problem_texts[i : i + BATCH]))

    # ── 5. Insert in batches ─────────────────────────────────────────────────
    print("\n[5/6] Inserting into Postgres...")

    INSERT_BATCH = 200
    chunk_records, problem_records = [], []

    for idx, (row, meta, c_emb, p_emb) in enumerate(
        zip(physics_rows[:len(chunk_texts)], meta_list, chunk_embeddings, problem_embeddings)
    ):
        topic    = str(row.get(topic_col, "") or "").strip()
        expl     = str(row.get(expl_col, "") or "").strip()
        question = str(row.get(q_col, "") or "").strip()
        answer   = str(row.get(a_col, "") or "").strip()
        grade    = row.get(grade_col, 11)
        complexity = int(row.get(cmplx_col, 5)) if cmplx_col and row.get(cmplx_col) is not None else 5
        difficulty = round(complexity / 10.0, 2)
        concepts  = map_concepts(topic, expl[:200])
        content   = chunk_texts[idx]

        chunk_records.append((
            "huggingface:physics:KadamParth/Ncert_dataset",
            "Physics",
            topic,
            idx,
            content,
            json.dumps(c_emb),
            json.dumps(meta),
        ))
        problem_records.append((
            "Physics",
            topic,
            None,            # subtopic (not in dataset)
            difficulty,
            question,
            answer,
            concepts,
            "NCERT_Physics_HF",
            json.dumps(p_emb),
        ))

    # Insert chunks in batches
    total_chunks = 0
    for i in tqdm(range(0, len(chunk_records), INSERT_BATCH), desc="Inserting chunks"):
        batch = chunk_records[i : i + INSERT_BATCH]
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO knowledge_chunks
                (source_file, subject, chapter, chunk_index, content, embedding, metadata)
            VALUES %s
            """,
            batch,
            template="(%s, %s, %s, %s, %s, %s::vector, %s::jsonb)",
        )
        conn.commit()
        total_chunks += len(batch)

    # Insert problems in batches
    total_problems = 0
    for i in tqdm(range(0, len(problem_records), INSERT_BATCH), desc="Inserting problems"):
        batch = problem_records[i : i + INSERT_BATCH]
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO problems
                (subject, topic, subtopic, difficulty, question_text,
                 verified_answer, concepts_tested, source, embedding)
            VALUES %s
            """,
            batch,
            template="(%s, %s, %s, %s, %s, %s, %s, %s, %s::vector)",
        )
        conn.commit()
        total_problems += len(batch)

    print(f"      Inserted {total_chunks} chunks, {total_problems} problems")

    # ── 6. Rebuild HNSW indexes ──────────────────────────────────────────────
    print("\n[6/6] Rebuilding vector indexes (this may take a minute)...")
    conn.autocommit = True
    cur.execute("DROP INDEX IF EXISTS idx_knowledge_chunks_embedding_hnsw;")
    cur.execute(
        "CREATE INDEX idx_knowledge_chunks_embedding_hnsw "
        "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);"
    )
    cur.execute("DROP INDEX IF EXISTS idx_problems_embedding_hnsw;")
    cur.execute(
        "CREATE INDEX idx_problems_embedding_hnsw "
        "ON problems USING hnsw (embedding vector_cosine_ops);"
    )
    conn.autocommit = False
    print("      Done.")

    # ── Summary ───────────────────────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM knowledge_chunks WHERE subject='Physics'")
    final_chunks = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM problems WHERE subject='Physics'")
    final_problems = cur.fetchone()[0]
    cur.execute("SELECT DISTINCT chapter FROM knowledge_chunks WHERE subject='Physics' LIMIT 30")
    unique_topics = [r[0] for r in cur.fetchall()]

    print(f"\n{'='*66}")
    print(f"  INGESTION COMPLETE")
    print(f"  knowledge_chunks (Physics)  : {final_chunks}")
    print(f"  problems (Physics)          : {final_problems}")
    print(f"  unique topics (chapters)    : {len(unique_topics)}")
    print(f"{'='*66}")

    # ── Test similarity searches ──────────────────────────────────────────────
    test_queries = [
        "what is Newton's second law of motion",
        "explain the photoelectric effect",
        "what is Gauss's law",
    ]
    for query in test_queries:
        print(f"\n  ── Query: {query!r}")
        q_emb = json.dumps(embed_single(query))
        cur.execute(
            "SELECT content, similarity FROM match_chunks(%s::vector, 3, 'Physics')",
            (q_emb,),
        )
        rows = cur.fetchall()
        if not rows:
            print("    (no results — match_chunks may use different subject filter)")
        for rank, (content, sim) in enumerate(rows, 1):
            preview = content[:120].replace("\n", " ")
            print(f"    [{rank}] sim={sim:.4f}  {preview}…")

    cur.close()
    conn.close()
    print("\n✓ Done.\n")


if __name__ == "__main__":
    main()
