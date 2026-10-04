"""Reference-based metrics (ROUGE, optional BERTScore) against ACI-Bench reference notes.

Synthetic ED cases have no reference note, so they are skipped here.

    python -m src.auto_metrics
    python -m src.auto_metrics --bertscore     # needs `pip install bert-score torch` (slow on CPU)
"""
from __future__ import annotations

import argparse
import re

import pandas as pd

from .common import OUT, load_config, load_encounters, read_jsonl


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _ngrams(toks, n):
    return [tuple(toks[i:i + n]) for i in range(len(toks) - n + 1)]


def _f1(p, r):
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def _rouge_n(ref, hyp, n):
    from collections import Counter
    r, h = Counter(_ngrams(ref, n)), Counter(_ngrams(hyp, n))
    overlap = sum((r & h).values())
    return _f1(overlap / max(sum(h.values()), 1), overlap / max(sum(r.values()), 1))


def _rouge_l(ref, hyp):
    # LCS by dynamic programming over tokens (fine for note-length texts)
    prev = [0] * (len(hyp) + 1)
    for a in ref:
        cur = [0]
        for j, b in enumerate(hyp, 1):
            cur.append(prev[j - 1] + 1 if a == b else max(prev[j], cur[j - 1]))
        prev = cur
    lcs = prev[-1]
    return _f1(lcs / max(len(hyp), 1), lcs / max(len(ref), 1))


def rouge_scores(ref: str, hyp: str) -> dict:
    try:  # prefer the standard implementation if installed
        from rouge_score import rouge_scorer
        sc = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True).score(ref, hyp)
        return {"rouge1": sc["rouge1"].fmeasure, "rouge2": sc["rouge2"].fmeasure, "rougeL": sc["rougeL"].fmeasure}
    except ImportError:
        r, h = _tokens(ref), _tokens(hyp)
        return {"rouge1": _rouge_n(r, h, 1), "rouge2": _rouge_n(r, h, 2), "rougeL": _rouge_l(r, h)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bertscore", action="store_true")
    args = ap.parse_args()

    notes = pd.DataFrame(read_jsonl(OUT / "notes.jsonl"))
    refs = load_encounters(load_config())[["encounter_id", "reference_note"]]
    df = notes.merge(refs, on="encounter_id").dropna(subset=["reference_note"])
    rows = [{"system": r.system, "encounter_id": r.encounter_id, **rouge_scores(r.reference_note, r.note),
             "note_words": len(r.note.split())} for r in df.itertuples()]
    out = pd.DataFrame(rows)

    if args.bertscore:
        from bert_score import score
        _, _, f1 = score(df["note"].tolist(), df["reference_note"].tolist(), lang="en", verbose=True)
        out["bertscore_f1"] = f1.numpy()

    out.to_csv(OUT / "auto_metrics.csv", index=False)
    print(out.groupby("system").mean(numeric_only=True).round(3))
    print(f"Saved {OUT / 'auto_metrics.csv'}")


if __name__ == "__main__":
    main()
