"""Clean core_rulebook.txt: remove sidebar nav, page headers, and fix broken lines."""

import re
from pathlib import Path

RULEBOOKS_DIR = Path(__file__).parent.parent / "rulebooks"


def main():
    txt_path = RULEBOOKS_DIR / "core_rulebook.txt"
    if not txt_path.exists():
        print(f"File not found: {txt_path}")
        return

    text = txt_path.read_text(encoding="utf-8")
    original_len = len(text)

    # 1. Remove recurring sidebar nav blocks.
    #    Pattern: [line with single number]\n[any lines]\nAppendix
    sidebar_count = len(
        re.findall(
            r"^\d+\n(?:.*\n)*?Appendix",
            text,
            flags=re.MULTILINE,
        )
    )
    text = re.sub(
        r"^\d+\n(?:.*\n)*?Appendix",
        "",
        text,
        flags=re.MULTILINE,
    )
    print(f"  Removed {sidebar_count} sidebar blocks")

    # # 2. Remove page headers ("Core Rulebook", newline, number, two newlines)
    # header_count = len(re.findall(r"^Core Rulebook\n\d+\n\n", text, flags=re.MULTILINE))
    # text = re.sub(r"^Core Rulebook\n\d+\n\n", "", text, flags=re.MULTILINE)
    # print(f"  Removed {header_count} page headers")

    # # 3. Fix broken lines: replace " \n" (space before newline) with just a space
    # broken_count = len(re.findall(r" \n", text))
    # text = re.sub(r" \n", " ", text)
    # print(f"  Rejoined {broken_count} broken lines")

    # # 4. Mark section titles with # prefix.
    # #    A section title is a text line (has letters, not purely digits) that does NOT
    # #    end with . ! or ? — but only when the previous non-blank line ends a sentence
    # #    (to avoid marking paragraph continuation lines).
    # lines = text.split("\n")
    # title_count = 0
    #
    # for i, line in enumerate(lines):
    #     stripped = line.strip()
    #
    #     if (
    #         stripped
    #         and re.search(r"[A-Za-z]", stripped)
    #         and not re.match(r"^\d+$", stripped)
    #         and not stripped.endswith((".", "!", "?"))
    #     ):
    #         # Find previous non-blank line
    #         prev_stripped = ""
    #         for j in range(i - 1, -1, -1):
    #             if lines[j].strip():
    #                 prev_stripped = lines[j].strip()
    #                 break
    #
    #         if not prev_stripped or prev_stripped[-1] in ".!?":
    #             lines[i] = f"\n# {stripped}"
    #             title_count += 1
    #
    # text = "\n".join(lines)
    # print(f"  Marked {title_count} section titles")

    txt_path.write_text(text, encoding="utf-8")
    print(f"\nCleaned core_rulebook.txt: {original_len:,} -> {len(text):,} chars")


if __name__ == "__main__":
    main()
