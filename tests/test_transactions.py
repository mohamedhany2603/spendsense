def _tx(merchant="Starbucks", amount=5.6, **extra):
    payload = {"merchant": merchant, "description": "s", "amount": amount, **extra}
    return payload


def test_create_requires_auth(client):
    r = client.post("/api/transactions", json=_tx())
    assert r.status_code == 401


def test_create_auto_categorizes_known_merchant(client, user_headers):
    r = client.post("/api/transactions", json=_tx(merchant="Starbucks"), headers=user_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "categorized"
    assert body["category_name"] == "Food & Dining"
    assert body["source"] in ("rule", "llm", "cache")


def test_create_with_explicit_category_is_manual(client, user_headers):
    r = client.post("/api/transactions", json=_tx(merchant="Weird Shop", category_id=2),
                    headers=user_headers)
    assert r.status_code == 201
    assert r.json()["source"] == "manual"
    assert r.json()["category_id"] == 2


def test_create_with_unknown_category_is_422(client, user_headers):
    r = client.post("/api/transactions", json=_tx(category_id=9999), headers=user_headers)
    assert r.status_code == 422


def test_create_negative_amount_is_422(client, user_headers):
    r = client.post("/api/transactions", json=_tx(amount=-3), headers=user_headers)
    assert r.status_code == 422


def test_create_zero_amount_is_422(client, user_headers):
    r = client.post("/api/transactions", json=_tx(amount=0), headers=user_headers)
    assert r.status_code == 422


def test_create_empty_merchant_is_422(client, user_headers):
    r = client.post("/api/transactions", json=_tx(merchant="   "), headers=user_headers)
    assert r.status_code == 422


def test_list_and_filter(client, user_headers):
    client.post("/api/transactions", json=_tx(merchant="Uber"), headers=user_headers)
    all_tx = client.get("/api/transactions", headers=user_headers)
    assert all_tx.status_code == 200
    assert len(all_tx.json()) == 1
    by_cat = client.get("/api/transactions?category_id=2", headers=user_headers)
    assert by_cat.status_code == 200
    assert len(by_cat.json()) == 1


def test_get_missing_transaction_is_404(client, user_headers):
    r = client.get("/api/transactions/9999", headers=user_headers)
    assert r.status_code == 404


def test_get_other_users_transaction_is_404(client, user_headers):
    r = client.post("/api/transactions", json=_tx(), headers=user_headers)
    tx_id = r.json()["id"]
    client.post("/api/auth/register",
                json={"email": "mallory@example.com", "password": "password123", "name": "M"})
    login = client.post("/api/auth/login",
                        json={"email": "mallory@example.com", "password": "password123"})
    other = {"Authorization": f"Bearer {login.json()['access_token']}"}
    r2 = client.get(f"/api/transactions/{tx_id}", headers=other)
    assert r2.status_code == 404


def test_patch_reassigns_category(client, user_headers):
    created = client.post("/api/transactions", json=_tx(merchant="Gym Pro"),
                          headers=user_headers).json()
    categories = {2: "Transport", 3: "Shopping"}
    r = client.patch(f"/api/transactions/{created['id']}", json={"category_id": 3},
                     headers=user_headers)
    assert r.status_code == 200
    assert r.json()["category_id"] == 3
    assert r.json()["source"] == "manual"


def test_patch_unknown_category_is_422(client, user_headers):
    created = client.post("/api/transactions", json=_tx(), headers=user_headers).json()
    r = client.patch(f"/api/transactions/{created['id']}", json={"category_id": 12345},
                     headers=user_headers)
    assert r.status_code == 422


def test_delete_then_get_is_404(client, user_headers):
    created = client.post("/api/transactions", json=_tx(), headers=user_headers).json()
    d = client.delete(f"/api/transactions/{created['id']}", headers=user_headers)
    assert d.status_code == 204
    r = client.get(f"/api/transactions/{created['id']}", headers=user_headers)
    assert r.status_code == 404


def test_bulk_create(client, user_headers):
    items = [_tx(merchant="Amazon"), _tx(merchant="Netflix"), _tx(merchant="Shell Gas")]
    r = client.post("/api/transactions/bulk", json={"items": items}, headers=user_headers)
    assert r.status_code == 201
    assert len(r.json()) == 3
    assert {t["category_name"] for t in r.json()} == {
        "Shopping", "Entertainment", "Transport"
    }