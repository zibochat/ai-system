from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from datetime import datetime

from recommender import recommend as _recommend
from llm_agent import save_conversation_interaction as _save_interaction


def chat_one_turn(
    *,
    user_id: str,
    chat_id: Optional[str],
    message: str,
    profile: Dict[str, Any],
    max_count: int = 5,
) -> Tuple[str, Dict[str, Any]]:
    """Run one chat turn and persist memory.

    Returns: (answer, log)
    """
    answer, log = _recommend(profile, message, max_count=max_count, user_id=user_id)
    try:
        _save_interaction(user_id, message, answer)
    except Exception:
        pass
    return answer, log


