"""Test vector search: embed a query and search MongoDB rulebook chunks."""
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

project_root = Path(__file__).resolve().parents[3]
load_dotenv(project_root / ".env")
sys.path.insert(0, str(project_root))

from pathfinder_discord_bot.config import settings
from pathfinder_discord_bot.database.mongodb_service import MongoDBService
from pathfinder_discord_bot.services.embedding_service import EmbeddingService


async def main():
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "How does flanking work in Pathfinder 2E?"

    print("=" * 70)
    print("VECTOR SEARCH TEST")
    print("=" * 70)
    print(f"\nQuery: \"{query}\"")

    embedding_service = EmbeddingService(
        api_key=settings.openai_api_key,
        model=settings.openai_embedding_model,
    )
    mongodb = MongoDBService(
        uri=settings.mongodb_uri,
        database_name=settings.mongodb_database,
    )

    # Ping MongoDB
    print("\n[1/3] Pinging MongoDB...", end="", flush=True)
    if not await mongodb.ping():
        print(" FAIL")
        return
    print(" OK")

    # Embed query
    print("[2/3] Embedding query...", end="", flush=True)
    result = await embedding_service.embed_text(query)
    print(f" OK ({result.tokens_used} tokens)")

    # Vector search
    print("[3/3] Searching...", end="", flush=True)
    results = await mongodb.vector_search_rulebooks(
        query_embedding=result.embedding, limit=5
    )
    print(f" OK ({len(results)} results)")

    if not results:
        print("\nNo results found. Check that:")
        print("  1. Rulebooks are ingested (python scripts/ingest_rulebooks.py)")
        print("  2. Vector index 'vector_index' exists on rulebook_chunks.embedding")
        await mongodb.close()
        return

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    for i, r in enumerate(results, 1):
        score = r.get("score", 0)
        source = r.get("source", "unknown")
        chunk_idx = r.get("chunk_index", 0)
        text = r.get("text", "")[:200].replace("\n", " ")
        print(f"\n  {i}. [score={score:.4f}] {source} (chunk {chunk_idx})")
        print(f"     {text}...")

    print("\n" + "=" * 70)
    await mongodb.close()


if __name__ == "__main__":
    asyncio.run(main())
