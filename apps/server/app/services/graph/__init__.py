from app.services.graph.state import AgentState, init_state

def build_agent_graph(**kwargs):
    from app.services.graph.graph import build_agent_graph as _build

    # 顶层默认走 A档最简可编译图（无 checkpointer，红线合规：不开启会话持久化）。
    # 完整大图仍可通过 minimal=False 显式构建（蓝图保留）。
    kwargs.setdefault("minimal", True)
    return _build(**kwargs)


def build_qloo_agent_graph():
    """B档 Qloo Agent 完整编排图（/chat/agent live 分支使用的默认图）。"""
    from app.services.graph.graph import build_qloo_agent_graph as _build

    return _build()


def draw_mermaid() -> str:
    """返回 B档 Qloo Agent 图的 Mermaid 拓扑文本（README / Devpost 展示用）。"""
    from app.services.graph.graph import draw_mermaid as _draw

    return _draw()

__all__ = [
    "AgentState",
    "init_state",
    "build_agent_graph",
    "build_qloo_agent_graph",
    "draw_mermaid",
]