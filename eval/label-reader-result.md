# Label reader test: result (Oct 27 2026)

Protocol: `eval/label-reader.md` (written before running). Code: `scripts/label_reader.py`. Presence only; signatures not verified. `c2patool` could not be run (running a downloaded binary was blocked), and `c2pa-python` did not build here.

**Correction to my protocol:** I assumed all four fixture videos were signed. They are not. The C2PA project's own tests use `c.mov`, `nested_moov_1000.mp4` and `BigBuckBunny_320x180.mp4` as *unsigned inputs* that the tests then sign (I checked by searching their test code; I did not verify with `c2patool`). Only `legacy.mp4` and `dashinit.mp4` carry a manifest. So the real controls are 2 signed, 3 unsigned.

| Check | Result |
|---|---|
| Signed controls (`legacy.mp4`, `dashinit.mp4`) show a manifest | **2 of 2** |
| Unsigned files (`c.mov`, `nested_moov_1000.mp4`, `BigBuckBunny`) | 0 of 3 reported (correct) |
| False positives on 63 negatives (30 pile clips, 16 iPhone originals, 17 WhatsApp copies) | **0** |
| Re-encode (`libx264`) of the signed files | manifest **gone** in both |
| Remux only (`-c copy`) | manifest **gone** in both (ffmpeg dropped it) |
| AI-generated marker found anywhere | 0 (no signed AI file in the test) |
| Tags on 16 iPhone originals | creation time 16, make 14, model 16, no GPS |
| Tags on the same clips after WhatsApp | **none**, 0 of 17 |

What it says: reading a manifest is easy and has no false alarms here, but it disappears with any re-encode or even a plain ffmpeg remux, and a WhatsApp copy loses all metadata including the capture time. So "no marker found" tells us nothing about a clip that has been through a platform. The reader is only useful as "this file itself declares X". It cannot say a clip is real.

Not tested: a real AI-generated file from a generator that signs its output, signature validity, SynthID or any platform detector, and whether Spark can classify AI video.
