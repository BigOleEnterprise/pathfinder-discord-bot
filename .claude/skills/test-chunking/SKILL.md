---
name: test-chunking
description: Test PDF text chunking on rulebooks (no API calls, local only)
allowed-tools: Bash
---

Run the chunking test on all PDFs in the `rulebooks/` directory. No API calls are made.

```bash
cd /Users/guppy/Github/NahnStuff_2/pathfinder-discord-bot && source .venv/bin/activate && python ${CLAUDE_SKILL_DIR}/test_chunking.py
```
