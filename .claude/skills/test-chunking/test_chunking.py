"""Test PDF text chunking on rulebooks. No API calls."""
import sys
from collections import Counter
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

from pathfinder_discord_bot.services.pdf_parser import PDFParserService
from pathfinder_discord_bot.utils.text_chunker import TextChunker


def main():
    rulebooks_dir = project_root / "rulebooks"
    pdfs = list(rulebooks_dir.glob("*.pdf"))

    if not pdfs:
        print(f"No PDFs found in {rulebooks_dir}")
        sys.exit(1)

    print("=" * 70)
    print("CHUNKING TEST")
    print("=" * 70)

    all_chunks = []

    for idx, pdf_path in enumerate(pdfs, 1):
        print(f"\n  [{idx}/{len(pdfs)}] {pdf_path.name}")
        pages = PDFParserService.extract_text_from_pdf(pdf_path)
        total_chars = sum(p.char_count for p in pages)
        print(f"    Extracted {len(pages)} pages ({total_chars:,} chars)")

        full_text = "\n\n".join(page.text for page in pages)
        chunks = TextChunker.chunk_by_tokens(full_text, max_tokens=800, overlap_tokens=100)
        print(f"    Chunked into {len(chunks)} chunks")

        for chunk in chunks:
            all_chunks.append({"source": pdf_path.stem, "text": chunk.text})

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    total_chars = sum(len(c["text"]) for c in all_chunks)
    print(f"  Total chunks:     {len(all_chunks)}")
    print(f"  Avg chunk size:   {total_chars // len(all_chunks):,} chars")
    print(f"  Est. total tokens: ~{total_chars // 4:,}")

    source_counts = Counter(c["source"] for c in all_chunks)
    print(f"\n  By source:")
    for source, count in source_counts.items():
        print(f"    {source}: {count} chunks")

    print(f"\n  Sample chunks:")
    for i, chunk in enumerate(all_chunks[:3], 1):
        preview = chunk["text"][:200].replace("\n", " ")
        print(f"    {i}. [{chunk['source']}] {preview}...")

    embedding_cost = (total_chars // 4 / 1_000_000) * 0.02
    print(f"\n  Est. embedding cost: ${embedding_cost:.2f}")
    print("=" * 70)


if __name__ == "__main__":
    main()
