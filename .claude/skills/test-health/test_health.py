"""Health check: ping MongoDB, OpenAI, and Claude."""
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
project_root = Path(__file__).resolve().parents[3]
load_dotenv(project_root / ".env")
sys.path.insert(0, str(project_root))

from pathfinder_discord_bot.config import settings


def test_mongodb() -> tuple[bool, int]:
    """Ping MongoDB via sync client."""
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError

    try:
        start = time.time()
        client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        latency = int((time.time() - start) * 1000)
        client.close()
        return True, latency
    except (PyMongoError, Exception) as e:
        print(f"    Error: {e}")
        return False, 0


def test_openai() -> tuple[bool, int]:
    """Generate a tiny embedding to verify OpenAI key and model."""
    from openai import OpenAI

    try:
        start = time.time()
        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.embeddings.create(model=settings.openai_embedding_model, input="ping")
        latency = int((time.time() - start) * 1000)
        dim = len(resp.data[0].embedding)
        print(f"    Model: {settings.openai_embedding_model}, Dimension: {dim}")
        return True, latency
    except Exception as e:
        print(f"    Error: {e}")
        return False, 0


def test_claude() -> tuple[bool, int]:
    """Send a minimal message to verify Anthropic key and model."""
    from anthropic import Anthropic

    try:
        start = time.time()
        client = Anthropic(api_key=settings.anthropic_api_key)
        msg = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1,
            messages=[{"role": "user", "content": "ping"}],
        )
        latency = int((time.time() - start) * 1000)
        print(f"    Model: {msg.model}")
        return True, latency
    except Exception as e:
        print(f"    Error: {e}")
        return False, 0


def main():
    # Allow testing a single service
    target = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    services = {
        "mongodb": ("MongoDB", test_mongodb),
        "openai": ("OpenAI Embeddings", test_openai),
        "claude": ("Claude API", test_claude),
    }

    if target != "all" and target not in services:
        print(f"Unknown service: {target}")
        print(f"Options: {', '.join(services.keys())}, all")
        sys.exit(1)

    targets = services if target == "all" else {target: services[target]}

    print("=" * 50)
    print("INTEGRATION HEALTH CHECK")
    print("=" * 50)

    results = {}
    for key, (name, fn) in targets.items():
        print(f"\n  {name}...", flush=True)
        ok, ms = fn()
        results[name] = (ok, ms)
        status = f"PASS ({ms}ms)" if ok else "FAIL"
        symbol = "+" if ok else "x"
        print(f"  [{symbol}] {name}: {status}")

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    all_ok = True
    for name, (ok, ms) in results.items():
        symbol = "+" if ok else "x"
        status = f"PASS ({ms}ms)" if ok else "FAIL"
        print(f"  [{symbol}] {name:25s} {status}")
        if not ok:
            all_ok = False

    print("=" * 50)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
