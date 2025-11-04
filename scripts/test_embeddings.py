"""Test script for embedding generation - Slice 3."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pathfinder_discord_bot.config import settings
from pathfinder_discord_bot.services.embedding_service import EmbeddingService
from pathfinder_discord_bot.services.pdf_parser import PDFParserService
from pathfinder_discord_bot.utils.text_chunker import TextChunker


async def main():
    """Test embedding generation on sample chunks."""
    print("=" * 80)
    print("SLICE 3: EMBEDDING GENERATION TEST")
    print("=" * 80)

    # Initialize embedding service
    print("\n🔧 Initializing OpenAI Embedding Service...")
    embedding_service = EmbeddingService(
        api_key=settings.openai_api_key,
        model=settings.openai_embedding_model,
    )
    print(f"   Model: {settings.openai_embedding_model}")
    print(f"   Dimension: {embedding_service.dimension}")

    # Get sample chunks from Core Rulebook
    print("\n📚 Getting sample chunks from Core Rulebook...")
    rulebooks_dir = Path(__file__).parent.parent / "rulebooks"
    core_pdf = rulebooks_dir / "core_rulebook.pdf"

    print("   Extracting first 10 pages...")
    pages = PDFParserService.extract_text_from_pdf(core_pdf)[:10]
    sample_text = "\n\n".join(page.text for page in pages)

    print("   Chunking sample text...")
    chunks = TextChunker.chunk_by_tokens(sample_text, max_tokens=800, overlap_tokens=100)
    print(f"   ✅ Created {len(chunks)} sample chunks")

    # Test embedding a few chunks
    num_test = min(5, len(chunks))
    print(f"\n🧪 Testing embedding generation on {num_test} chunks...")
    print("-" * 80)

    total_tokens = 0

    for i, chunk in enumerate(chunks[:num_test], 1):
        print(f"\nChunk {i}/{num_test}:")
        print(f"  Text preview: {chunk.text[:100]}...")
        print(f"  Length: {len(chunk.text)} chars (~{len(chunk.text) // 4} tokens)")

        # Generate embedding
        print(f"  Generating embedding...", end="", flush=True)
        result = await embedding_service.embed_text(chunk.text)
        print(f" ✅")

        total_tokens += result.tokens_used

        print(f"  Embedding dimension: {len(result.embedding)}")
        print(f"  Tokens used: {result.tokens_used}")
        print(f"  First 5 values: {result.embedding[:5]}")

    # Calculate costs
    print("\n" + "=" * 80)
    print("EMBEDDING TEST RESULTS")
    print("=" * 80)
    print(f"✅ Successfully embedded {num_test} chunks")
    print(f"Total tokens used: {total_tokens:,}")

    # Cost for test
    test_cost = (total_tokens / 1_000_000) * 0.02  # $0.02 per 1M tokens
    print(f"Test cost: ${test_cost:.4f}")

    # Estimate full cost
    full_chunks = 2314  # From Slice 2 results
    avg_tokens_per_chunk = total_tokens // num_test
    estimated_full_tokens = full_chunks * avg_tokens_per_chunk
    estimated_full_cost = (estimated_full_tokens / 1_000_000) * 0.02

    print(f"\n📊 Estimated Full Ingestion:")
    print(f"   Total chunks: {full_chunks:,}")
    print(f"   Avg tokens/chunk: ~{avg_tokens_per_chunk}")
    print(f"   Total tokens: ~{estimated_full_tokens:,}")
    print(f"   Estimated cost: ${estimated_full_cost:.2f}")

    print(f"\n✅ Slice 3 Complete! Embeddings are working.")
    print(f"\n💡 Next: Ingest all chunks to MongoDB with embeddings")


if __name__ == "__main__":
    asyncio.run(main())
