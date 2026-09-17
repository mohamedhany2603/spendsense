def _add_tx(client, headers, merchant="Starbucks"):
    r = client.post("/api/transactions", json={"merchant": merchant,
                                                "description": "s", "amount": 10.0},
                    headers=headers)
    assert r.status_code == 201
    return r.json()


def test_analytics_first_call_not_cached_second_cached(client, user_headers):
    _add_tx(client, user_headers)
    month = "2026-09"  # transactions created now fall in the current month
    first = client.get(f"/api/analytics/monthly?month={month}", headers=user_headers)
    assert first.status_code == 200
    assert first.json()["cached"] is False
    second = client.get(f"/api/analytics/monthly?month={month}", headers=user_headers)
    assert second.status_code == 200
    assert second.json()["cached"] is True
    assert second.json()["total_expense"] == 10.0


def test_analytics_invalidated_after_new_transaction(client, user_headers):
    _add_tx(client, user_headers, "Uber")
    month = "2026-09"
    client.get(f"/api/analytics/monthly?month={month}", headers=user_headers)
    warmed = client.get(f"/api/analytics/monthly?month={month}", headers=user_headers)
    assert warmed.json()["cached"] is True
    _add_tx(client, user_headers, "Netflix")  # write -> invalidate cache
    after = client.get(f"/api/analytics/monthly?month={month}", headers=user_headers)
    assert after.json()["cached"] is False


def test_classifier_cache_reused(client, user_headers):
    costs_before = client.get("/api/llm/costs", headers=user_headers).json()["total_calls"]
    first = client.post("/api/llm/categorize",
                        json={"merchant": "Ferris Market", "description": "produce"},
                        headers=user_headers).json()
    assert first["source"] in ("llm", "rule")  # a real computation happened
    costs_mid = client.get("/api/llm/costs", headers=user_headers).json()["total_calls"]
    assert costs_mid == costs_before + 1

    second = client.post("/api/llm/categorize",
                         json={"merchant": "Ferris Market", "description": "produce"},
                         headers=user_headers).json()
    assert second["source"] == "cache"
    assert second["cost_estimated_usd"] == 0.0
    costs_after = client.get("/api/llm/costs", headers=user_headers).json()["total_calls"]
    assert costs_after == costs_mid  # cache hit -> no new LLM call, no new cost entry