from datetime import date


def make_bill(client, headers, **over):
    payload = {
        "name": "Internet",
        "type": "INTERNET",
        "default_amount": "999.00",
        "frequency": "MONTHLY",
        "first_due_date": "2026-10-10",
        "reminder_days_before": 3,
    }
    payload.update(over)
    r = client.post("/bills", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def occurrences(client, headers, **params):
    r = client.get("/occurrences", params=params, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_create_bill_makes_first_occurrence(client, headers):
    bill = make_bill(client, headers)
    occ = bill["next_occurrence"]
    assert occ["due_date"] == "2026-10-10"
    assert occ["reminder_date"] == "2026-10-07"
    assert occ["expected_amount"] == "999.00"


def test_status_changes_with_the_calendar(client, headers, clock):
    make_bill(client, headers)
    clock.today = date(2026, 10, 1)
    assert occurrences(client, headers)[0]["status"] == "UPCOMING"
    clock.today = date(2026, 10, 7)
    assert occurrences(client, headers)[0]["status"] == "DUE"
    clock.today = date(2026, 10, 10)
    assert occurrences(client, headers)[0]["status"] == "DUE"
    clock.today = date(2026, 10, 11)
    assert occurrences(client, headers)[0]["status"] == "OVERDUE"


def test_paying_stops_reminder_and_schedules_next(client, headers, clock):
    make_bill(client, headers)
    clock.today = date(2026, 10, 8)
    reminders = occurrences(client, headers, status="REMINDERS")
    assert len(reminders) == 1

    r = client.post(f"/occurrences/{reminders[0]['id']}/pay", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "PAID"
    assert r.json()["paid_amount"] == "999.00"

    assert occurrences(client, headers, status="REMINDERS") == []  # reminder is gone
    all_cycles = occurrences(client, headers)
    assert [o["due_date"] for o in all_cycles] == ["2026-10-10", "2026-11-10"]
    assert all_cycles[1]["status"] == "UPCOMING"

    clock.today = date(2026, 11, 8)  # next month's reminder appears, only for the new cycle
    reminders = occurrences(client, headers, status="REMINDERS")
    assert [o["due_date"] for o in reminders] == ["2026-11-10"]


def test_cannot_pay_twice_and_next_cycle_created_once(client, headers):
    make_bill(client, headers)
    occ_id = occurrences(client, headers)[0]["id"]
    assert client.post(f"/occurrences/{occ_id}/pay", headers=headers).status_code == 200
    assert client.post(f"/occurrences/{occ_id}/pay", headers=headers).status_code == 409
    assert len(occurrences(client, headers)) == 2


def test_variable_amount_keeps_history_and_template(client, headers):
    bill = make_bill(client, headers, is_variable=True)
    occ_id = bill["next_occurrence"]["id"]
    r = client.post(
        f"/occurrences/{occ_id}/pay",
        json={"amount": "1049.50", "payment_method": "UPI", "note": "txn 123"},
        headers=headers,
    )
    assert r.json()["paid_amount"] == "1049.50"
    assert r.json()["payment_method"] == "UPI"
    assert client.get(f"/bills/{bill['id']}", headers=headers).json()["default_amount"] == "999.00"
    history = client.get(f"/bills/{bill['id']}/occurrences", headers=headers).json()
    assert history[0]["due_date"] == "2026-11-10"  # newest first
    assert history[1]["paid_amount"] == "1049.50"


def test_future_payment_date_rejected(client, headers):
    bill = make_bill(client, headers)
    r = client.post(
        f"/occurrences/{bill['next_occurrence']['id']}/pay", json={"paid_on": "2026-12-01"}, headers=headers
    )
    assert r.status_code == 400


def test_skip_schedules_next(client, headers):
    bill = make_bill(client, headers)
    r = client.post(f"/occurrences/{bill['next_occurrence']['id']}/skip", headers=headers)
    assert r.json()["status"] == "SKIPPED"
    assert len(occurrences(client, headers)) == 2


def test_undo_payment(client, headers):
    bill = make_bill(client, headers)
    occ_id = bill["next_occurrence"]["id"]
    client.post(f"/occurrences/{occ_id}/pay", headers=headers)
    r = client.post(f"/occurrences/{occ_id}/undo", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] in ("UPCOMING", "DUE", "OVERDUE")
    assert r.json()["paid_amount"] is None
    assert len(occurrences(client, headers)) == 1  # auto-created next cycle removed
    assert client.post(f"/occurrences/{occ_id}/pay", headers=headers).status_code == 200  # can pay again
    assert len(occurrences(client, headers)) == 2


def test_cannot_undo_when_later_cycle_is_paid(client, headers):
    bill = make_bill(client, headers)
    first = bill["next_occurrence"]["id"]
    client.post(f"/occurrences/{first}/pay", headers=headers)
    second = occurrences(client, headers)[1]["id"]
    client.post(f"/occurrences/{second}/pay", headers=headers)
    assert client.post(f"/occurrences/{first}/undo", headers=headers).status_code == 409


def test_no_auto_next_then_safety_net(client, headers):
    bill = make_bill(client, headers, auto_create_next=False)
    client.post(f"/occurrences/{bill['next_occurrence']['id']}/pay", headers=headers)
    assert len(occurrences(client, headers)) == 1
    client.patch(f"/bills/{bill['id']}", json={"auto_create_next": True}, headers=headers)
    client.get("/bills", headers=headers)  # listing runs ensure_occurrences
    assert len(occurrences(client, headers)) == 2


def test_update_syncs_pending_cycle_only(client, headers):
    bill = make_bill(client, headers)
    r = client.patch(
        f"/bills/{bill['id']}",
        json={"reminder_days_before": 5, "default_amount": "1100.00"},
        headers=headers,
    )
    occ = r.json()["next_occurrence"]
    assert occ["reminder_date"] == "2026-10-05"
    assert occ["expected_amount"] == "1100.00"


def test_validation(client, headers):
    bad = {"name": "X", "default_amount": "0", "first_due_date": "2026-10-10"}
    assert client.post("/bills", json=bad, headers=headers).status_code == 422
    bad = {"name": "", "default_amount": "10", "first_due_date": "2026-10-10"}
    assert client.post("/bills", json=bad, headers=headers).status_code == 422


def test_delete_bill_removes_history(client, headers):
    bill = make_bill(client, headers)
    assert client.delete(f"/bills/{bill['id']}", headers=headers).status_code == 204
    assert client.get(f"/bills/{bill['id']}", headers=headers).status_code == 404
    assert occurrences(client, headers) == []


def test_users_cannot_see_each_others_bills(client, make_headers):
    a = make_headers("a@example.com")
    b = make_headers("b@example.com")
    bill = make_bill(client, a)
    occ_id = bill["next_occurrence"]["id"]

    assert client.get(f"/bills/{bill['id']}", headers=b).status_code == 404
    assert client.patch(f"/bills/{bill['id']}", json={"name": "hacked"}, headers=b).status_code == 404
    assert client.delete(f"/bills/{bill['id']}", headers=b).status_code == 404
    assert client.get(f"/bills/{bill['id']}/occurrences", headers=b).status_code == 404
    assert client.post(f"/occurrences/{occ_id}/pay", headers=b).status_code == 404
    assert client.post(f"/occurrences/{occ_id}/skip", headers=b).status_code == 404
    assert client.get("/bills", headers=b).json() == []
    assert occurrences(client, b) == []
    assert client.get("/bills", headers={}).status_code == 401
