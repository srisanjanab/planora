"""Pure money maths for trip splitting. Works in integer paise so totals always add up exactly."""
from decimal import Decimal

TWO_DP = Decimal("0.01")


def to_paise(amount: Decimal) -> int:
    return int((Decimal(amount) * 100).to_integral_value())


def from_paise(paise: int) -> Decimal:
    return (Decimal(paise) / 100).quantize(TWO_DP)


def equal_shares(total_paise: int, member_ids: list[int]) -> dict[int, int]:
    """Split evenly; leftover paise go one each to the lowest ids, so shares sum to the total."""
    ids = sorted(member_ids)
    base, extra = divmod(total_paise, len(ids))
    return {m: base + (1 if i < extra else 0) for i, m in enumerate(ids)}


def suggest_settlements(balances: dict[int, int]) -> list[tuple[int, int, int]]:
    """balances: member -> paise (positive = is owed money, negative = owes).
    Returns (debtor, creditor, paise) payments. Greedy: always match the biggest debtor with the
    biggest creditor, which needs at most (people - 1) payments."""
    creditors = {m: b for m, b in balances.items() if b > 0}
    debtors = {m: -b for m, b in balances.items() if b < 0}
    payments = []
    while creditors and debtors:
        c = max(creditors, key=lambda m: (creditors[m], -m))
        d = max(debtors, key=lambda m: (debtors[m], -m))
        pay = min(creditors[c], debtors[d])
        payments.append((d, c, pay))
        creditors[c] -= pay
        debtors[d] -= pay
        if creditors[c] == 0:
            del creditors[c]
        if debtors[d] == 0:
            del debtors[d]
    return payments
