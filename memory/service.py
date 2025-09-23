from __future__ import annotations

from typing import Any, Dict

from llm_agent import (
    get_user_memory as _get_user_memory,
    ensure_product_summary_cached as _ensure_product_summary_cached,
)


def get_memory_snapshot(user_id: str) -> Dict[str, Any]:
    mem = _get_user_memory(user_id)
    return {
        "recent_context": mem.get_recent_context(5),
        "summary": mem.get_memory_summary(),
    }


