"""
Taxonomy API — Subject → Chapter → Topic hierarchy.

GET /taxonomy
    Returns all distinct Subject → Chapter (topic) → Topic (subtopic) combinations
    from the concepts table, nested as JSON.

Note: we query `concepts` rather than `knowledge_chunks` because the concepts
table carries the full three-level hierarchy (subject / topic / subtopic) while
knowledge_chunks only has subject + chapter.
"""
import logging
from collections import defaultdict

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/taxonomy", tags=["taxonomy"])


@router.get("")
async def get_taxonomy(request: Request):
    """
    Return the full syllabus hierarchy as nested JSON:

    {
      "subjects": [
        {
          "name": "Mathematics",
          "chapters": [
            {
              "name": "Relations",
              "topics": ["Cartesian Product of Sets", "Reflexive Relations", …]
            }
          ]
        }
      ]
    }
    """
    pool = request.app.state.db_pool

    rows = await pool.fetch(
        """
        SELECT DISTINCT subject, topic, subtopic
        FROM concepts
        WHERE subject IS NOT NULL
          AND topic   IS NOT NULL
          AND subtopic IS NOT NULL
        ORDER BY subject, topic, subtopic
        """
    )

    # Build nested structure: subject → chapter → [topics]
    tree: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        tree[row["subject"]][row["topic"]].append(row["subtopic"])

    subjects = [
        {
            "name": subject,
            "chapters": [
                {"name": chapter, "topics": topics}
                for chapter, topics in sorted(chapters.items())
            ],
        }
        for subject, chapters in sorted(tree.items())
    ]

    logger.info("Taxonomy fetched: %d subjects, %d rows", len(subjects), len(rows))
    return {"subjects": subjects}
