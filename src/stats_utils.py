"""Statistics and data-shaping helpers used by the analysis notebook."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import binomtest, norm
from sklearn.metrics import cohen_kappa_score

from .common import ANN, OUT, read_jsonl, taxonomy_codes

# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_human(set_name: str = "main", ann_dir=ANN) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (notes, errors, traps) for an annotation set, unblinded via the key file."""
    key = pd.read_csv(ANN / f"key_{set_name}.csv")
    notes = pd.read_csv(ann_dir / f"human_notes_{set_name}.csv").merge(key, on="uid")
    notes = notes[notes.reviewed == 1]
    errs = pd.read_csv(ann_dir / f"human_errors_{set_name}.csv").merge(key, on="uid")
    errs = errs[errs.uid.isin(notes.uid)]
    tp = ann_dir / f"human_traps_{set_name}.csv"
    traps = pd.read_csv(tp).merge(key, on="uid") if tp.exists() and tp.stat().st_size > 30 else pd.DataFrame(
        columns=["uid", "trap_id", "result", "system", "encounter_id"])
    return notes, errs, traps


def load_judge() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (judged_notes, judge_errors) in long format."""
    recs = read_jsonl(OUT / "judge.jsonl")
    notes = pd.DataFrame([{k: r[k] for k in ("system", "encounter_id", "status")} for r in recs])
    errs = pd.DataFrame([{"system": r["system"], "encounter_id": r["encounter_id"], **e}
                         for r in recs if r["status"] == "ok" for e in r["errors"]],
                        columns=["system", "encounter_id", "category", "severity", "note_text",
                                 "transcript_evidence", "explanation"])
    return notes, errs


def note_level(notes: pd.DataFrame, errs: pd.DataFrame) -> pd.DataFrame:
    """One row per (system, encounter): any_error, any_critical, n_errors, and per-category flags.

    A reviewed note with no error rows is a genuine zero.
    """
    base = notes[["system", "encounter_id"]].drop_duplicates().copy()
    e = errs.copy()
    e["crit"] = (e.severity >= 3).astype(int)
    g = e.groupby(["system", "encounter_id"])
    agg = pd.DataFrame({"n_errors": g.size(), "n_critical": g.crit.sum()}).reset_index()
    out = base.merge(agg, how="left", on=["system", "encounter_id"]).fillna({"n_errors": 0, "n_critical": 0})
    out["any_error"] = (out.n_errors > 0).astype(int)
    out["any_critical"] = (out.n_critical > 0).astype(int)
    for code in taxonomy_codes():
        has = e[e.category == code].groupby(["system", "encounter_id"]).size().rename(f"cat_{code}")
        out = out.merge(has, how="left", on=["system", "encounter_id"])
        out[f"cat_{code}"] = (out[f"cat_{code}"].fillna(0) > 0).astype(int)
    return out


# ---------------------------------------------------------------------------
# Intervals and tests
# ---------------------------------------------------------------------------

def wilson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float, float]:
    if n == 0:
        return np.nan, np.nan, np.nan
    z = norm.ppf(1 - alpha / 2)
    p = k / n
    d = 1 + z ** 2 / n
    c = (p + z ** 2 / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def bootstrap_mean_ci(x, n_boot: int = 5000, alpha: float = 0.05, seed: int = 0):
    x = np.asarray(x, dtype=float)
    rng = np.random.default_rng(seed)
    boots = rng.choice(x, size=(n_boot, len(x)), replace=True).mean(axis=1)
    return x.mean(), np.quantile(boots, alpha / 2), np.quantile(boots, 1 - alpha / 2)


def paired(df: pd.DataFrame, a: str, b: str, col: str) -> pd.DataFrame:
    """Wide table of `col` for systems a and b on encounters both were evaluated on."""
    w = df[df.system.isin([a, b])].pivot_table(index="encounter_id", columns="system", values=col)
    return w.dropna()[[a, b]]


def paired_diff_ci(x_ref, x_new, n_boot: int = 5000, alpha: float = 0.05, seed: int = 0):
    """Difference new - ref in means, with paired (encounter-level) bootstrap CI."""
    d = np.asarray(x_new, float) - np.asarray(x_ref, float)
    return bootstrap_mean_ci(d, n_boot, alpha, seed)


def mcnemar_exact(x_ref, x_new) -> dict:
    x_ref, x_new = np.asarray(x_ref, int), np.asarray(x_new, int)
    b = int(((x_ref == 1) & (x_new == 0)).sum())   # ref worse
    c = int(((x_ref == 0) & (x_new == 1)).sum())   # new worse
    p = binomtest(b, b + c, 0.5).pvalue if b + c else 1.0
    return {"ref_only": b, "new_only": c, "p_value": p}


def noninferiority(x_ref, x_new, margin: float, alpha: float = 0.05, n_boot: int = 5000) -> dict:
    """Error-rate endpoint (lower is better). Non-inferior if upper bound of the
    (1 - 2*alpha) CI for (new - ref) is below the margin."""
    est, lo, hi = paired_diff_ci(x_ref, x_new, n_boot=n_boot, alpha=2 * alpha)
    return {"diff_new_minus_ref": est, "ci_low": lo, "ci_high": hi, "ci_level": 1 - 2 * alpha,
            "margin": margin, "noninferior": bool(hi < margin)}


def decide(x_ref, x_new, hypothesis: str, margin: float = 0.10, alpha: float = 0.05, n_boot: int = 5000) -> dict:
    """Pre-specified one-sided test on an error-rate endpoint (lower is better).

    superiority:    candidate better if the upper bound of the (1 - 2*alpha) paired CI for (new - ref) < 0
    noninferiority: candidate acceptable if that upper bound < margin
    """
    if hypothesis not in ("superiority", "noninferiority"):
        raise ValueError("hypothesis must be 'superiority' or 'noninferiority'")
    threshold = 0.0 if hypothesis == "superiority" else margin
    est, lo, hi = paired_diff_ci(x_ref, x_new, n_boot=n_boot, alpha=2 * alpha)
    return {"hypothesis": hypothesis, "diff_new_minus_ref": est, "ci_low": lo, "ci_high": hi,
            "ci_level": 1 - 2 * alpha, "threshold": threshold, "met": bool(hi < threshold)}


# ---------------------------------------------------------------------------
# Agreement
# ---------------------------------------------------------------------------

def agreement(human, judge) -> dict:
    """Binary agreement with the human as reference standard."""
    h, j = np.asarray(human, int), np.asarray(judge, int)
    tp, fp = int(((h == 1) & (j == 1)).sum()), int(((h == 0) & (j == 1)).sum())
    fn, tn = int(((h == 1) & (j == 0)).sum()), int(((h == 0) & (j == 0)).sum())
    sens = wilson(tp, tp + fn)
    ppv = wilson(tp, tp + fp)
    spec = wilson(tn, tn + fp)
    kappa = cohen_kappa_score(h, j) if len(set(h) | set(j)) > 1 else np.nan
    return {"n": len(h), "prevalence": h.mean() if len(h) else np.nan, "kappa": kappa,
            "sensitivity": sens[0], "sens_lo": sens[1], "sens_hi": sens[2],
            "ppv": ppv[0], "ppv_lo": ppv[1], "ppv_hi": ppv[2], "specificity": spec[0],
            "tp": tp, "fp": fp, "fn": fn, "tn": tn}
