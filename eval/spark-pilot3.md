# Spark pilot 3: overlays masked, order swapped, stricter "same event"

Written Oct 26 2026 before the first call of this round. Pilot 2 (`eval/spark-pilot2-result.md`) found Spark strong on "same recording" (14 of 14 edited copies, no false merge) but weak on "same event" (said yes on 10 of 24 different-event pairs), and 39 of 48 answers cited a burned-in clock or overlay. This round tests whether the recording result survives with the text removed and whether a stricter event question separates same-event from different-event.

## Changes from pilot 2

- Same 12 source clips and the same five edits, rebuilt after a black bar covers the top 13% and bottom 13% of every source frame. That hides the burned-in clocks and watermarks seen in A1, A2, A3, A4, B2, N1, N4 and N5. I check a montage of the masked frames before the first call; if any text is still readable I widen the bars and say so here.
- The 48 pairs of pilot 2, plus 8 new easy-sanity negatives (each of A1 to A4 against B1 and B2, a meteor against a rocket) that a stricter prompt must still call "no". 56 pairs.
- Every pair is asked twice, once as A then B and once as B then A. 112 calls.
- Prompt v3 (frozen in `scripts/spark_pilot3.py`): same_footage as before, plus "judge the picture and sound, not on-screen text". same_event may be "yes" only if Spark names a specific detail shared by both (same landmarks or place, same light path and timing); a similar kind of event is not enough; "unsure" if it cannot name one; "no" if the details contradict. The answer includes shared_detail.

## Pass bar (decided now)

1. Edited copies (14): same_footage yes in both orders on at least 12.
2. No false merge: same_footage yes on none of the 42 non-copy pairs, in either order.
3. Hard negatives (24): same_event yes in either order on at most 2. "Unsure" is acceptable.
4. Easy negatives (8): same_event no in both orders on at least 7.
5. Order consistency: same_footage identical across the two orders on at least 90% of the 56 pairs.
6. Reported, no bar: same_event answers on the 9 same-event pairs (they may drop to "unsure" once the clocks are gone, which would be honest), compilation spans, how often observations still cite text.

PASS needs 1, 2, 3, 4 and 5. If 1 fails, the pilot 2 result was an overlay-reading shortcut and Spark is not the recording verifier. If 3 fails, Spark stays out of any "same event" claim.

## Cost

About $2.3 (112 calls at about $0.02). Stop if the first 10 calls average over $0.04.
