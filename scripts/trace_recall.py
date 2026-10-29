"""Retrieval recall of trace's sources on dev cases (eval/trace-v2.md, Dev measurement). Nothing is downloaded.

  python scripts/trace_recall.py <cases.csv> --cache <dir> [--sources web,keyframe,channel,ytapi,youtube]
      [--per-query N] [--by-date] [--no-prerank] [--no-date-filter] [--max-usd 1] [--out results.csv]

cases.csv columns: case, clip (input path), claimed_date, known (space-separated post ids of known earlier uploads of
the recording). For each case the script runs trace's candidate search with the chosen sources and settings and
reports whether a known earlier upload is anywhere in the pool and whether it is among the candidates trace would
fetch (the first MAX_CANDIDATES that are posts and not skipped before download).
"""
import argparse
import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from indexreel import cli, trace, verify  # noqa: E402


def fetch_list(searcher, order):
    """The URLs trace would fetch, in order."""
    out = []
    for _, _, u in order:
        if len(out) < trace.MAX_CANDIDATES and trace.post_url(u) and u not in searcher.notes:
            out.append(u)
    return out


def hit(url, known):
    return any(k in url for k in known)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cases", type=Path)
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--sources", default=",".join(trace.SOURCES))
    ap.add_argument("--per-query", type=int, default=trace.PER_QUERY)
    ap.add_argument("--by-date", action="store_true")
    ap.add_argument("--no-prerank", action="store_true")
    ap.add_argument("--no-date-filter", action="store_true")
    ap.add_argument("--max-usd", type=float, default=1.0)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    trace.PER_QUERY, trace.BY_DATE = a.per_query, a.by_date
    key = os.environ.get(trace.KEY_NAME)
    cache = verify.Cache(a.cache / "trace")
    s = trace.Searcher(trace.SparkSearch(a.cache / "verify" / "clips"), cache, max_usd=a.max_usd,
                       google=trace.Google(key) if key else None, thumbs=trace.Thumbs(cli.MODEL, cache), meta=trace.post_meta,
                       sources=a.sources.split(","), prerank=not a.no_prerank, date_filter=not a.no_date_filter)
    rows = []
    for c in csv.DictReader(open(a.cases, newline="")):
        known = c["known"].split()
        order, _, _ = s.candidates(str(ROOT / c["clip"]), c["claimed_date"])
        pool = [u for _, _, u in order]
        fetched = fetch_list(s, order)
        rank = next((i + 1 for i, u in enumerate(pool) if hit(u, known)), "")
        srcs = "+".join(sorted({x for src, _, u in order if hit(u, known) for x in src.split("+")}))
        row = {"case": c["case"], "pool": len(pool), "in_pool": int(bool(rank)), "pool_rank": rank,
               "fetched": int(any(hit(u, known) for u in fetched)), "sources": srcs,
               "leak_exposed": "+".join(k for k, v in s.leaks.items() if v),
               "skipped": sum(1 for k in s.notes if k != "_off")}
        rows.append(row)
        print(" ".join(f"{k}={v}" for k, v in row.items()), flush=True)
    n = len(rows)
    print(f"trace_recall: sources {a.sources}, {a.per_query} per query, by_date {a.by_date}, prerank {not a.no_prerank}, "
          f"date_filter {not a.no_date_filter}: in pool {sum(r['in_pool'] for r in rows)}/{n}, fetched "
          f"{sum(r['fetched'] for r in rows)}/{n}; spent ${s.spent:.4f}")
    if trace.VISION_COUNTER.exists():
        print(f"trace_recall: Vision requests so far {trace.VISION_COUNTER.read_text()}")
    if a.out:
        with open(a.out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    main()
