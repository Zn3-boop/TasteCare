# TasteCare Documentation

Evidence of genuine engineering effort — every diagram in this folder is
generated from the actual code, no aspirational schematics.

| Document | What it shows |
|---|---|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | End-to-end system architecture: web demo, FastAPI agent workflow, Qloo taste graph, LLM provider, health-screening layers, community matching. |
| [QLOO_AGENT_GRAPH.md](./QLOO_AGENT_GRAPH.md) | The LangGraph `StateGraph` that powers `/api/v1/chat/agent` — intent branching, retry loop, and fallback decision table. |
| [ABLATION_EXPERIMENT.md](./ABLATION_EXPERIMENT.md) | How we prove the difference is Qloo: single-variable ablation at both the unit-test level (`test_chat_ablation_consistency.py`) and the demo level (`/api/v1/ablation/comparison`). |

## How to reproduce the diagrams

The graph topology is not hand-drawn — it is exported from the compiled graph:

```bash
cd apps/server
python -c "from app.services.graph import draw_mermaid; print(draw_mermaid())"
```

The mermaid text is also asserted in `app/services/graph/tests/test_qloo_agent_workflow.py`.