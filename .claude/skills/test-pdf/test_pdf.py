"""Test PDF text extraction from rulebooks. No API calls."""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

from pathfinder_discord_bot.services.pdf_parser import PDFParserService


def main():
    rulebooks_dir = project_root / "rulebooks"
    pdfs = list(rulebooks_dir.glob("*.pdf"))

    if not pdfs:
        print(f"No PDFs found in {rulebooks_dir}")
        sys.exit(1)

    print("=" * 70)
    print("PDF EXTRACTION TEST")
    print("=" * 70)

    print(f"\nFound {len(pdfs)} PDFs:")
    for pdf in pdfs:
        print(f"  - {pdf.name} ({pdf.stat().st_size / 1_000_000:.1f} MB)")

    for pdf_path in pdfs:
        print(f"\n{'─' * 70}")
        print(f"  {pdf_path.name}")
        print(f"{'─' * 70}")

        metadata = PDFParserService.get_pdf_metadata(pdf_path)
        for key, value in metadata.items():
            if value:
                print(f"    {key}: {value}")

        pages = PDFParserService.extract_text_from_pdf(pdf_path)
        total_chars = sum(p.char_count for p in pages)
        print(f"\n    Pages: {len(pages)}")
        print(f"    Total chars: {total_chars:,}")
        print(f"    Avg chars/page: {total_chars // len(pages):,}")

        print(f"\n    First 3 pages:")
        for page in pages[:3]:
            preview = page.text[:300].replace("\n", " ")
            print(f"      Page {page.page_number} ({page.char_count} chars): {preview}...")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
