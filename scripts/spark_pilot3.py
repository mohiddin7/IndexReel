"""Spark pilot 3: overlays masked, order swapped, stricter "same event". Protocol: eval/spark-pilot3.md (frozen before the first call).

  python scripts/spark_pilot3.py clips      mask the top and bottom 13% of every source, then rebuild the edits (needs data/spark_pilot2/raw)
  python scripts/spark_pilot3.py run        needs MODEL_API_KEY in my shell; 56 pairs, each in both orders, about $2.3; resumes
  python scripts/spark_pilot3.py report     score the pass bar

Reuses the clip recipes and the Spark call from spark_pilot2.py. Media stays in data/spark_pilot3 (ignored by git).
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import spark_pilot2 as p

D = Path(__file__).resolve().parents[1] / "data" / "spark_pilot3"
p.D, p.C = D, D / "clips"
MASK = ",drawbox=y=0:w=iw:h=ih*0.13:color=black:t=fill,drawbox=y=ih*0.87:w=iw:h=ih*0.13:color=black:t=fill"
PROMPT = """You are shown two short videos, A and B. Answer with JSON only, no other text. Judge the picture and the sound, not any text drawn on the screen.
same_footage: does either video contain footage from the same original camera recording as the other? It may be re-encoded, resized, cropped, mirrored, sped up, overlaid, given other music, or only partly reused. yes, no or unsure.
same_event: do they show the same real-world occurrence at overlapping moments? Answer yes only if you can name a specific detail that both videos show (the same landmarks or place, the same light path and timing). A similar kind of event, such as another meteor or another rocket, is not enough. Answer unsure if you cannot name such a detail, and no if the details contradict (different place, time of day, weather or kind of event).
Two different cameras filming the same event are same_footage no.
A video cut together from several recordings has same_footage yes if any part comes from the other video's recording.
Return {"same_footage": ..., "same_event": ..., "shared_detail": "..." or null, "shared_span_a": [start_s, end_s] or null, "shared_span_b": [start_s, end_s] or null, "observations": [up to 3 short concrete things you saw or heard], "unsure_because": "..."}."""


def pairs():
    base = [(a, b, k) for a, b, k in p.pairs()]
    base += [(a, b, "easy_negative") for a in ("A1", "A2", "A3", "A4") for b in ("B1", "B2")]
    return [x for a, b, k in base for x in ((a, b, k), (b, a, k))]


def run():
    cli, res = p.client(), D / "results.jsonl"
    done = {(r["a"], r["b"]) for r in map(json.loads, res.read_text().splitlines())} if res.exists() else set()
    todo = [x for x in pairs() if x[:2] not in done]
    ids = p.upload(cli, {n for x in todo for n in x[:2]})

    def one(x):
        a, b, kind = x
        content = [{"type": "input_text", "text": PROMPT + "\nVideo A:"}, {"type": "input_file", "file_id": ids[a]},
                   {"type": "input_text", "text": "Video B:"}, {"type": "input_file", "file_id": ids[b]}]
        raw, ans, u = p.ask(cli, content)
        return {"a": a, "b": b, "kind": kind, "answer": ans, "raw": None if ans else raw, "input_tokens": u.input_tokens, "output_tokens": u.output_tokens}

    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(one, todo):
            with res.open("a") as f:
                f.write(json.dumps(r) + "\n")
            a = r["answer"] or {}
            print(r["kind"], r["a"], r["b"], a.get("same_footage"), a.get("same_event"), flush=True)


def report():
    rows = [json.loads(l) for l in (D / "results.jsonl").read_text().splitlines()]
    g = {}
    for r in rows:
        g.setdefault((frozenset((r["a"], r["b"])), r["kind"]), []).append(r["answer"] or {})
    both = lambda rs, k, v: len(rs) == 2 and all(x.get(k) == v for x in rs)
    anyo = lambda rs, k, v: any(x.get(k) == v for x in rs)
    kinds = lambda k: [rs for (_, kk), rs in g.items() if kk == k]
    ec, hn, en, oc = kinds("edited_copy"), kinds("hard_negative"), kinds("easy_negative"), kinds("other_camera")
    non = [rs for (_, k), rs in g.items() if k != "edited_copy"]
    print(f"pairs {len(g)}, answers {len(rows)}, unparsed {sum(r['answer'] is None for r in rows)}")
    print(f"1 edited copies same_footage yes in both orders {sum(both(rs, 'same_footage', 'yes') for rs in ec)}/{len(ec)} (bar 12/14)")
    print(f"2 non-copy pairs with any same_footage yes {sum(anyo(rs, 'same_footage', 'yes') for rs in non)}/{len(non)} (bar 0)")
    print(f"3 hard negatives with any same_event yes {sum(anyo(rs, 'same_event', 'yes') for rs in hn)}/{len(hn)} (bar <=2)")
    print(f"4 easy negatives same_event no in both orders {sum(both(rs, 'same_event', 'no') for rs in en)}/{len(en)} (bar 7/8)")
    same = sum(len({x.get('same_footage') for x in rs}) == 1 for rs in g.values())
    print(f"5 same_footage identical across orders {same}/{len(g)} = {same / len(g):.0%} (bar 90%)")
    print("same-event pairs (other_camera) same_event answers:", sorted(x.get("same_event") for rs in oc for x in rs))
    text = re.compile(r"timestamp|clock|date|overlay|watermark|on-screen text|caption|logo", re.I)
    print("answers citing text-like evidence:", sum(bool(text.search(" ".join((r["answer"] or {}).get("observations", [])))) for r in rows), "/", len(rows))
    print("cost $%.2f" % (sum(r["input_tokens"] * 1.25 + r["output_tokens"] * 4.25 for r in rows) / 1e6))
    print("\nfalse merges and misses:")
    for (ab, k), rs in sorted(g.items(), key=lambda t: (t[0][1], sorted(t[0][0]))):
        fp = [x.get("same_footage") for x in rs]
        ev = [x.get("same_event") for x in rs]
        if (k != "edited_copy" and "yes" in fp) or (k == "edited_copy" and fp != ["yes", "yes"]) or (k in ("hard_negative", "easy_negative") and "yes" in ev):
            print(" ", k, sorted(ab), "footage", fp, "event", ev)
    print("\ncompilation spans (truth: A1 0-6, N1 6-12, A3 12-18 inside the compilation):")
    for r in rows:
        if "A1N1A3_e4" in (r["a"], r["b"]):
            a = r["answer"] or {}
            print(" ", r["a"], r["b"], a.get("same_footage"), a.get("shared_span_a" if r["a"] == "A1N1A3_e4" else "shared_span_b"))


if __name__ == "__main__":
    if sys.argv[1] == "clips":
        (D).mkdir(parents=True, exist_ok=True)
        if not (D / "raw").exists():
            (D / "raw").symlink_to("../spark_pilot2/raw")
        p.clips(MASK)
    else:
        {"run": run, "report": report}[sys.argv[1]]()
