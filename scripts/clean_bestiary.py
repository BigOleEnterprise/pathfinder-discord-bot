"""Remove repeated PDF artifact blocks from bestiary.txt.

Matches blocks starting with a line that is just 'p' and ending with a 7-digit
number starting with '44', removing everything in between (inclusive).
"""

import re
from pathlib import Path

RULEBOOKS_DIR = Path(__file__).parent.parent / "rulebooks"


def main():
    txt_path = RULEBOOKS_DIR / "bestiary.txt"
    if not txt_path.exists():
        print(f"File not found: {txt_path}")
        return

    text = txt_path.read_text(encoding="utf-8")
    original_len = len(text)

    # Match: line with just "p", any lines in between, then a line with a 7-digit number starting with 44
    cleaned = re.sub(r"^p\n(?:.*\n)*?44\d{5}\n", "", text, flags=re.MULTILINE)

    removed_chars = original_len - len(cleaned)
    txt_path.write_text(cleaned, encoding="utf-8")
    print(f"Cleaned bestiary.txt: removed {removed_chars:,} chars ({original_len:,} -> {len(cleaned):,})")


if __name__ == "__main__":
    main()
