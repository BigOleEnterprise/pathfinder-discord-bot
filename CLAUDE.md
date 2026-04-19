# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pathfinder 2E Discord bot with dice rolling (`/roll`), LLM-powered rules Q&A (`/ask`) using RAG, and campaign lore tracking (planned). Python 3.11+, async throughout.

## Running Locally

1. Copy `.env.example` to `.env` and fill in credentials (Discord token, Anthropic key, OpenAI key, MongoDB URI)
2. Set `MONGODB_URI` to your MongoDB Atlas connection string (not `mongodb://mongodb:27017` — that's the Docker service name)
3. Install dependencies and run:

```bash
# Create venv and install (uses uv, same as Dockerfile)
python -m venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Run the bot
python -m pathfinder_discord_bot.bot
```

To populate the rulebook vector store (needed for `/ask`):
```bash
python scripts/ingest_rulebooks.py
```

### Running with Docker

```bash
docker-compose up --build
```

Code is mounted as a volume so changes reflect without rebuilding, but you need to restart the container.

## Other Commands

```bash
# Lint and format
ruff check pathfinder_discord_bot/
ruff format pathfinder_discord_bot/

# Type checking
mypy pathfinder_discord_bot/

# Tests (test directory not yet created)
pytest
pytest -x tests/test_specific.py::test_name  # single test
```

## Architecture

**Entry point:** `pathfinder_discord_bot/bot.py` — `PathfinderBot` loads cogs dynamically from `cogs/` and syncs slash commands.

**RAG pipeline (`/ask` command):**
1. User question → rate limit check (in-memory sliding window)
2. Question embedded via OpenAI (`text-embedding-3-small`, 1536-dim)
3. MongoDB vector search on `rulebook_chunks` collection
4. Claude API called with rulebook context as RAG grounding
5. Response + token usage logged to `question_logs` collection
6. Discord embed with optional "Sources" button showing excerpts

**Key patterns:**
- Cogs (`cogs/`) are Discord command handlers, auto-discovered by `bot.py`
- Services (`services/`) contain business logic — Claude, OpenAI embeddings, dice rolling, PDF parsing
- All API clients are async: `AsyncAnthropic`, `AsyncOpenAI`, `motor` for MongoDB
- Pydantic models (`database/models.py`) handle validation and MongoDB serialization
- `tenacity` retry decorators on external API calls
- `secrets` module used for cryptographically secure dice rolls

**External dependencies:**
- MongoDB Atlas — collections: `question_logs`, `rulebook_chunks` (with vector index on `embedding` field)
- Anthropic Claude API — rules Q&A
- OpenAI API — text embeddings only
- Discord.py — bot framework with slash commands

## Configuration

All config via `.env` (see `.env.example`). Loaded through Pydantic Settings in `config/settings.py` as a singleton.

Required: Discord token, Anthropic API key, OpenAI API key, MongoDB URI.

## Ruff Config

Line length: 100. Lint rules: E, F, I, N, W (E501 ignored). Target: Python 3.11.
