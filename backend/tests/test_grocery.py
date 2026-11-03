def add(client, headers, name="Milk", **over):
    r = client.post("/grocery/items", json={"name": name, "category": "DAIRY", **over}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def items(client, headers, **params):
    return client.get("/grocery/items", params=params, headers=headers).json()


def test_add_with_defaults(client, headers):
    item = add(client, headers, "Tomato", category="VEGETABLES", quantity="2 kg", estimated_price="60")
    assert item["is_bought"] is False
    assert item["bought_at"] is None
    assert item["priority"] == "MEDIUM"
    assert item["estimated_price"] == "60.00"


def test_validation(client, headers):
    assert client.post("/grocery/items", json={"name": ""}, headers=headers).status_code == 422
    r = client.post("/grocery/items", json={"name": "x", "category": "CARS"}, headers=headers)
    assert r.status_code == 422
    r = client.post("/grocery/items", json={"name": "x", "estimated_price": "-5"}, headers=headers)
    assert r.status_code == 422


def test_checkbox_tick_and_untick(client, headers):
    item = add(client, headers)
    r = client.patch(f"/grocery/items/{item['id']}", json={"is_bought": True}, headers=headers)
    assert r.json()["is_bought"] is True
    assert r.json()["bought_at"] is not None
    r = client.patch(f"/grocery/items/{item['id']}", json={"is_bought": False}, headers=headers)  # accidental tick
    assert r.json()["is_bought"] is False
    assert r.json()["bought_at"] is None


def test_filter_bought_and_not_bought(client, headers):
    a = add(client, headers, "Milk")
    add(client, headers, "Curd")
    client.patch(f"/grocery/items/{a['id']}", json={"is_bought": True}, headers=headers)
    assert [i["name"] for i in items(client, headers, bought=True)] == ["Milk"]
    assert [i["name"] for i in items(client, headers, bought=False)] == ["Curd"]
    # not-bought items are listed first, bought ones go to the completed section
    assert [i["name"] for i in items(client, headers)] == ["Curd", "Milk"]


def test_edit_item_fields(client, headers):
    item = add(client, headers, "Rice", category="GRAINS")
    r = client.patch(
        f"/grocery/items/{item['id']}", json={"quantity": "5 kg", "priority": "HIGH", "name": "Basmati"}, headers=headers
    )
    assert r.json()["quantity"] == "5 kg"
    assert r.json()["priority"] == "HIGH"
    assert r.json()["name"] == "Basmati"
    assert r.json()["category"] == "GRAINS"


def test_clear_completed_archives_not_deletes(client, headers):
    a = add(client, headers, "Milk", estimated_price="30")
    add(client, headers, "Curd", estimated_price="20")
    client.patch(f"/grocery/items/{a['id']}", json={"is_bought": True}, headers=headers)

    assert client.post("/grocery/clear-completed", headers=headers).json() == {"archived": 1}
    assert [i["name"] for i in items(client, headers)] == ["Curd"]
    assert [i["name"] for i in items(client, headers, include_archived="true")] == ["Curd", "Milk"]  # still stored
    assert client.post("/grocery/clear-completed", headers=headers).json() == {"archived": 0}


def test_summary(client, headers):
    a = add(client, headers, "Milk", estimated_price="30.50")
    add(client, headers, "Curd", estimated_price="20")
    add(client, headers, "Salt")  # no price
    client.patch(f"/grocery/items/{a['id']}", json={"is_bought": True}, headers=headers)
    s = client.get("/grocery/summary", headers=headers).json()
    assert s == {"remaining": 2, "bought": 1, "estimated_remaining_cost": "20.00"}


def test_delete(client, headers):
    item = add(client, headers)
    assert client.delete(f"/grocery/items/{item['id']}", headers=headers).status_code == 204
    assert items(client, headers) == []


def test_users_are_isolated(client, make_headers):
    a, b = make_headers("a@example.com"), make_headers("b@example.com")
    item = add(client, a)
    assert client.patch(f"/grocery/items/{item['id']}", json={"is_bought": True}, headers=b).status_code == 404
    assert client.delete(f"/grocery/items/{item['id']}", headers=b).status_code == 404
    assert items(client, b) == []
    assert client.post("/grocery/clear-completed", headers=b).json() == {"archived": 0}
    assert client.get("/grocery/items", headers={}).status_code == 401
