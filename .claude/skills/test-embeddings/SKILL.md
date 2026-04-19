---
name: test-embeddings
description: Test OpenAI embedding generation on provided text or a sample
allowed-tools: Bash
argument-hint: [text to embed]
---

Run the embedding test. Pass optional text as arguments (default: a sample PF2E rules snippet).

```bash
cd /Users/guppy/Github/NahnStuff_2/pathfinder-discord-bot && source .venv/bin/activate && python ${CLAUDE_SKILL_DIR}/test_embeddings.py $ARGUMENTS
```
