# PR 描述 · P3 反馈存储 DI 重构收尾（feature/feedback-store-di）

## 概述

本次 PR 承载 P3 主线（`feedback_store` 模块级单例 → 依赖注入重构）及此前累积的
B 档 Agent 图扩展，全部测试通过（离线 511 + live real_api 14）。

## 主线：P3 反馈存储 DI 重构

- `app/services/qloo/feedback.py`：删除模块级 shim（`_DEFAULT_STORE`、四池 dict、五个模块级函数），
  落地 `FeedbackStore`（四池 + `RLock` + `session_id` + TTL）+ `FeedbackStoreRegistry`
  （session 分片，跨请求进程内持久，TTL 3600s）。
- 四个生产调用点（`chat.py` / `tastecare.py` / `taste.py` / graph node）全部显式注入 / 读 session store：
  - `get_taste_based_recommendations` / `get_cross_domain_discovery` / `apply_taste_preferences` /
    `build_cultural_context_for_llm` 增加 `store: FeedbackStore | None = None`；
  - `qloo_cultural_recommend_node` 从 `AgentState.feedback_store` 取出，三个 taste 调用透传 `store=`；
  - `/chat/agent` 与 `/feedback`、`/liked-anchors` 按 `session_id` 收敛到同一实例。
- 测试触点全部改走 `get_feedback_store()` / 实例方法；conftest autouse fixture 保留但改写为
  `reset_feedback_stores()`（防 suite 顺序依赖 flaky）。
- 唯一保留的宽松点（按计划，后续 pass 收紧）：`apply_taste_preferences` 对未注入调用方
  `store is None` 时回落 registry。
- 细节与决策见 `docs/backlog/p3-feedback-store-di-refactor.md`。

## 本次收尾新增

- `docs/backlog/p3-feedback-store-di-refactor.md` 追加附录九"真实 Qloo API 约束观测"（live 实测记录，无代码变更）。
- `scripts/qloo_smoke_test.py` + `scripts/qloo_tastecare_smoke.py` 在 `PYTHONIOENCODING=utf-8`
  下实测跑通全链路（真实 hackathon key）。
- 全仓 grep 确认 `_DEFAULT_STORE` 无源码残留（仅 backlog 文档描述 / design draft 引用）。

## 附加观测：Qloo real API 实体类型约束

> 以下为 live 实测记录，**第三方行为，本 PR 无代码改动**。评审请知悉。

跨域 discovery：anchor 实体类型会影响下游域合法性。

- anchor = place（Frank Sinatra Service Area）：movie / brand / destination / podcast / book 域
  返回 400 `All of the provided signal.interests.entities were invalid`；代码防御逻辑自动跳过
  失败域，仅输出 WARNING 日志，dining 推荐正常返回。
- anchor = artist：7 个域全部成功。

说明：Qloo 后端对"实体类型 + 目标域"组合存在校验限制；项目已有 live/preview 降级与异常容错，
本次仅做观测记录，未改任何代码。

## 测试

- 离线：`python -m pytest -m "not real_api"` → **511 passed**。
- Live（真实 `QLOO_API_KEY`）：`tests/test_qloo_endpoints_real_api.py` +
  `tests/test_ablation_real_api.py` → **14 passed**。
- smoke：`qloo_smoke_test.py`（search → insights → places → live prefereneced overlay）与
  `qloo_tastecare_smoke.py`（推荐 + 健康约束 + 用药筛查）均跑通。
- B 档完整图 live e2e：`build_qloo_agent_graph().ainvoke()` 真实 key 下
  `intent=qloo_recommend`、`qloo_enabled=True`、`taste_data_source=live`、`retry_count=0`。

## 待办（本次不含，PR 合并后启动）

- 后续 pass：`store=None` 强制注入收紧（移除 `apply_taste_preferences` 的 registry 回落兜底）。