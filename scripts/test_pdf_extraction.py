"""Test script for PDF text extraction - Slice 1."""
import sys
from pathlib import Path

# Add parent directory to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from pathfinder_discord_bot.services.pdf_parser import PDFParserService


def main():
    """Extract and preview text from rulebook PDFs."""
    print("=" * 80)
    print("SLICE 1: PDF TEXT EXTRACTION TEST")
    print("=" * 80)

    rulebooks_dir = Path(__file__).parent.parent / "rulebooks"

    # Find PDFs
    pdfs = list(rulebooks_dir.glob("*.pdf"))

    if not pdfs:
        print(f"\n❌ No PDFs found in {rulebooks_dir}")
        print("Make sure PDFs are in the rulebooks/ directory")
        return

    print(f"\n📚 Found {len(pdfs)} PDFs:")
    for pdf in pdfs:
        print(f"  - {pdf.name} ({pdf.stat().st_size / 1_000_000:.1f} MB)")

    # Extract from first PDF
    pdf_path = pdfs[0]
    print(f"\n🔍 Extracting text from: {pdf_path.name}")
    print("-" * 80)

    # Get metadata
    metadata = PDFParserService.get_pdf_metadata(pdf_path)
    print(f"\n📄 PDF Metadata:")
    for key, value in metadata.items():
        if value:
            print(f"  {key.capitalize()}: {value}")

    # Extract pages
    pages = PDFParserService.extract_text_from_pdf(pdf_path)

    print(f"\n✅ Extraction Complete!")
    print(f"  Total Pages: {len(pages)}")
    print(f"  Total Characters: {sum(p.char_count for p in pages):,}")
    print(f"  Average chars/page: {sum(p.char_count for p in pages) // len(pages):,}")

    # Preview first few pages
    print(f"\n📖 Preview of First 3 Pages:")
    print("=" * 80)

    for page in pages[:3]:
        preview = page.text[:500].replace("\n", " ")
        print(f"\nPage {page.page_number} ({page.char_count} chars):")
        print(f"  {preview}...")
        print("-" * 80)

    print(f"\n✅ Slice 1 Complete! PDF extraction is working.")
    print(f"\n💡 Next: Run chunking script to split text into embeddable chunks")


if __name__ == "__main__":
    main()
