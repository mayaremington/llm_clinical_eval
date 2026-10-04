"""Shared helpers: config, taxonomy, encounters, file paths."""
from __future__ import annotations

import json
import random
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"
ANN = ROOT / "annotation"


def load_config(path: str | Path = ROOT / "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_taxonomy() -> dict:
    with open(ROOT / "taxonomy" / "error_taxonomy.yaml") as f:
        return yaml.safe_load(f)


def taxonomy_codes() -> list[str]:
    return [c["code"] for c in load_taxonomy()["categories"]]


def taxonomy_as_text() -> str:
    """Render the taxonomy for inclusion in the judge prompt."""
    tax = load_taxonomy()
    lines = ["Categories:"]
    for c in tax["categories"]:
        lines.append(f"- {c['code']}: {c['definition'].strip()}")
        if c.get("not_this"):
            lines.append(f"  Not this: {c['not_this'].strip()}")
    lines.append("Severity:")
    for s in tax["severity"]:
        lines.append(f"- {s['level']} ({s['name']}): {s['definition'].strip()}")
    return "\n".join(lines)


def load_encounters(cfg: dict) -> pd.DataFrame:
    """Return one row per encounter: encounter_id, source, dialogue, reference_note."""
    d = cfg["data"]
    aci = pd.read_csv(ROOT / d["aci_bench_csv"])
    n = d.get("aci_bench_n")
    if n and n < len(aci):
        aci = aci.sample(n=n, random_state=d.get("seed", 13)).sort_values("encounter_id")
    aci = pd.DataFrame({
        "encounter_id": aci["encounter_id"],
        "source": "aci_bench_" + aci["dataset"],
        "dialogue": aci["dialogue"],
        "reference_note": aci["note"],
    })

    frames = [aci]
    syn_path = d.get("synthetic_ed_yaml")
    if syn_path and (ROOT / syn_path).exists():
        with open(ROOT / syn_path) as f:
            cases = yaml.safe_load(f)
        frames.append(pd.DataFrame({
            "encounter_id": [c["id"] for c in cases],
            "source": "synthetic_ed",
            "dialogue": [c["dialogue"].strip() for c in cases],
            "reference_note": None,
        }))
    return pd.concat(frames, ignore_index=True)


def load_traps(cfg: dict) -> pd.DataFrame:
    syn_path = cfg["data"].get("synthetic_ed_yaml")
    if not syn_path or not (ROOT / syn_path).exists():
        return pd.DataFrame(columns=["encounter_id", "trap_id", "category", "check"])
    with open(ROOT / syn_path) as f:
        cases = yaml.safe_load(f)
    rows = [{"encounter_id": c["id"], "trap_id": t["id"], "category": t["category"], "check": t["check"]}
            for c in cases for t in c.get("traps", [])]
    return pd.DataFrame(rows)


def resolve(p: str | Path) -> Path:
    """Paths in CLI args are relative to the repo root unless absolute."""
    p = Path(p)
    return p if p.is_absolute() else ROOT / p


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def append_jsonl(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")


def seeded_rng(seed: int = 13) -> random.Random:
    return random.Random(seed)
