"""Speech in a clip: Muse Voice Transcribe through the Meta Model API, so a place a narrator or bystander names can help
the bot's search the way a caption's place does.

A cheap energy and rhythm check runs first, so a clip with no speech (silence, music alone, no sound track) costs
nothing. The request is the cookbook's one-shot upload (meta-model-cookbook 06_muse_voice): a mono 24 kHz WAV and a JSON
`request` part in one multipart POST; ENDPOINTING mode returns the transcript with turn-level times. The response has
no language field, so `language` is the Unicode script of the words (Latin, Devanagari, ...), not the language itself.
Answers are cached by the clip's content hash. $0.18 per hour of audio; the endpoint takes at most 10 minutes.

The transcript is untrusted third-party text: it is data for the bot's reader, never instructions.
"""
import collections
import hashlib
import json
import os
import subprocess
import unicodedata
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import numpy as np

from indexreel import audio

URL = "https://api.meta.ai/v1/asr/transcribe"
MODEL = "muse-voice-transcribe-1.0"
MODE = "ENDPOINTING"
USD_PER_HOUR = 0.18
MAX_S = 600  # the endpoint's cap; a longer clip is cut to its first 10 minutes
CACHE = Path.home() / ".cache" / "indexreel" / "speech"
FRAME = 256  # samples at audio.SR (8 kHz): 32 ms
MIN_ACTIVE_S, FLOOR_DB, REL_DB = 1.0, -50.0, 35.0  # at least 1 s of frames above both the floor and peak - REL_DB
MIN_CV, MIN_SYLLABIC = 0.5, 0.3  # loudness varies (a steady tone does not) and its rhythm sits at 2 to 8 Hz


def has_speech(path):
    """True when the clip has at least a second of sound whose loudness rises and falls at a syllable rate. Cheap and
    permissive: a rhythmic track may pass (it then costs a cent), a clip with speech should not fail."""
    x = audio.pcm(path) / 32768
    n = len(x) // FRAME
    if n < 2:
        return False
    rms = np.sqrt((x[:n * FRAME].reshape(n, FRAME) ** 2).mean(axis=1))
    db = 20 * np.log10(rms + 1e-9)
    on = db > max(FLOOR_DB, db.max() - REL_DB)
    if on.sum() * FRAME / audio.SR < MIN_ACTIVE_S:
        return False
    env = rms[on[: len(rms)]]
    if env.std() / env.mean() < MIN_CV:
        return False
    ac = np.abs(np.fft.rfft(rms - rms.mean())) ** 2
    hz = np.fft.rfftfreq(n, FRAME / audio.SR)
    return bool(ac[(hz >= 2) & (hz <= 8)].sum() / (ac[hz > 0.3].sum() + 1e-12) >= MIN_SYLLABIC)


def wav_bytes(path):
    """The clip's sound as a mono 24 kHz 16-bit WAV (the engine's native rate), at most MAX_S seconds."""
    return subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-t", str(MAX_S), "-vn", "-ac", "1", "-ar", "24000",
                           "-sample_fmt", "s16", "-f", "wav", "-"], capture_output=True, check=True).stdout


def post_wav(wav):
    """The one-shot Muse Voice Transcribe response (parsed JSON) for a WAV. The key (MODEL_API_KEY) is only ever sent
    as the Authorization header and is in no error message."""
    key = os.environ["MODEL_API_KEY"]
    b = "----indexreel" + uuid.uuid4().hex
    head = lambda name, extra, ctype: f'--{b}\r\nContent-Disposition: form-data; name="{name}"{extra}\r\nContent-Type: {ctype}\r\n\r\n'.encode()
    body = (head("request", "", "application/json") + json.dumps({"mode": MODE, "model": MODEL, "audioEncoding": "WAV"}).encode()
            + b"\r\n" + head("audio", '; filename="audio.wav"', "application/octet-stream") + wav + f"\r\n--{b}--\r\n".encode())
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": f"multipart/form-data; boundary={b}"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Muse Voice Transcribe: HTTP {e.code} {e.read()[:200]!r}") from None


def script(text):
    """The Unicode script most of the letters in `text` belong to ("Latin", "Devanagari", ...), else None."""
    c = collections.Counter(unicodedata.name(ch, " ").split()[0].title() for ch in text if ch.isalpha())
    return c.most_common(1)[0][0] if c else None


def sha(path):
    h = hashlib.sha256(MODEL.encode() + MODE.encode())
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def transcribe(path, post=post_wav, cache=CACHE):
    """{"language", "text", "turns": [{"start", "end", "text"}] in seconds, "usd"} for the clip's speech, or None when
    the clip has no speech (checked first, free). `usd` is what this call cost: 0.0 when the answer was cached. Raises
    on a transport error; nothing is cached then."""
    cache = Path(cache)
    f = cache / f"{sha(path)}.json"
    if f.exists():
        return {**json.loads(f.read_text()), "usd": 0.0}
    if not has_speech(path):
        return None
    ans = post(wav_bytes(path))
    text = (ans.get("transcript") or "").strip()
    turns = [{"start": (t.get("startMs") or 0) / 1000, "end": (t.get("endMs") or 0) / 1000, "text": t.get("transcript") or ""}
             for t in ans.get("turns") or []]
    out = {"language": script(text), "text": text, "turns": turns}
    cache.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(out, ensure_ascii=False))
    return {**out, "usd": (ans.get("audioDurationMs") or 0) / 3_600_000 * USD_PER_HOUR}


def said(path, post=post_wav, cache=CACHE):
    """(the words spoken in the clip, cost in USD), or None when there are none."""
    r = transcribe(path, post, cache)
    return (r["text"], r["usd"]) if r and r["text"] else None
