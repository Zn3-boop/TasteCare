# TasteCare — Culturally Intelligent Dining for Seniors (Devpost Submission)

> Final submission draft for the Qloo × LLM Hackathon. Copy sections into the
> Devpost form fields (add gallery images + demo video links at the end).

---

## Tagline

The thing that only works because it knows what people love.

## Elevator Pitch (One-liner)

TasteCare is a Qloo-powered agent that recommends meals an older adult would *actually love* — grounded in their real cultural taste, then filtered for their health reality (easy-to-chew, low-sodium, medication-aware).

## Summary

Generic LLMs fixated on "what's healthy" tell an 82-year-old like Maria to eat "grilled chicken breast, steamed vegetables, oatmeal." Nutritionally fine. Culturally tone-deaf — she wouldn't recognize any of it as *her* food, so she ignores it.

TasteCare fixes that. The agent resolves Maria's cultural anchors (Sinatra, jazz-era supper clubs, Italian cuisine) through Qloo's 250M+ entity taste graph, then filters every candidate against her medical constraints. The result: dinners she'd recognize as hers — and that actually fit her health needs. Cultural intelligence is the difference between "technically functional" and "actually good."

## Repository Structure

This repo is organized as **Agent Skeleton + TasteCare Subsystem**. The `apps/server/app/services/qloo/` directory is the TasteCare core — the culturally intelligent dining recommendation engine. The surrounding agent skeleton (graph, LLM client, RAG pipeline) provides the orchestration infrastructure that TasteCare plugs into. Legacy desktop-agent code has been cleaned out; only TasteCare-relevant components remain. A `docs/` folder holds the **[architecture diagrams](https://github.com/Zn3-boop/TasteCare/blob/main/docs/ARCHITECTURE.md)**, the **[LangGraph agent-workflow spec](https://github.com/Zn3-boop/TasteCare/blob/main/docs/QLOO_AGENT_GRAPH.md)**, and the **[ablation methodology](https://github.com/Zn3-boop/TasteCare/blob/main/docs/ABLATION_EXPERIMENT.md)** used to evidence Qloo's contribution.

## The Problem

Seniors frequently ignore dietary advice that has no cultural resonance. A meal that isn't "theirs" gets rejected, no matter how healthy. Existing LLM assistants can make educated guesses about taste; they can't *know* a person's cultural preferences the way a real taste graph can — and they certainly can't bridge across domains (film → dining → fashion).

## The Solution — Why Qloo

- **Grounding, not guessing:** The agent calls a `qloo:taste-context` tool to fetch real taste-graph entities (cuisine, flavor, cultural anchors) and injects them into the LLM context.
- **Culture first, health second:** Qloo grounds the recommendation; our health-constraint layer filters it. Both matter; neither is skipped.
- **Cross-domain discovery:** "If you like Nolan films and Chicago blues, here's where to eat in New York and what to wear" — a connection only a taste graph can make.
- **Feedback loop:** 👍 / 👎 on any recommendation updates the taste profile (live → Qloo; preview → in-memory demo pool), closing the loop toward a personalized model.

## The Architecture

```
Web Frontend (React + Vite, hosted demo)
        │  POST /chat/agent, /chat/feedback, /qloo/*
        ▼
FastAPI TasteCare Agent Workflow  ──►  Qloo Taste Graph (250M+ entities)
        │                              LLM (OpenAI / DeepSeek)
        └──► Health Constraint Filter (soft-chewable, low-sodium, medication-aware)
```

- `qloo:search`, `qloo:recommend`, `qloo:cross-domain`, `qloo:cultural-fit`, `qloo:taste-context` are first-class tools in the agent's decision loop, exposed as REST endpoints under `/qloo/*`.
- TasteCare endpoints return food grounded in taste *and* safe per the user's constraints, with a clear medical disclaimer.
- `/chat/agent` wraps every reply with the Qloo cultural system prompt (`prompts.py`), so the LLM is contractually grounded — it must use taste data, not generic guesses.

## Preview / Live Dual Mode

The demo runs end-to-end **without a Qloo API key** using a clearly-labelled Maria preview pool; the moment `QLOO_API_KEY` is set, the same UI and API switch to live Qloo data. `data_source` (preview = orange / live = green) makes the provenance explicit. The Agent tab shows a **Qloo Grounding Evidence panel** so judges can see the Qloo call rather than trusting it blindly.

## Testing — "Mock is the foundation, live is the proof"

- **395 automated tests** (`python -m pytest`): 382 offline (mocks/unit/contract, runs in CI with no secrets) + 13 live `real_api` smoke tests (run automatically when `QLOO_API_KEY` is present).
- Coverage spans: Qloo client serialization, taste-context executor, dining discriminator, health/medication screening, ablation comparison, HTTP contract, prompt-template rendering, and cache behavior.
- **CI dual track** (`.github/workflows/ci.yml`): offline backend suite (no key needed) + optional live job (only when `QLOO_API_KEY` secret is set) + frontend web/desktop builds.
- We probed the real Qloo hackathon API during development and caught a genuine API quirk (`signal == results` returns an empty body) — three service functions were fixed and verified against live endpoints, then locked in with the `real_api` suite.

## Live Demo Script (Judge Prompt)

> "Recommend dinner for Maria, who has hypertension, poor dentition, and prefers light Jiangnan home cooking."

Expected: the agent calls `qloo:taste-context`, shows the grounding evidence panel, recommends culturally recognizable, health-safe meals (low-sodium Jiangnan braised dishes, soft steamed vegetables) — and accepts your 👍/👎 to refine the profile.

Cross-domain probe: *"I love the films of Christopher Nolan and classic Chicago blues — where should I eat in New York, and what should I wear?"*

## Built With

- Qloo API (Cultural taste graph / LLM hackathon endpoint)
- **LangGraph StateGraph** — core recommendation workflow orchestration: conditional routing, automatic retry & error recovery loops, and the `qloo_cultural_recommend_node` running *inside* the graph (satisfies the "built using an agent framework" requirement with real graph execution, not a wrapper)
- FastAPI (Python) — agent workflow, tools, health filter
- React + Vite + TypeScript — hosted web demo
- numpy (community peer matching demo: cosine similarity with local all-MiniLM-L6-v2; FAISS scaling plan pre-written offline for >1000 peers)
- pytest — automated tests; CI dual track: offline suite + optional live job when `QLOO_API_KEY` secret exists

## Agent Framework (LangGraph)

Our core recommendation workflow is orchestrated with **LangGraph StateGraph**, with conditional routing, automatic retry & error recovery loops. The Qloo cultural matching node runs inside the graph to satisfy agent framework requirements — `/chat/agent` live grounding executes `qloo_cultural_recommend_node` (the same node the compiled graph routes through via `taste_context_extract → health_constraint_extract → qloo_cultural_recommend_node`), so the evidence panel is backed by genuine graph execution.

## Scaling Architecture

Peer matching uses lightweight **numpy vector search for demo** (sentence-transformers + all-MiniLM-L6-v2 local model, plain numpy cosine — no FAISS in the hot path). A fully-tested **FAISS IndexFlatIP scaling plan** is pre-written as offline expansion code, ready to be enabled once peer count exceeds 1000.

## Ablation Experiment — the difference is Qloo, measured

We don't just claim Qloo makes us better; we prove it with strict
**single-variable ablation** at two levels:

### Level 1 — unit test (`test_chat_ablation_consistency.py`)

The with-Qloo branch and the `disable_qloo=true` baseline fire with identical
session/profile state. Only the `[Qloo Cultural Context]` block can differ:

| Variable | With Qloo | Without Qloo |
|---|---|---|
| System prompt | `CULTURAL_RECOMMENDATION_SYSTEM_PROMPT` | **identical** |
| User taste-profile likes | injected | **identical** |
| `temperature` / `task_type` | 0.2 / `qloo_cultural_recommendation` | **identical** |
| Raw user message | `"Please suggest a low-sodium dinner."` | **identical** |
| **Qloo grounding** | **`[Qloo Cultural Context]` injected** | **absent** — the ONLY difference |

### Level 2 — live demo method (`POST /api/v1/ablation/comparison`)

Same senior-dining prompts → **Variant A** (pure rule-based health screening,
no Qloo, no LLM) vs **Variant B** (the real Qloo TasteCare pipeline), sharing
identical candidates — so the on-screen gap is exactly the cultural grounding.
The web **Ablation tab** renders both side-by-side in one click, with an honest
`● Live Qloo data` vs clearly-labeled preview indicator.

> Run it yourself: `cd apps/server && python -m pytest tests/test_chat_ablation_consistency.py -v`, or click **"▶ Run Ablation Comparison"** in the hosted demo.

Full methodology, the controlled-variable table, and threats to validity are in
[`docs/ABLATION_EXPERIMENT.md`](https://github.com/Zn3-boop/TasteCare/blob/main/docs/ABLATION_EXPERIMENT.md).

## Try It

```bash
# Backend
cd apps/server && pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend
pnpm install && pnpm --dir apps/web dev   # http://localhost:3000
```

Optional: `QLOO_API_KEY=...` for live Qloo data; works in demo/preview mode otherwise.

## What's Next

- Persist feedback and learn a real per-user taste model across sessions.
- Expand health constraints with medication-interaction knowledge and clinician-verified data.
- Voice-first experience for older adults; caregiver dashboard for medication and meal coordination.

## Journey / Notes for Judges

- We prioritized an **honest** prototype: preview data is labeled preview, medical limits are stated clearly, and no real user data is stored.
- We found and fixed a real bug the demo would have hit: the chat endpoint originally called the OpenAI SDK's non-callable namespace object and would have crashed at runtime; it now routes through the shared LLM provider and wraps replies with the Qloo cultural system prompt.
- The core insight we want the judges to take away: **without Qloo, this is just another healthy-meal list; with Qloo, it becomes advice a person will actually follow.**

---

## ⚠️ Medical Disclaimer

TasteCare is a hackathon prototype for demonstration only. It is not medical software, a licensed medical device, dietitian, or clinical recommendation system. Do not use it to diagnose, treat, or make decisions about health, medications, or diet without consulting a qualified physician or registered dietitian. All recommendations are AI-generated and simplified; seniors, caregivers, and clinicians must independently verify every suggestion. Use at your own risk.