---
name: test-search
description: Test vector search by embedding a query and searching MongoDB rulebook chunks
allowed-tools: Bash
argument-hint: [query text]
---

Run the vector search test. Pass an optional query as arguments (default: "How does flanking work in Pathfinder 2E?").

```bash
cd /Users/guppy/Github/NahnStuff_2/pathfinder-discord-bot && source .venv/bin/activate && python ${CLAUDE_SKILL_DIR}/test_search.py $ARGUMENTS
```

If no results are returned, check:
- Rulebooks have been ingested (`python scripts/ingest_rulebooks.py`)
- MongoDB Atlas vector index named `vector_index` exists on the `rulebook_chunks` collection
