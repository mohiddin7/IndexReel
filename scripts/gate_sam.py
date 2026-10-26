"""Capture raw SAM output for one split of the gate. Needs MODEL_API_KEY in the environment.

  python scripts/gate_sam.py dev --dry     show the cost and stop
  python scripts/gate_sam.py dev           run dev, then gate (only after eval/gate.md is public and dev looks sane)
"""
import asyncio
import sys
from pathlib import Path

from indexreel import sam

RUN = Path(__file__).resolve().parents[1] / "data" / "gate_run"

if __name__ == "__main__":
    split = sys.argv[1]
    clips = sorted((RUN / "in" / split).glob("*.mp4"))
    cost = sam.estimate_dollars(len(clips))
    print(f"{split}: {len(clips)} clips, {len(sam.PROMPTS)} prompts, about ${cost:.2f}")
    if "--dry" not in sys.argv:
        asyncio.run(sam.run_dir(clips, RUN / "sam_raw" / split))
