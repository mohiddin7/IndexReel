"""Verify stage: Muse Spark judges the unresolved pairs of a run directory (eval/run-format.md) and fills the verify
columns of pairs.csv.

Settings are the ones measured in eval/spark-h10 to h15: clips re-encoded to a 180 px shorter side, minimal reasoning
effort, one anchor clip and up to 4 candidates per request (the API takes at most 5 videos). Then every conflict is
re-asked one pair at a time at 360 px and default effort, in both orders (eval/spark-h15.md). A conflict is a pair the
judge did not call the same although both clips are linked to a third clip (merged band or verified same), or a pair
whose sound matches (eval/audio-h2-result.md) while the picture judge did not say same. The sound alone never sets a
verdict: a soundtrack can be reused under another picture or replaced on a copy.

  MODEL_API_KEY=... python -m indexreel.verify <run dir> [--max-usd 5]

Answers are cached by clip content, prompt and settings, so a rerun costs nothing.
"""
import argparse
import csv
import hashlib
import itertools
import json
import os
import re
import subprocess
import tempfile
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from indexreel import audio

MODEL = "muse-spark-1.3"
K = 4
AUDIO_MATCH = 0.03  # between the highest negative (0.0066) and the lowest copy (0.105) in eval/audio-h2-result.md
PRICE = {"input": 1.25, "cached": 0.15, "output": 4.25}  # USD per million tokens, Model API list prices
VERDICT = {"yes": "same", "no": "different"}  # anything else, including no answer, is abstain

# eval/spark-h12.md, unchanged
GROUP_PROMPT = """You are shown one reference video A followed by N candidate videos B1 to BN. Answer with JSON only, no other text. Judge the picture and the sound, not any text drawn on the screen.
For each candidate, decide independently whether it contains footage from the same original camera recording as A. A copy may be re-encoded, resized, cropped, mirrored, sped up, overlaid, given other music, or only partly reused. A video cut together from several recordings counts as yes if any part comes from A's recording. Two different cameras filming the same event are no. Do not compare the candidates with each other. Answer yes, no or unsure.
Return {"results": [{"candidate": "B1", "same_footage": ..., "shared_detail": "..." or null}, ...]} with one entry per candidate, in order."""

# eval/spark-pilot3.md (prompt v3), unchanged
PAIR_PROMPT = """You are shown two short videos, A and B. Answer with JSON only, no other text. Judge the picture and the sound, not any text drawn on the screen.
same_footage: does either video contain footage from the same original camera recording as the other? It may be re-encoded, resized, cropped, mirrored, sped up, overlaid, given other music, or only partly reused. yes, no or unsure.
same_event: do they show the same real-world occurrence at overlapping moments? Answer yes only if you can name a specific detail that both videos show (the same landmarks or place, the same light path and timing). A similar kind of event, such as another meteor or another rocket, is not enough. Answer unsure if you cannot name such a detail, and no if the details contradict (different place, time of day, weather or kind of event).
Two different cameras filming the same event are same_footage no.
A video cut together from several recordings has same_footage yes if any part comes from the other video's recording.
Return {"same_footage": ..., "same_event": ..., "shared_detail": "..." or null, "shared_span_a": [start_s, end_s] or null, "shared_span_b": [start_s, end_s] or null, "observations": [up to 3 short concrete things you saw or heard], "unsure_because": "..."}."""


SETTINGS = {"group": [180, "minimal", GROUP_PROMPT], "pair": [360, "default", PAIR_PROMPT]}  # part of every cache key


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


class Cache:
    """Answers on disk, one JSON file per request, keyed by clip content, prompt and settings."""

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._sha = {}

    def key(self, kind, paths):
        for p in paths:
            self._sha.setdefault(p, sha(p))
        return hashlib.sha256(json.dumps([MODEL, SETTINGS[kind], [self._sha[p] for p in paths]]).encode()).hexdigest()

    def get(self, key):
        f = self.root / f"{key}.json"
        return json.loads(f.read_text()) if f.exists() else None

    def put(self, key, value):
        tmp = self.root / f"{key}.tmp"
        tmp.write_text(json.dumps(value))
        tmp.replace(self.root / f"{key}.json")


class SparkJudge:
    """Muse Spark on the Meta Model API. group() is the cheap call, pair() the full-fidelity one."""

    def __init__(self, workdir):
        from openai import OpenAI
        self.cli = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"], timeout=600)
        self.workdir = Path(workdir)
        self.ids = {}
        self.lock = threading.Lock()  # one encode and upload per clip and size, even with parallel requests

    def _file(self, path, size):
        with self.lock:
            return self._upload(path, size)

    def _upload(self, path, size):
        key = (path, size)
        if key not in self.ids:
            out = self.workdir / f"{size}" / f"{sha(path)}.mp4"
            if not out.exists():
                out.parent.mkdir(parents=True, exist_ok=True)
                vf = f"scale='if(gt(iw,ih),-2,{size})':'if(gt(iw,ih),{size},-2)'"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vf", vf, "-c:v", "libx264", "-crf", "28",
                                "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(out)], check=True)
            with open(out, "rb") as f:
                self.ids[key] = self.cli.files.create(purpose="user_data", file=f,
                                                      expires_after={"anchor": "created_at", "seconds": 86400}).id
        return self.ids[key]

    def _ask(self, content, **kw):
        for attempt in range(3):  # transport failures only (no response.completed); an answer is never re-asked
            try:
                text = []
                with self.cli.responses.stream(model=MODEL, input=[{"type": "message", "role": "user", "content": content}], **kw) as s:
                    for ev in s:
                        if ev.type == "response.output_text.delta":
                            text.append(ev.delta)
                    u = s.get_final_response().usage
                break
            except RuntimeError:
                if attempt == 2:
                    raise
        m = re.search(r"\{.*\}", "".join(text), re.S)
        try:
            ans = json.loads(m.group(0)) if m else None
        except json.JSONDecodeError:
            ans = None
        cached = u.input_tokens_details.cached_tokens or 0
        cost = ((u.input_tokens - cached) * PRICE["input"] + cached * PRICE["cached"] + u.output_tokens * PRICE["output"]) / 1e6
        return ans, cost

    def group(self, anchor, candidates):
        content = [{"type": "input_text", "text": GROUP_PROMPT + "\nVideo A:"}, {"type": "input_file", "file_id": self._file(anchor, 180)}]
        for i, c in enumerate(candidates, 1):
            content += [{"type": "input_text", "text": f"Video B{i}:"}, {"type": "input_file", "file_id": self._file(c, 180)}]
        ans, cost = self._ask(content, max_output_tokens=8000, reasoning={"effort": "minimal"},
                              prompt_cache_key="indexreel-verify", prompt_cache_retention="24h")
        results = (ans or {}).get("results") or []
        by = {str(e.get("candidate")): e for e in results if isinstance(e, dict)}
        return [by.get(f"B{i}") for i in range(1, len(candidates) + 1)], cost

    def pair(self, a, b):
        content = [{"type": "input_text", "text": PAIR_PROMPT + "\nVideo A:"}, {"type": "input_file", "file_id": self._file(a, 360)},
                   {"type": "input_text", "text": "Video B:"}, {"type": "input_file", "file_id": self._file(b, 360)}]
        return self._ask(content, max_output_tokens=4000)


def chunks(pairs):
    """The clip with more pairs anchors each one (ties by id); its partners go K at a time (eval/spark-h14.md)."""
    deg = Counter(n for a, b in pairs for n in (a, b))
    g = defaultdict(list)
    for a, b in pairs:
        x, y = (a, b) if (deg[a], a) >= (deg[b], b) else (b, a)
        g[x].append(y)
    return [(x, ys[i:i + K]) for x, ys in sorted(g.items()) for ys in [sorted(ys)] for i in range(0, len(ys), K)]


def conflicts(rows, verdict, sound):
    """Pairs to escalate: not called same, but both clips are linked to a third clip, or their sound matches."""
    linked = defaultdict(set)
    for r in rows:
        if r["band"] == "merged" or verdict.get(r["pair_id"]) == "same":
            linked[r["a"]].add(r["b"])
            linked[r["b"]].add(r["a"])
    out = set()
    for ns in linked.values():
        for x, y in itertools.combinations(sorted(ns), 2):
            if verdict.get(f"{x}~{y}", "same") != "same":
                out.add(f"{x}~{y}")
    out |= {p for p, s in sound.items() if s is not None and s >= AUDIO_MATCH and verdict.get(p, "same") != "same"}
    return sorted(out)


def sound_scores(paths, pairs):
    h = {c: audio.hashes(paths[c]) for c in sorted({c for p in pairs for c in p.split("~")})}
    return {p: audio.score(*(h[c] for c in p.split("~"))) for p in pairs}


def verify(run, judge, cache, sound=None, max_usd=5.0, workers=4):
    """Fill the verify columns of run/pairs.csv for every unresolved pair. Returns (spent now, cost of all answers)."""
    run = Path(run)
    paths = {c["id"]: str((run / c["path"]).resolve()) for c in json.loads((run / "clips.json").read_text())["clips"]}
    with open(run / "pairs.csv", newline="") as f:
        reader = csv.DictReader(f)
        columns, rows = reader.fieldnames, list(reader)
    todo = [r["pair_id"] for r in rows if r["band"] == "unresolved"]
    sound = sound_scores(paths, todo) if sound is None else sound
    spent, budget_hit = 0.0, False

    def call(kind, ids, fn):
        nonlocal spent, budget_hit
        key = cache.key(kind, [paths[i] for i in ids])
        hit = cache.get(key)
        if hit is not None:
            return hit
        if spent >= max_usd:
            budget_hit = True
            return None
        first, *rest = (paths[i] for i in ids)
        ans, cost = fn(first, rest) if kind == "group" else fn(first, *rest)  # group(anchor, [candidates]); pair(a, b)
        spent += cost
        hit = {"answer": ans, "cost": cost}
        cache.put(key, hit)
        return hit

    answers, cost, detail = defaultdict(list), defaultdict(float), {}
    with ThreadPoolExecutor(workers) as ex:
        work = chunks([tuple(p.split("~")) for p in todo])
        for (anchor, cands), hit in zip(work, ex.map(lambda w: call("group", [w[0], *w[1]], judge.group), work)):
            if hit is None:
                continue
            for c, ent in zip(cands, hit["answer"]):
                p = "~".join(sorted((anchor, c)))
                answers[p].append((ent or {}).get("same_footage"))
                cost[p] += hit["cost"] / len(cands)
                detail[p] = (ent or {}).get("shared_detail")
    verdict = {p: VERDICT.get(a[0], "abstain") for p, a in answers.items()}
    escalate = [p for p in conflicts(rows, verdict, sound) if p in answers]
    with ThreadPoolExecutor(workers) as ex:
        orders = [(p, ids) for p in escalate for ids in (p.split("~"), p.split("~")[::-1])]
        for (p, _), hit in zip(orders, ex.map(lambda o: call("pair", o[1], judge.pair), orders)):
            if hit is None:
                continue
            ans = hit["answer"] or {}
            answers[p].append(ans.get("same_footage"))
            cost[p] += hit["cost"]
            detail[p] = ans.get("shared_detail") or ans.get("unsure_because") or detail.get(p)
    for p in escalate:
        full = answers[p][1:]
        if full:  # eval/spark-h15.md: a yes in either order clears the conflict
            verdict[p] = "same" if "yes" in full else "different" if full == ["no", "no"] else "abstain"

    for r in rows:
        p = r["pair_id"]
        if p not in verdict:
            continue
        v, s = verdict[p], sound.get(p)
        agree = sum(VERDICT.get(a, "abstain") == v for a in answers[p]) / len(answers[p])
        note = "escalated, " if p in escalate else ""
        r.update(verify_verdict=v, verify_confidence=f"{agree:.2f}", verify_cost_usd=f"{cost[p]:.5f}",
                 verify_reason=f"{note}{(detail.get(p) or 'no shared detail named')[:160]}; sound "
                               + ("not usable" if s is None else f"{'matches' if s >= AUDIO_MATCH else 'differs'} ({s:.3f})"))
    fd, tmp = tempfile.mkstemp(dir=run, suffix=".csv")
    with os.fdopen(fd, "w", newline="") as f:
        w = csv.DictWriter(f, columns)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, run / "pairs.csv")
    if budget_hit:
        print(f"stopped at ${spent:.2f} (--max-usd {max_usd}); pairs without an answer keep empty verify columns")
    return spent, sum(cost.values())


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m indexreel.verify", description="Judge the unresolved pairs of a run directory.")
    ap.add_argument("run", type=Path, help="run directory written by `indexreel match`")
    ap.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "indexreel" / "verify")
    ap.add_argument("--max-usd", type=float, default=5.0, help="stop making new calls once this much is spent")
    a = ap.parse_args(argv)
    spent, total = verify(a.run, SparkJudge(a.cache / "clips"), Cache(a.cache / "answers"), max_usd=a.max_usd)
    print(f"verify: spent ${spent:.4f} now; answers in pairs.csv cost ${total:.4f} at list prices")


if __name__ == "__main__":
    main()
