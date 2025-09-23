from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from recommender import (
    recommend as _recommend,
    index_products_to_faiss as _index_products,
)


def recommend_with_profile(
    profile: Dict[str, Any],
    user_message: str,
    *,
    user_id: Optional[str] = None,
    max_count: int = 5,
) -> Tuple[str, Dict[str, Any]]:
    return _recommend(profile, user_message, max_count=max_count, user_id=user_id)


def index_products() -> int:
    return _index_products("products_index")


