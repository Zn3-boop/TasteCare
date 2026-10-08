from __future__ import annotations

import pytest


class TestGraphSmoke:
    def test_import_state(self):
        from app.services.graph.state import AgentState
        assert AgentState is not None

    def test_import_nodes_functions(self):
        from app.services.graph.nodes import (
            taste_health_filter_node,
            route_after_taste_health_filter,
            route_after_qloo,
            answer_generation_node,
        )
        assert taste_health_filter_node is not None
        assert route_after_taste_health_filter is not None
        assert route_after_qloo is not None
        assert answer_generation_node is not None