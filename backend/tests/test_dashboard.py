from datetime import date


def test_empty_dashboard(client, headers):
    d = client.get("/dashboard", headers=headers).json()
    assert d["bills"]["reminder_count"] == 0
    assert d["bills"]["amount_due"] == "0.00"
    assert d["expenses"]["month_total"] == "0.00"
    assert d["expenses"]["recent"] == []
    assert d["grocery"] == {"remaining": 0, "bought": 0, "estimated_remaining_cost": "0.00"}


def test_dashboard_requires_login(client):
    assert client.get("/dashboard").status_code == 401


def test_dashboard_pulls_all_modules_together(client, headers, clock):
    clock.today = date(2026, 10, 8)
    bill = lambda **o: client.post(
        "/bills",
        json={"name": "Internet", "default_amount": "999", "first_due_date": "2026-10-10", "reminder_days_before": 3, **o},
        headers=headers,
    ).json()
    internet = bill()  # reminder 7th -> DUE today
    bill(name="Milk", default_amount="1500", first_due_date="2026-10-05")  # overdue
    bill(name="Rent", default_amount="8000", first_due_date="2026-10-28")  # upcoming

    d = client.get("/dashboard", headers=headers).json()["bills"]
    assert d["reminder_count"] == 2
    assert d["overdue_count"] == 1
    assert d["amount_due"] == "2499.00"
    assert [r["bill_name"] for r in d["reminders"]] == ["Milk", "Internet"]  # soonest due first
    assert [u["bill_name"] for u in d["upcoming"]] == ["Rent"]
    assert d["paid_this_month"] == "0.00"

    # pay internet: reminder drops, next cycle becomes upcoming, paid total rises
    client.post(
        f"/occurrences/{internet['next_occurrence']['id']}/pay", json={"amount": "1049.50"}, headers=headers
    )
    d = client.get("/dashboard", headers=headers).json()["bills"]
    assert d["reminder_count"] == 1
    assert d["amount_due"] == "1500.00"
    assert d["paid_this_month"] == "1049.50"
    assert "Internet" in [u["bill_name"] for u in d["upcoming"]]  # November cycle

    for title, amount, day in [("A", "100", "2026-10-01"), ("B", "250.50", "2026-10-07"), ("Old", "9", "2026-09-30")]:
        client.post("/expenses", json={"title": title, "amount": amount, "spent_on": day}, headers=headers)
    e = client.get("/dashboard", headers=headers).json()["expenses"]
    assert e["month"] == "2026-10"
    assert e["month_total"] == "350.50"
    assert e["month_count"] == 2
    assert [x["title"] for x in e["recent"]] == ["B", "A", "Old"]

    client.post("/grocery/items", json={"name": "Milk", "estimated_price": "30"}, headers=headers)
    g = client.get("/dashboard", headers=headers).json()["grocery"]
    assert g == {"remaining": 1, "bought": 0, "estimated_remaining_cost": "30.00"}


def test_paused_bill_does_not_nag(client, headers, clock):
    clock.today = date(2026, 10, 9)
    bill = client.post(
        "/bills",
        json={"name": "Old magazine", "default_amount": "100", "first_due_date": "2026-10-10"},
        headers=headers,
    ).json()
    assert client.get("/dashboard", headers=headers).json()["bills"]["reminder_count"] == 1
    client.patch(f"/bills/{bill['id']}", json={"is_active": False}, headers=headers)
    assert client.get("/dashboard", headers=headers).json()["bills"]["reminder_count"] == 0
    assert client.get("/occurrences", params={"status": "REMINDERS"}, headers=headers).json() == []


def test_dashboards_are_isolated(client, make_headers, clock):
    a, b = make_headers("a@example.com"), make_headers("b@example.com")
    client.post("/expenses", json={"title": "x", "amount": "100", "spent_on": "2026-10-01"}, headers=a)
    client.post("/grocery/items", json={"name": "Milk"}, headers=a)
    d = client.get("/dashboard", headers=b).json()
    assert d["expenses"]["month_total"] == "0.00"
    assert d["grocery"]["remaining"] == 0
