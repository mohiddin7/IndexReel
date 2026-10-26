# Day-1 gate: pre-registration

I wrote this on Oct 26 2026, before the first SAM call and before any gate footage was scored. I commit it before I run anything. After that I don't change the rules below; if I do, I log why and the result counts as development evidence, not as the gate.

## Question

Does SAM 3.1 localisation recover picture-in-picture (PiP) and re-filmed copies better than a fair OpenCV control, with no false merges, on footage I haven't tuned on?

This tests localisation on prepared copy fixtures. It does not show that IndexReel finds recordings in the wild.

## Data

- 8 scene blocks split as 4 dev and 4 gate. Each block has one target recording `T` and one look-alike `N` (same kind of scene, recorded separately). That is 8 families per split.
- Each family has 3 versions: `orig`, `pip` (the clip boxed into a studio-style template) and `refilm_sim` (simulated re-film: screen warp, bezel, glare, shake).
- Templates are shared between unrelated families inside a split, so false merges on template look-alikes can show up.
- 24 clips per split, 276 pairs, 24 positive pairs.
- Every original is a non-political, non-war clip with a recorded licence. The Commons clips from the Oct 22 spike are for debugging only and are not in either split.
- Physical phone re-films are scored separately later and never decide the gate.

## Preprocessing

Ten-second clips, resampled to 640x360 at 5 fps, exactly 50 frames. Both localisers get identical pixels. The processed output is written at 10 fps by duplicating each frame, so the existing scorer samples 1 fps.

## Arms

- **cv**: OpenCV control. Grayscale, Gaussian 5x5 sigma 1, Canny(50,150), close 3x3 once, all contours through the quad checks below. The fixed PiP rectangle is one more candidate.
- **sam**: SAM 3.1 video, prompts `screen` and `video inset`, each once per clip. I use the first completed response and never a best-of rerun. Masks from both prompts are pooled.

## Quad rule (both arms)

Take the largest 8-connected component of a mask (or the contour), its convex hull, and approximate with epsilon = 0.02 x perimeter. Accept only if it has four convex vertices, area between 5% and 90% of the frame, and every edge at least 16 px.

Rank candidates by: mean absolute grayscale change inside the quad from the previous frame, then the fraction of boundary pixels within 2 px of a Canny edge, then area, then coordinates. No matcher score takes part in selection. Sort corners clockwise from the minimum x+y, warp to (0,0),(639,0),(639,359),(0,359). If no valid quad exists, use the full frame and log it. Keep the original frame beside every warp.

No manual boxes, no routing by filename, no reference-assisted choice.

## Matching and threshold

PDQ is the primary matcher, SSCD (224 px, unchanged from the spike) is secondary and not used for the verdict. Minimum matched-frame coverage 50%. The threshold is `max(0.5, highest PDQ score among negative dev pairs)`, set on dev only, accepted strictly above.

## Pass rule

PASS needs all of these:
1. Zero false merges on the gate split, for both arms.
2. SAM recovers at least 3 of 4 gate targets on PiP and at least 3 of 4 on re-film.
3. On at least one of those transforms, SAM recovers at least one more target than cv.

FAIL: any other complete result. INCOMPLETE: any API failure, missing credit or partial run. INCOMPLETE is never read as PASS.

With 4 targets per transform, four SAM-only wins give a one-sided sign test of p = 1/16, so this is an engineering go/no-go, not proof that SAM is better. I report every paired outcome, not only the verdict.

## What each result does

- **PASS**: SAM is the localiser in the product. Real phone re-films are reported next to it.
- **FAIL**: the OpenCV localiser ships as the default and SAM goes into the ablation as an honest red cell. I do not pivot to another idea. The event-coder and bulletin-coder ideas use terrorism and conflict data, which the participant guide lists as a banned topic ("anything political or involving war"). I may spend at most 3 hours on one extra try, a Muse Spark or Muse Wonder localiser, scored on dev only and reported as such.
- **INCOMPLETE**: I run the cv arm, retry SAM the next morning, and build the matching core in the meantime. I make no decision on partial data.

Deadline for a decision: Tue Oct 27, 11 PM ET.

## Cost

8 blocks x 2 recordings x 3 versions x 50 frames x 2 prompts = 4,800 billed frames = $0.96. A full retry makes it $1.92. Video requests bill at least 50 frames, so I don't switch to image requests.

## Not allowed

Changing prompts, quad rules, threshold, split membership or the pass rule after I see gate results. Tuning on gate. Re-running SAM until it passes.

## Report

For each arm: false merges, the four paired outcomes per transform, k/4 with Wilson 95% intervals, the threshold, any full-frame fallbacks, cost and latency.

## Amendment 1 (Oct 26, before any gate-split output and before any SAM call)

The first dev run of the OpenCV control scored 0 of 4 on both transforms with zero full-frame fallbacks. The cause is in my rules: the fixed inset rectangle is a candidate, but nothing says when a candidate is good enough to accept, so the control cropped that patch out of every clip, including the plain originals, and broke their matches. SAM returns nothing when a concept is absent, so this made the control unfairly weak.

Change: an OpenCV candidate counts only if its edge support is at least theta. Edge support is the share of the quad's boundary pixels that lie within 2 px of a Canny edge. I set theta on dev only, from {0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9}: the largest theta that gives the highest dev total (PiP hits plus re-film hits). Then I freeze it for the gate split. Nothing else changes. SAM output is accepted as returned, with the same quad rule and no confidence cut-off. I keep the theta = 0 result in the report as a diagnostic.
