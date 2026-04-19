---
name: test-health
description: Ping MongoDB, OpenAI, and Claude to verify all integrations are working
allowed-tools: Bash
---

Run the integration health check script. This pings all three external services (MongoDB, OpenAI, Claude) and reports pass/fail with latency.

```bash
cd /Users/guppy/Github/NahnStuff_2/pathfinder-discord-bot && source .venv/bin/activate && python ${CLAUDE_SKILL_DIR}/test_health.py $ARGUMENTS
```

If a service fails, check:
- `.env` file has the correct API keys and MongoDB URI
- The virtual environment is activated and dependencies are installed
- MongoDB Atlas cluster is running and network access is configured
