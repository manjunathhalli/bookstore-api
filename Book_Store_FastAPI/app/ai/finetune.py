"""Feature 11 — Fine-tuning: a small classifier trained on this store's own data.

Every other AI feature in this app hands a general-purpose model fresh
instructions or data on *every single call* — a system prompt (Features 1-3,
8-9), retrieved rows (RAG, Feature 5b), or a tool result (the Agent/LangGraph
chatbots). None of them change the model itself. Fine-tuning is the different
move: keep training a pretrained representation — just a small classifier head
here — on labelled examples from this specific business, so the "knowledge"
lives in the model's weights instead of being re-supplied every request.

Pipeline: the same local embedding model semantic search already uses (no API
key, no network call, no torch) turns each review into a vector; a scikit-learn
logistic regression head is trained on those vectors against the store's OWN
ground truth — a review's star rating (>=4 Positive, ==3 Neutral, <=2
Negative) — not the zero-shot LLM's own guess from Feature 1, so the
side-by-side comparison in the UI is honest. Training and inference are both
local and instant; the trained model is cached to disk and reused until
retrained.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ai import AIError, ClaudeService
from app.feedback.models import Feedback

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "sentiment_finetuned.joblib"
META_PATH = ARTIFACT_DIR / "sentiment_finetuned.json"

LABELS = ("Negative", "Neutral", "Positive")
MIN_PER_CLASS = 3  # below this, training is refused outright
HOLDOUT_PER_CLASS = 6  # at/above this, hold out a test split instead of grading on train data

_model = None  # module-level cache: load once, reuse across requests


def _label_from_rating(rating: int) -> str:
    """The store's own ground truth — what the customer actually rated."""
    if rating >= 4:
        return "Positive"
    if rating == 3:
        return "Neutral"
    return "Negative"


def _examples(db: Session) -> list[tuple[str, str]]:
    rows = db.execute(
        select(Feedback.feedback, Feedback.rating).where(Feedback.feedback.isnot(None))
    ).all()
    return [(r.feedback, _label_from_rating(r.rating)) for r in rows if r.feedback]


def dataset_stats(db: Session) -> dict:
    """How much labelled training data this store currently has."""
    examples = _examples(db)
    counts = {label: 0 for label in LABELS}
    for _, label in examples:
        counts[label] += 1
    ready = all(counts[label] >= MIN_PER_CLASS for label in LABELS)
    return {
        "total": len(examples),
        "counts": counts,
        "ready": ready,
        "min_per_class": MIN_PER_CLASS,
    }


def finetuned_enabled() -> bool:
    return MODEL_PATH.exists()


def metadata() -> dict | None:
    """Metadata from the last successful training run, if any."""
    if not META_PATH.exists():
        return None
    try:
        return json.loads(META_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _load_model():
    global _model
    if _model is None and MODEL_PATH.exists():
        import joblib

        _model = joblib.load(MODEL_PATH)
    return _model


def train(claude: ClaudeService, db: Session) -> dict:
    """Fine-tune (train) the local classifier on this store's own reviews.

    Raises ``ValueError`` — with a message safe to show the admin — when there
    isn't enough labelled data yet, or the embedding backend is unavailable.
    """
    stats = dataset_stats(db)
    if not stats["ready"]:
        raise ValueError(
            f"Need at least {MIN_PER_CLASS} reviews per sentiment "
            f"(Positive/Neutral/Negative) to fine-tune — currently have "
            f"{stats['counts']}."
        )

    examples = _examples(db)
    texts = [text for text, _ in examples]
    labels = [label for _, label in examples]

    try:
        vectors = claude.embed_many(texts)
    except AIError as exc:
        raise ValueError(str(exc)) from exc

    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import confusion_matrix
    from sklearn.model_selection import train_test_split
    import joblib

    # Only hold out a test split once every class has enough rows to survive
    # a stratified split; otherwise report train accuracy/confusion and say so.
    indices = list(range(len(examples)))
    holdout = all(count >= HOLDOUT_PER_CLASS for count in stats["counts"].values())
    if holdout:
        idx_train, idx_test = train_test_split(
            indices, test_size=0.25, random_state=42, stratify=labels
        )
    else:
        idx_train = idx_test = indices  # train accuracy/confusion only — small dataset

    x_train = [vectors[i] for i in idx_train]
    y_train = [labels[i] for i in idx_train]
    x_test = [vectors[i] for i in idx_test]
    y_test = [labels[i] for i in idx_test]

    clf = LogisticRegression(max_iter=1000)
    clf.fit(x_train, y_train)
    y_pred = clf.predict(x_test)
    accuracy = clf.score(x_test, y_test)

    cm = confusion_matrix(y_test, y_pred, labels=list(LABELS))
    confusion = {
        true_label: {pred_label: int(cm[i][j]) for j, pred_label in enumerate(LABELS)}
        for i, true_label in enumerate(LABELS)
    }
    per_class_recall = {}
    for i, label in enumerate(LABELS):
        row_total = int(cm[i].sum())
        per_class_recall[label] = round(float(cm[i][i] / row_total), 4) if row_total else None

    # Every example that went into this run, tagged by which split it landed
    # in — "test" only exists when `holdout` is true, otherwise everything
    # trained (and was graded on) the same rows.
    test_positions = set(idx_test) if holdout else set()
    example_rows = [
        {"text": text, "label": label, "split": "test" if i in test_positions else "train"}
        for i, (text, label) in enumerate(examples)
    ]

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, MODEL_PATH)
    meta = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "n_examples": len(examples),
        "counts": stats["counts"],
        "accuracy": round(float(accuracy), 4),
        "holdout": holdout,
        "confusion": confusion,
        "per_class_recall": per_class_recall,
        "examples": example_rows,
    }
    META_PATH.write_text(json.dumps(meta))

    global _model
    _model = clf
    return meta


def predict(claude: ClaudeService, text: str) -> dict | None:
    """Predict with the fine-tuned local classifier (``None`` if not trained yet)."""
    clf = _load_model()
    if clf is None:
        return None
    vector = claude.embed(text)
    label = str(clf.predict([vector])[0])
    proba = dict(zip(clf.classes_, clf.predict_proba([vector])[0]))
    return {"label": label, "confidence": round(float(proba.get(label, 0.0)), 4)}
