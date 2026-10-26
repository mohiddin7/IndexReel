"""Capture raw SAM 3.1 video output. Decoding is a separate step, so a parsing bug never costs a second call."""
import asyncio
import os
import random
import re
from pathlib import Path

import numpy as np
from meta_sam_parser import SegmentationMask, decode_mask_to_raster

from openai import APIStatusError, AsyncOpenAI

PROMPTS = ("screen", "video inset")  # frozen in eval/gate.md
DOLLARS_PER_FRAME = 0.20 / 1000
MIN_BILLED_FRAMES = 50


def client():
    # the key comes from the environment only; it is never written to a file in this folder
    return AsyncOpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"], max_retries=0)


async def capture_once(cli, file_id, phrase):
    """One streamed request; returns the concatenated output text (one line per frame)."""
    parts = []
    async with cli.responses.stream(
        model="sam-3.1",
        input=[{"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": phrase}, {"type": "input_video", "file_id": file_id}]}],
        metadata={"mask_encoding": "one_bit", "include_confidence": "true"},
    ) as stream:
        async for ev in stream:
            if ev.type == "response.output_text.delta":
                parts.append(ev.delta)
    return "".join(parts)


async def capture(cli, file_id, phrase, tries=4):
    """Retry only transport and capacity errors (429, 503), honouring Retry-After. A 400 is permanent."""
    for n in range(tries):
        try:
            return await capture_once(cli, file_id, phrase)
        except APIStatusError as e:
            if e.status_code not in (429, 503) or n == tries - 1:
                raise
            wait = float(e.response.headers.get("retry-after", 2 ** n)) + random.random()
            await asyncio.sleep(wait)


async def run_dir(clips, out_dir, parallel=8):
    """Upload each clip once and capture each frozen prompt once. Existing raw files are kept, never redone."""
    cli, sem, out_dir = client(), asyncio.Semaphore(parallel), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    async def one(path):
        todo = [p for p in PROMPTS if not (out_dir / f"{path.stem}__{p.replace(' ', '_')}.txt").exists()]
        if not todo:
            return
        async with sem:
            with open(path, "rb") as fh:
                file_id = (await cli.files.create(purpose="user_data", file=fh)).id
            for phrase in todo:
                text = await capture(cli, file_id, phrase)
                (out_dir / f"{path.stem}__{phrase.replace(' ', '_')}.txt").write_text(text)
                print(path.stem, repr(phrase), len(text.splitlines()), "frame lines", flush=True)

    await asyncio.gather(*(one(p) for p in clips))


def estimate_dollars(n_clips, frames_per_clip=50):
    return n_clips * len(PROMPTS) * max(frames_per_clip, MIN_BILLED_FRAMES) * DOLLARS_PER_FRAME


_RECORD = re.compile(r"<\|box;x1=(\d+);y1=(\d+);x2=(\d+);y2=(\d+);w=(\d+);h=(\d+)[^|]*\|>"
                     r"<\|mask;x=0;y=0;(?:c=[\d.]+;)?data=(\d+),(\d+),(.*?)\|>(?=,|$)")


def api_masks(text, height, width):
    """Raw API output -> {frame index: [boolean masks at frame size]}. A mask raster is a crop of its box."""
    frames = {}
    for line in text.splitlines():
        head = re.match(r"<(\d+)f>", line)
        if not head:
            continue
        masks = []
        for x1, y1, x2, y2, _, _, mh, mw, payload in _RECORD.findall(line):
            raster = np.frombuffer(decode_mask_to_raster(
                SegmentationMask(encoding="one_bit", payload=payload, width=int(mw), height=int(mh))), np.uint8)
            full = np.zeros((height, width), bool)
            full[int(y1):int(y1) + int(mh), int(x1):int(x1) + int(mw)] = raster.reshape(int(mh), int(mw)) > 0
            masks.append(full)
        frames[int(head.group(1))] = masks
    return frames
