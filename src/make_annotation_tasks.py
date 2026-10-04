"""Build blinded, shuffled annotation tasks for the annotation tool.

    python -m src.make_annotation_tasks                 # -> annotation/tasks_main.json + key_main.csv
    python -m src.make_annotation_tasks --relabel 15    # Subsequent day: re-label set for intra-rater agreement

Open annotation/annotator.html in a browser and load the tasks JSON.
Don't open the key CSV until you finish annotating.
"""
from __future__ import annotations

import argparse
import json
import secrets

import pandas as pd

from .common import ANN, OUT, load_config, load_encounters, load_taxonomy, load_traps, read_jsonl, seeded_rng


def build(notes: pd.DataFrame, cfg: dict, set_name: str, seed: int) -> None:
    enc = load_encounters(cfg).set_index("encounter_id")
    traps = load_traps(cfg)
    rng = seeded_rng(seed)
    idx = list(notes.index)
    rng.shuffle(idx)

    tasks, key = [], []
    for order, i in enumerate(idx, 1):
        r = notes.loc[i]
        uid = f"{set_name[0].upper()}{secrets.token_hex(3)}"
        t = traps[traps.encounter_id == r.encounter_id]
        tasks.append({
            "uid": uid, "order": order, "encounter_id": r.encounter_id,
            "transcript": enc.loc[r.encounter_id, "dialogue"], "note": r.note,
            "traps": t[["trap_id", "category", "check"]].to_dict("records"),
        })
        key.append({"uid": uid, "system": r.system, "encounter_id": r.encounter_id, "set": set_name})

    tax = load_taxonomy()
    payload = {"set": set_name, "taxonomy_version": tax["version"],
               "categories": [{"code": c["code"], "name": c["name"], "definition": c["definition"].strip()}
                              for c in tax["categories"]],
               "severity": tax["severity"], "tasks": tasks}
    ANN.mkdir(exist_ok=True)
    (ANN / f"tasks_{set_name}.json").write_text(json.dumps(payload, indent=1))
    pd.DataFrame(key).to_csv(ANN / f"key_{set_name}.csv", index=False)
    print(f"Wrote {len(tasks)} tasks to annotation/tasks_{set_name}.json (key: annotation/key_{set_name}.csv)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--relabel", type=int, default=0, help="sample N already-annotated notes for re-labeling")
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args()

    cfg = load_config()
    notes = pd.DataFrame(read_jsonl(OUT / "notes.jsonl"))
    if notes.empty:
        raise SystemExit("No notes found. Run `python -m src.generate` first.")

    if args.relabel:
        main_key = pd.read_csv(ANN / "key_main.csv")
        pick = main_key.sample(n=args.relabel, random_state=args.seed + 1)
        sub = notes.merge(pick[["system", "encounter_id"]], on=["system", "encounter_id"])
        build(sub.reset_index(drop=True), cfg, "relabel", args.seed + 2)
    else:
        if (ANN / "key_main.csv").exists():
            raise SystemExit("annotation/key_main.csv exists; delete it first if you really want to re-randomize.")
        build(notes, cfg, "main", args.seed)


if __name__ == "__main__":
    main()
