from datetime import date

from app.services.insights import linear_forecast


def test_linear_forecast():
    assert linear_forecast([1000, 1000, 1000, 1500]) == 1500
    assert linear_forecast([100, 100, 100]) == 100
    assert linear_forecast([300, 200, 100]) == 0  # never predicts a negative bill


def make_paid_bill(client, headers, clock, amounts, name="Electricity"):
    clock.today = date(2026, 10, 15)
    client.post("/bills", json={"name": name, "type": "ELECTRICITY", "default_amount": "1000", "is_variable": True,
                                "first_due_date": "2026-06-10"}, headers=headers)
    for amount in amounts:
        pending = client.get("/occurrences", params={"status": "OVERDUE"}, headers=headers).json()
        pending = [o for o in pending if o["bill_name"] == name]
        r = client.post(f"/occurrences/{pending[0]['id']}/pay", json={"amount": str(amount)}, headers=headers)
        assert r.status_code == 200, r.text


def test_empty_insights(client, headers):
    d = client.get("/insights", headers=headers).json()
    assert d["highlights"] == [] and d["bills"] == []
    assert d["spending"]["projected_total"] is None and d["spending"]["top_category"] is None


def test_requires_login(client):
    assert client.get("/insights").status_code == 401


def test_bill_forecast_and_unusual_bill_alert(client, headers, clock):
    make_paid_bill(client, headers, clock, [1000, 1000, 1000, 1500])
    d = client.get("/insights", headers=headers).json()
    b = d["bills"][0]
    assert b["bill_name"] == "Electricity" and b["payments_used"] == 4
    assert b["average"] == "1000.00" and b["last_paid"] == "1500.00"
    assert b["forecast_next"] == "1500.00" and b["change_vs_average_pct"] == 50.0
    assert "50% higher" in b["alert"]
    assert b["alert"] in d["highlights"]


def test_normal_bill_has_no_alert(client, headers, clock):
    make_paid_bill(client, headers, clock, [1000, 1050, 1020])
    b = client.get("/insights", headers=headers).json()["bills"][0]
    assert b["alert"] is None


def test_too_little_history_gives_no_forecast(client, headers, clock):
    make_paid_bill(client, headers, clock, [1000, 1000])
    assert client.get("/insights", headers=headers).json()["bills"] == []


def test_month_end_projection_and_category_jump(client, headers, clock):
    clock.today = date(2026, 10, 10)
    add = lambda title, amount, cat, day: client.post(
        "/expenses", json={"title": title, "amount": amount, "category": cat, "spent_on": day}, headers=headers)
    add("Dinners", "2000", "FOOD", "2026-10-02")
    add("Cab", "300", "TRAVEL", "2026-10-03")
    add("Dinners", "1000", "FOOD", "2026-09-05")
    add("Cab", "300", "TRAVEL", "2026-09-06")
    s = client.get("/insights", headers=headers).json()["spending"]
    assert s["spent_so_far"] == "2300.00" and s["last_month_total"] == "1300.00"
    assert s["projected_total"] == "7130.00"  # 2300 / 10 days * 31
    assert s["change_vs_last_month_pct"] == 76.9 and s["top_category"] == "FOOD"
    assert any("Food spending is up 100%" in n for n in s["notes"])


def test_projection_waits_for_enough_days(client, headers, clock):
    clock.today = date(2026, 10, 1)
    client.post("/expenses", json={"title": "x", "amount": "100", "spent_on": "2026-10-01"}, headers=headers)
    assert client.get("/insights", headers=headers).json()["spending"]["projected_total"] is None


def test_insights_are_per_user(client, make_headers, clock):
    a, b = make_headers("a@example.com"), make_headers("b@example.com")
    make_paid_bill(client, a, clock, [1000, 1000, 1000, 2000])
    assert client.get("/insights", headers=b).json()["bills"] == []
