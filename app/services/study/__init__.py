"""Study Path (Mode 1) — concept-card composer.

v0.20: assembles Notes / Practice / PYQs / Mastery for any
(subject, chapter, topic) tuple by re-using existing infra
(Retriever, problems table, jee_problems table, concept_mastery).

Zero new content generation — every section is computed at request time
from data already indexed.
"""
