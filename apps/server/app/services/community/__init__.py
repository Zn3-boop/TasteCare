"""Community matching — connect people with the same cultural tastes + health needs.

Everything runs on Qloo's cloud API (search / insights) via httpx — no local
models and no LLM key required, so it works on memory-constrained machines.
"""

from app.services.community.matcher import (
    DEMO_PEERS,
    match_peers,
    semantic_match_peers,
    request_connection,
    accept_connection,
    connection_status,
    list_connections,
)

__all__ = [
    "DEMO_PEERS",
    "match_peers",
    "semantic_match_peers",
    "request_connection",
    "accept_connection",
    "connection_status",
    "list_connections",
]
