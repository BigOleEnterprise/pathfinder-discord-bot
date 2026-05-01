"""Chunk and embed rulebook text files into MongoDB for RAG vector search.

Usage:
    python scripts/ingest_rulebooks.py          # only process new .txt files
    python scripts/ingest_rulebooks.py --full    # wipe all chunks and reprocess everything
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pathfinder_discord_bot.config import settings
from pathfinder_discord_bot.database.models import RulebookChunk
from pathfinder_discord_bot.database.mongodb_service import MongoDBService
from pathfinder_discord_bot.services.embedding_service import EmbeddingService
from pathfinder_discord_bot.utils.text_chunker import TextChunker

RULEBOOKS_DIR = Path(__file__).parent.parent / "rulebooks"


async def ingest_source(
    source_name: str,
    text: str,
    embedding_service: EmbeddingService,
    mongodb: MongoDBService,
) -> tuple[int, int]:
    """Chunk, embed, and save a single source. Returns (chunks_saved, tokens_used)."""
    # Chunk
    print("  [1/3] Chunking...", end="", flush=True)
    text_chunks = TextChunker.chunk_by_tokens(text, max_tokens=800, overlap_tokens=100)
    print(f" {len(text_chunks)} chunks")

    # Embed
    print(f"  [2/3] Embedding {len(text_chunks)} chunks...")
    chunk_texts = [chunk.text for chunk in text_chunks]
    embeddings = await embedding_service.embed_batch(chunk_texts, batch_size=100)

    total_tokens = sum(e.tokens_used for e in embeddings)

    # Build models
    chunks_to_save = []
    for i, (text_chunk, embedding_result) in enumerate(zip(text_chunks, embeddings)):
        chunks_to_save.append(
            RulebookChunk(
                text=text_chunk.text,
                source=source_name,
                chunk_index=i,
                char_count=len(text_chunk.text),
                token_count=len(text_chunk.text) // 4,
                embedding=embedding_result.embedding,
                embedding_model=embedding_result.model,
            )
        )

    # Save in batches
    print("  [3/3] Saving to MongoDB...", end="", flush=True)
    saved_count = 0
    batch_size = 100
    for i in range(0, len(chunks_to_save), batch_size):
        batch = chunks_to_save[i : i + batch_size]
        saved_count += await mongodb.save_rulebook_chunks_batch(batch)
    print(f" {saved_count} chunks saved")

    return saved_count, total_tokens


async def main():
    parser = argparse.ArgumentParser(description="Ingest rulebook text into MongoDB vector store.")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Wipe all existing chunks and reprocess everything (default: only add new sources)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print(f"RULEBOOK INGESTION ({'FULL REBUILD' if args.full else 'NEW ONLY'})")
    print("=" * 70)

    # Find .txt files
    txt_files = sorted(RULEBOOKS_DIR.glob("*.txt"))
    if not txt_files:
        print(f"\nNo .txt files found in {RULEBOOKS_DIR}")
        print("Run 'python scripts/extract_rulebooks.py' first to extract PDFs.")
        return

    # Initialize services
    print("\nInitializing services...")
    embedding_service = EmbeddingService(
        api_key=settings.openai_api_key,
        model=settings.openai_embedding_model,
    )
    mongodb = MongoDBService(
        uri=settings.mongodb_uri,
        database_name=settings.mongodb_database,
    )

    if not await mongodb.ping():
        print("MongoDB connection failed. Check your connection string.")
        return

    # Full mode: wipe everything
    if args.full:
        deleted = await mongodb.clear_rulebook_chunks()
        print(f"Cleared {deleted} existing chunks")
        existing_sources: set[str] = set()
    else:
        existing_sources = await mongodb.get_existing_rulebook_sources()
        if existing_sources:
            print(f"Already ingested: {', '.join(sorted(existing_sources))}")

    # Determine which files to process
    to_process = []
    for txt_path in txt_files:
        source_name = txt_path.stem
        if source_name in existing_sources:
            print(f"  SKIP  {txt_path.name} (already ingested)")
        else:
            to_process.append(txt_path)

    if not to_process:
        print("\nNothing new to ingest.")
        await mongodb.close()
        return

    print(f"\nProcessing {len(to_process)} source(s)...\n")

    total_saved = 0
    total_tokens = 0

    for idx, txt_path in enumerate(to_process, 1):
        source_name = txt_path.stem
        text = txt_path.read_text(encoding="utf-8")

        print(f"[{idx}/{len(to_process)}] {source_name} ({len(text):,} chars)")
        saved, tokens = await ingest_source(source_name, text, embedding_service, mongodb)
        total_saved += saved
        total_tokens += tokens
        print()

    # Summary
    print("=" * 70)
    print("INGESTION COMPLETE")
    print("=" * 70)
    print(f"Chunks saved: {total_saved}")
    print(f"Tokens used:  {total_tokens:,}")
    cost = (total_tokens / 1_000_000) * 0.02
    print(f"Est. cost:    ${cost:.4f}")

    await mongodb.close()


if __name__ == "__main__":
    asyncio.run(main())
