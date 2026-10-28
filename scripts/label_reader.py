"""Read what a video file says about itself: C2PA manifest present, AI-generated marker, container tags.
Protocol: eval/label-reader.md. Presence only: the signature is NOT verified.

  python -I scripts/label_reader.py file1 file2 ...
"""
import json
import mmap
import subprocess
import sys

C2PA_UUID = bytes.fromhex("d8fec3d61b0e483c92975828877ec481")  # C2PA manifest box in MP4/MOV
AI_TYPES = (b"trainedAlgorithmicMedia", b"compositeWithTrainedAlgorithmicMedia", b"algorithmicMedia")
TAGS = ("creation_time", "location", "com.apple.quicktime.location.ISO6709", "com.apple.quicktime.make",
        "com.apple.quicktime.model", "encoder", "com.apple.quicktime.creationdate")


def read(path):
    with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
        present = m.find(C2PA_UUID) >= 0 or (m.find(b"jumb") >= 0 and m.find(b"c2pa") >= 0)
        ai = [t.decode() for t in AI_TYPES if m.find(t) >= 0]
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags:stream_tags", "-of", "json", str(path)],
                         capture_output=True, text=True).stdout
    tags = {}
    for blob in [json.loads(out or "{}").get("format", {}).get("tags", {})] + [s.get("tags", {}) for s in json.loads(out or "{}").get("streams", [])]:
        tags.update({k: v for k, v in blob.items() if k in TAGS})
    return {"c2pa": present, "ai_marker": ai, "tags": tags}


if __name__ == "__main__":
    for p in sys.argv[1:]:
        r = read(p)
        print(f"{p.split('/')[-1][:40]:40} c2pa={int(r['c2pa'])} ai={','.join(r['ai_marker']) or '-'} tags={sorted(r['tags']) or '-'}")
