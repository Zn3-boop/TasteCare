"""Qloo integration smoke test.

Runs the 3 minimal calls that prove the hackathon integration works end-to-end:

  1. /search            -> resolve "Totoro" to a Qloo entity id
  2. /v2/insights       -> movie recommendations anchored on that entity id
  3. /v2/insights       -> place (restaurant) recommendations anchored on that id + location

Plus a new live-feedback overlay check:
  4. /v2/insights with 👍/👎 preference overlay (apply_taste_preferences) applied.

Usage:
    $env:QLOO_API_KEY = "hackathon-key"
    python -m app.scripts.qloo_smoke_test            # (run from apps/server)
    # or from repo root:
    python apps/server/scripts/qloo_smoke_test.py
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

# main.py loads apps/server/.env at startup; standalone scripts must load it
# BEFORE importing anything that builds QlooConfig.from_env().
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(Path(_SERVER_DIR) / ".env")
except Exception:  # pragma: no cover - dotenv optional for key-via-env runs
    pass

from app.services.qloo.client import QlooClient, QlooConfig  # noqa: E402
from app.services.qloo.feedback import record_feedback  # noqa: E402
from app.services.qloo.taste import (  # noqa: E402
    apply_taste_preferences,
    search_cultural_entities,
    get_taste_based_recommendations,
)


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

    # --- 1) Search: human name -> entity id -------------------------------
    print("\n[1] /search  ->  resolve 'Totoro'")
    hits = await search_cultural_entities(client, "Totoro", domain="film", limit=5)
    if not hits:
        print("   no results. Check key/URL/domain.")
        await client.close()
        return
    for h in hits[:5]:
        print(f"   {h['name']!r:40} id={h['entity_id']}  subtype={h['type']}")
    anchor = hits[0]["entity_id"]
    anchor_name = hits[0]["name"]

    # --- 2) Movie recommendations anchored on the id ---------------------
    print(f"\n[2] /v2/insights  -> movies similar to '{anchor_name}' ({anchor})")
    rec = await get_taste_based_recommendations(client, [anchor], target_domain="film", limit=8)
    if rec.get("error"):
        print(f"   ERROR: {rec['error']}")
    for r in rec.get("recommendations", [])[:8]:
        print(f"   {r['name']!r:44} subtype={r['type']}  pop={r.get('popularity')}")

    # --- 3) Place (restaurant) recommendations + location ----------------
    print(f"\n[3] /v2/insights  -> places similar to '{anchor_name}' in 'New York'")
    payload = await client.insights(
        filter_type="urn:entity:place",
        signal_entities=[anchor],
        location_query="New York",
        take=8,
    )
    if "error" in payload:
        print(f"   ERROR: {payload['error']}")
    results = payload.get("results", {})
    entities = results.get("entities", []) if isinstance(results, dict) else []
    for e in entities[:8]:
        print(f"   {e.get('name','')!r:44} subtype={e.get('subtype','')}  pop={e.get('popularity')}")

    # --- 4) Live feedback preference overlay -----------------------------
    print("\n[4] live 👍/👎 overlay  -> apply_taste_preferences")
    record_feedback("smoke-like", "up", [hits[0]["name"]])
    liked_names = {n for n, w in __import__("app.services.qloo.feedback", fromlist=["get_liked_taste_names"]).get_liked_taste_names().items()}
    print(f"   liked pool (names): {sorted(liked_names)}")
    overlay = await apply_taste_preferences(client, signal_entities=[anchor], take=5, filter_type="urn:entity:movie")
    if "error" in overlay:
        print(f"   ERROR: {overlay['error']}")
    ov_results = overlay.get("results", {})
    pref = ov_results.get("preferences_applied", {})
    print(f"   preferences_applied = {pref}")
    for e in (ov_results.get("entities") or [])[:5]:
        print(f"   {e.get('name','')!r:44} entity_id={e.get('entity_id','')}")

    await client.close()
    print("\nSmoke test complete. Integration is wired to the hackathon API.")


if __name__ == "__main__":
    asyncio.run(main())

