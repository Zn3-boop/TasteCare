# [REFACTOR] feedback.py 引入 FeedbackStore 类（RLock + session_id）+ 模块级兼容层

> 单一任务：P3-Phase 1（只新增代码，零行为变更，全量回归）。
> 主 ticket：`docs/backlog/github-issue-feedback-store-di.md`（Phase 1 节）。
> 初稿对照：`docs/drafts/feedback_store_di_draft.py`（已 py_compile + 冒烟验证）。

## 范围
在 `app/services/qloo/feedback.py`：
1. 新增 `FeedbackStore` 类：
   - 构造入参 `session_id: str | None = None`（缺省自动生成），4 个业务池为实例属性；
   - 全部读写方法由 **RLock** 包裹；
   - ⚠️ 数据模型对齐现状：liked/disliked = `dict[str, float]` 权重累加池；
     records = `dict[str, dict]`（key=message_id，空 key 生成 `anon-*`）。**不得改成 set/list**。
2. 保留模块级 `_legacy_global_store` 实例；**5 个模块级函数名**委托到该实例：
   `record_feedback` / `get_liked_taste_names` / `get_disliked_taste_names` /
   `get_feedback_records` / `get_preview_pool_deltas`。
   - ⚠️ 生产代码没有 `feedback_store` 全局名（它只是测试别名），兼容层保函数名。
3. 现有业务代码 / 现有测试**零修改**。

## 新增单测（tests/test_feedback_store.py 或 qloo/tests 下）
- [ ] 多 session 实例互相隔离（A 实例写入不影响 B）
- [ ] 并发读写（threading 多线程）无竞争、无死锁
- [ ] 权重累加语义（同名 liked 两次 → 权重 2.0）
- [ ] 空 message_id → `anon-*` key
- [ ] toggle / clear / preview deltas 行为与模块级一致

## 验收
- [ ] 全量 `pytest -x`：479 passed、0 failures、0 warnings
- [ ] 现有测试未改一字仍全绿（证明兼容层成立）
- [ ] `py_compile` 通过
