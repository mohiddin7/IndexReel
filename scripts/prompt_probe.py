"""Which concept phrases make the Model API find a picture-in-picture box or a screen? Dev clips only, one frame each.

  PYTHONPATH=src python scripts/prompt_probe.py        needs MODEL_API_KEY in my shell; about 50 image requests, around $0.15

This is exploratory prompt discovery for the product. The gate's frozen prompts and verdict are not touched.
Results go to data/gate_run/prompt_probe.json: per clip and phrase, the objects found, the best confidence and the
largest object's share of the frame.
"""
import base64
import json
import os
from pathlib import Path

import cv2
from openai import OpenAI

from indexreel import sam

RUN = Path(__file__).resolve().parents[1] / "data" / "gate_run"
CLIPS = ["T01__pip", "T02__pip", "T01__refilm_sim", "T02__refilm_sim", "N01__orig"]
PHRASES = ["video inset", "picture in picture", "inset video window", "small video window", "video window",
           "television", "television screen", "monitor", "computer monitor", "screen"]


def frame0(clip):
    cap = cv2.VideoCapture(str(RUN / "in" / "dev" / f"{clip}.mp4"))
    ok, f = cap.read()
    assert ok
    return "data:image/png;base64," + base64.b64encode(cv2.imencode(".png", f)[1].tobytes()).decode()


def ask(cli, url, phrase):
    text = []
    with cli.responses.stream(model="sam-3.1", input=[{"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": phrase}, {"type": "input_image", "image_url": url}]}],
            metadata={"mask_encoding": "one_bit", "include_confidence": "true"}) as s:
        for ev in s:
            if ev.type == "response.output_text.delta":
                text.append(ev.delta)
    found = sam.api_masks("".join(text), 360, 640).get(0, [])
    return {"objects": len(found), "largest_share": round(max((m.mean() for m in found), default=0.0), 3),
            "raw_confidences": [round(float(c), 2) for c in __import__("re").findall(r"mask;x=0;y=0;c=([\d.]+)", "".join(text))]}


if __name__ == "__main__":
    cli = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"])
    out = {}
    for clip in CLIPS:
        url = frame0(clip)
        out[clip] = {p: ask(cli, url, p) for p in PHRASES}
        print(clip, {p: r["objects"] for p, r in out[clip].items()}, flush=True)
    (RUN / "prompt_probe.json").write_text(json.dumps(out, indent=1))
