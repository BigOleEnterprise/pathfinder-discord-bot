"""Test script for vector search - Slice 5."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pathfinder_discord_bot.config import settings
from pathfinder_discord_bot.database.mongodb_service import MongoDBService
from pathfinder_discord_bot.services.embedding_service import EmbeddingService


async def main():
    """Test vector search on rulebook chunks."""
    print("=" * 80)
    print("SLICE 5: VECTOR SEARCH TEST")
    print("=" * 80)

    # Get search query from command line or use default
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = "How does flanking work?"

    print(f"\n🔍 Search Query: \"{query}\"")
    print("-" * 80)

    # Initialize services
    print("\n[1/4] Initializing services...", end="", flush=True)
    embedding_service = EmbeddingService(
        api_key=settings.openai_api_key,
        model=settings.openai_embedding_model,
    )
    mongodb = MongoDBService(
        uri=settings.mongodb_uri,
        database_name=settings.mongodb_database,
    )
    print(" ✅")

    # Test MongoDB connection
    print("[2/4] Testing MongoDB connection...", end="", flush=True)
    if not await mongodb.ping():
        print(" ❌ Failed!")
        return
    print(" ✅")

    # Embed the query
    print(f"[3/4] Embedding query...", end="", flush=True)
    query_result = await embedding_service.embed_text(query)
    print(f" ✅ ({query_result.tokens_used} tokens)")

    # Search for similar chunks
    print(f"[4/4] Searching rulebook chunks...", end="", flush=True)
    results = await mongodb.vector_search_rulebooks(
        query_embedding=query_result.embedding,
        limit=5,
    )
    print(f" ✅ Found {len(results)} results")

    # Display results
    print("\n" + "=" * 80)
    print("SEARCH RESULTS")
    print("=" * 80)

    if not results:
        print("\n❌ No results found. Check that:")
        print("   1. Vector index is created and active")
        print("   2. Chunks are in MongoDB")
        print("   3. Index name is 'vector_index'")
        await mongodb.close()
        return

    for i, result in enumerate(results, 1):
        score = result.get("score", 0)
        source = result.get("source", "unknown")
        chunk_idx = result.get("chunk_index", 0)
        text = result.get("text", "")

        print(f"\n{'─' * 80}")
        print(f"Result {i} - Score: {score:.4f} - Source: {source} (chunk {chunk_idx})")
        print(f"{'─' * 80}")

        # Show first 300 chars
        preview = text[:300].replace("\n", " ")
        print(f"{preview}...")

    print("\n" + "=" * 80)
    print("✅ Slice 5 Complete! Vector search is working.")
    print("\n💡 Next: Integrate search with /ask command")
    print("\nTry other searches:")
    print("  python scripts/test_search.py critical hit")
    print("  python scripts/test_search.py action economy")
    print("  python scripts/test_search.py spellcasting")

    await mongodb.close()


if __name__ == "__main__":
    asyncio.run(main())
