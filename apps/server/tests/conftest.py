import os

os.environ.setdefault("GRAPH_ENV", "dev")
os.environ.setdefault("LLM_MODE", "mock")
os.environ.setdefault("TOOL_DEF_CONFIG_PATH", "config/tools.yaml")

import pytest
import pytest_asyncio
pytest_plugins = ["pytest_asyncio"]


@pytest.fixture(autouse=True)
def _reset_qloo_feedback_store():
    """Isolate every test from the session-keyed Qloo feedback registry.

    Root cause of the historical flaky full-suite failure (test_chat_agent_qloo_grounding.py
    ::test_chat_agent_live_grounding_falls_back_when_graph_compile_fails):

    1. Earlier tests (own-file /chat/feedback tests + app/services/qloo/tests/
       test_taste.py feedback recording) leave entries in the default session's
       liked pool.
    2. /chat/agent merges that pool into profile_likes -> seed_names.
    3. The fallback test's fake_search is a catch-all that returns "Frank Sinatra"
       for ANY query, so every extra seed name resolves to another identical
       taste_entity -> duplicate taste_entities and a false assertion failure.

    The node's dedupe is exact-string based; it cannot see through equivalent names
    that came from different seeds. Resetting the registry before every test makes
    the suite order-independent.
    """
    from app.services.qloo.feedback import reset_feedback_stores

    # Drop every session store from the DI registry (fresh default store per
    # test). The registry is the only module-level mutable state left.
    reset_feedback_stores()
    yield