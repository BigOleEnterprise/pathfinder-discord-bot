"""Extract text from rulebook PDFs and save as .txt files."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pathfinder_discord_bot.services.pdf_parser import PDFParserService

RULEBOOKS_DIR = Path(__file__).parent.parent / "rulebooks"


def main():
    """Extract text from all PDFs in rulebooks/ and save as .txt alongside them."""
    pdfs = sorted(RULEBOOKS_DIR.glob("*.pdf"))

    if not pdfs:
        print(f"No PDFs found in {RULEBOOKS_DIR}")
        return

    print(f"Found {len(pdfs)} PDF(s) in {RULEBOOKS_DIR}\n")

    for pdf_path in pdfs:
        txt_path = pdf_path.with_suffix(".txt")

        if txt_path.exists():
            print(f"  SKIP  {pdf_path.name} -> {txt_path.name} (already exists)")
            continue

        print(f"  EXTRACT  {pdf_path.name} ...", end="", flush=True)
        pages = PDFParserService.extract_text_from_pdf(pdf_path)
        full_text = "\n\n".join(page.text for page in pages)

        txt_path.write_text(full_text, encoding="utf-8")
        print(f" {len(pages)} pages, {len(full_text):,} chars -> {txt_path.name}")

    print("\nDone. Text files saved in rulebooks/")


if __name__ == "__main__":
    main()
