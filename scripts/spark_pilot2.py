"""Spark pilot 2: recent footage, real-world edits, hard negatives. Protocol: eval/spark-pilot2.md (frozen before the first call).

  python scripts/spark_pilot2.py clips      cut windows and make the five edits from data/spark_pilot2/raw
  python scripts/spark_pilot2.py pdq        PDQ clip score for every pair (PYTHONPATH=src)
  python scripts/spark_pilot2.py run        needs MODEL_API_KEY in my shell; 48 pairs, about $1; resumes
  python scripts/spark_pilot2.py recall     one clip at a time: where and when was this filmed
  python scripts/spark_pilot2.py report     score the pass bar and the PDQ disagreement table

Media stays in data/spark_pilot2 (ignored by git). Uploaded files expire after a day.
"""
import json
import os
import random
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "data" / "spark_pilot2"
C = D / "clips"
# id: (raw id, start s, length s)
SRC = {"A1": ("7aI5RXbjQ4w", 0, 30), "A2": ("ck8_RKGdJf4", 0, 30), "A3": ("rL0e0hD2T3k", 0, 30), "A4": ("mGOXiJWIpIQ", 0, 30),
       "B1": ("Bbwieo6Qq8o", 60, 30), "B2": ("77Q4UNqDZTs", 95, 25),
       "N1": ("k6xMJps3igE", 0, 30), "N2": ("55nx36neZGc", 0, 30), "N3": ("y2sIq3jWdmY", 0, 30),
       "N4": ("g4x2zOjR130", 0, 30), "N5": ("75TwSw8b_dg", 0, 30), "N6": ("iGDWmGBS-rw", 0, 30)}
PROMPT = """You are shown two short videos, A and B. Answer with JSON only, no other text.
same_event: do they show the same real-world occurrence at overlapping moments? yes, no or unsure.
same_footage: does either video contain footage from the same original camera recording as the other? It may be re-encoded, resized, cropped, mirrored, sped up, overlaid, given other music, or only partly reused. yes, no or unsure.
Two different cameras filming the same event are same_event yes and same_footage no.
A video cut together from several recordings has same_footage yes if any part comes from the other video's recording.
Return {"same_event": ..., "same_footage": ..., "shared_span_a": [start_s, end_s] or null, "shared_span_b": [start_s, end_s] or null, "observations": [up to 3 short concrete things you saw or heard], "unsure_because": "..."}."""
RECALL = "Where and when was this video filmed? Name a place and a date only if you can see or hear evidence for it in the video; otherwise say unknown. Answer in two short lines."


def ff(*a):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *a], check=True)


def clips(extra=""):
    C.mkdir(parents=True, exist_ok=True)
    for k, (raw, ss, t) in SRC.items():
        ff("-ss", str(ss), "-t", str(t), "-i", str(D / "raw" / f"{raw}.mp4"), "-vf", "scale=-2:360,fps=15" + extra, "-c:v", "libx264",
           "-crf", "28", "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(C / f"{k}.mp4"))
    enc = ["-c:v", "libx264", "-crf", "28", "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart"]
    for k in ("A1", "A3", "A4", "B2"):
        ff("-i", str(C / f"{k}.mp4"), "-vf", "hflip,setpts=PTS/1.25", "-af", "atempo=1.25", *enc, str(C / f"{k}_e1.mp4"))
        ff("-i", str(C / f"{k}.mp4"), "-filter_complex",
           "[0:v]split[a][b];[a]scale=360:640:force_original_aspect_ratio=increase,crop=360:640,boxblur=20:2[bg];[b]scale=360:-2[fg];"
           "[bg][fg]overlay=(W-w)/2:(H-h)/2,drawbox=y=ih-70:w=iw:h=70:color=red@0.9:t=fill,drawbox=x=10:y=10:w=80:h=36:color=white@0.9:t=fill",
           *enc, str(C / f"{k}_e2.mp4"))
    for k in ("A1", "A3"):
        ff("-f", "lavfi", "-i", "color=c=0x1f3a93:s=640x360:r=15", "-i", str(C / f"{k}.mp4"), "-filter_complex",
           "[1:v]scale=300:-2[f];[0:v][f]overlay=320:60:shortest=1,drawbox=y=300:w=640:h=60:color=red@0.9:t=fill,drawbox=x=16:y=16:w=100:h=40:color=white@0.9:t=fill[v]",
           "-map", "[v]", "-map", "1:a", "-shortest", *enc, str(C / f"{k}_e3.mp4"))
    segs = []
    for i, (k, ss) in enumerate((("A1", 0), ("N1", 6), ("A3", 12))):
        s = C / f"_seg{i}.mp4"
        ff("-ss", str(ss), "-t", "6", "-i", str(C / f"{k}.mp4"), "-vf", "scale=640:360,fps=15", "-ar", "44100", "-ac", "2", *enc, str(s))
        segs.append(s)
    (C / "_list.txt").write_text("".join(f"file '{s}'\n" for s in segs))
    ff("-f", "concat", "-safe", "0", "-i", str(C / "_list.txt"), "-c", "copy", str(C / "A1N1A3_e4.mp4"))
    ff("-i", str(C / "A2.mp4"), "-f", "lavfi", "-i", "sine=frequency=440", "-map", "0:v", "-map", "1:a", "-vf", "scale=-2:240", "-shortest",
       "-c:v", "libx264", "-crf", "40", "-c:a", "aac", "-b:a", "32k", "-movflags", "+faststart", str(C / "A2_e5.mp4"))


def pairs():
    p = []
    for k in ("A1", "A3", "A4", "B2"):
        p += [(k, f"{k}_e1", "edited_copy"), (k, f"{k}_e2", "edited_copy")]
    p += [("A1", "A1_e3", "edited_copy"), ("A3", "A3_e3", "edited_copy")]
    p += [("A1N1A3_e4", k, "edited_copy") for k in ("A1", "N1", "A3")]
    p += [("A2", "A2_e5", "edited_copy")]
    cams = ["A1", "A2", "A3", "A4"]
    p += [(a, b, "other_camera") for i, a in enumerate(cams) for b in cams[i + 1:]]
    p += [("A1_e2", "A2", "other_camera"), ("A3_e1", "A4", "other_camera"), ("A4_e1", "A1", "other_camera")]
    p += [("B1", "B2", "no_shared_view")]
    p += [(a, n, "hard_negative") for a in cams for n in ("N1", "N2", "N3", "N4", "N5", "N6")]
    rng = random.Random(1013)
    return [(b, a, k) if rng.random() < 0.5 else (a, b, k) for a, b, k in p]


def client():
    from openai import OpenAI
    return OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"], timeout=600)


def upload(cli, names):
    ids = {}
    for n in names:
        with open(C / f"{n}.mp4", "rb") as f:
            ids[n] = cli.files.create(purpose="user_data", file=f, expires_after={"anchor": "created_at", "seconds": 86400}).id
    return ids


def ask(cli, content):
    for attempt in range(3):  # transport failures only (no response.completed); an answer is never re-asked
        try:
            return _ask(cli, content)
        except RuntimeError:
            if attempt == 2:
                raise


def _ask(cli, content):
    text = []
    with cli.responses.stream(model="muse-spark-1.3", max_output_tokens=4000,
                              input=[{"type": "message", "role": "user", "content": content}]) as s:
        for ev in s:
            if ev.type == "response.output_text.delta":
                text.append(ev.delta)
        u = s.get_final_response().usage
    raw = "".join(text)
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        ans = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        ans = None
    return raw, ans, u


def run():
    cli, res = client(), D / "results.jsonl"
    done = {(r["a"], r["b"]) for r in map(json.loads, res.read_text().splitlines())} if res.exists() else set()
    todo = [p for p in pairs() if p[:2] not in done]
    ids = upload(cli, {n for p in todo for n in p[:2]})

    def one(p):
        a, b, kind = p
        content = [{"type": "input_text", "text": PROMPT + "\nVideo A:"}, {"type": "input_file", "file_id": ids[a]},
                   {"type": "input_text", "text": "Video B:"}, {"type": "input_file", "file_id": ids[b]}]
        raw, ans, u = ask(cli, content)
        return {"a": a, "b": b, "kind": kind, "answer": ans, "raw": None if ans else raw, "input_tokens": u.input_tokens, "output_tokens": u.output_tokens}

    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(one, todo):
            with res.open("a") as f:
                f.write(json.dumps(r) + "\n")
            a = r["answer"] or {}
            print(r["kind"], r["a"], r["b"], a.get("same_event"), a.get("same_footage"), flush=True)


def recall():
    cli = client()
    names = [k for k in SRC]
    ids = upload(cli, names)

    def one(n):
        raw, _, u = ask(cli, [{"type": "input_text", "text": RECALL}, {"type": "input_file", "file_id": ids[n]}])
        return {"clip": n, "answer": raw.strip(), "input_tokens": u.input_tokens, "output_tokens": u.output_tokens}

    with ThreadPoolExecutor(4) as ex:
        rows = list(ex.map(one, names))
    (D / "recall.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    for r in rows:
        print(r["clip"], "|", r["answer"].replace("\n", " / "))


def pdq():
    from indexreel import match
    ps = pairs()
    h = {n: match.sampled_hashes(C / f"{n}.mp4") for n in {x for p in ps for x in p[:2]}}
    (D / "pdq.json").write_text(json.dumps({f"{a}|{b}": round(match.score(h[a], h[b]), 3) for a, b, _ in ps}, indent=1))
    print("pdq scores written for", len(ps), "pairs")


def report():
    rows = [json.loads(l) for l in (D / "results.jsonl").read_text().splitlines()]
    pdqs = json.loads((D / "pdq.json").read_text()) if (D / "pdq.json").exists() else {}
    ans = lambda r, k: (r["answer"] or {}).get(k)
    by = {k: [r for r in rows if r["kind"] == k] for k in ("edited_copy", "other_camera", "no_shared_view", "hard_negative")}
    ec, oc, hn = by["edited_copy"], by["other_camera"], by["hard_negative"]
    r1 = sum(ans(r, "same_footage") == "yes" for r in ec)
    r2a, r2b = sum(ans(r, "same_footage") == "no" for r in oc), sum(ans(r, "same_event") == "yes" for r in oc)
    r3a, r3b = sum(ans(r, "same_event") == "no" for r in hn), sum(ans(r, "same_footage") == "yes" for r in hn)
    print(f"1 edited copies same_footage yes {r1}/{len(ec)} (bar 11/14)")
    print(f"2 other camera same_footage no {r2a}/{len(oc)} (bar all), same_event yes {r2b}/{len(oc)} (bar 7/9)")
    print(f"3 hard negatives same_event no {r3a}/{len(hn)} (bar 22/24), same_footage yes {r3b} (bar 0)")
    print("false merges (same_footage yes on a non-copy):", [(r["a"], r["b"]) for r in rows if r["kind"] != "edited_copy" and ans(r, "same_footage") == "yes"])
    print("unparsed:", sum(r["answer"] is None for r in rows), " unsure answers:", sum(v == "unsure" for r in rows for v in ((r["answer"] or {}).get("same_event"), (r["answer"] or {}).get("same_footage"))))
    print("cost $%.2f" % (sum(r["input_tokens"] * 1.25 + r["output_tokens"] * 4.25 for r in rows) / 1e6))
    print("\nkind | a | b | spark event/footage | pdq score")
    for r in sorted(rows, key=lambda r: (r["kind"], r["a"], r["b"])):
        print(r["kind"], r["a"], r["b"], ans(r, "same_event"), ans(r, "same_footage"), pdqs.get(f"{r['a']}|{r['b']}"), ans(r, "shared_span_a") if r["a"] == "A1N1A3_e4" else "")
    print("\ncompilation spans (true: A1 0-6, N1 6-12, A3 12-18 inside the compilation):")
    for r in rows:
        if "A1N1A3_e4" in (r["a"], r["b"]):
            a = r["answer"] or {}
            side = "a" if r["a"] == "A1N1A3_e4" else "b"
            print(r["a"], r["b"], a.get("same_footage"), a.get(f"shared_span_{side}"))


if __name__ == "__main__":
    {"clips": clips, "run": run, "recall": recall, "pdq": pdq, "report": report}[sys.argv[1]]()
