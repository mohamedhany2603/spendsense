from pathlib import Path

from app.services.reports import REPORTS_DIR


def test_report_requires_auth(client):
    r = client.post("/api/reports/generate", json={"month": "2026-08"})
    assert r.status_code == 401


def test_generate_and_download_pdf(client, user_headers):
    for m in ["Starbucks", "Uber", "Netflix", "Amazon"]:
        client.post("/api/transactions", json={"merchant": m, "description": "s",
                                                "amount": 20.0}, headers=user_headers)
    r = client.post("/api/reports/generate", json={"month": "2026-09"}, headers=user_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["month"] == "2026-09"
    assert body["transaction_count"] == 4
    assert body["total_expense"] == 80.0
    assert (Path(REPORTS_DIR) / body["file_name"]).exists()

    dl = client.get(f"/api/reports/{body['id']}/download", headers=user_headers)
    assert dl.status_code == 200
    assert dl.headers["content-type"].startswith("application/pdf")
    assert dl.content[:5] == b"%PDF-"


def test_generate_empty_month_still_produces_report(client, user_headers):
    r = client.post("/api/reports/generate", json={"month": "2024-01"}, headers=user_headers)
    assert r.status_code == 201
    assert r.json()["total_expense"] == 0.0
    assert r.json()["transaction_count"] == 0


def test_generate_bad_month_format_is_422(client, user_headers):
    r = client.post("/api/reports/generate", json={"month": "bad-format"}, headers=user_headers)
    assert r.status_code == 422


def test_download_other_users_report_is_404(client, user_headers):
    created = client.post("/api/reports/generate", json={"month": "2026-09"},
                          headers=user_headers).json()
    client.post("/api/auth/register",
                json={"email": "oscar@example.com", "password": "password123", "name": "O"})
    login = client.post("/api/auth/login",
                        json={"email": "oscar@example.com", "password": "password123"})
    other = {"Authorization": f"Bearer {login.json()['access_token']}"}
    r = client.get(f"/api/reports/{created['id']}/download", headers=other)
    assert r.status_code == 404


def test_list_reports(client, user_headers):
    client.post("/api/reports/generate", json={"month": "2026-08"}, headers=user_headers)
    r = client.get("/api/reports", headers=user_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["month"] == "2026-08"