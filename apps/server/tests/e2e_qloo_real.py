"""End-to-end tests with real Qloo API key — judges can run these."""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

QLOO_KEY = os.getenv("QLOO_API_KEY", "")


async def main():
    if not QLOO_KEY:
        print("QLOO_API_KEY is not set — run with QLOO_API_KEY=... python e2e_qloo_real.py")
        return

    from app.services.qloo.client import QlooClient, QlooConfig
    from app.services.qloo.tastecare import recommend_meals, MEDICATION_DISCLAIMER

    config = QlooConfig(
        api_key=QLOO_KEY,
        base_url="https://hackathon.api.qloo.com",
        timeout_seconds=30,
        max_retries=2,
    )
    client = QlooClient(config=config)
    results = []

    # 1. Qloo search
    try:
        search = await client.search("Jazz", entity_types=["urn:entity:artist"], take=3)
        ok = "error" not in search
        results.append(("1. Qloo search Jazz", ok, str(list(search.keys())[:5])))
    except Exception as e:
        results.append(("1. Qloo search Jazz", False, str(e)[:120]))

    # 2. Qloo insights (Italian restaurants)
    try:
        insights = await client.insights(
            filter_type="urn:entity:place",
            signal_entities=[],
            signal_tags=["urn:tag:cuisine:qloo:italian"],
            filter_tags=["urn:tag:category:place:restaurant"],
            filters={"filter.popularity.min": 0.5},
            take=3,
        )
        ok = "results" in insights
        results.append(("2. Qloo insights Italian restaurants", ok, str(list(insights.keys())[:5])))
    except Exception as e:
        results.append(("2. Qloo insights Italian restaurants", False, str(e)[:120]))

    # 3. recommend_meals with health constraints
    try:
        rec = await recommend_meals(
            client,
            cultural_likes=["Italian"],
            location="New York",
            constraints={"low_sodium": True, "low_sugar": True, "medications": ["warfarin"]},
            take=5,
        )
        n = len(rec.get("recommendations", []))
        ac = rec.get("active_constraints", [])
        ok = rec.get("source") == "qloo" and "medications" in ac and rec.get("disclaimer") == MEDICATION_DISCLAIMER
        results.append(("3. recommend_meals w/ constraints", ok, f"recs={n}, constraints={ac}"))
    except Exception as e:
        results.append(("3. recommend_meals w/ constraints", False, str(e)[:150]))

    # 4. recommend_meals soft_chewable + statins
    try:
        rec2 = await recommend_meals(
            client,
            cultural_likes=["Chinese"],
            constraints={"soft_chewable": True, "medications": ["statins"]},
            take=5,
        )
        ac2 = rec2.get("active_constraints", [])
        ok2 = "medications" in ac2
        results.append(("4. recommend_meals soft+statins", ok2, f"recs={len(rec2.get('recommendations',[]))}, constraints={ac2}"))
    except Exception as e:
        results.append(("4. recommend_meals soft+statins", False, str(e)[:150]))

    # 5. Cross-domain discovery
    try:
        from app.services.qloo.taste import search_cultural_entities, get_cross_domain_discovery
        hits = await search_cultural_entities(client, "Frank Sinatra", domain="music", limit=1)
        if hits:
            eid = hits[0].get("entity_id", "")
            cross = await get_cross_domain_discovery(client, [eid], domains=["dining", "film"], per_domain_limit=3)
            dn = len(cross.get("dining", []))
            fn = len(cross.get("film", []))
            results.append(("5. Cross-domain Sinatra", dn > 0 or fn > 0, f"dining={dn}, film={fn}"))
        else:
            results.append(("5. Cross-domain Sinatra", False, "No entity found"))
    except Exception as e:
        results.append(("5. Cross-domain Sinatra", False, str(e)[:150]))

    # 6. Cultural fit scoring
    try:
        from app.services.qloo.entities import score_cultural_fit
        fit = await score_cultural_fit(client, ["Jazz"], ["Blues"], domain="music")
        results.append(("6. Cultural fit Jazz vs Blues", "scores" in fit, str(list(fit.keys()))))
    except Exception as e:
        results.append(("6. Cultural fit Jazz vs Blues", False, str(e)[:150]))

    # 7. LLM context building
    try:
        from app.services.qloo.taste import build_cultural_context_for_llm
        ctx = await build_cultural_context_for_llm(client, ["Jazz", "Italian food"], target_domain="dining", limit=5)
        ok7 = len(ctx) > 0 and "Qloo" in ctx
        results.append(("7. LLM context from Qloo", ok7, f"len={len(ctx)}"))
    except Exception as e:
        results.append(("7. LLM context from Qloo", False, str(e)[:150]))

    # 8. Bridge graph (live mode — needs real entity IDs)
    try:
        from app.services.qloo.taste import search_cultural_entities, get_cross_domain_bridge_graph
        sinatra_hits = await search_cultural_entities(client, "Frank Sinatra", domain="music", limit=1)
        sinatra_id = sinatra_hits[0]["entity_id"] if sinatra_hits else ""
        graph = await get_cross_domain_bridge_graph(client, [sinatra_id] if sinatra_id else [], center_label="Frank Sinatra", per_domain_limit=3)
        is_live = graph.get("data_source") == "live"
        nn = len(graph.get("nodes", []))
        results.append(("8. Bridge graph live", is_live and nn > 0, f"source={graph.get('data_source')}, nodes={nn}"))
    except Exception as e:
        results.append(("8. Bridge graph live", False, str(e)[:150]))

    # 9. Bridge graph (preview mode — disabled client)
    try:
        from app.services.qloo.taste import get_cross_domain_bridge_graph
        disabled_config = QlooConfig(api_key="", base_url="https://hackathon.api.qloo.com", timeout_seconds=10, max_retries=1)
        disabled_client = QlooClient(config=disabled_config)
        graph2 = await get_cross_domain_bridge_graph(disabled_client, [], center_label="Frank Sinatra", per_domain_limit=3)
        is_preview = graph2.get("data_source") == "preview"
        nn2 = len(graph2.get("nodes", []))
        results.append(("9. Bridge graph preview", is_preview and nn2 > 0, f"source={graph2.get('data_source')}, nodes={nn2}"))
    except Exception as e:
        results.append(("9. Bridge graph preview", False, str(e)[:150]))

    # 10. Taste similarity
    try:
        from app.services.qloo.taste import get_taste_similarity_score
        sim = await get_taste_similarity_score(client, ["entity_id_dummy"], target_type="urn:entity:artist", limit=3)
        has_sim = "similar" in sim
        results.append(("10. Taste similarity", has_sim, f"keys={list(sim.keys())}"))
    except Exception as e:
        results.append(("10. Taste similarity", False, str(e)[:150]))

    await client.close()

    print("\n" + "=" * 60)
    print("  Qloo E2E Test Results (Real API Key)")
    print("=" * 60)
    passed = 0
    for name, ok, detail in results:
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        print(f"  [{status}] {name}")
        print(f"         {detail}")
    print(f"\n  Total: {passed}/{len(results)} passed")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())