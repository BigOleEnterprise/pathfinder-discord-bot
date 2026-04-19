---
name: test-pdf
description: Test PDF text extraction from rulebooks (no API calls, local only)
allowed-tools: Bash
---

Run the PDF extraction test on rulebooks in the `rulebooks/` directory. No API calls are made.

```bash
cd /Users/guppy/Github/NahnStuff_2/pathfinder-discord-bot && source .venv/bin/activate && python ${CLAUDE_SKILL_DIR}/test_pdf.py
```
