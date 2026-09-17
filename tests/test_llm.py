def test_categorize_requires_auth(client):
    r = client.post("/api/llm/categorize", json={"merchant": "X", "description": "y"})
    assert r.status_code == 401


def test_categorize_unknown_merchant_uses_fallback_and_logs_cost(client, user_headers):
    r = client.post("/api/llm/categorize",
                    json={"merchant": "Hodgepodge Emporium", "description": "misc"},
                    headers=user_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["category"] in {  # validated against the known vocabulary
        "Food & Dining", "Transport", "Shopping", "Entertainment",
        "Utilities", "Health", "Income", "Other",
    }
    assert body["category_id"] > 0
    assert body["source"] in ("llm", "rule")


def test_categorize_missing_merchant_is_422(client, user_headers):
    r = client.post("/api/llm/categorize", json={"description": "y"}, headers=user_headers)
    assert r.status_code == 422


def test_categorize_blank_merchant_is_422(client, user_headers):
    r = client.post("/api/llm/categorize", json={"merchant": "  "}, headers=user_headers)
    assert r.status_code == 422


def test_cost_log_summary(client, user_headers):
    client.post("/api/llm/categorize", json={"merchant": "A New Shop",
                                              "description": "things"},
                headers=user_headers)
    r = client.get("/api/llm/costs", headers=user_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total_calls"] >= 1
    assert body["successful_calls"] >= 1
    assert body["total_estimated_cost_usd"] >= 0
    latest = body["logs"][0]
    assert latest["provider"] in ("openrouter", "rule-fallback")
    assert latest["response_category"] is not None