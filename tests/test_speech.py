import json
import wave

import numpy as np
import pytest

from indexreel import speech

SR = 16000


def wav(path, x):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    return path


def seconds(n):
    return np.arange(int(n * SR)) / SR


def speechlike(n=6, seed=0):
    """Noise whose loudness rises and falls about 4 times a second, with a pause between phrases."""
    t = seconds(n)
    env = np.clip(np.sin(2 * np.pi * 4 * t), 0, 1) ** 2 * (np.sin(2 * np.pi * 0.4 * t) > -0.3)
    return 0.3 * env * np.random.default_rng(seed).standard_normal(len(t))


def music(n=6):
    t = seconds(n)
    return 0.2 * (np.sin(2 * np.pi * 220 * t) + np.sin(2 * np.pi * 330 * t) + np.sin(2 * np.pi * 440 * t))


def test_has_speech_gate(tmp_path):
    assert speech.has_speech(wav(tmp_path / "s.wav", speechlike()))
    assert not speech.has_speech(wav(tmp_path / "silence.wav", np.zeros(6 * SR)))
    assert not speech.has_speech(wav(tmp_path / "hiss.wav", 0.0005 * np.random.default_rng(1).standard_normal(6 * SR)))
    assert not speech.has_speech(wav(tmp_path / "music.wav", music()))
    assert not speech.has_speech(wav(tmp_path / "blip.wav", np.r_[music(0.3), np.zeros(6 * SR)]))  # under a second of sound
    assert not speech.has_speech(tmp_path / "missing.wav")  # no audio track: nothing to transcribe


API = {"sessionId": "x", "transcript": "Yeah, this is Dantewada. Look at the sky.", "audioDurationMs": 36000,
       "turns": [{"turnId": 0, "startMs": 1500, "endMs": 3000, "transcript": "Yeah, this is Dantewada.", "speaker": "A"},
                 {"turnId": 1, "startMs": 3500, "endMs": 5000, "transcript": "Look at the sky."}]}


class Post:
    def __init__(self, answer=API):
        self.answer, self.sent = answer, []

    def __call__(self, wav_bytes):
        self.sent.append(wav_bytes)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def test_transcribe_returns_turns_with_times_language_and_cost(tmp_path):
    clip = wav(tmp_path / "c.wav", speechlike())
    post = Post()
    r = speech.transcribe(clip, post=post, cache=tmp_path / "cache")
    assert r["turns"] == [{"start": 1.5, "end": 3.0, "text": "Yeah, this is Dantewada."},
                          {"start": 3.5, "end": 5.0, "text": "Look at the sky."}]
    assert r["text"] == API["transcript"] and r["language"] == "Latin"
    assert r["usd"] == pytest.approx(36 / 3600 * 0.18) and len(post.sent) == 1
    assert post.sent[0][:4] == b"RIFF"  # a WAV, not the clip's own container


def test_transcribe_is_cached_by_the_clip_hash(tmp_path):
    clip = wav(tmp_path / "c.wav", speechlike())
    post = Post()
    first = speech.transcribe(clip, post=post, cache=tmp_path / "cache")
    copy = tmp_path / "other-name.wav"
    copy.write_bytes(clip.read_bytes())
    again = speech.transcribe(copy, post=post, cache=tmp_path / "cache")
    assert len(post.sent) == 1 and again["usd"] == 0.0 and {**again, "usd": 0} == {**first, "usd": 0}


def test_clips_without_speech_cost_nothing(tmp_path):
    post = Post()
    for name, x in (("silence", np.zeros(6 * SR)), ("music", music())):
        assert speech.transcribe(wav(tmp_path / f"{name}.wav", x), post=post, cache=tmp_path / "cache") is None
    assert post.sent == []


def test_a_transport_error_is_raised_and_not_cached(tmp_path):
    clip = wav(tmp_path / "c.wav", speechlike())
    with pytest.raises(RuntimeError):
        speech.transcribe(clip, post=Post(RuntimeError("down")), cache=tmp_path / "cache")
    assert not list((tmp_path / "cache").glob("*.json"))


def test_language_follows_the_script_of_the_words(tmp_path):
    clip = wav(tmp_path / "c.wav", speechlike())
    hindi = {"transcript": "यह छत्तीसगढ़ है", "audioDurationMs": 3000, "turns": [{"startMs": 0, "endMs": 900, "transcript": "यह छत्तीसगढ़ है"}]}
    assert speech.transcribe(clip, post=Post(hindi), cache=tmp_path / "c1")["language"] == "Devanagari"
    nothing = {"transcript": "", "audioDurationMs": 3000, "turns": []}
    r = speech.transcribe(clip, post=Post(nothing), cache=tmp_path / "c2")
    assert r["turns"] == [] and r["language"] is None


def test_said_gives_the_text_and_cost_or_none(tmp_path):
    clip = wav(tmp_path / "c.wav", speechlike())
    text, usd = speech.said(clip, post=Post(), cache=tmp_path / "cache")
    assert text == API["transcript"] and usd > 0
    assert speech.said(wav(tmp_path / "q.wav", np.zeros(SR * 6)), post=Post(), cache=tmp_path / "cache") is None
    empty = {"transcript": "  ", "audioDurationMs": 1000, "turns": []}
    assert speech.said(clip, post=Post(empty), cache=tmp_path / "c2") is None  # sound, but no words


def test_the_request_is_a_multipart_endpointing_upload(monkeypatch):
    seen = {}

    class R:
        def read(self):
            return json.dumps(API).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    def fake(req, timeout):
        seen["req"], seen["timeout"] = req, timeout
        return R()

    monkeypatch.setenv("MODEL_API_KEY", "k-secret")
    monkeypatch.setattr(speech.urllib.request, "urlopen", fake)
    assert speech.post_wav(b"RIFFdata") == API
    req = seen["req"]
    assert req.full_url == "https://api.meta.ai/v1/asr/transcribe" and req.get_method() == "POST"
    assert req.get_header("Authorization") == "Bearer k-secret"
    assert req.get_header("Content-type").startswith("multipart/form-data; boundary=")
    body = req.data
    assert b'"mode": "ENDPOINTING"' in body and b"muse-voice-transcribe-1.0" in body and b'"audioEncoding": "WAV"' in body
    assert b"RIFFdata" in body


def test_post_wav_never_puts_the_key_in_an_error(monkeypatch):
    import io
    import urllib.error

    def boom(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 401, "no", {}, io.BytesIO(b"bad key"))

    monkeypatch.setenv("MODEL_API_KEY", "k-secret")
    monkeypatch.setattr(speech.urllib.request, "urlopen", boom)
    with pytest.raises(RuntimeError) as e:
        speech.post_wav(b"x")
    assert "401" in str(e.value) and "k-secret" not in str(e.value)
