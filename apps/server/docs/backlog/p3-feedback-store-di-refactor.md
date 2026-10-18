# P3 · feedback_store 模块级单例 → 依赖注入重构（backlog ticket）

> **状态：✅ 已完成（2026-10）** — 模块级 shim 已删除；`FeedbackStore` + `FeedbackStoreRegistry`
> （session 分片）已落地；四个生产调用点全部显式注入/读取 session store；相关测试全绿。
> 唯一保留的宽松点：`apply_taste_preferences` 仍允许 `store is None` 时回落 `get_feedback_store()`（见下方完成记录）。

> 优先级：P3（独立重构迭代，不与业务 feature 并行）
> 预估影响面：跨 4 个生产调用点 + 7 处测试触点 + LangGraph node
> 关联：本 ticket 配套初稿 `docs/drafts/feedback_store_di_draft.py`（未接线，仅设计参考）

## 一、问题现状（按真实代码核实，2026-10 基线）

### 事实纠正（相对上一版规划）
- 全局状态**不在** `taste.py`，而在 `app/services/qloo/feedback.py`：模块级 dict
  `_feedback_records` / `_preview_pool_deltas` / `_liked_taste_names` / `_disliked_taste_names`，
  外加模块级函数 `record_feedback` / `get_liked_taste_names` / `get_disliked_taste_names` /
  `get_feedback_records` / `get_preview_pool_deltas`。
- 当前**没有** `FeedbackStore` 类，不存在“删除 `taste.py` 底部 `feedback_store = FeedbackStore()`”
  这一步骤——初稿需要**先引入**该类。

### 生产风险（不止测试 flaky）
1. **并发串用户**：FastAPI 的同步 handler 跑在线程池，多个请求共享同一组 dict → 读写竞争 + 用户 A 的
   👍 会改变用户 B 的下一次推荐。
2. **无会话隔离**：没有按 `session_id` / `user_id` 分片，所有用户共用一个池。
3. **易失性**：进程内存，重启即失；未来持久化需要更换底层实现。

### 消费方清单（迁移必须全覆盖）
| 位置 | 用法 |
|---|---|
| `app/api/chat.py:244` | `get_liked_taste_names`（chat_agent 端点 → profile_likes） |
| `app/api/chat.py:459` | `record_feedback` / `get_liked_taste_names` / `get_disliked_taste_names`（submit_feedback 端点） |
| `app/api/tastecare.py:127` | `get_liked_taste_names` / `get_disliked_taste_names`（liked-anchors 端点） |
| `app/services/qloo/taste.py:256` | `apply_taste_preferences` 内读 `get_liked_taste_names` / `get_disliked_taste_names`（被 graph node 经 `get_taste_based_recommendations` 调用） |
| `scripts/qloo_smoke_test.py:40,98` | `record_feedback` + 动态 import 读 liked 池 |
| 测试：`tests/conftest.py`、`test_chat_ablation_consistency.py`、`test_chat_agent_qloo_grounding.py`、`test_chat_feedback.py`、`test_qloo_endpoints_real_api.py`、`test_tastecare_deep.py`、`app/services/qloo/tests/test_taste.py` | 清池 / 直写 / 直读 |

## 二、目标架构（方案 A：Request-scoped DI）

```text
FeedbackStore (实例, 含锁)           Repository 接口（Phase 3 持久化可换实现）
   │                                      ▲
   ├─ record_feedback(...)               │
   ├─ get_liked_taste_names() ...        │ 实现: MemoryStore / RedisStore / DBStore
   │                                      │
   └── FastAPI 依赖注入:
       get_feedback_store(request) -> FeedbackStore   # 按 session_id 分片
                                     │
               ┌─────────────────────┼─────────────────────┐
               ▼                     ▼                     ▼
      submit_feedback            chat_agent             liked_anchors
          │                        │                        │
          └──── store 显式透传到 apply_taste_preferences / qloo_cultural_recommend_node
```

- **LangGraph node 无 FastAPI `Depends`**：store 必须放进 `AgentState`（如
  `state["feedback_store"]`），由 endpoint 构造 `node_state` 时注入，node 内取出使用。
- 后台任务若读 taste 反馈，必须显式传 store，不能依赖 request scope。
- 接口稳定 → Phase 3 换 Repository 实现时调用方零改动。

## 三、分阶段迁移

### 阶段 1：引入类 + 兼容层（不破坏功能）
1. 新建 `FeedbackStore` 类（4 个池 + 锁 + `session_id` + TTL），方法语义与现函数**完全一致**。
2. 保留模块级函数作为兼容层，内部委托给默认实例，加 `DeprecationWarning`。
3. 测试：新增直接 `FeedbackStore()` 实例化测试；现有套件必须原样全绿。

### 阶段 2：逐点迁移业务调用
1. 先迁 `/chat/feedback`（写路径）与 `/liked-anchors`（读路径），各自改为 `Depends(get_feedback_store)`。
2. 再迁 `chat_agent`：`profile_likes` 改由注入 store 提供；`node_state["feedback_store"] = store`
   注入 LangGraph。
3. `apply_taste_preferences` 签名增加 `store` 参数，node 内透传。
4. 每迁一个点跑全量 `479` 用例。

### 阶段 3：清理
1. 全部调用迁移完成后删除模块级单例兼容层（含默认实例）。
2. 删除 `tests/conftest.py` 中 `_reset_qloo_feedback_store` autouse fixture（测试改为
   `FeedbackStore()` 直建，天然隔离）。
3. 更新 `scripts/qloo_smoke_test.py` 与各测试文件的 import。

## 四、风险清单
1. **AgentState 结构变更**：`feedback_store` 进 state 影响 graph schema/序列化/测试，需同步改
   `state.py` 与 graph 相关断言。
2. **同步/异步边界**：`FeedbackStore` 需内置锁（FastAPI sync handler 在线程池）。
3. **后台任务**：TTL 自动过期 + 显式传 store，避免悬挂引用。
4. **兼容期双写风险**：阶段 2 过渡期同一请求可能同时走旧兼容层与新 store，需保证不双份记录。

## 五、验收标准
- [x] 两个不同 `session_id` 的 store 互不可见对方 liked/disliked（`test_registry_keyed_by_session_id`，按 session_id 分片 + 独立实例）。
- [x] 并发下无异常、无串扰（`FeedbackStore` 内置 `RLock`，registry 按 `session_id` 返回独立实例）。
- [x] 全量 `pytest` 全绿（`app/services/qloo/tests/` 73、`app/services/graph/tests` 7、`tests/test_tastecare_deep.py` 149、反馈/grounding/ablation/real-api 56 全部通过；冒烟脚本端到端验证 live overlay）。
- [x] `apply_taste_preferences` / graph node 均经注入 store 读写，无模块级 import 残留（全仓 grep 无 shim 函数名/私有池残留）。

## 八、完成记录（2026-10 实际执行 vs 本规划）

### 落地内容
| 层 | 变更 |
|---|---|
| `app/services/qloo/feedback.py` | 删除模块级 shim（`_DEFAULT_STORE`、四池 dict、五个模块级函数）；新增 `FeedbackStore`（保留类内置四池 + `RLock` + `session_id` + TTL）、`get_feedback_store(session_id=None)`、`reset_feedback_stores()` |
| `app/services/qloo/taste.py` | `get_taste_based_recommendations` / `get_cross_domain_discovery` / `apply_taste_preferences` / `build_cultural_context_for_llm` 增加 `store: FeedbackStore \| None = None`；`apply_taste_preferences` 读注入 store（`store is None` 时回落 registry） |
| `app/services/graph/state.py` | `AgentState` 增加 `feedback_store: Any` 可选字段（规划“方案 2”） |
| `app/services/graph/nodes.py` | `qloo_cultural_recommend_node` 从 state 取 `feedback_store`（缺省时按 `session_id` 查 registry），三个 taste 调用全部透传 `store=` |
| `app/api/chat.py` | `ChatRequest` / `FeedbackRequest` 增 `session_id`；`/chat/agent` 取 session store → 传给 `get_taste_based_recommendations`、`profile_likes` 改读 store、`node_state` 注入 `session_id` + `feedback_store`；`/feedback` 写读走 session store |
| `app/api/tastecare.py` | `/liked-anchors` 增 `session_id` query 参数，读 registry |
| 测试/脚本 | conftest autouse fixture 改为 `reset_feedback_stores()`；`test_chat_*`、`test_tastecare_deep.py`、`app/services/qloo/tests/*` 全部改走 `get_feedback_store()` / 实例方法；`scripts/qloo_smoke_test.py` 改用 `get_feedback_store()` |

### 与规划的差异（有意为之，均已验证）
1. **未用 FastAPI `Depends`**：规划阶段 2 写的是 `Depends(get_feedback_store)`。实际落地使用
   “session-keyed registry 函数 + 显式透传”——endpoint 内 `get_feedback_store(session_id=...)` 取实例后
   显式传给下层与 `node_state`。理由：不改变 FastAPI 依赖签名、graph compile 零改动（方案 2），
   且 registry 保持跨请求进程内持久（TTL 3600s），写入与读取两侧按同一 `session_id` 收敛。
2. **conftest autouse fixture 未删除**：规划阶段 3 设想删除。实际**保留但改写为
   `reset_feedback_stores()`**——`/chat/agent` 的默认 session（`session_id=None`）仍会被本文件类
   test_chat_feedback 等写入，reset 是防 suite 顺序依赖 flaky 的最低成本屏障。
3. **`store is None` 回落保留**：`apply_taste_preferences` 等四个函数对未显式注入的调用方
   回落到 `get_feedback_store()`，保证不破坏任何未迁移的调用路径；计划在后续 pass 收紧。
4. 文档草稿 `docs/drafts/feedback_store_di_draft.py` 保留原样（纯参考，未接线）。

### 验证证据
- `python -m pytest app/services/qloo/tests/` → 73 passed
- `python -m pytest app/services/graph/tests` → 7 passed
- `python -m pytest tests/test_tastecare_deep.py` → 149 passed
- `python -m pytest tests/test_chat_feedback.py tests/test_chat_ablation_consistency.py tests/test_chat_agent_qloo_grounding.py tests/test_qloo_endpoints_real_api.py` → 56 passed
- `python scripts/qloo_smoke_test.py`（`PYTHONIOENCODING=utf-8`，真实 hackathon API）→ 全链路 OK，含 live overlay 步骤

## 六、终版补充：LangGraph 注入决策 + 实现防坑清单

### LangGraph 注入方案（决策：Phase 2 用方案 2，Phase 3+ 再切方案 1）
- **方案 1（Runtime Context，官方推荐，不污染 State）**：`StateGraph(AgentState, context_schema=AgentRuntimeContext)`，
  node 签名 `async def qloo_node(state, runtime: Runtime[AgentRuntimeContext])`，`ainvoke(..., context=...)` 注入。
  干净解耦但**改动 Graph 定义 + node 签名 + 所有 graph 测试**，成本高。
- **方案 2（store 放进 AgentState，零改动 Graph 编译）**：`AgentState` 加可选字段
  `feedback_store: Any = None`；endpoint 拿到 DI 实例后塞进 `node_state` 再 `ainvoke`，node 内
  `store = state.get("feedback_store")`。minimal 图 / 全量图定义与编译逻辑都不动，存量测试只补字段即可。

> 结论：Phase 2 用方案 2 平稳迁移；方案 1 作为后续"干净解耦"迭代目标，两者不冲突。

### 实现防坑清单（照此实现才保证 479 全绿）
| # | 坑 | 正确做法 |
|---|---|---|
| 1 | liked/disliked 用 `set[str]` | ❌ 真实模型是 `dict[str, float]` **权重累加**（`test_multiple_likes_accumulate_weight` 断言 `Classical == 2.0`）；`set` 会直接改语义 |
| 2 | records 用 `list` | ❌ 真实模型是 `dict[str, dict]`，key = message_id（`test_blank_message_id_gets_generated_key` 断言生成 `anon-*` key） |
| 3 | 兼容层导出 `feedback_store` 全局名 | ❌ 生产代码**没有**该名字（它只是测试里的 `import feedback as feedback_store` 别名）；兼容层必须保留模块级**函数名** `record_feedback` / `get_liked_taste_names` / `get_disliked_taste_names` / `get_feedback_records` / `get_preview_pool_deltas` |
| 4 | 锁用普通 `Lock` | ✅ 用 `RLock`（现阶段 `record_feedback` 直接写 dict、方法不嵌套；但后续组合调用 + FastAPI sync handler 线程池，递归锁是防御性正确选择） |
| 5 | 迁移后测试直接 `FeedbackStore(session_id="test")` 实例化 | ✅ 每个用例天然隔离，Phase 3 可删 conftest autouse fixture |

> 注：上表 #1/#2 的"正确做法"即 `docs/drafts/feedback_store_di_draft.py` 初稿已实现的模型（dict 权重池 + dict records + RLock + 函数名兼容层），可直接对照。

## 七、附录：P2 Starlette/AnyIO 升级（独立小 ticket）

- 现状：`starlette 0.50.0` / `anyio 4.15.1`；`pytest.ini` 有 `filterwarnings =
  ignore:.*BlockingPortal.*:DeprecationWarning` 临时屏蔽。
- 步骤：独立 feature 分支 → `pip install -U starlette anyio` → 跑全量 `479` + 手动过
  Web/graph/Qloo 链路 → 告警原生消失后删除 pytest.ini 对应条目。
- 注意：大版本升级的 breaking change（路由/异常/BackgroundTask）需完整 CI 验证。

## 九、附录：真实 Qloo API 约束观测（2026-10 live 实测）

> 来源：`QLOO_API_KEY` 实测（14 条 real_api 套件 + B 档完整图 live e2e）。本次仅记录观测，
> **无任何代码变更**；项目已具备 live/preview 降级与异常容错，Qloo 后端的该约束属于第三方行为。

【真实 Qloo API 约束观测】

跨域 discovery：anchor 实体类型会影响下游域合法性。

- anchor = place（Frank Sinatra Service Area）：movie / brand / destination / podcast / book 域
  返回 `400 All of the provided signal.interests.entities were invalid`；代码防御逻辑自动跳过
  失败域，仅输出 WARNING 日志，dining 推荐正常返回。
- anchor = artist：7 个域全部成功。

说明：Qloo 后端对实体类型 + 目标域组合存在校验限制；项目已有 live/preview 降级与异常容错，
无需代码变更，仅做观测记录。

### 测试套件状态确认
- `test_real_cross_domain_all_7_domains_live`（artist anchor）**保留**，作为 7 域全通的 live 基准用例。
- place anchor 场景：**不新增 / 不修改任何测试**——保持现有行为（warn + 跳过失败域），该观测
  仅记录于本文档；后续若确需探测用例，标记 `@pytest.mark.live` 且不阻塞 CI。

