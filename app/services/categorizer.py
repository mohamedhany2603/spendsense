"""LLM integration — one narrow AI job: merchant string -> expense category.

Design:
  * A `Classifier` gives a category for a merchant string based on a small set of
    allowed categories (validation at the boundary).
  * When OPENROUTER_API_KEY is configured we ask a real LLM model for a JSON answer
    and validate it strictly (single category that must exist in the DB).
  * Otherwise a deterministic rule-based classifier is used so the whole system runs
    on a clean machine with $0 and no keys. Costs are logged either way.
  * Every call — real or fallback — is recorded in LlmCostLog with token usage and
    an estimated US$ cost, and caching is applied before any call is made.
"""

import json
import re
from dataclasses import dataclass

import httpx
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Category, LlmCostLog
from .cache import cached_merchant_key, get_cached_classification, set_cached_classification

# Rough public pricing for the default model (US$ per 1M tokens).
MODEL_PRICES: dict[str, tuple[float, float]] = {
    "openai/gpt-4o-mini": (0.150, 0.600),
}


@dataclass
class ClassificationResult:
    merchant: str
    category_id: int
    category_name: str
    source: str  # "llm" | "rule" | "cache"
    cost_estimated_usd: float
    prompt_tokens: int
    completion_tokens: int


RULE_KEYWORDS: dict[str, list[str]] = {
    "Food & Dining": [
        "restaurant", "cafe", "coffee", "starbucks", "mcdonald", "burger",
        "pizza", "sushi", "grocer", "supermarket", "whole foods", "lidl",
        "kfc", "subway", "domino", "chipotle", "panera",
    ],
    "Transport": [
        "uber", "lyft", "taxi", "train", "rail", "metro", "bus", "gas",
        "fuel", "shell", "esso", "airline", "flight", "parking",
    ],
    "Shopping": [
        "amazon", "walmart", "target", "best buy", "zalando", "ebay", "etsy",
        "aliexpress", "asos", "nike", "adidas", "uniqlo",
    ],
    "Entertainment": [
        "netflix", "spotify", "hulu", "disney", "steam", "playstation", "xbox",
        "cinema", "movie", "concert", "youtube premium", "apple music",
    ],
    "Utilities": [
        "electric", "water", "internet", "wifi", "phone", "mobile", "gas bill",
        "heating", "council tax", "energy", "verizon", "att bill", "t-mobile",
    ],
    "Health": [
        "pharmacy", "chemist", "doctor", "dentist", "gym", "hospital", "fitness",
        "vitamin", "clinic",
    ],
    "Income": [
        "salary", "payroll", "refund", "deposit", "bonus", "dividend", "interest",
    ],
}

DEFAULT_CATEGORY = "Other"

DEFAULT_CATEGORIES: list[tuple[str, str]] = [
    ("Food & Dining", "Restaurants, cafés, groceries, supermarkets."),
    ("Transport", "Rideshare, public transport, fuel, flights."),
    ("Shopping", "Retail and online purchases."),
    ("Entertainment", "Streaming, games, cinema, events."),
    ("Utilities", "Electricity, water, internet, phone bills."),
    ("Health", "Pharmacy, doctors, gym memberships."),
    ("Income", "Deposits, refunds, pay."),
    ("Other", "Anything that does not fit elsewhere."),
]


def ensure_default_categories(db: Session) -> None:
    if db.query(Category).count() > 0:
        return
    db.add_all([Category(name=n, description=d) for n, d in DEFAULT_CATEGORIES])
    db.commit()


def _matches_rules(merchant_key: str) -> str | None:
    for category, keywords in RULE_KEYWORDS.items():
        if any(keyword in merchant_key for keyword in keywords):
            return category
    return None


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    price_in, price_out = MODEL_PRICES.get(model, (0.150, 0.600))
    return (prompt_tokens / 1_000_000) * price_in + (completion_tokens / 1_000_000) * price_out


def _write_cost_log(
    db: Session,
    provider: str,
    model: str,
    merchant: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    category: str | None,
    success: bool,
    error: str | None = None,
) -> None:
    db.add(
        LlmCostLog(
            provider=provider,
            model=model,
            merchant=merchant,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost_usd=cost_usd,
            response_category=category,
            success=success,
            error=error,
        )
    )
    db.commit()


def _classify_with_llm(db: Session, merchant: str, description: str) -> ClassificationResult | None:
    """Returns None when the call fails (caller falls back to rules)."""
    settings = get_settings()
    if not settings.openrouter_api_key:
        return None

    prompt = (
        "You are a transaction categorizer. Given a merchant name and a description, "
        "answer with exactly one JSON object: {\"category\": \"<name>\"}. "
        "Pick only from this list: "
        + ", ".join(c.name for c in db.query(Category).order_by(Category.name).all())
        + ". "
        f'Merchant: "{merchant}". Description: "{description}". '
        "Return only the JSON object, nothing else."
    )

    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.openrouter_model,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        body = resp.json()
        raw = body["choices"][0]["message"]["content"].strip()
        usage = body.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        match = re.search(r"\{(?:[^{}]|\{[^{}]*\})*\}", raw)
        if not match:
            raise ValueError("No JSON object found in LLM response")
        # Validation of the LLM output: strict category lookup.
        category_name = json.loads(match.group(0))["category"]
        category = db.query(Category).filter(Category.name == category_name).first()
        if category is None:
            raise ValueError(f"LLM returned unknown category: {category_name!r}")

        cost = _estimate_cost(settings.openrouter_model, prompt_tokens, completion_tokens)
        _write_cost_log(
            db, "openrouter", settings.openrouter_model, merchant,
            prompt_tokens, completion_tokens, cost, category.name, True,
        )
        return ClassificationResult(
            merchant=merchant, category_id=category.id, category_name=category.name,
            source="llm", cost_estimated_usd=cost,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        )
    except (httpx.HTTPError, ValueError, KeyError, IndexError, json.JSONDecodeError) as exc:
        _write_cost_log(
            db, "openrouter", settings.openrouter_model, merchant,
            len(prompt.encode("utf-8")) // 4, len(merchant) // 4, 0.0, None, False, str(exc),
        )
        return None


def _classify_with_rules(db: Session, merchant: str, description: str) -> ClassificationResult:
    settings = get_settings()
    merchant_key = cached_merchant_key(merchant)
    category_name = _matches_rules(merchant_key) or DEFAULT_CATEGORY
    category = db.query(Category).filter(Category.name == category_name).first()
    fallback = db.query(Category).filter(Category.name == DEFAULT_CATEGORY).first()
    category = category or fallback

    prompt_tokens = len(merchant.encode("utf-8")) // 4 + 8
    completion_tokens = len(category_name.encode("utf-8")) // 4 + 4
    cost = _estimate_cost(settings.openrouter_model, prompt_tokens, completion_tokens)
    _write_cost_log(
        db, "rule-fallback", settings.openrouter_model, merchant,
        prompt_tokens, completion_tokens, cost, category.name, True,
    )
    return ClassificationResult(
        merchant=merchant, category_id=category.id, category_name=category.name,
        source="rule", cost_estimated_usd=cost,
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
    )


def classify_merchant(db: Session, merchant: str, description: str = "") -> ClassificationResult:
    """Determine a category for a merchant, using the cache first.

    Order: DB cache -> real LLM (if configured) -> deterministic rule fallback.
    Successful results are stored back into the cache for reuse.
    """
    cached = get_cached_classification(db, merchant)
    if cached is not None:
        return ClassificationResult(
            merchant=merchant, category_id=cached.category_id,
            category_name=cached.category.name, source="cache",
            cost_estimated_usd=0.0, prompt_tokens=0, completion_tokens=0,
        )

    result = _classify_with_llm(db, merchant, description)
    if result is None:
        result = _classify_with_rules(db, merchant, description)

    category = db.query(Category).filter(Category.id == result.category_id).first()
    set_cached_classification(
        db, merchant, category, result.source,
        result.prompt_tokens, result.completion_tokens,
    )
    return result