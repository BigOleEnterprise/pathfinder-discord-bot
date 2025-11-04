"""Test script for text chunking - Slice 2."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pathfinder_discord_bot.services.pdf_parser import PDFParserService
from pathfinder_discord_bot.utils.text_chunker import TextChunker


def main():
    """Extract PDFs and chunk the text."""
    print("=" * 80)
    print("SLICE 2: TEXT CHUNKING TEST")
    print("=" * 80)

    rulebooks_dir = Path(__file__).parent.parent / "rulebooks"
    pdfs = list(rulebooks_dir.glob("*.pdf"))

    if not pdfs:
        print(f"\n❌ No PDFs found in {rulebooks_dir}")
        return

    all_chunks = []

    for idx, pdf_path in enumerate(pdfs, 1):
        print(f"\n📚 Processing {idx}/{len(pdfs)}: {pdf_path.name}")
        print("-" * 80)

        # Extract text
        print("  [1/3] Extracting pages...")
        pages = PDFParserService.extract_text_from_pdf(pdf_path)
        print(f"        ✅ Extracted {len(pages)} pages ({sum(p.char_count for p in pages):,} chars)")

        # Combine all pages into full text
        print("  [2/3] Combining all pages...")
        full_text = "\n\n".join(page.text for page in pages)
        print(f"        ✅ Combined into {len(full_text):,} characters")

        # Chunk the full text at once (with optimized algorithm)
        print(f"  [3/3] Chunking full text into ~800 token chunks...")
        pdf_chunks = TextChunker.chunk_by_tokens(
            full_text,
            max_tokens=800,
            overlap_tokens=100,
        )
        print(f"        ✅ Created {len(pdf_chunks)} chunks")

        # Store chunks with source info
        print(f"  [4/4] Adding metadata...", end="", flush=True)
        for chunk in pdf_chunks:
            all_chunks.append({
                "source": pdf_path.stem,
                "text": chunk.text,
                "char_count": len(chunk.text),
            })

    # Summary
    print("\n" + "=" * 80)
    print("CHUNKING SUMMARY")
    print("=" * 80)
    print(f"Total Chunks: {len(all_chunks)}")
    print(f"Average Chunk Size: {sum(c['char_count'] for c in all_chunks) // len(all_chunks):,} chars")
    print(f"Estimated Tokens: ~{sum(c['char_count'] for c in all_chunks) // 4:,} tokens total")

    # Show distribution
    from collections import Counter
    source_counts = Counter(c['source'] for c in all_chunks)
    print(f"\nChunks by Source:")
    for source, count in source_counts.items():
        print(f"  {source}: {count} chunks")

    # Preview sample chunks
    print("\n" + "=" * 80)
    print("SAMPLE CHUNKS (First 3)")
    print("=" * 80)

    for i, chunk in enumerate(all_chunks[:3], 1):
        preview = chunk['text'][:300].replace("\n", " ")
        print(f"\nChunk {i} ({chunk['source']}) - {chunk['char_count']} chars:")
        print(f"  {preview}...")
        print("-" * 80)

    print(f"\n✅ Slice 2 Complete! Text is properly chunked.")
    print(f"\n💡 Next: Generate embeddings for these chunks")

    # Estimate embedding cost
    total_tokens = sum(c['char_count'] for c in all_chunks) // 4
    embedding_cost = (total_tokens / 1_000_000) * 0.02  # $0.02 per 1M tokens
    print(f"\n💰 Estimated embedding cost: ${embedding_cost:.2f}")


if __name__ == "__main__":
    main()
