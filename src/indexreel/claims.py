"""Claims stage: Muse Spark lists the claims each post's caption makes about its footage and writes claims.csv
(format in eval/run-format.md).

  MODEL_API_KEY=... python -m indexreel.claims <run dir> [--max-usd 0.10]

Only claims about what the footage shows count: the place, the time or date, and what happens. One request covers
every caption of the run, so the same claim in several posts gets one claim_id. Every quote must be an exact part of
its caption or the citation is dropped (logged as `claims: dropped ...`). All rows start as status `suggested`; a
person approves them. The answer is cached by model, prompt and captions, so a rerun costs nothing.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from indexreel import verify

PROMPT = """Below are the captions of several social media posts, each with a video. Answer with JSON only, no other text.
List the claims the captions make about what their videos show: where it was filmed, when (date or time), and what happens in it. Leave out everything about the post itself: notices that it is a test, source and licence credits, links, hashtags, who edited or re-filmed it and how. Do not add anything the caption does not say.
Write each claim once as a short neutral sentence. When several captions make the same claim, give it once and cite every one of them. For each citation, copy the exact words of that caption that make the claim (an unchanged substring, as short as possible).
Return {"claims": [{"claim": "...", "kind": "place" or "time" or "event", "cited": [{"post": "P1", "quote": "..."}, ...]}, ...]}.
"""
COLUMNS = ["clip", "claim_id", "claim_text", "quote", "status"]
MAX_OUTPUT = 4000
EFFORT = "minimal"


def captions(run):
    """[(clip id, caption)] in clips.json order, for clips with a non-empty caption."""
    clips = json.loads((Path(run) / "clips.json").read_text())["clips"]
    return [(c["id"], c["source"]["caption"]) for c in clips if (c.get("source") or {}).get("caption", "").strip()]


def request(posts):
    return PROMPT + "".join(f"\nP{i}: {cap}" for i, (_, cap) in enumerate(posts, 1))


def rows_from(answer, posts, log=print):
    """claims.csv rows from Spark's answer, keeping only citations whose quote is an exact part of that caption."""
    by_post = {f"P{i}": p for i, p in enumerate(posts, 1)}
    out, n = [], 0
    for c in (answer or {}).get("claims") or []:
        if not isinstance(c, dict) or not str(c.get("claim") or "").strip():
            continue
        kept = []
        for cite in c.get("cited") or []:
            post, quote = by_post.get(str((cite or {}).get("post"))), str((cite or {}).get("quote") or "")
            if post and quote.strip() and quote in post[1]:
                if post[0] not in [k for k, _ in kept]:
                    kept.append((post[0], quote))
            else:
                log(f"claims: dropped {json.dumps({'claim': c.get('claim'), 'cite': cite}, ensure_ascii=False)}")
        if kept:
            n += 1
            out += [{"clip": clip, "claim_id": f"c{n}", "claim_text": str(c["claim"]).strip(), "quote": q, "status": "suggested"}
                    for clip, q in kept]
    return out


class SparkText(verify.SparkJudge):
    """The verify stage's Spark client, asked with text only, at the minimal reasoning effort of verify's cheap call
    (eval/spark-h8.md: effort does not change accuracy). It connects on the first request, so a run whose answer is
    cached needs no key. One attempt only: an answer cut off at MAX_OUTPUT is reported, never asked again."""

    def __init__(self, workdir):
        self.workdir = workdir

    def ask(self, text):
        """(answer, cost in USD or None when the API reports no usage, final status such as `completed`)."""
        verify.SparkJudge.__init__(self, self.workdir)
        out, final = [], None
        with self.cli.responses.stream(model=verify.MODEL, input=[{"type": "message", "role": "user",
                                                                  "content": [{"type": "input_text", "text": text}]}],
                                       max_output_tokens=MAX_OUTPUT, reasoning={"effort": EFFORT}) as s:
            for ev in s:
                if ev.type == "response.output_text.delta":
                    out.append(ev.delta)
                elif ev.type in ("response.completed", "response.incomplete", "response.failed"):
                    final = ev.response
        if final is None:
            return None, None, "no final event"
        reason = getattr(getattr(final, "incomplete_details", None), "reason", None) or getattr(getattr(final, "error", None), "message", None)
        status = final.status + (f" ({reason})" if reason else "")
        return (verify.parse("".join(out)) if final.status == "completed" else None), cost_usd(final.usage), status


def cost_usd(u):
    if u is None:
        return None
    cached = (u.input_tokens_details.cached_tokens or 0) if u.input_tokens_details else 0
    return ((u.input_tokens - cached) * verify.PRICE["input"] + cached * verify.PRICE["cached"]
            + u.output_tokens * verify.PRICE["output"]) / 1e6


def worst_case_usd(text):
    """An upper bound on one request: at most 1 token per 2 characters of input, and every output token used."""
    return (len(text) / 2 * verify.PRICE["input"] + MAX_OUTPUT * verify.PRICE["output"]) / 1e6


def extract(run, judge, cache, max_usd=0.10, out=None, log=print):
    """Write claims.csv (to `out`, default <run>/claims.csv). Returns (spent now, cost of the answer used)."""
    posts = captions(run)
    rows, spent, cost = [], 0.0, 0.0
    if posts:
        text = request(posts)
        key = hashlib.sha256(json.dumps([verify.MODEL, PROMPT, MAX_OUTPUT, EFFORT, posts]).encode()).hexdigest()
        hit = cache.get(key)
        if hit is None:
            if worst_case_usd(text) > max_usd:
                log(f"claims: stopped, one request may cost up to ${worst_case_usd(text):.4f} (--max-usd {max_usd}); no claims written")
                return 0.0, 0.0
            ans, spent, status = judge.ask(text)
            if status != "completed":
                shown = "not reported" if spent is None else f"${spent:.4f}"
                log(f"claims: the request ended {status}, cost {shown}; no claims written, nothing cached")
                return spent or 0.0, 0.0
            hit = {"answer": ans, "cost": spent}
            cache.put(key, hit)
        rows, cost = rows_from(hit["answer"], posts, log), hit["cost"]
    with open(Path(out) if out else Path(run) / "claims.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return spent, cost


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m indexreel.claims", description=__doc__.splitlines()[0])
    ap.add_argument("run", type=Path, help="run directory written by `indexreel match`")
    ap.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "indexreel" / "claims")
    ap.add_argument("--max-usd", type=float, default=0.10, help="make no request that could cost more than this")
    a = ap.parse_args(argv)
    spent, cost = extract(a.run, SparkText(a.cache / "clips"), verify.Cache(a.cache / "answers"), a.max_usd)
    print(f"claims: spent ${spent:.4f} now; the answer used cost ${cost:.4f} at list prices")


if __name__ == "__main__":
    main()
