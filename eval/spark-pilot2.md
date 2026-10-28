# Spark pilot 2: recent footage, real-world edits, hard negatives

Written Oct 26 2026 before the first call of this round. Pilot 1 (`eval/spark-pilot.md`, result in `eval/spark-pilot-result.md`) passed, but its events were famous (training-data risk), its negatives were easy and its copies were mild. This round fixes those three things. Exploratory, not the gate.

## Research use of third-party footage

These clips were downloaded for private research only. They stay in `data/spark_pilot2/` (ignored by git), are never rehosted, and never in the repo or any published material.

## Data (all uploaded Oct 2026 or earlier; ids are YouTube video ids, checked for upload date and description)

Event A, Phoenix-area meteor, Oct 6 2026 about 01:04 local. Four cameras:
- A1 `7aI5RXbjQ4w` backyard security camera, Mesa, looking north
- A2 `ck8_RKGdJf4` "AZ Meteor Over Phoenix"
- A3 `rL0e0hD2T3k` "Huge meteor over Phoenix"
- A4 `mGOXiJWIpIQ` Scottsdale

Event B, Falcon 9 CRS-35 launch, Oct 13 2026, early morning:
- B1 `Bbwieo6Qq8o` Florida, trimmed to the launch
- B2 `77Q4UNqDZTs` dashcam over North Carolina, about 6:40 am

Hard negatives, same kind of event, different event:
- N1 `k6xMJps3igE` Winnipeg meteor, Oct 5 2026, security camera (near in time, similar look)
- N2 `55nx36neZGc` American Meteor Society, Phoenix, May 10 2026
- N3 `y2sIq3jWdmY` American Meteor Society, Phoenix, Aug 31 2026
- N4 `g4x2zOjR130`, N5 `75TwSw8b_dg`, N6 `iGDWmGBS-rw`: Phoenix meteor, June 2 2016 (older clip, same city)

Clips are cut to at most 30 seconds, 640 pixels wide at most, mp4.

## Real-world edits (made with ffmpeg)

- e1: mirrored and 1.25x faster
- e2: vertical 9:16 reframe with blurred background, caption bar and logo block (short-video style)
- e3: picture-in-picture, the clip shrunk into a corner over a coloured studio background with a banner
- e4: compilation, 6 seconds of A1, then 6 of N1, then 6 of A3
- e5: re-encoded small with the audio replaced by a tone

## Pairs (48), each asked once, A/B order fixed by seed

- Edited copies, expect same_footage yes (14): A1, A3, A4 and B2 with e1 and e2 (8); A1 and A3 with e3 (2); e4 against A1, N1 and A3 (3, partial reuse); A2 with e5 (1).
- Other camera, same moment, expect same_event yes and same_footage no (9): all six A pairs, plus three edited-against-other-camera pairs (A1_e2 vs A2, A3_e1 vs A4, A4_e1 vs A1).
- Same event, no shared view (1): B1 vs B2. Reported, not scored.
- Hard negatives, expect same_event no and same_footage no (24): each of A1 to A4 against N1, N2, N3 (12) and against N4, N5, N6 (12).

## Prompt (v2, frozen in `scripts/spark_pilot2.py`)

Two videos. Answer JSON only. same_event: same real-world occurrence at overlapping moments, yes, no or unsure. same_footage: either video contains footage from the same original camera recording as the other (it may be re-encoded, resized, cropped, mirrored, sped up, overlaid, given other music, or only partly reused). Different cameras on the same event are same_event yes and same_footage no. A video cut together from several recordings has same_footage yes if any part comes from the other video's recording. Also shared_span_a and shared_span_b in seconds when same_footage is yes, else null, plus up to three observations and an unsure reason. Model `muse-spark-1.3`, Standard mode, default reasoning, no tools.

## Recall probe (one clip at a time, 13 calls)

"Where and when was this filmed? Answer a place and a date only if you can see or hear evidence, otherwise say unknown." Asked of every clip, to see whether Spark names the Oct 2026 events (it should not) and whether it dates the 2016 clips from content or by recognising them.

## Pixel matcher on the same pairs

`indexreel.match.score` (PDQ, frozen, mirror-aware) on every pair, to build a disagreement table: Spark says same footage and PDQ does not, or the reverse.

## Pass bar (decided now)

1. Edited copies: same_footage yes on at least 11 of 14.
2. Other camera, same moment: same_footage no on all 9, and same_event yes on at least 7 of 9.
3. Hard negatives: same_event no on at least 22 of 24, and same_footage yes on 0 of 24.
4. Compilation pairs: when Spark gives a shared span, it must overlap the true span (A1 from 0 to 6 seconds, N1 from 6 to 12, A3 from 12 to 18 in the compilation). Reported, not a pass condition.

PASS needs 1, 2 and 3. One false merge (same_footage yes on any non-copy pair) is a FAIL for using Spark as a reader in the product, whatever else happens.

## Honesty notes

48 pairs and one run show failure modes, not a rate. Dates of the Oct 2026 events come from the uploaders and from news articles (Space.com and Axios Phoenix on the Oct 6 meteor), not from me. Spark's training cutoff is unknown to me; the recall probe tests it, it does not prove it.
