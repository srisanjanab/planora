import pytest

from app.ml.categorizer import load_heldout, predict
from app.ml.train import evaluate


def test_accuracy_on_unseen_titles_stays_high():
    assert evaluate()["heldout_accuracy"] >= 0.9


def test_hard_set_is_a_known_weakness_but_not_random():
    # Brands the model has never seen: we only guard against it getting worse than chance-plus.
    assert evaluate(hard=True)["heldout_accuracy"] >= 0.3


def test_confident_predictions_on_hard_set_are_mostly_right():
    titles, labels = load_heldout(hard=True)
    confident = [(y, predict(t, 1)[0]) for t, y in zip(titles, labels) if predict(t, 1)[0][1] >= 0.5]
    assert confident and sum(y == p[0] for y, p in confident) / len(confident) >= 0.7


@pytest.mark.parametrize("title,expected", [
    ("Swiggy lunch order", "FOOD"), ("Ola ride to office", "TRAVEL"), ("Netflix monthly plan", "ENTERTAINMENT"),
    ("Apollo pharmacy tablets", "HEALTH"), ("Jio recharge 299", "UTILITIES"), ("Udemy python course", "EDUCATION"),
    ("Myntra shirt", "SHOPPING"), ("Birthday gift for mom", "OTHER"),
])
def test_examples(title, expected):
    assert predict(title, 1)[0][0] == expected


def test_probabilities_are_sorted_and_valid():
    ranked = predict("zomato biryani", 3)
    assert len(ranked) == 3
    assert [p for _, p in ranked] == sorted((p for _, p in ranked), reverse=True)
    assert all(0 <= p <= 1 for _, p in ranked)


def test_endpoint_model_suggestion(client, headers):
    r = client.get("/expenses/suggest-category", params={"title": "Swiggy dinner with team"}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["category"] == "FOOD" and body["source"] == "model" and body["confident"] is True
    assert len(body["alternatives"]) == 2


def test_endpoint_learns_from_your_history(client, headers):
    title = "Valorant skins"  # the model alone gets this wrong
    first = client.get("/expenses/suggest-category", params={"title": title}, headers=headers).json()
    client.post("/expenses", json={"title": title, "amount": "500", "category": "ENTERTAINMENT"}, headers=headers)
    again = client.get("/expenses/suggest-category", params={"title": title.upper()}, headers=headers).json()
    assert again == {"category": "ENTERTAINMENT", "confidence": 1.0, "confident": True, "source": "history", "alternatives": []}
    assert first["source"] == "model"


def test_history_is_per_user(client, make_headers):
    a, b = make_headers("a@example.com"), make_headers("b@example.com")
    client.post("/expenses", json={"title": "Weird thing", "amount": "5", "category": "HEALTH"}, headers=a)
    assert client.get("/expenses/suggest-category", params={"title": "Weird thing"}, headers=b).json()["source"] == "model"


def test_endpoint_validation_and_auth(client, headers):
    assert client.get("/expenses/suggest-category", params={"title": ""}, headers=headers).status_code == 422
    assert client.get("/expenses/suggest-category", headers=headers).status_code == 422
    assert client.get("/expenses/suggest-category", params={"title": "x"}).status_code == 401
