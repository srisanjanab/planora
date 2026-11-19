from decimal import Decimal

from app.services.splits import equal_shares, from_paise, suggest_settlements, to_paise


def test_paise_round_trip():
    assert to_paise(Decimal("4000.00")) == 400000
    assert to_paise(Decimal("0.07")) == 7
    assert from_paise(100050) == Decimal("1000.50")


def test_equal_split_four_friends():
    assert equal_shares(400000, [1, 2, 3, 4]) == {1: 100000, 2: 100000, 3: 100000, 4: 100000}


def test_equal_split_leftover_paise_always_adds_up():
    shares = equal_shares(10000, [3, 1, 2])  # Rs 100 among 3
    assert sum(shares.values()) == 10000
    assert shares == {1: 3334, 2: 3333, 3: 3333}
    assert sum(equal_shares(1, [1, 2, 3]).values()) == 1  # a single paisa still adds up


def test_suggest_settlements_simple():
    # A paid 4000 for four: A is owed 3000, B, C, D owe 1000 each
    pays = suggest_settlements({1: 300000, 2: -100000, 3: -100000, 4: -100000})
    assert sorted(pays) == [(2, 1, 100000), (3, 1, 100000), (4, 1, 100000)]


def test_suggest_settlements_minimises_and_balances_out():
    balances = {1: 5000, 2: 3000, 3: -4000, 4: -4000}
    pays = suggest_settlements(balances)
    assert len(pays) <= 3  # at most people - 1
    net = dict.fromkeys(balances, 0)
    for debtor, creditor, amount in pays:
        net[debtor] += amount
        net[creditor] -= amount
    assert all(net[m] == -balances[m] for m in balances)  # everyone ends at zero


def test_suggest_settlements_nothing_to_do():
    assert suggest_settlements({1: 0, 2: 0}) == []
