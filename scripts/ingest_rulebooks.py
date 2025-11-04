"""Full rulebook ingestion script - Slice 4."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pathfinder_discord_bot.config import settings
from pathfinder_discord_bot.database.models import RulebookChunk
from pathfinder_discord_bot.database.mongodb_service import MongoDBService
from pathfinder_discord_bot.services.embedding_service import EmbeddingService
from pathfinder_discord_bot.services.pdf_parser import PDFParserService
from pathfinder_discord_bot.utils.text_chunker import TextChunker


async def main():
    """Full rulebook ingestion pipeline."""
    print("=" * 80)
    print("SLICE 4: FULL RULEBOOK INGESTION")
    print("=" * 80)

    # Initialize services
    print("\n🔧 Initializing services...")
    embedding_service = EmbeddingService(
        api_key=settings.openai_api_key,
        model=settings.openai_embedding_model,
    )
    mongodb = MongoDBService(
        uri=settings.mongodb_uri,
        database_name=settings.mongodb_database,
    )

    # Test MongoDB connection
    print("   Testing MongoDB connection...", end="", flush=True)
    if not await mongodb.ping():
        print(" ❌ Failed!")
        print("\n⚠️  MongoDB connection failed. Check your connection string.")
        return
    print(" ✅")

    # Clear existing chunks (fresh start)
    print("   Clearing existing chunks...", end="", flush=True)
    deleted = await mongodb.clear_rulebook_chunks()
    print(f" ✅ Deleted {deleted} old chunks")

    # Process PDFs
    rulebooks_dir = Path(__file__).parent.parent / "rulebooks"
    pdfs = list(rulebooks_dir.glob("*.pdf"))

    print(f"\n📚 Found {len(pdfs)} PDFs to process")

    all_chunks_to_save = []
    total_tokens = 0

    for idx, pdf_path in enumerate(pdfs, 1):
        print(f"\n{'=' * 80}")
        print(f"Processing {idx}/{len(pdfs)}: {pdf_path.name}")
        print('=' * 80)

        # Step 1: Extract
        print(f"[1/4] Extracting pages...", end="", flush=True)
        pages = PDFParserService.extract_text_from_pdf(pdf_path)
        full_text = "\n\n".join(page.text for page in pages)
        print(f" ✅ {len(pages)} pages, {len(full_text):,} chars")

        # Step 2: Chunk
        print(f"[2/4] Chunking text...", end="", flush=True)
        text_chunks = TextChunker.chunk_by_tokens(full_text, max_tokens=800, overlap_tokens=100)
        print(f" ✅ {len(text_chunks)} chunks")

        # Step 3: Generate embeddings (with progress)
        print(f"[3/4] Generating {len(text_chunks)} embeddings...")
        chunk_texts = [chunk.text for chunk in text_chunks]

        # Batch embed for efficiency
        embeddings = await embedding_service.embed_batch(chunk_texts, batch_size=100)
        print(f"      ✅ All embeddings generated")

        # Step 4: Create chunk models
        print(f"[4/4] Creating chunk models...", end="", flush=True)
        for i, (text_chunk, embedding_result) in enumerate(zip(text_chunks, embeddings)):
            chunk_model = RulebookChunk(
                text=text_chunk.text,
                source=pdf_path.stem,
                chunk_index=i,
                char_count=len(text_chunk.text),
                token_count=len(text_chunk.text) // 4,  # Rough estimate
                embedding=embedding_result.embedding,
                embedding_model=embedding_result.model,
            )
            all_chunks_to_save.append(chunk_model)
            total_tokens += embedding_result.tokens_used

        print(f" ✅ {len(text_chunks)} models created")

    # Save all chunks to MongoDB
    print(f"\n{'=' * 80}")
    print("SAVING TO MONGODB")
    print('=' * 80)
    print(f"Total chunks to save: {len(all_chunks_to_save)}")
    print(f"Saving in batches of 100...")

    saved_count = 0
    batch_size = 100

    for i in range(0, len(all_chunks_to_save), batch_size):
        batch = all_chunks_to_save[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(all_chunks_to_save) + batch_size - 1) // batch_size

        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} chunks)...", end="", flush=True)
        count = await mongodb.save_rulebook_chunks_batch(batch)
        saved_count += count
        print(f" ✅")

    # Final summary
    print(f"\n{'=' * 80}")
    print("INGESTION COMPLETE!")
    print('=' * 80)
    print(f"✅ Saved {saved_count}/{len(all_chunks_to_save)} chunks to MongoDB")
    print(f"📊 Total tokens used: {total_tokens:,}")

    cost = (total_tokens / 1_000_000) * 0.02
    print(f"💰 Total cost: ${cost:.2f}")

    print(f"\n💡 Next: Set up vector search index in MongoDB Atlas")
    print(f"\n⚠️  IMPORTANT: You need to create a vector search index in MongoDB Atlas!")
    print(f"   1. Go to MongoDB Atlas → Database → Search")
    print(f"   2. Create Search Index on 'rulebook_chunks' collection")
    print(f"   3. Index the 'embedding' field as vector (1536 dimensions)")

    await mongodb.close()


if __name__ == "__main__":
    asyncio.run(main())
