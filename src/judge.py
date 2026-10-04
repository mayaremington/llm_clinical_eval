"""LLM-as-judge. Grades every generated note with the same taxonomy you used.

Resumable (skips notes already judged). Invalid JSON is retried once, then logged as parse_error.

    python -m src.judge
    python -m src.judge --mock
"""
from __future__ import annotations

import argparse
import json
import re

from .common import OUT, ROOT, append_jsonl, load_config, load_encounters, read_jsonl, taxonomy_as_text, taxonomy_codes
from .llm import complete


def parse_judge(text: str, valid_codes: set[str]) -> list[dict]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in judge output")
    obj = json.loads(m.group(0))
    out = []
    for e in obj.get("errors", []):
        cat = str(e.get("category", "")).upper().strip()
        sev = int(e.get("severity", 0))
        if cat not in valid_codes or sev not in (1, 2, 3):
            cat = cat if cat in valid_codes else "OTHER"
            sev = min(max(sev, 1), 3)
        out.append({"category": cat, "severity": sev, "note_text": e.get("note_text", ""),
                    "transcript_evidence": e.get("transcript_evidence", ""), "explanation": e.get("explanation", "")})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    cfg = load_config()
    jc = cfg["judge"]
    tpl = (ROOT / jc["prompt"]).read_text()
    tax = taxonomy_as_text()
    codes = set(taxonomy_codes())
    dialogues = load_encounters(cfg).set_index("encounter_id")["dialogue"]

    out_path = OUT / "judge.jsonl"
    done = {(r["system"], r["encounter_id"]) for r in read_jsonl(out_path)}
    notes = [n for n in read_jsonl(OUT / "notes.jsonl") if (n["system"], n["encounter_id"]) not in done]
    if args.limit:
        notes = notes[: args.limit]
    print(f"Judging {len(notes)} notes with {jc['provider']}:{jc['model']}")

    for i, n in enumerate(notes, 1):
        prompt = tpl.format(taxonomy=tax, transcript=dialogues[n["encounter_id"]], note=n["note"])
        provider = "mock" if args.mock else jc["provider"]
        errors, status, raw = [], "ok", ""
        for attempt in range(2):
            r = complete(provider, jc["model"], prompt, temperature=jc.get("temperature", 0.0),
                         max_tokens=jc.get("max_tokens", 3000), base_url=jc.get("base_url"))
            raw = r["text"]
            try:
                errors = parse_judge(raw, codes)
                status = "ok"
                break
            except (ValueError, json.JSONDecodeError) as e:
                status = f"parse_error: {e}"
        append_jsonl(out_path, {"system": n["system"], "encounter_id": n["encounter_id"], "judge_model": jc["model"],
                                "status": status, "errors": errors, "raw": raw if status != "ok" else ""})
        print(f"[{i}/{len(notes)}] {n['system']} {n['encounter_id']}: {len(errors)} errors ({status})")


if __name__ == "__main__":
    main()
