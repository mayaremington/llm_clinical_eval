"""Side-by-side review of physician vs judge errors, in the same order as the annotator.

    python -m src.compare_errors              # -> outputs/human_vs_judge.html and .csv

Open the HTML in a browser. Each note shows the agreement status (both / physician only /
judge only / neither), then your errors on the left and the judge's on the right.
judge.jsonl is not modified.
"""
from __future__ import annotations

import html
import json

import pandas as pd

from .common import ANN, OUT, read_jsonl

STATUS = {(1, 1): "both", (1, 0): "physician only (judge missed)", (0, 1): "judge only", (0, 0): "neither"}
COLOR = {"both": "#2e7d32", "physician only (judge missed)": "#c62828", "judge only": "#ef6c00", "neither": "#757575"}


def esc(x) -> str:
    return "" if pd.isna(x) else html.escape(str(x))


def err_html(e: dict, who: str) -> str:
    ev = e.get("transcript_evidence")
    extra = e.get("comment") if who == "human" else e.get("explanation")
    return (f'<div class="err sev{int(e["severity"])}"><b>{esc(e["category"])}</b> · sev {int(e["severity"])}'
            + (f'<div>Note: “{esc(e.get("note_text"))}”</div>' if not pd.isna(e.get("note_text")) and e.get("note_text") else "")
            + (f'<div class="muted">Transcript: “{esc(ev)}”</div>' if not pd.isna(ev) and ev else "")
            + (f'<div class="muted">{esc(extra)}</div>' if not pd.isna(extra) and extra else "")
            + "</div>")


def main() -> None:
    tasks = json.loads((ANN / "tasks_main.json").read_text())["tasks"]
    order = pd.DataFrame([{"uid": t["uid"], "order": t["order"]} for t in tasks])
    key = pd.read_csv(ANN / "key_main.csv")
    hn = pd.read_csv(ANN / "human_notes_main.csv")
    reviewed = hn.loc[hn.reviewed == 1, "uid"]
    base = order.merge(key, on="uid")
    base = base[base.uid.isin(reviewed)].sort_values("order")

    herr = pd.read_csv(ANN / "human_errors_main.csv").merge(key[["uid", "system", "encounter_id"]], on="uid")
    jrecs = {(r["system"], r["encounter_id"]): r for r in read_jsonl(OUT / "judge.jsonl")}

    rows, cards = [], []
    for b in base.itertuples():
        h = herr[herr.uid == b.uid].to_dict("records")
        jr = jrecs.get((b.system, b.encounter_id))
        j = jr["errors"] if jr and jr.get("status") == "ok" else []
        jstatus = jr.get("status") if jr else "missing"
        st = STATUS[(int(bool(h)), int(bool(j)))]
        rows.append({"order": b.order, "uid": b.uid, "system": b.system, "encounter_id": b.encounter_id,
                     "status": st, "n_human": len(h), "n_judge": len(j),
                     "human_categories": "; ".join(f'{e["category"]}({int(e["severity"])})' for e in h),
                     "judge_categories": "; ".join(f'{e["category"]}({int(e["severity"])})' for e in j),
                     "judge_status": jstatus})
        cards.append(f"""<section data-status="{st}"><h2>#{b.order} · {esc(b.encounter_id)} · {esc(b.system)}
 <span class="badge" style="background:{COLOR[st]}">{st}</span>{'' if jstatus == 'ok' else f' <span class="badge" style="background:#555">judge: {esc(jstatus)}</span>'}</h2>
<div class="cols"><div><h3>Physician ({len(h)})</h3>{''.join(err_html(e, 'human') for e in h) or '<div class="muted">No errors.</div>'}</div>
<div><h3>Judge ({len(j)})</h3>{''.join(err_html(e, 'judge') for e in j) or '<div class="muted">No errors.</div>'}</div></div></section>""")

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "human_vs_judge.csv", index=False)
    counts = df.status.value_counts().to_dict()
    buttons = "".join(f'<button onclick="f(\'{s}\')">{s} ({counts.get(s, 0)})</button>' for s in STATUS.values())
    page = f"""<!doctype html><meta charset="utf-8"><title>Physician vs judge</title>
<style>
:root{{color-scheme:light dark}} body{{font:14px/1.45 system-ui,sans-serif;max-width:1200px;margin:auto;padding:16px;background:Canvas;color:CanvasText}}
section{{border:1px solid #8884;border-radius:8px;padding:8px 12px;margin:12px 0}} h2{{font-size:15px;margin:4px 0}} h3{{font-size:13px;margin:6px 0}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:16px}} .err{{border-left:4px solid #999;padding:4px 8px;margin:6px 0;background:#8881}}
.sev2{{border-color:#ef6c00}} .sev3{{border-color:#c62828}} .muted{{opacity:.7}} .badge{{color:#fff;border-radius:10px;padding:1px 8px;font-size:12px}}
button{{margin:2px}}
</style>
<h1>Physician vs judge errors (annotator order)</h1>
<div><button onclick="f('')">all ({len(df)})</button>{buttons}</div>
{''.join(cards)}
<script>function f(s){{document.querySelectorAll('section').forEach(e=>e.style.display=!s||e.dataset.status===s?'':'none')}}</script>"""
    (OUT / "human_vs_judge.html").write_text(page)
    print(f"Wrote outputs/human_vs_judge.html and .csv ({len(df)} notes): {counts}")


if __name__ == "__main__":
    main()
