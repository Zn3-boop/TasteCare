# Ablation Experiment — Proving the Difference Is Qloo

The challenge asks for work that fails without Qloo. We hold up to that by
making the Qloo-vs-no-Qloo difference **measurable and honest** at two levels.

## Level 1 — Single-variable unit test

`apps/server/tests/test_chat_ablation_consistency.py` proves the with-Qloo
branch differs from the `disable_qloo=true` baseline **only** by the Qloo
entity-context block:

| Variable | With Qloo | Without Qloo | Controlled? |
|---|---|---|---|
| System prompt | `CULTURAL_RECOMMENDATION_SYSTEM_PROMPT` | same | ✅ identical |
| User taste-profile likes | `[User Taste Profile]` injected | same | ✅ identical |
| `temperature` / `task_type` | `0.2` / `qloo_cultural_recommendation` | same | ✅ identical |
| Raw user message | `"Please suggest a low-sodium dinner."` | same | ✅ identical |
| **Qloo grounding** | **`[Qloo Cultural Context]` block present** | **absent** | ✅ the ONLY difference |

The test fires both branches with the same session/profile state and asserts:
1. Both receive the exact same system prompt string.
2. `temperature` and `task_type` are equal across branches (no hidden drift).
3. Both branches see the same `[User Taste Profile]` likes.
4. The `[Qloo Cultural Context]` marker appears **only** in the with-Qloo call.
5. The raw user message survives intact in both.

The corresponding behavior is implemented in `app/api/chat.py`:
`disable_qloo` reuses the same provider call and profile — only the Qloo
parsing/injection is bypassed.

## Level 2 — Interactive demo comparison

`POST /api/v1/ablation/comparison` (`app/services/eval/ablation.py`) runs the
**same senior-dining prompts** through two variants:

- **Variant A (no Qloo):** pure rule-based health screening over a
  deterministic candidate pool. No LLM, no Qloo. `data_source = "rules"`.
- **Variant B (with Qloo):** the real TasteCare pipeline (`recommend_meals`),
  with a labeled preview fallback when no key is set.

Both variants share identical candidates, so the on-screen difference is
exactly the cultural grounding. The web **Ablation tab** renders the paired
result side-by-side in one click, with an honest `● Live Qloo data` vs
`Demo preview data (clearly labelled)` indicator.

Demo prompts are realistic senior-care scenarios:

> "My mother has high blood pressure and poor dentition, and wants light
> Jiangnan home-style dishes. Recommend a few nearby restaurants."
> — constraints: `low_sodium` + `soft_chewable`

## Threats to validity (addressed)

- **Prompt drift** → both arms reuse one system prompt constant.
- **Profile skew** → the taste profile is read once and applied to both arms.
- **LLM temperature variance** → both arms use temperature `0.2`; the Level-1
  test uses a recording provider stub, so assertion-based output is
  deterministic.
- **Fake preview** → preview data is always labeled preview; the web UI never
  presents Qloo branding for non-live output (enforced in `QlooGroundingPanel.tsx`).

## The claim it backs

> Without Qloo this is "another healthy-meal list"; with Qloo it becomes
> advice a person will actually follow.

Run it yourself:

```bash
cd apps/server
python -m pytest tests/test_chat_ablation_consistency.py -v   # unit level
# then click "▶ Run Ablation Comparison" in the web demo's Ablation tab.
```