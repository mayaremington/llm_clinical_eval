"""Generates a note for every (system, encounter) pair.

A system is a model plus a prompt. A system may also set `verify_prompt` to run a
second pass: the model reviews its own draft against the transcript and returns a
corrected note. The draft is saved too, so you can see what the verify pass changed.

Resumable: pairs already in outputs/notes.jsonl are skipped, so you can re-run after a crash.

    python -m src.generate                # real run
    python -m src.generate --mock         # dry run with fake outputs, no API keys
    python -m src.generate --limit 3      # quick smoke test on 3 encounters
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from .common import ROOT, append_jsonl, load_config, load_encounters, read_jsonl, resolve
from .llm import complete


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--mock", action="store_true", help="use the mock provider for every system")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default="outputs/notes.jsonl")
    args = ap.parse_args()

    cfg = load_config(args.config)
    enc = load_encounters(cfg)
    if args.limit:
        enc = enc.head(args.limit)
    out_path = resolve(args.out)
    done = {(r["system"], r["encounter_id"]) for r in read_jsonl(out_path)}
    gen = cfg.get("generation", {})
    kw = {"temperature": gen.get("temperature", 0.0), "max_tokens": gen.get("max_tokens", 2000)}

    todo = [(s, e) for s in cfg["systems"] for e in enc.itertuples() if (s["name"], e.encounter_id) not in done]
    print(f"{len(enc)} encounters x {len(cfg['systems'])} systems; {len(todo)} notes to generate")

    templates: dict[str, str] = {}

    def tpl(path: str) -> str:
        return templates.setdefault(path, (ROOT / path).read_text())

    for i, (sys, e) in enumerate(todo, 1):
        provider = "mock" if args.mock else sys["provider"]
        r = complete(provider, sys["model"], tpl(sys["prompt"]).format(transcript=e.dialogue),
                     base_url=sys.get("base_url"), **kw)
        rec = {
            "system": sys["name"], "provider": provider, "model": sys["model"], "prompt_file": sys["prompt"],
            "encounter_id": e.encounter_id, "source": e.source, "note": r["text"],
            "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"], "latency_s": r["latency_s"],
        }
        if sys.get("verify_prompt"):
            v = complete(provider, sys["model"],
                         tpl(sys["verify_prompt"]).format(transcript=e.dialogue, draft=r["text"]),
                         base_url=sys.get("base_url"), **kw)
            rec.update({
                "draft_note": r["text"], "note": v["text"], "verify_prompt_file": sys["verify_prompt"],
                "input_tokens": (r["input_tokens"] or 0) + (v["input_tokens"] or 0) if r["input_tokens"] is not None else None,
                "output_tokens": (r["output_tokens"] or 0) + (v["output_tokens"] or 0) if r["output_tokens"] is not None else None,
                "latency_s": round(r["latency_s"] + v["latency_s"], 2),
            })
        rec["created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        append_jsonl(out_path, rec)
        print(f"[{i}/{len(todo)}] {sys['name']} {e.encounter_id} ({rec['latency_s']}s)")
    print(f"Done. Notes in {out_path}")


if __name__ == "__main__":
    main()
