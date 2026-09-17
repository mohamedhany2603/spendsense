"""Caching logic.

Two layers:
  1. In-memory TTL cache for the expensive monthly analytics rollup.
  2. A durable DB-backed cache (ClassifierCache) for LLM categorization results —
     the truly expensive work.

The analytics cache stores a JSON snapshot of the rollup result and re-uses it until
the TTL expires OR the user's data changes (explicit invalidation). Re-using a stored
expensive result instead of recomputing it is the caching concept from Section 2.
"""

import json
import threading
import time

from sqlalchemy.orm import Session

from ..models import ClassifierCache, Category


class TTLCache:
    """Minimal thread-safe TTL cache with explicit invalidation."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get(self, key: str, ttl_seconds: int) -> object | None:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            expires_at, value = item
            if time.monotonic() > expires_at:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: object, ttl_seconds: int) -> None:
        with self._lock:
            self._store[key] = (time.monotonic() + ttl_seconds, value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)


analytics_cache = TTLCache()


def analytics_key(user_id: int, month: str) -> str:
    return f"analytics:{user_id}:{month}"


def get_cached_analytics(user_id: int, month: str, ttl_seconds: int) -> dict | None:
    cached = analytics_cache.get(analytics_key(user_id, month), ttl_seconds)
    if cached is None:
        return None
    return json.loads(cached)


def set_cached_analytics(user_id: int, month: str, payload: dict, ttl_seconds: int) -> None:
    analytics_cache.set(analytics_key(user_id, month), json.dumps(payload), ttl_seconds)


def invalidate_user_cache(user_id: int) -> None:
    """Data changed for this user — drop every cached analytics key for the user."""
    prefix = f"analytics:{user_id}:"
    for key in list(analytics_cache._store):
        hit = analytics_cache._store.get(key)
        if hit is None:
            continue
        if key.startswith(prefix):
            analytics_cache.delete(key)


def cached_merchant_key(merchant: str) -> str:
    """Normalize a merchant name so mini-brand variations hit the same cache row."""
    return " ".join(merchant.lower().split())


def get_cached_classification(db: Session, merchant: str) -> ClassifierCache | None:
    row = (
        db.query(ClassifierCache)
        .filter(ClassifierCache.merchant_key == cached_merchant_key(merchant))
        .first()
    )
    if row is not None:
        row.hits += 1
        db.commit()
    return row


def set_cached_classification(
    db: Session,
    merchant: str,
    category: Category,
    source: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> ClassifierCache:
    row = ClassifierCache(
        merchant_key=cached_merchant_key(merchant),
        category_id=category.id,
        source=source,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row