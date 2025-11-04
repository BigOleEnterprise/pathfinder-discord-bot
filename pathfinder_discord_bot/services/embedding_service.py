"""Generic embedding service using OpenAI - reusable for rulebooks and lore."""
import logging
from typing import NamedTuple

import numpy as np
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class EmbeddingResult(NamedTuple):
    """Result of embedding text."""

    embedding: list[float]
    tokens_used: int
    model: str


class EmbeddingService:
    """
    Handles text embeddings using OpenAI.

    Reusable for:
    - Rulebook chunks
    - Campaign lore
    - Any text that needs vector search
    """

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        """Initialize embedding service with OpenAI API key and model."""
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.dimension = 1536  # text-embedding-3-small dimension

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def embed_text(self, text: str) -> EmbeddingResult:
        """Generate embedding vector for a single piece of text."""
        try:
            logger.debug(f"Embedding text ({len(text)} chars)...")

            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
            )

            embedding = response.data[0].embedding
            tokens_used = response.usage.total_tokens

            logger.debug(f"Generated embedding ({tokens_used} tokens)")

            return EmbeddingResult(
                embedding=embedding,
                tokens_used=tokens_used,
                model=response.model,
            )

        except Exception as e:
            logger.exception(f"Error generating embedding: {e}")
            raise

    async def embed_batch(self, texts: list[str], batch_size: int = 100) -> list[EmbeddingResult]:
        """Generate embeddings for multiple texts in batches of up to batch_size."""
        results = []
        total_batches = (len(texts) + batch_size - 1) // batch_size

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_num = i // batch_size + 1

            logger.info(f"Embedding batch {batch_num}/{total_batches} ({len(batch)} texts)...")

            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=batch,
                )

                for j, data in enumerate(response.data):
                    results.append(
                        EmbeddingResult(
                            embedding=data.embedding,
                            tokens_used=response.usage.total_tokens // len(batch),  # Approximate
                            model=response.model,
                        )
                    )

                logger.info(
                    f"Batch {batch_num}/{total_batches} complete "
                    f"({response.usage.total_tokens} tokens)"
                )

            except Exception as e:
                logger.exception(f"Error embedding batch {batch_num}: {e}")
                raise

        return results

    @staticmethod
    def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors (returns score from -1 to 1)."""
        a = np.array(vec1)
        b = np.array(vec2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
