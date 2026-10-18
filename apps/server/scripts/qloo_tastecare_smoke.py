"""TasteCare Dining — end-to-end smoke test against the real Qloo hackathon API.

Proves the TasteCare scenario shell works with a real key:
  1. Resolve a senior's cultural likes (e.g. an artist + a movie) to entity ids.
  2. Ask Qloo /v2/insights for dining places anchored on those, in a location,
     filtered for a 55-and-older audience.
  3. Annotate each place with senior health constraints (low-sodium / low-sugar
     / soft-chewable) and print a plain-language explanation + disclaimer.

Usage (set your hackathon key — NEVER hardcode it here):
    $env:QLOO_API_KEY = "your-key"
    python -m app.scripts.qloo_tastecare_smoke     # (run from apps/server)
    # or from repo root:
    python apps/server/scripts/qloo_tastecare_smoke.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Make `app` package importable whether run from apps/server or repo root.
_SERVER_DIR = Path(__file__).resolve().parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

from app.services.qloo.client import QlooClient, QlooConfig  # noqa: E402
from app.services.qloo.tastecare import recommend_meals  # noqa: E402


async def main() -> None:
    if not os.getenv("QLOO_API_KEY"):
        print("ERROR: QLOO_API_KEY not set. Grab a hackathon key and set it in env/.env first.")
        return

    client = QlooClient(config=QlooConfig.from_env())
    print(f"base_url = {client.config.base_url}")
    print(f"enabled  = {client.enabled}")
    if not client.enabled:
        print("ERROR: Qloo client not enabled (missing key).")
        return

    # --- Sample senior profile: likes a jazz singer + a classic film ---------
    cultural_likes = ["Frank Sinatra", "Roman Holiday"]
    constraints = {
        "low_sodium": True,
        "low_sugar": True,
        "soft_chewable": True,
        "medications": ["血压药"],
    }

    print("\n[TasteCare] recommending senior-friendly dining places...")
    print(f"  cultural likes : {cultural_likes}")
    print(f"  location       : New York")
    print(f"  constraints    : {constraints}")

    result = await recommend_meals(
        client,
        cultural_likes=cultural_likes,
        location="New York",
        constraints=constraints,
        take=10,
    )

    if result.get("error"):
        print(f"ERROR: {result['error']}")
        print("  Likely causes: wrong key / wrong base URL / /search resolution failed.")
        await client.close()
        return

    recs = result["recommendations"]
    print(f"\nGot {len(recs)} places from Qloo insights.")
    for r in recs[:10]:
        health = r["health"]
        flag = "PASS" if health["passes"] else "flag"
        labels = "、".join(health["labels"]) or "-"
        warns = "；".join(health["warnings"]) or "-"
        print(f"  [{flag}] {r['name']!r:40} pop={r.get('popularity')}")
        print(f"         labels  : {labels}")
        if health["warnings"]:
            print(f"         warnings: {warns}")

    print("\n[Explanation]")
    print(result["explanation"])
    print("\n[Disclaimer]")
    print(result["disclaimer"])

    await client.close()
    print("\nTasteCare smoke test complete.")


if __name__ == "__main__":
    asyncio.run(main())
