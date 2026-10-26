"""Run the open SAM 3.1 weights on a Modal GPU for the gate (Amendment 2 in eval/gate.md).

One-time setup (in my own terminal, never in a file here):
  uv pip install --python .venv/bin/python modal "cbor2<6"   # cbor2 6 has no wheel for an Intel Mac
  .venv/bin/modal setup
  .venv/bin/modal secret create hf-token HF_TOKEN=<my read token>

Switching workspace when one runs out of credit (no code change; nothing in this file names a workspace):
  .venv/bin/modal profile list
  .venv/bin/modal profile activate <other profile>        # or: MODAL_PROFILE=<other> .venv/bin/modal run ...
  .venv/bin/modal secret create hf-token HF_TOKEN=<token>  # secrets are per workspace, so create it once in each
The weights cache volume is created in the new workspace on first use and downloads the checkpoint once more (a few GB, minutes).

Run:
  .venv/bin/modal run scripts/modal_sam.py --split dev --dry   # list clips and stop
  .venv/bin/modal run scripts/modal_sam.py --split dev --limit 1    # one-clip smoke test first
  .venv/bin/modal run scripts/modal_sam.py --split dev

Raw per-frame outputs are saved untouched to data/gate_run/sam_open/<split>/<clip>__<prompt>.npz and decoded later.
"""
import io
from pathlib import Path

import modal

SAM3_COMMIT = "f1647e8d0c1d280991f4d1b7d974c2704537fe66"  # facebookresearch/sam3 main on Oct 26 2026
PROMPTS = ("screen", "video inset")  # frozen in eval/gate.md
RUN = Path(__file__).resolve().parents[1] / "data" / "gate_run"

app = modal.App("indexreel-sam")
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git", "ffmpeg", "libgl1", "libglib2.0-0")
    .pip_install("torch==2.10.0", "torchvision", index_url="https://download.pytorch.org/whl/cu128")
    .pip_install(f"git+https://github.com/facebookresearch/sam3.git@{SAM3_COMMIT}", "opencv-python-headless",
                 "huggingface_hub", "numpy<2", "einops", "pycocotools", "psutil", "timm>=1.0.17", "iopath>=0.1.10",
                 "ftfy==6.1.1", "regex", "tqdm", "typing_extensions", "setuptools<81",  # pkg_resources
                 "scipy", "hydra-core", "omegaconf")  # every module-level import that sam3's model builder reaches
)
weights = modal.Volume.from_name("indexreel-hf-cache", create_if_missing=True)


def _arrays(obj, prefix, out):
    """Flatten whatever the predictor returns into named numpy arrays, so nothing is lost or interpreted."""
    import numpy as np
    if isinstance(obj, dict):
        for k, v in obj.items():
            _arrays(v, f"{prefix}/{k}", out)
    elif hasattr(obj, "detach"):
        out[prefix] = obj.detach().cpu().numpy()
    else:
        try:
            a = np.asarray(obj)
            out[prefix] = a if a.dtype != object else np.asarray(str(obj))
        except Exception:
            out[prefix] = np.asarray(str(obj))


# L4 (24 GB) ran out of memory on clips with tracked objects. L40S has 48 GB and costs about $2 an hour, so the
# 60-minute timeout caps one call at about $2. A100-40GB is the fallback.
@app.function(image=image, gpu=["L40S", "A100-40GB"], timeout=3600,
              secrets=[modal.Secret.from_name("hf-token")],
              volumes={"/root/.cache/huggingface": weights})
def segment(clips: dict[str, bytes]):
    """Yields (file name, bytes) after each clip, so a late failure never loses finished clips."""
    import json
    import time
    import traceback

    import numpy as np
    import torch
    from sam3.model_builder import build_sam3_multiplex_video_predictor, download_ckpt_from_hf

    ckpt = download_ckpt_from_hf(version="sam3.1")
    weights.commit()
    t0 = time.time()
    predictor = build_sam3_multiplex_video_predictor(checkpoint_path=ckpt, use_fa3=False)
    load_s = time.time() - t0
    gpu = torch.cuda.get_device_name(0)

    # sam3 revision f1647e8: the base predictor's start_session always passes offload_state_to_cpu, which the
    # multiplex model's init_state does not accept. False is its default, so dropping it changes nothing.
    init_state = predictor.model.init_state
    predictor.model.init_state = lambda **kw: init_state(**{k: v for k, v in kw.items() if k != "offload_state_to_cpu"})

    for name, data in clips.items():
        session, stats = None, {"gpu": gpu, "model_load_s": round(load_s, 1), "prompts": {}}
        try:
            path = f"/tmp/{name}.mp4"
            Path(path).write_bytes(data)
            # frames stay in CPU memory and cached per-frame outputs are evicted as they stream; neither changes masks
            session = predictor.handle_request(request=dict(type="start_session", resource_path=path,
                                                            offload_video_to_cpu=True))["session_id"]
            files = {}
            for phrase in PROMPTS:
                torch.cuda.reset_peak_memory_stats()
                t = time.time()
                predictor.handle_request(request=dict(type="reset_session", session_id=session))
                predictor.handle_request(request=dict(type="add_prompt", session_id=session, frame_index=0, text=phrase))
                arrays = {}
                for resp in predictor.handle_stream_request(request=dict(type="propagate_in_video", session_id=session,
                                                                         evict_cached_frame_outputs=True)):
                    _arrays(resp["outputs"], f"f{resp['frame_index']:03d}", arrays)
                buf = io.BytesIO()
                np.savez_compressed(buf, **arrays)
                files[f"{name}__{phrase.replace(' ', '_')}.npz"] = buf.getvalue()
                stats["prompts"][phrase] = {"seconds": round(time.time() - t, 2), "frames": len(arrays) // 6,
                                            "peak_gpu_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2)}
                print(name, repr(phrase), stats["prompts"][phrase], flush=True)
            files[f"{name}__stats.json"] = json.dumps(stats).encode()
            yield from files.items()
        except Exception:  # keep the other clips; the failure is saved and the run counts as INCOMPLETE
            print(name, "FAILED", flush=True)
            yield f"{name}__ERROR.txt", traceback.format_exc().encode()
        finally:  # always free the session, or one failure starves every later clip
            if session:
                try:
                    predictor.handle_request(request=dict(type="close_session", session_id=session))
                except Exception:
                    pass
            torch.cuda.empty_cache()


@app.local_entrypoint()
def main(split: str = "dev", dry: bool = False, limit: int = 0):
    out = RUN / "sam_open" / split
    for stale in out.glob("*__ERROR.txt"):  # errors from an earlier attempt; the clip is retried below
        stale.unlink()
    todo = [p for p in sorted((RUN / "in" / split).glob("*.mp4"))
            if not all((out / f"{p.stem}__{q.replace(' ', '_')}.npz").exists() for q in PROMPTS)]
    if limit:
        todo = todo[:limit]
    clips = {p.stem: p.read_bytes() for p in todo}
    print(f"{split}: {len(clips)} clips to run, {len(PROMPTS)} prompts each")
    if dry or not clips:
        return
    out.mkdir(parents=True, exist_ok=True)
    for name, blob in segment.remote_gen(clips):
        (out / name).write_bytes(blob)
        print("saved", name, flush=True)
    errors = sorted(out.glob("*__ERROR.txt"))
    print("saved to", out, "| clips that failed:", len(errors), "(INCOMPLETE)" if errors else "")
