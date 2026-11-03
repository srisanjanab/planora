from datetime import date


def add(client, headers, **over):
    payload = {"title": "Lunch", "category": "FOOD", "amount": "450", "spent_on": "2026-10-05"}
    payload.update(over)
    r = client.post("/expenses", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_defaults_date_to_today(client, headers, clock):
    clock.today = date(2026, 10, 20)
    r = client.post("/expenses", json={"title": "Tea", "amount": "20"}, headers=headers)
    assert r.status_code == 201
    assert r.json()["spent_on"] == "2026-10-20"
    assert r.json()["category"] == "OTHER"


def test_validation(client, headers):
    assert client.post("/expenses", json={"title": "x", "amount": "0"}, headers=headers).status_code == 422
    assert client.post("/expenses", json={"title": "", "amount": "5"}, headers=headers).status_code == 422
    bad = {"title": "x", "amount": "5", "category": "NOPE"}
    assert client.post("/expenses", json=bad, headers=headers).status_code == 422


def test_filters_and_ordering(client, headers):
    add(client, headers, title="A", spent_on="2026-10-01", category="FOOD", payment_method="UPI")
    add(client, headers, title="B", spent_on="2026-10-10", category="TRAVEL", payment_method="CASH")
    add(client, headers, title="C", spent_on="2026-10-20", category="FOOD", payment_method="CASH")

    titles = lambda r: [e["title"] for e in r.json()]
    assert titles(client.get("/expenses", headers=headers)) == ["C", "B", "A"]  # newest first
    assert titles(client.get("/expenses", params={"category": "FOOD"}, headers=headers)) == ["C", "A"]
    assert titles(client.get("/expenses", params={"payment_method": "CASH"}, headers=headers)) == ["C", "B"]
    r = client.get("/expenses", params={"date_from": "2026-10-05", "date_to": "2026-10-15"}, headers=headers)
    assert titles(r) == ["B"]
    assert titles(client.get("/expenses", params={"limit": 1}, headers=headers)) == ["C"]


def test_update_and_delete(client, headers):
    e = add(client, headers)
    r = client.patch(f"/expenses/{e['id']}", json={"amount": "500", "category": "SHOPPING"}, headers=headers)
    assert r.json()["amount"] == "500.00"
    assert r.json()["category"] == "SHOPPING"
    assert r.json()["title"] == "Lunch"  # untouched
    assert client.delete(f"/expenses/{e['id']}", headers=headers).status_code == 204
    assert client.get(f"/expenses/{e['id']}", headers=headers).status_code == 404


def test_monthly_summary(client, headers):
    add(client, headers, amount="100.10", category="FOOD", spent_on="2026-10-01")
    add(client, headers, amount="200.20", category="FOOD", spent_on="2026-10-31")
    add(client, headers, amount="50", category="TRAVEL", spent_on="2026-10-15")
    add(client, headers, amount="999", category="FOOD", spent_on="2026-09-30")  # previous month
    add(client, headers, amount="7", category="FOOD", spent_on="2026-11-01")  # next month

    s = client.get("/expenses/summary", params={"month": "2026-10"}, headers=headers).json()
    assert s["month"] == "2026-10"
    assert s["total"] == "350.30"  # exact decimal arithmetic, no float noise
    assert s["count"] == 3
    assert s["previous_month_total"] == "999.00"
    assert s["by_category"][0] == {"category": "FOOD", "total": "300.30", "count": 2}
    assert s["by_category"][1]["category"] == "TRAVEL"


def test_summary_defaults_to_current_month_and_handles_january(client, headers, clock):
    clock.today = date(2027, 1, 15)
    add(client, headers, amount="10", spent_on="2027-01-02")
    add(client, headers, amount="30", spent_on="2026-12-31")
    s = client.get("/expenses/summary", headers=headers).json()
    assert s["month"] == "2027-01"
    assert s["total"] == "10.00"
    assert s["previous_month_total"] == "30.00"


def test_summary_bad_month(client, headers):
    for bad in ("2026-13", "oct", "2026"):
        assert client.get("/expenses/summary", params={"month": bad}, headers=headers).status_code == 422


def test_empty_summary(client, headers):
    s = client.get("/expenses/summary", params={"month": "2026-10"}, headers=headers).json()
    assert s["total"] == "0.00" and s["count"] == 0 and s["by_category"] == []


def test_users_are_isolated(client, make_headers):
    a, b = make_headers("a@example.com"), make_headers("b@example.com")
    e = add(client, a)
    assert client.get(f"/expenses/{e['id']}", headers=b).status_code == 404
    assert client.patch(f"/expenses/{e['id']}", json={"title": "hacked"}, headers=b).status_code == 404
    assert client.delete(f"/expenses/{e['id']}", headers=b).status_code == 404
    assert client.get("/expenses", headers=b).json() == []
    assert client.get("/expenses/summary", params={"month": "2026-10"}, headers=b).json()["total"] == "0.00"
    assert client.get("/expenses", headers={}).status_code == 401
