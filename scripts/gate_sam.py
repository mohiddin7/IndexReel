"""Capture raw SAM output from the Meta Model API for one split of the gate. Needs MODEL_API_KEY in my shell.

  python scripts/gate_sam.py dev --dry          show the cost and stop
  python scripts/gate_sam.py dev --limit 1      one clip first, to look at the real response
  python scripts/gate_sam.py dev                the whole split

The gate split is refused until eval/gate-result.md exists: under Amendment 2 the first complete SAM run decides
the verdict, so an API run on gate afterwards is only a consistency check.
"""
import asyncio
import sys
from pathlib import Path

from indexreel import sam

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "data" / "gate_run"

if __name__ == "__main__":
    split = sys.argv[1]
    if split == "gate" and not (ROOT / "eval" / "gate-result.md").exists():
        sys.exit("refused: eval/gate-result.md does not exist yet, so the open-weights verdict is not written")
    clips = sorted((RUN / "in" / split).glob("*.mp4"))
    if "--limit" in sys.argv:
        clips = clips[: int(sys.argv[sys.argv.index("--limit") + 1])]
    print(f"{split}: {len(clips)} clips, {len(sam.PROMPTS)} prompts, about ${sam.estimate_dollars(len(clips)):.2f}")
    if "--dry" not in sys.argv:
        asyncio.run(sam.run_dir(clips, RUN / "sam_raw" / split))
