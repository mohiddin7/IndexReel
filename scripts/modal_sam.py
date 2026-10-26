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


@app.function(image=image, gpu=["L4", "A10G", "L40S"], timeout=1800,  # first free of these; all are about $1 an hour or less, so one call costs at most about $0.50
               secrets=[modal.Secret.from_name("hf-token")],
              volumes={"/root/.cache/huggingface": weights})
def segment(clips: dict[str, bytes]) -> dict[str, bytes]:
    import numpy as np
    from sam3.model_builder import build_sam3_multiplex_video_predictor, download_ckpt_from_hf

    ckpt = download_ckpt_from_hf(version="sam3.1")
    weights.commit()
    predictor = build_sam3_multiplex_video_predictor(checkpoint_path=ckpt, use_fa3=False)

    # sam3 revision f1647e8: the base predictor's start_session always passes offload_state_to_cpu, which the
    # multiplex model's init_state does not accept. False is its default, so dropping it changes nothing.
    init_state = predictor.model.init_state
    predictor.model.init_state = lambda **kw: init_state(**{k: v for k, v in kw.items() if k != "offload_state_to_cpu"})
    import traceback
    results = {}
    for name, data in clips.items():
        try:
            path = f"/tmp/{name}.mp4"
            Path(path).write_bytes(data)
            session = predictor.handle_request(request=dict(type="start_session", resource_path=path))["session_id"]
            for phrase in PROMPTS:
                predictor.handle_request(request=dict(type="reset_session", session_id=session))
                predictor.handle_request(request=dict(type="add_prompt", session_id=session, frame_index=0, text=phrase))
                arrays = {}
                for resp in predictor.handle_stream_request(request=dict(type="propagate_in_video", session_id=session)):
                    _arrays(resp["outputs"], f"f{resp['frame_index']:03d}", arrays)
                buf = io.BytesIO()
                np.savez_compressed(buf, **arrays)
                results[f"{name}__{phrase.replace(' ', '_')}.npz"] = buf.getvalue()
                print(name, repr(phrase), len(arrays), "arrays", flush=True)
            predictor.handle_request(request=dict(type="close_session", session_id=session))
        except Exception:  # keep the other clips; the failure is saved and the run counts as INCOMPLETE
            results[f"{name}__ERROR.txt"] = traceback.format_exc().encode()
            print(name, "FAILED", flush=True)
    return results


@app.local_entrypoint()
def main(split: str = "dev", dry: bool = False, limit: int = 0):
    out = RUN / "sam_open" / split
    todo = [p for p in sorted((RUN / "in" / split).glob("*.mp4"))
            if not all((out / f"{p.stem}__{q.replace(' ', '_')}.npz").exists() for q in PROMPTS)]
    if limit:
        todo = todo[:limit]
    clips = {p.stem: p.read_bytes() for p in todo}
    print(f"{split}: {len(clips)} clips to run, {len(PROMPTS)} prompts each")
    if dry or not clips:
        return
    out.mkdir(parents=True, exist_ok=True)
    for name, blob in segment.remote(clips).items():
        (out / name).write_bytes(blob)
    errors = sorted(out.glob("*__ERROR.txt"))
    print("saved to", out, "| clips that failed:", len(errors), "(INCOMPLETE)" if errors else "")
