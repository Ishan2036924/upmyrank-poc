"""
Student Memory System — 3-layer persistent context.

    Layer 1 (hot):    Redis `hot:{student_id}` — last 2 session summaries, 48hr TTL
    Layer 2 (warm):   Postgres student_memory.compressed_profile — rewritten every 5 sessions
    Layer 3 (detail): concept_mastery.error_fingerprint — per-concept error decay map

Fixed ~300 token context bundle injected at every new session start.
"""
