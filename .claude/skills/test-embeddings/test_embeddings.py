"""Test OpenAI embedding generation on provided text or a sample."""
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

project_root = Path(__file__).resolve().parents[3]
load_dotenv(project_root / ".env")
sys.path.insert(0, str(project_root))

from pathfinder_discord_bot.config import settings
from pathfinder_discord_bot.services.embedding_service import EmbeddingService

DEFAULT_TEXT = (
    "A creature is flat-footed when flanked by two allies on opposite sides. "
    "Flanking requires the two allies to be on directly opposite sides of the target."
)


async def main():
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else DEFAULT_TEXT

    print("=" * 70)
    print("EMBEDDING TEST")
    print("=" * 70)
    print(f"\nModel: {settings.openai_embedding_model}")
    print(f"Input: \"{text[:100]}{'...' if len(text) > 100 else ''}\"")
    print(f"Input length: {len(text)} chars (~{len(text) // 4} tokens)")

    embedding_service = EmbeddingService(
        api_key=settings.openai_api_key,
        model=settings.openai_embedding_model,
    )

    print("\nGenerating embedding...", end="", flush=True)
    result = await embedding_service.embed_text(text)
    print(" OK")

    print(f"\n  Dimension:    {len(result.embedding)}")
    print(f"  Tokens used:  {result.tokens_used}")
    print(f"  Model:        {result.model}")
    print(f"  First 5 vals: {result.embedding[:5]}")

    cost = (result.tokens_used / 1_000_000) * 0.02
    print(f"  Est. cost:    ${cost:.6f}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
