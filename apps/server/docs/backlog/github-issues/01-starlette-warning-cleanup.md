# [CHORE] 升级 starlette/anyio，移除 BlockingPortal 测试告警过滤

> 单一任务：P2 告警清理。主 ticket：`docs/backlog/github-issue-feedback-store-di.md`（P2 节）。
> 独立分支，零业务代码变更。

## 现状
- `starlette 0.50.0` / `anyio 4.15.1` 触发 `BlockingPortal` DeprecationWarning 刷屏。
- `pytest.ini` 存在临时 `filterwarnings = ignore:.*BlockingPortal.*:DeprecationWarning`。

## 验收（全部满足即合）
- [ ] `pip install -U starlette anyio`
- [ ] 全量 `pytest -x`（479 用例）通过，且 `BlockingPortal` 警告**原生消失**（不靠过滤）
- [ ] 删除 `pytest.ini` 中对应 filterwarnings 条目
- [ ] CI 全绿；无业务代码变更，无回归风险

## 注意
- 大版本 breaking change（路由 / 异常 / BackgroundTask）需完整 CI + 手动过 Web/graph/Qloo 链路。
- 若 `pytest -x` 出现新的 `0 passed / 0 warnings` 之外的告警，如实记录，不回滚到过滤方案。
