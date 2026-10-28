# Label reader test: can we read "this file declares itself AI-made" and file metadata?

Written Oct 27 2026 before the reader was run on any file. Exploratory. This is not an AI-video detector. It reads what a file says about itself and reports when it says nothing.

## What the reader does

For one video file: (1) is a C2PA manifest (Content Credentials) present, found as the C2PA `uuid` box in MP4/MOV or `jumb` plus `c2pa` labels; (2) does the file contain the IPTC "digital source type" marker for AI-generated media (`trainedAlgorithmicMedia`, `compositeWithTrainedAlgorithmicMedia`, `algorithmicMedia`); (3) container tags from ffprobe: creation time, location, make and model, encoder. **It does not verify the signature**, so "present" means a manifest is there, not that it is trustworthy. A real product would verify with the C2PA library; I could not run Adobe's `c2patool` here (running a downloaded binary was blocked), so this test checks presence only.

## Files

- Signed controls: four sample videos from the C2PA project's own test fixtures (`contentauth/c2pa-rs`, `sdk/tests/fixtures`: `legacy.mp4`, `dashinit.mp4`, `nested_moov_1000.mp4`, `c.mov`), downloaded as data.
- Stripping: `c.mov` and `legacy.mp4` re-encoded with ffmpeg (`-c:v libx264`), and remuxed with `-c copy`.
- Negatives (no manifest expected): the 30 pile clips, `BigBuckBunny_320x180.mp4` from the same fixtures, my iPhone originals and their WhatsApp copies in `data/iphone_by_me`.

## Pass bar (decided now)

1. All 4 signed controls: manifest present.
2. 0 manifests reported on the negatives.
3. Re-encoded copies of the controls: report whether the manifest survives (expected: gone); the remux is reported, not scored.
4. Report which tags survive WhatsApp (creation time, location) compared with the iPhone originals.

## Not tested

A real AI-generated video from a generator that signs its output (I have none and will not generate one for this test), signature validity, SynthID or any platform's own detector, and whether a model such as Spark can tell AI video from real. "No marker found" proves nothing about a clip.
