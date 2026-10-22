# [REFACTOR] 迁移 feedback 消费方到 DI 实例并删除全局兼容层

> 单一任务：P3-Phase 2 + Phase 3。主 ticket：`docs/backlog/github-issue-feedback-store-di.md`。
> 前置：issue 02（FeedbackStore 类 + 兼容层）已合入且 479 全绿。

## 范围
### Phase 2：分批迁移（endpoint → graph node → 脚本，每批全量回归）
按序替换 5 处生产调用点：
1. `app/api/chat.py:244` → `get_liked_taste_names()`（/chat/agent profile_likes）
2. `app/api/chat.py:459` → `record_feedback()` + getters（/chat/feedback）
3. `app/services/qloo/tastecare.py:127` → getters（liked-anchors）
4. `app/services/qloo/taste.py:256` → getters（apply_taste_preferences）
5. `scripts/qloo_smoke_test.py:40/98` → record_feedback / 动态 import getter

方案（选定，勿改）：
- FastAPI DI 工厂：按请求生成 `FeedbackStore(session_id=...)` 实例（接线草稿见初稿结尾）；
- `AgentState`（TypedDict，state.py:32）新增可选字段 `feedback_store`，
  endpoint 塞入 node_state → `ainvoke`，node 内 `state.get("feedback_store")`；
- Graph 定义与编译代码零改动；
- 每替换一处即删除该处全局函数引用；每批全量 `pytest -x`。

### Phase 3：收尾清理
- [ ] 删除 `_legacy_global_store` 模块级兼容层（连同 5 个委托函数）
- [ ] 删除 `tests/conftest.py` autouse 清池 fixture
- [ ] 测试直建 `FeedbackStore(session_id="test")` 实例：
  `tests/test_chat_feedback.py`、`tests/test_chat_agent_qloo_grounding.py`、
  `tests/test_chat_ablation_consistency.py`、`tests/test_tastecare_deep.py`、
  `tests/test_qloo_endpoints_real_api.py`、`app/services/qloo/tests/test_taste.py`

## 约束
- 后台/异步任务禁止读全局实例，显式传递 store。
- 线上异常：Phase 2 全程保留兼容层，可一键切回；Phase 3 删除后不可回退，需先行全量验证。

## 验收
- [ ] 全量 479 passed、0 flaky、0 warnings、无 `coroutine was never awaited`
- [ ] 多 session 并发隔离（可写并发冒烟脚本验证）
- [ ] 全代码库 `grep feedback_store` 仅剩 DI 注入与实例化，无模块级单例引用
