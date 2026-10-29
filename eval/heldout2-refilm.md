# Held-out run 2, real re-film arm: phone re-films of the final2 originals, posted and downloaded back

Written Oct 28 2026, before any re-film of the final2 originals exists and before any final2 clip was opened by me (I have seen only the file list). Frozen by the commit that adds it. This is a separate protocol from `eval/heldout2.md` (the simulated arm). Both use the same code, and nothing in code or thresholds changes between the two runs, whichever runs first.

## Question

Does the pipeline put a realistic phone re-film of a recording into the same recording as its original after the re-film has been posted to a platform and downloaded back, without joining it to any other recording? The re-films are handheld, filmed tight with no bezel, and some are portrait.

## Data

- **Originals:** the 16 final2 sources `data/final2/b17_T.mp4` to `b24_N.mp4`, each a target or its look-alike from 8 blocks, unchanged.
- **Re-films:** made by me after this commit. Each one films an original playing on a screen, handheld, framed tight with no bezel visible, some in portrait. Each take is posted through X or WhatsApp and the platform's copy is downloaded back. Only the downloaded copy is used.
- **Manifest:** `data/final2_refilm/manifest.csv`, written when the re-films are made and before any is scored, with one row per re-film: `file`, `original` (for example `b19_T`), `framing` (`landscape` or `portrait`), `platform` (`x` or `whatsapp`). Truth comes from the manifest by construction. File names never reach the models: the matcher reads pixels, and the judge sees "Video A" and "Video B".
- `scripts/heldout.py prepare_refilm` puts the 16 originals and every re-film (named `refilm_<stem>`) into one folder, so the run is one pile: every re-film is scored against all 16 originals and against every other re-film.

## Pipeline (frozen)

- Code at commit `23614a4`, the same as `eval/heldout2.md`: `indexreel match` (`merge_at` 0.55, `floor` 0.20, theta 0.9, mirrored margin 0.02, SSCD sha256 `9f26bd4c848cc19b73d2ae92eea6e04886f61a7b764ceb7a13aeee62e6a6db56`), then `python -m indexreel.verify` (verifier from `6119685`: every merged and unresolved pair, conflict re-asks, at most 2 rounds), then `cluster.resolve`.
- Commands: `indexreel match data/heldout2_refilm/in --out data/heldout2_refilm/run`, then `python -m indexreel.verify data/heldout2_refilm/run --cache data/heldout2_refilm/verify_cache --max-usd 10` (fresh cache), then `scripts/heldout.py score_refilm`. No human decisions; run once.

## Decision rule

A re-film is **found** when `cluster.resolve` puts it in the same recording as its own original. A pair is **joined** when its effective band is `merged` and neither clip is marked a compilation.

## Pass bar

1. **No false merges:** 0 joined pairs between clips of different originals (re-film against original, and re-film against re-film), and no recording that mixes two originals.
2. **Found:** at least 75% of the re-films are found (the H5 bar, `eval/refilm-h5.md`).

A bar 1 failure is a FAIL whatever else happens.

## Reported, not scored

- Found rate by framing (landscape, portrait) and by platform (X, WhatsApp), each as k/n.
- Each own-original pair by band and verdict.
- The matcher alone (own original in the `merged` band) against matcher plus verifier.
- Every miss, with its framing, platform, aligned score, band and verdict reason. A miss in the `apart` band never reached the verifier, and the report says so.
- Compilation flags (expected 0). Re-asks. Cost at list prices.

## Limits

One person, one phone, one screen and one room. The 16 originals come in 8 target and look-alike pairs. Re-films of one original are not independent of each other. The platforms' processing on the day of upload is whatever it was then. Sound is the screen's speaker recorded by the phone, and the final2 sources may be silent. The arm tests the shipped pipeline on realistic copies of fresh recordings, not on copies found in the wild.

## Addendum A (Oct 28, before any re-film exists)

All takes go through WhatsApp only (a licensing choice made before filming). The manifest's `platform` column is therefore `whatsapp` on every row, and the per-platform breakdown has one level. Nothing else changes. The run uses a detached checkout of `23614a4` for matching, verifying and scoring (`cluster.resolve`), because later commits changed how a detected compilation is counted; with no compilation detected, the two give identical output.

## Addendum B (Oct 28, after a crash in the verify step, before any verdict)

The run started once as frozen, from a detached checkout of `23614a4` with a fresh answer cache. The 32 re-films were checked against the manifest (32 rows, all files present, originals b17 to b24, framing landscape or portrait, platform whatsapp, unique names).

- **Match finished.** Its one-line summary is all I saw of the results: 1,128 pairs (35 `merged`, 13 `unresolved`, 1,080 `apart`) and 22 recordings, 2 of them flagged as compilations by the frozen automatic rule. This set has no compilations, so those 2 flags will be reported as false flags.
- **Verify crashed before writing `pairs.csv`.** One full-fidelity re-ask (360 px, default effort, `max_output_tokens` 4000) raised "Didn't receive a response.completed event" on all 3 tries. Most likely the reasoning used the whole output allowance and the API ended the response as incomplete, which the frozen code treats as a transport error. The cache held 32 group answers and 17 full-fidelity answers, $0.451 at list prices; the failed tries were not logged and cost at most about $0.03 each. No verdict was written, read or scored.
- **Patch** (also on main as `3ff95f6`, with tests showing that an incomplete answer can never become `same`). `_ask` reads the stream's final event. A response that ends incomplete or failed is no answer for that order, at its reported cost, and is not asked again. Only a stream with no final event is retried as a transport failure. The prompts, effort, output caps, grouping, escalation and decision rule are unchanged. A missing full-fidelity answer leaves the pair `abstain` unless the other order said yes, the same rule as before.
- **Rerun:** the same checkout with only this patch applied, `verify` run once more with the same answer cache (the 49 answered calls stay as they were; only missing calls are made), total under the $10 cap, then `score_refilm` once. The bars do not change.

The patch applied to `23614a4`:

```diff
diff --git a/src/indexreel/verify.py b/src/indexreel/verify.py
index 13d2bcc..75ba72e 100644
--- a/src/indexreel/verify.py
+++ b/src/indexreel/verify.py
@@ -112,14 +112,17 @@ class SparkJudge:
         return self.ids[key]
 
     def _ask(self, content, **kw):
-        for attempt in range(3):  # transport failures only (no response.completed); an answer is never re-asked
+        for attempt in range(3):  # transport failures only (no final event); an answer is never re-asked
             try:
-                text = []
+                text, final = [], None
                 with self.cli.responses.stream(model=MODEL, input=[{"type": "message", "role": "user", "content": content}], **kw) as s:
                     for ev in s:
                         if ev.type == "response.output_text.delta":
                             text.append(ev.delta)
-                    u = s.get_final_response().usage
+                        elif ev.type in ("response.completed", "response.incomplete", "response.failed"):
+                            final = ev.response
+                if final is None:
+                    raise RuntimeError("the stream ended without a final event")
                 break
             except RuntimeError:
                 if attempt == 2:
@@ -129,9 +132,11 @@ class SparkJudge:
             ans = json.loads(m.group(0)) if m else None
         except json.JSONDecodeError:
             ans = None
-        cached = u.input_tokens_details.cached_tokens or 0
-        cost = ((u.input_tokens - cached) * PRICE["input"] + cached * PRICE["cached"] + u.output_tokens * PRICE["output"]) / 1e6
-        return ans, cost
+        u = final.usage
+        cached = (u.input_tokens_details.cached_tokens or 0) if u and u.input_tokens_details else 0
+        cost = ((u.input_tokens - cached) * PRICE["input"] + cached * PRICE["cached"] + u.output_tokens * PRICE["output"]) / 1e6 if u else 0.0
+        # an answer cut off at max_output_tokens, or failed, is no answer for this order: it can never count as same
+        return (ans if final.status == "completed" else None), cost
 
     def group(self, anchor, candidates):
         content = [{"type": "input_text", "text": GROUP_PROMPT + "\nVideo A:"}, {"type": "input_file", "file_id": self._file(anchor, 180)}]
```
