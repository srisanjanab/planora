"""Evaluate the categoriser on titles it never trained on.   Run from backend:  python -m app.ml.train
Prints a per-category report and saves app/ml/metrics.json (handy for your README)."""
import json
from pathlib import Path

from sklearn.metrics import accuracy_score, classification_report, f1_score

from app.ml.categorizer import build_pipeline, load_data, load_heldout


def evaluate(hard: bool = False) -> dict:
    train_x, train_y = load_data()
    test_x, test_y = load_heldout(hard)
    model = build_pipeline().fit(train_x, train_y)
    predicted = model.predict([t.lower() for t in test_x])
    return {
        "train_samples": len(train_x),
        "heldout_samples": len(test_x),
        "heldout_accuracy": round(accuracy_score(test_y, predicted), 3),
        "heldout_macro_f1": round(f1_score(test_y, predicted, average="macro"), 3),
        "report": classification_report(test_y, predicted, output_dict=True, zero_division=0),
        "mistakes": [(t, y, p) for t, y, p in zip(test_x, test_y, predicted) if y != p],
    }


if __name__ == "__main__":
    for hard in (False, True):
        m = evaluate(hard)
        print("--- unseen titles with known keywords ---" if not hard else "--- hard: unseen brands and words ---")
        print(f"trained on {m['train_samples']} examples, tested on {m['heldout_samples']} unseen titles")
        print(f"accuracy: {m['heldout_accuracy']}   macro F1: {m['heldout_macro_f1']}")
        for title, truth, guess in m["mistakes"]:
            print(f"  wrong: {title!r}  expected {truth}, got {guess}")
        name = "metrics_hard.json" if hard else "metrics.json"
        Path(__file__).with_name(name).write_text(json.dumps({k: v for k, v in m.items() if k != "mistakes"}, indent=2))
