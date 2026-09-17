def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert "jobs" in body  # scheduler is off under tests by design


def test_health_auth_requires_token(client):
    r = client.get("/health/me")
    assert r.status_code == 401