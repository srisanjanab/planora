"""Expense auto-categorisation: TF-IDF text features + logistic regression.

The model is trained from the labelled CSV when first used (takes well under a second), so there is no
binary model file to keep in sync with your scikit-learn version."""
import csv
from functools import lru_cache
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline, make_union

from app.ml.keywords import KEYWORDS

DATA_FILE = Path(__file__).parent / "data" / "expense_titles.csv"
HELDOUT_FILE = Path(__file__).parent / "data" / "heldout.csv"
HARD_FILE = Path(__file__).parent / "data" / "heldout_hard.csv"


def _read(path: Path) -> tuple[list[str], list[str]]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [r["title"] for r in rows], [r["category"] for r in rows]


def load_data() -> tuple[list[str], list[str]]:
    """Hand-written titles plus keyword-based examples ('zomato', 'paid zomato', 'zomato payment')."""
    titles, labels = _read(DATA_FILE)
    for category, words in KEYWORDS.items():
        for w in words:
            for t in (w, f"paid {w}", f"{w} payment"):
                titles.append(t)
                labels.append(category)
    return titles, labels


def load_heldout(hard: bool = False) -> tuple[list[str], list[str]]:
    """Titles the model never trains on. The 'hard' set deliberately uses words and brands that are in
    neither the training titles nor the keyword lexicon, so it shows real-world generalisation."""
    return _read(HARD_FILE if hard else HELDOUT_FILE)


def build_pipeline():
    return make_pipeline(
        make_union(
            # character n-grams cope with typos and brand names: 'swigy', 'zomatto'
            TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True),
            TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True),
        ),
        LogisticRegression(max_iter=1000, C=10, random_state=0),
    )


@lru_cache(maxsize=1)
def get_model():
    titles, labels = load_data()
    return build_pipeline().fit(titles, labels)


def predict(title: str, top_k: int = 3) -> list[tuple[str, float]]:
    """Best categories for a title, most likely first, as (category, probability)."""
    model = get_model()
    probs = model.predict_proba([title.strip().lower()])[0]
    ranked = sorted(zip(model.classes_, probs), key=lambda x: -x[1])[:top_k]
    return [(str(c), round(float(p), 3)) for c, p in ranked]
