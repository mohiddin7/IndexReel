"""Can Muse Spark tell a copy from another camera on the same event? Protocol: eval/spark-pilot.md (frozen before the first call).

  python scripts/spark_pilot.py clips            cut the windows and make the derived copies from data/spark_pilot/raw
  python scripts/spark_pilot.py run --limit 1    needs MODEL_API_KEY in my shell; one pair first to measure cost
  python scripts/spark_pilot.py run              all 23 pairs, resumes from data/spark_pilot/results.jsonl

Media stays in data/spark_pilot (ignored by git). Uploaded files expire after a day.
"""
import argparse
import json
import os
import random
import re
import subprocess
from itertools import product
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "data" / "spark_pilot"
SOURCES = {  # id: (raw file, start s, length s)
    "Y": ("chel_yekat.webm", 8, 24), "M": ("chel_magnit.webm", 8, 24), "I": ("chel_ivanov.ogv", 12, 24),
    "C0": ("ifts1_wb57cam0.webm", 190, 30), "C4": ("ifts1_wb57cam4.webm", 320, 30), "MA": ("ifts1_matamoros.webm", 0, 24)}
COPIES = ["Y", "I", "C0", "MA"]
PROMPT = """You are shown two short videos, A and B. Decide two things separately and answer with JSON only, no other text.
same_event: do they show the same real-world event at overlapping moments? yes, no or unsure.
same_footage: are they the same camera recording, possibly re-encoded, resized, cropped or with overlays added? yes, no or unsure.
Two different cameras filming the same event are same_event yes and same_footage no.
Return {"same_event": ..., "same_footage": ..., "observations": [up to 3 short concrete things you saw or heard], "unsure_because": "..."}."""


def ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def clips():
    out = D / "clips"
    out.mkdir(parents=True, exist_ok=True)
    for k, (raw, ss, t) in SOURCES.items():
        ff("-ss", str(ss), "-t", str(t), "-i", str(D / "raw" / raw), "-vf", "scale=-2:360,fps=15",
           "-c:v", "libx264", "-crf", "28", "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(out / f"{k}.mp4"))
    for k in COPIES:
        ff("-i", str(out / f"{k}.mp4"), "-vf", "scale=-2:240", "-c:v", "libx264", "-crf", "42", "-c:a", "aac", "-b:a", "32k",
           "-movflags", "+faststart", str(out / f"{k}_reenc.mp4"))
        ff("-i", str(out / f"{k}.mp4"), "-vf",
           "crop=iw*0.85:ih*0.85,scale=640:360,drawbox=y=ih-60:w=iw:h=60:color=red@0.9:t=fill,drawbox=x=12:y=12:w=90:h=40:color=white@0.9:t=fill",
           "-c:v", "libx264", "-crf", "28", "-c:a", "copy", "-movflags", "+faststart", str(out / f"{k}_banner.mp4"))


def pairs():
    p = [(k, f"{k}_{v}", "copy") for k in COPIES for v in ("reenc", "banner")]
    p += [(a, b, "other_camera") for a, b in (("Y", "M"), ("Y", "I"), ("M", "I"), ("C0", "C4"))]
    p += [("MA", "C0", "same_event_no_shared_moment"), ("MA", "C4", "same_event_no_shared_moment")]
    p += [(a, b, "different_event") for a, b in product(("Y", "M", "I"), ("C0", "C4", "MA"))]
    rng = random.Random(2610)
    return [(b, a, kind) if rng.random() < 0.5 else (a, b, kind) for a, b, kind in p]


def run(limit):
    from openai import OpenAI
    cli = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"])
    res = D / "results.jsonl"
    done = {(r["a"], r["b"]) for r in map(json.loads, res.read_text().splitlines())} if res.exists() else set()
    ids = {}

    def fid(name):
        if name not in ids:
            with open(D / "clips" / f"{name}.mp4", "rb") as f:
                ids[name] = cli.files.create(purpose="user_data", file=f, expires_after={"anchor": "created_at", "seconds": 86400}).id
        return ids[name]

    for a, b, kind in [p for p in pairs() if p[:2] not in done][:limit]:
        content = [{"type": "input_text", "text": PROMPT + "\nVideo A:"}, {"type": "input_file", "file_id": fid(a)},
                   {"type": "input_text", "text": "Video B:"}, {"type": "input_file", "file_id": fid(b)}]
        text = []
        with cli.responses.stream(model="muse-spark-1.3", max_output_tokens=4000,
                                  input=[{"type": "message", "role": "user", "content": content}]) as s:
            for ev in s:
                if ev.type == "response.output_text.delta":
                    text.append(ev.delta)
            usage = s.get_final_response().usage
        raw = "".join(text)
        m = re.search(r"\{.*\}", raw, re.S)
        try:
            ans = json.loads(m.group(0)) if m else None
        except json.JSONDecodeError:
            ans = None
        row = {"a": a, "b": b, "kind": kind, "answer": ans, "raw": None if ans else raw,
               "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}
        with res.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(kind, a, b, ans and (ans.get("same_event"), ans.get("same_footage")), usage.input_tokens, usage.output_tokens, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["clips", "run"])
    ap.add_argument("--limit", type=int, default=99)
    a = ap.parse_args()
    clips() if a.cmd == "clips" else run(a.limit)
