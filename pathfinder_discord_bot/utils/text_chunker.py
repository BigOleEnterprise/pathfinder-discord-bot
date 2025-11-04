"""Text chunking utility for embedding - reusable for rulebooks and lore."""
import re
from typing import NamedTuple


class TextChunk(NamedTuple):
    """A chunk of text with metadata."""

    text: str
    start_index: int
    end_index: int


class TextChunker:
    """
    Splits text into chunks suitable for embeddings.

    Reusable for:
    - Rulebook pages
    - Campaign lore entries
    - Any long text that needs vectorization
    """

    @staticmethod
    def chunk_by_tokens(
        text: str,
        max_tokens: int = 800,
        overlap_tokens: int = 100,
    ) -> list[TextChunk]:
        """Chunk text by approximate token count with overlap at sentence boundaries."""
        if not text or not text.strip():
            return []

        # Rough token estimation: 1 token ≈ 4 characters
        max_chars = max_tokens * 4
        overlap_chars = overlap_tokens * 4

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            # Find end of chunk
            end = min(start + max_chars, text_len)

            # Simple boundary check: look for newline or space near end
            if end < text_len and end - start > 100:
                # Look back max 100 chars for a natural break
                search_end = end
                search_start = max(start, end - 100)

                # Find last newline or period + space
                last_newline = text.rfind('\n', search_start, search_end)
                last_period = text.rfind('. ', search_start, search_end)

                # Use whichever is later
                break_point = max(last_newline, last_period)
                if break_point > search_start:
                    end = break_point + 1

            chunk_text = text[start:end].strip()

            if chunk_text:
                chunks.append(
                    TextChunk(
                        text=chunk_text,
                        start_index=start,
                        end_index=end,
                    )
                )

            # Move to next chunk with overlap
            start = max(end - overlap_chars, start + 1)

        return chunks

    @staticmethod
    def chunk_by_paragraphs(
        text: str,
        max_tokens: int = 800,
    ) -> list[TextChunk]:
        """Chunk text by paragraphs, combining small ones up to max_tokens."""
        max_chars = max_tokens * 4

        # Split by double newlines (paragraphs)
        paragraphs = re.split(r'\n\s*\n', text)

        chunks = []
        current_chunk = []
        current_length = 0
        start_index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_length = len(para)

            # If adding this paragraph exceeds max, save current chunk
            if current_length + para_length > max_chars and current_chunk:
                chunk_text = "\n\n".join(current_chunk)
                chunks.append(
                    TextChunk(
                        text=chunk_text,
                        start_index=start_index,
                        end_index=start_index + len(chunk_text),
                    )
                )

                # Start new chunk
                current_chunk = [para]
                current_length = para_length
                start_index = start_index + len(chunk_text)
            else:
                current_chunk.append(para)
                current_length += para_length

        # Add remaining chunk
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(
                TextChunk(
                    text=chunk_text,
                    start_index=start_index,
                    end_index=start_index + len(chunk_text),
                )
            )

        return chunks
