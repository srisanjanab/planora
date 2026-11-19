from datetime import date


def make_trip(client, headers, **over):
    payload = {"name": "Goa", "destination": "Goa", "start_date": "2026-12-20", "end_date": "2026-12-25",
               "member_names": ["Ravi", "Sita", "Kiran"]}
    payload.update(over)
    r = client.post("/trips", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def ids(trip):
    return {m["display_name"]: m["id"] for m in trip["members"]}


def expense(client, headers, trip_id, **over):
    payload = {"title": "Hotel", "amount": "4000", "category": "TRAVEL"}
    payload.update(over)
    return client.post(f"/trips/{trip_id}/expenses", json=payload, headers=headers)


def report(client, headers, trip_id):
    return client.get(f"/trips/{trip_id}/settlement", headers=headers).json()


def balances(rep):
    return {b["name"]: b["balance"] for b in rep["balances"]}


# ---------- trip basics ----------

def test_create_trip_adds_you_and_friends(client, headers):
    trip = make_trip(client, headers)
    assert [m["display_name"] for m in trip["members"]] == ["T", "Ravi", "Sita", "Kiran"]
    assert trip["members"][0]["user_id"] is not None
    assert trip["status"] == "UPCOMING"
    assert trip["total_spent"] == "0.00"


def test_trip_validation(client, headers):
    bad = {"name": "X", "start_date": "2026-12-25", "end_date": "2026-12-20"}
    assert client.post("/trips", json=bad, headers=headers).status_code == 422
    r = client.post("/trips", json={"name": "X", "start_date": "2026-12-20", "end_date": "2026-12-21",
                                    "member_names": ["Ravi", "ravi"]}, headers=headers)
    assert r.status_code == 400  # duplicate names would be confusing in splits


def test_status_follows_the_calendar(client, headers, clock):
    trip = make_trip(client, headers)
    clock.today = date(2026, 12, 22)
    assert client.get(f"/trips/{trip['id']}", headers=headers).json()["status"] == "ONGOING"
    clock.today = date(2026, 12, 26)
    assert client.get(f"/trips/{trip['id']}", headers=headers).json()["status"] == "PAST"


def test_update_and_delete(client, headers):
    trip = make_trip(client, headers)
    r = client.patch(f"/trips/{trip['id']}", json={"budget": "50000", "name": "Goa 2026"}, headers=headers)
    assert r.json()["budget"] == "50000.00" and r.json()["name"] == "Goa 2026"
    r = client.patch(f"/trips/{trip['id']}", json={"end_date": "2026-12-01"}, headers=headers)
    assert r.status_code == 400
    assert client.delete(f"/trips/{trip['id']}", headers=headers).status_code == 204
    assert client.get(f"/trips/{trip['id']}", headers=headers).status_code == 404


def test_members_add_and_remove(client, headers):
    trip = make_trip(client, headers, member_names=[])
    r = client.post(f"/trips/{trip['id']}/members", json={"display_name": "Meena"}, headers=headers)
    assert r.status_code == 201
    assert client.post(f"/trips/{trip['id']}/members", json={"display_name": "meena"}, headers=headers).status_code == 400
    assert client.delete(f"/trips/{trip['id']}/members/{r.json()['id']}", headers=headers).status_code == 204
    me = trip["members"][0]["id"]
    assert client.delete(f"/trips/{trip['id']}/members/{me}", headers=headers).status_code == 409  # not yourself


def test_cannot_remove_member_with_expenses(client, headers):
    trip = make_trip(client, headers)
    m = ids(trip)
    expense(client, headers, trip["id"], paid_by_member_id=m["Ravi"])
    assert client.delete(f"/trips/{trip['id']}/members/{m['Sita']}", headers=headers).status_code == 409


# ---------- itinerary & tickets ----------

def test_itinerary_sorted_and_within_dates(client, headers):
    trip = make_trip(client, headers)
    base = f"/trips/{trip['id']}/itinerary"
    client.post(base, json={"day": "2026-12-21", "time": "18:00", "title": "Beach sunset"}, headers=headers)
    client.post(base, json={"day": "2026-12-20", "time": "10:00", "title": "Check in", "location": "Hotel"}, headers=headers)
    client.post(base, json={"day": "2026-12-21", "time": "09:00", "title": "Breakfast"}, headers=headers)
    assert [i["title"] for i in client.get(base, headers=headers).json()] == ["Check in", "Breakfast", "Beach sunset"]
    assert client.post(base, json={"day": "2027-01-10", "title": "Too late"}, headers=headers).status_code == 400
    item = client.get(base, headers=headers).json()[0]
    assert client.delete(f"{base}/{item['id']}", headers=headers).status_code == 204


def test_tickets(client, headers):
    trip = make_trip(client, headers)
    base = f"/trips/{trip['id']}/tickets"
    r = client.post(base, json={"type": "FLIGHT", "provider": "IndiGo", "booking_ref": "ABC123",
                                "cost": "5600", "starts_at": "2026-12-20T06:30:00"}, headers=headers)
    assert r.status_code == 201 and r.json()["cost"] == "5600.00"
    assert client.post(base, json={"type": "SPACESHIP"}, headers=headers).status_code == 422
    assert len(client.get(base, headers=headers).json()) == 1
    assert client.delete(f"{base}/{r.json()['id']}", headers=headers).status_code == 204


# ---------- splitting ----------

def test_equal_split_hotel_example_from_the_spec(client, headers):
    """A pays 4000 for A, B, C, D -> each share 1000; B, C, D owe A 1000 each."""
    trip = make_trip(client, headers)
    m = ids(trip)
    r = expense(client, headers, trip["id"], paid_by_member_id=m["T"])
    assert r.status_code == 201
    assert [s["share_amount"] for s in r.json()["shares"]] == ["1000.00"] * 4
    rep = report(client, headers, trip["id"])
    assert balances(rep) == {"T": "3000.00", "Ravi": "-1000.00", "Sita": "-1000.00", "Kiran": "-1000.00"}
    assert rep["total_spent"] == "4000.00"
    pays = {(p["from_name"], p["to_name"], p["amount"]) for p in rep["suggested_payments"]}
    assert pays == {("Ravi", "T", "1000.00"), ("Sita", "T", "1000.00"), ("Kiran", "T", "1000.00")}


def test_equal_split_with_subset_and_odd_amount(client, headers):
    trip = make_trip(client, headers)
    m = ids(trip)
    r = expense(client, headers, trip["id"], title="Cab", amount="100.00", paid_by_member_id=m["Ravi"],
                participant_ids=[m["T"], m["Ravi"], m["Sita"]])
    shares = [s["share_amount"] for s in r.json()["shares"]]
    assert sorted(shares) == ["33.33", "33.33", "33.34"]  # adds up to exactly 100.00
    rep = report(client, headers, trip["id"])
    assert sum(float(b["balance"]) for b in rep["balances"]) == 0
    assert balances(rep)["Kiran"] == "0.00"  # was not part of it


def test_custom_split(client, headers):
    trip = make_trip(client, headers)
    m = ids(trip)
    r = expense(client, headers, trip["id"], title="Dinner", amount="1500", paid_by_member_id=m["Sita"],
                split_type="CUSTOM",
                shares=[{"member_id": m["T"], "amount": "200"}, {"member_id": m["Sita"], "amount": "800"},
                        {"member_id": m["Kiran"], "amount": "500"}])
    assert r.status_code == 201
    assert balances(report(client, headers, trip["id"])) == {
        "T": "-200.00", "Ravi": "0.00", "Sita": "700.00", "Kiran": "-500.00"}


def test_custom_split_must_add_up(client, headers):
    trip = make_trip(client, headers)
    m = ids(trip)
    r = expense(client, headers, trip["id"], amount="1500", paid_by_member_id=m["T"], split_type="CUSTOM",
                shares=[{"member_id": m["T"], "amount": "700"}, {"member_id": m["Ravi"], "amount": "700"}])
    assert r.status_code == 400 and "1400.00" in r.json()["detail"]
    assert report(client, headers, trip["id"])["total_spent"] == "0.00"  # nothing was saved


def test_expense_validation(client, headers):
    trip = make_trip(client, headers)
    m = ids(trip)
    assert expense(client, headers, trip["id"], paid_by_member_id=9999).status_code == 400
    assert expense(client, headers, trip["id"], paid_by_member_id=m["T"], participant_ids=[9999]).status_code == 400
    assert expense(client, headers, trip["id"], paid_by_member_id=m["T"], participant_ids=[]).status_code == 400
    assert expense(client, headers, trip["id"], paid_by_member_id=m["T"], split_type="CUSTOM").status_code == 400
    assert expense(client, headers, trip["id"], paid_by_member_id=m["T"], amount="0").status_code == 422
    dup = [{"member_id": m["T"], "amount": "2000"}, {"member_id": m["T"], "amount": "2000"}]
    assert expense(client, headers, trip["id"], paid_by_member_id=m["T"], split_type="CUSTOM", shares=dup).status_code == 400


def test_settling_up_brings_balances_to_zero(client, headers):
    trip = make_trip(client, headers)
    m = ids(trip)
    expense(client, headers, trip["id"], paid_by_member_id=m["T"])
    for friend in ("Ravi", "Sita", "Kiran"):
        r = client.post(f"/trips/{trip['id']}/settlements",
                        json={"from_member_id": m[friend], "to_member_id": m["T"], "amount": "1000"}, headers=headers)
        assert r.status_code == 201 and r.json()["from_name"] == friend
    rep = report(client, headers, trip["id"])
    assert set(balances(rep).values()) == {"0.00"}
    assert rep["suggested_payments"] == []


def test_partial_settlement_and_undo(client, headers):
    trip = make_trip(client, headers)
    m = ids(trip)
    expense(client, headers, trip["id"], paid_by_member_id=m["T"])
    st = client.post(f"/trips/{trip['id']}/settlements",
                     json={"from_member_id": m["Ravi"], "to_member_id": m["T"], "amount": "400"}, headers=headers).json()
    assert balances(report(client, headers, trip["id"]))["Ravi"] == "-600.00"
    assert len(client.get(f"/trips/{trip['id']}/settlements", headers=headers).json()) == 1
    client.delete(f"/trips/{trip['id']}/settlements/{st['id']}", headers=headers)
    assert balances(report(client, headers, trip["id"]))["Ravi"] == "-1000.00"


def test_settlement_validation(client, headers):
    trip = make_trip(client, headers)
    m = ids(trip)
    url = f"/trips/{trip['id']}/settlements"
    assert client.post(url, json={"from_member_id": m["T"], "to_member_id": m["T"], "amount": "5"}, headers=headers).status_code == 400
    assert client.post(url, json={"from_member_id": m["T"], "to_member_id": 9999, "amount": "5"}, headers=headers).status_code == 400
    assert client.post(url, json={"from_member_id": m["T"], "to_member_id": m["Ravi"], "amount": "-5"}, headers=headers).status_code == 422


def test_multiple_payers_balance_out(client, headers):
    trip = make_trip(client, headers)
    m = ids(trip)
    expense(client, headers, trip["id"], title="Hotel", amount="4000", paid_by_member_id=m["T"])
    expense(client, headers, trip["id"], title="Food", amount="2000", paid_by_member_id=m["Ravi"])
    expense(client, headers, trip["id"], title="Fuel", amount="1200", paid_by_member_id=m["Sita"])
    rep = report(client, headers, trip["id"])
    assert rep["total_spent"] == "7200.00"
    assert abs(sum(float(b["balance"]) for b in rep["balances"])) < 0.001
    # following the suggested payments leaves everybody at zero
    bal = {b["member_id"]: float(b["balance"]) for b in rep["balances"]}
    for p in rep["suggested_payments"]:
        bal[p["from_member_id"]] += float(p["amount"])
        bal[p["to_member_id"]] -= float(p["amount"])
    assert all(abs(v) < 0.001 for v in bal.values())


def test_delete_expense_updates_balances(client, headers):
    trip = make_trip(client, headers)
    m = ids(trip)
    e = expense(client, headers, trip["id"], paid_by_member_id=m["T"]).json()
    assert client.delete(f"/trips/{trip['id']}/expenses/{e['id']}", headers=headers).status_code == 204
    assert client.get(f"/trips/{trip['id']}/expenses", headers=headers).json() == []
    assert set(balances(report(client, headers, trip["id"])).values()) == {"0.00"}


def test_trip_list_and_dashboard_card(client, headers, clock):
    clock.today = date(2026, 12, 1)
    trip = make_trip(client, headers)
    make_trip(client, headers, name="Old trip", start_date="2026-01-01", end_date="2026-01-05")
    expense(client, headers, trip["id"], amount="1000", paid_by_member_id=trip["members"][0]["id"])
    listing = client.get("/trips", headers=headers).json()
    assert [t["name"] for t in listing] == ["Goa", "Old trip"]  # newest first
    assert listing[0]["total_spent"] == "1000.00" and listing[0]["member_count"] == 4
    card = client.get("/dashboard", headers=headers).json()["trips"]["upcoming"]
    assert [t["name"] for t in card] == ["Goa"]  # past trips are not shown


def test_expense_list_newest_first(client, headers):
    trip = make_trip(client, headers)
    me = trip["members"][0]["id"]
    expense(client, headers, trip["id"], title="A", spent_on="2026-12-20", paid_by_member_id=me)
    expense(client, headers, trip["id"], title="B", spent_on="2026-12-22", paid_by_member_id=me)
    assert [e["title"] for e in client.get(f"/trips/{trip['id']}/expenses", headers=headers).json()] == ["B", "A"]


# ---------- security ----------

def test_users_cannot_touch_each_others_trips(client, make_headers):
    a, b = make_headers("a@example.com"), make_headers("b@example.com")
    trip = make_trip(client, a)
    t = trip["id"]
    m = ids(trip)
    exp = expense(client, a, t, paid_by_member_id=m["T"]).json()
    urls = [("get", f"/trips/{t}"), ("get", f"/trips/{t}/expenses"), ("get", f"/trips/{t}/settlement"),
            ("get", f"/trips/{t}/itinerary"), ("get", f"/trips/{t}/tickets"), ("get", f"/trips/{t}/settlements"),
            ("delete", f"/trips/{t}"), ("delete", f"/trips/{t}/expenses/{exp['id']}")]
    for method, url in urls:
        assert getattr(client, method)(url, headers=b).status_code == 404, url
    assert client.post(f"/trips/{t}/members", json={"display_name": "Spy"}, headers=b).status_code == 404
    assert expense(client, b, t, paid_by_member_id=m["T"]).status_code == 404
    assert client.get("/trips", headers=b).json() == []
    assert client.get(f"/trips/{t}", headers={}).status_code == 401
