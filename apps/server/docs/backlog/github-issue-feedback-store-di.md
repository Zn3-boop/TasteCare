# [REFACTOR] 全局 feedback 池改造为会话隔离 DI 实例 + Starlette 告警清理（两阶段落地）

> 状态：待执行
> 关联：`docs/backlog/p3-feedback-store-di-refactor.md`（技术债 ticket）、
> `docs/drafts/feedback_store_di_draft.py`（初稿：已 py_compile + 会话隔离/record/toggle/clear 冒烟验证）
> ⚠️ 校正说明：本 issue 已按代码实际事实修正四处——① `chat.py:244` 是 `get_liked_taste_names`（非 record_feedback）；
> ② 生产代码**没有** `feedback_store` 全局名，兼容层必须保**函数名**；③ RLock 是防御性选择，现 API 方法不嵌套；
> ④ Checkpointer 仅 minimal 图未启用，全量图**已内置**三档工厂。

## 一、问题现状（只写故障与风险，不写科普）
1. **测试侧**：`app/services/qloo/feedback.py` 模块级可变池
   （`_liked_taste_names` / `_disliked_taste_names` / `_feedback_records` / `_preview_pool_deltas`）
   被跨用例污染，必须靠 `tests/conftest.py` autouse fixture 强制重置，长期 flaky 隐患。
2. **生产侧**：FastAPI 同步 handler 跑在线程池 + 模块级单例 → 并发下多请求共用一套喜好池，
   用户数据串扰；临界区无锁保护。
3. **遗留告警**：
   - Starlette `BlockingPortal` DeprecationWarning 刷屏（升级 starlette/anyio 后原生消除）；
   - 消融测试 `coroutine was never awaited`（patch `apply_taste_preferences` 撞 AsyncMock，已用 hermetic stub 消除）。
4. **边界澄清（执行约束，严禁越界）**
   - ❌ 本次**不做 Checkpointer 跨会话持久化**：`/chat/agent` 走 minimal 图（`graph.py:202` `builder.compile()` 无 checkpointer），
     状态仅存活在单次请求内；
   - ✅ 用户口味、忌口、文化偏好作为外部 Profile 入参注入图（当前来源：feedback 池 + `/chat/feedback` 写入），
     健康约束由图内节点从消息实时提取；**Graph 内部不做会话存储**。

## 二、整体技术方案（可落地，含代码选型）
### 1. FeedbackStore 实例类（线程安全 + 会话隔离）
- 新增 `FeedbackStore(session_id=...)` 类；`session_id` 缺省自动生成，每会话独立内存池。
- 使用 **RLock 递归锁**：防御性正确——FastAPI sync handler 线程池并发 + 未来 `record_feedback`
  与 getter 组合调用（现 API 方法不嵌套，勿以"当前嵌套会死锁"作为理由写注释）。
- ⚠️ **数据模型必须对齐现状，不可改语义**：
  - liked/disliked = `dict[str, float]` **权重累加**池（`test_multiple_likes_accumulate_weight` 断言 `Classical == 2.0`，不能是 set）；
  - records = `dict[str, dict]`，key = message_id（`test_blank_message_id_gets_generated_key` 断言生成 `anon-*` key，不能是 list）。
  - 以上模型即 `docs/drafts/feedback_store_di_draft.py` 已实现版本，直接对照。
- 初稿已含 `ttl_seconds` 构造入参 + 惰性过期钩子；本 issue **不落地**后台清理任务（见 Out of Scope）。

### 2. LangGraph 依赖注入（方案 2，选定，不再讨论）
- `AgentState` 是 **TypedDict（total=False）**（`app/services/graph/state.py:32`），
  新增可选字段 `feedback_store: Optional[FeedbackStore]` **零 pydantic 校验成本**；
- FastAPI endpoint 通过 DI 生成独立实例 → 塞进 node_state → `ainvoke`；
  node 内 `store = state.get("feedback_store")`，不再 import 全局函数；
- Graph 定义与编译代码**零改动**（minimal 图与全量图均不动）。
- 后续迭代再平滑迁移 Runtime Context（官方推荐、不污染 State），本 issue 不做。

### 3. 兼容兜底策略（保证全量 479 不崩）
- 保留模块级 `_legacy_global_store` 实例，**5 个模块级函数名**委托到该实例：
  `record_feedback` / `get_liked_taste_names` / `get_disliked_taste_names` /
  `get_feedback_records` / `get_preview_pool_deltas`；
- ⚠️ 生产代码**没有** `feedback_store` 全局名（它只是测试里的 `import feedback as feedback_store`
  别名）。兼容层若只导出 `feedback_store` 名字、不保函数名，生产调用方会在 Phase 3 直接崩。

## 三、完整迁移清单（文件 + 调用点位，逐条执行）
### 生产调用点位（5 处，分批替换）
| # | 位置 | 调用 | 端点/场景 |
|---|---|---|---|
| 1 | `app/api/chat.py:244` | `get_liked_taste_names()` | `/chat/agent`：profile_likes 注入 seed_names |
| 2 | `app/api/chat.py:459` | `record_feedback()` + `get_liked_taste_names()` / `get_disliked_taste_names()` | `/chat/feedback`：写入 + 回显 |
| 3 | `app/services/qloo/tastecare.py:127` | `get_liked_taste_names()` / `get_disliked_taste_names()` | liked-anchors 端点 |
| 4 | `app/services/qloo/taste.py:256` | `get_liked_taste_names()` / `get_disliked_taste_names()` | `apply_taste_preferences` 读取 likes |
| 5 | `scripts/qloo_smoke_test.py:40/98` | `record_feedback()` / 动态 `import_module("...feedback").get_liked_taste_names()` | 脚本入口 |

### 测试触达点位（7 处断言/调用点，跨 5+ 文件）
`tests/test_chat_feedback.py`、`tests/test_chat_agent_qloo_grounding.py`、
`tests/test_chat_ablation_consistency.py`、`tests/test_tastecare_deep.py`、
`tests/test_qloo_endpoints_real_api.py`、`app/services/qloo/tests/test_taste.py`。
改造目标：不依赖全局池，直接 `FeedbackStore(session_id="test")` 独立实例。

## 四、分阶段执行计划（可拆 3 个独立 PR）
### P2（本周，独立分支，零业务改动）：Starlette/AnyIO 告警清理
- [ ] `pip install -U starlette anyio`
- [ ] 全量 `pytest -x` → 确认 BlockingPortal 警告**原生消失**
- [ ] 删除 `pytest.ini` 对应 `filterwarnings` 条目
- [ ] CI 全绿后合并；无业务代码变更，无回归风险

### P3（单独重构迭代）：feedback 池 DI 改造
#### Phase 1：兼容层搭建（只新增代码，不改老调用，测试全绿）
- [ ] `feedback.py` 新增带 RLock + session_id 的 `FeedbackStore` 类（对照初稿）
- [ ] 模块级 5 函数改为委托 `_legacy_global_store` 实例
- [ ] 新增单测：多 session 互相隔离、并发读写无竞争、`anon-*` key / 权重累加语义保持
- [ ] 全量 479 用例通过

#### Phase 2：分批迁移（endpoint → graph node → 脚本，每批全量回归）
- [ ] FastAPI DI 工厂：按 session_id 生成独立实例（接线草稿见初稿结尾）
- [ ] 实例注入 `AgentState["feedback_store"]`，node 从 state 读取，不再 import 全局函数
- [ ] 每替换一处调用点即删除该处全局引用；每批跑全量 pytest

#### Phase 3：收尾清理
- [ ] 删除 `_legacy_global_store` 兼容层
- [ ] 删除 conftest autouse 清池 fixture
- [ ] 所有测试改为直建 `FeedbackStore(session_id="test")`，彻底根除 flaky 根源

## 五、生产风险与回滚方案（必须遵守）
1. **并发安全**：全部成员读写由 RLock 包裹。
2. **会话隔离**：每请求唯一 session_id，独立内存池，用户数据完全隔离。
3. **一键回滚**：Phase 1 + Phase 2 全程保留兼容层；线上异常直接切回全局实例，无需代码回退。
4. **异步约束**：后台/异步任务禁止读全局实例，必须显式接收上游传递的 store 对象。

## 六、验收标准（可量化）
- ✅ 全量 479 passed、0 flaky、0 warnings、无 `coroutine was never awaited`
- ✅ 多 session 并发：不同用户喜好池完全隔离，互不污染
- ✅ 读写线程安全、无死锁
- ✅ BlockingPortal DeprecationWarning 彻底消除，CI 日志干净
- ✅ 兼容层存续期间存量代码零修改即可正常运行

## 七、Out of Scope（不扩量）
1. Checkpointer 跨会话持久化：本次不动。minimal 图无 checkpointer；全量图三档工厂
   （`graph.py:35`）为**预留扩展点**，需要多轮对话时切换即可，核心 node 零改动。
2. Redis/DB 持久化：仅预留 Repository 接口定义，不落地实现。
3. 锁粒度拆分：仅用 RLock 全池锁；细粒度锁留后续。
4. TTL 自动过期后台任务：`ttl_seconds` 构造参数已备（初稿含惰性过期），本次不接线清理任务。

## 八、后续可选 backlog（本次不开发）
1. 内存池 TTL 自动过期后台任务，防长期运行内存溢出
2. Repository 接口：内存 / Redis 双实现无缝切换
3. 4 个业务池拆分，细化锁粒度，降低锁竞争

---

### 配套答辩文案（独立段落，不混入执行步骤）
**Q：为什么没有做对话记忆？**
A：`/chat/agent` 使用 minimal 图，`compile()` 不传 checkpointer，LangGraph 状态只在**单次请求内**
流转，不引入外部存储与序列化开销（demo 轻量目标）。用户口味、文化偏好、健康约束作为**外部 Profile
入参**在请求入口喂给图，健康约束由图内节点从消息实时提取；跨会话长时记忆不在本次原型范围。
同时平台全量图**已内置** Checkpointer 工厂（dev=MemorySaver / test=Sqlite / prod=Postgres，
`graph.py:35 get_checkpointer()` + `scripts/init_postgres.sql`），需要多轮对话时切全量图即可，
核心 node 零改动——升级通道已预留，当前是刻意的范围选择而非技术缺口。
