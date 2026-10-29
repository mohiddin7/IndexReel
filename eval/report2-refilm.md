# Held-out run 2, real re-film arm: result (Oct 28 2026)

Protocol: `eval/heldout2-refilm.md`, frozen at `175eeb5` before any re-film existed. Addendum A (`18a42e4`): WhatsApp only, and the run uses a `23614a4` checkout. Addendum B (`660c8a9`): verify crashed on an incomplete answer, and the patch was committed before any verdict existed. The code is `23614a4` plus that patch. Script: `scripts/heldout.py prepare_refilm` and `score_refilm`. The pile holds the 16 final2 originals and 32 phone re-films posted through WhatsApp and downloaded back: 48 clips, 1,128 pairs, run once, no human decisions.

## Verdict: PASS

| | result | bar |
|---|---|---|
| 1 False merges (joined pairs of different originals) | **0 / 1,080** (Wilson 95% 0.0000 to 0.0035); no recording mixes two originals | 0 |
| 2 Re-films in the same recording as their own original | **27 / 32** (84%, Wilson 95% 0.68 to 0.93) | at least 75% |
| By framing | landscape **16/16**, portrait **11/16** | reported |
| By platform | WhatsApp 27/32 (one level, Addendum A) | reported |
| Matcher alone (own original in `merged`) | 23 / 32 | reported |
| Compilation flags after verify | 0 | reported, expected 0 |
| Verifier cost | $0.469 at list prices (48 pairs verified, 9 re-asked), of which $0.018 in the rerun after Addendum B | reported |

## Pair by pair

- **Negatives:** the matcher put all 1,080 in `apart`, and the highest negative scored aligned 0.185. Bar 1 therefore rests on the matcher alone, and the verifier saw no negative here. Before verify, the frozen automatic rule had flagged 2 compilations on the matcher's bands. After verify demoted some links, no flag was left.
- **Own-original pairs (32):**
  - Of 23 `merged`, the verifier said `same` on 21 and `abstain` on 2 (`rf21`, `rf22`). Those 2 were demoted to `unresolved`. That is the recall cost of verifying merged pairs (fix b).
  - Of 9 `unresolved`, the verifier said `same` on 6 and `different` on 3 (`rf12`, `rf16`, `rf30`).
  - None was `apart`.
- **Re-film against re-film pairs of one original (16):** the verifier said `same` on 9 and demoted 5 of the 12 the matcher had merged (3 `different`, 2 `abstain`). The recordings still join through the own-original pairs.
- **Re-asks:** 9 pairs, all ending `same`.
- **Incomplete or unparsed answers:** 1 full-fidelity call and 2 entries in group answers. After Addendum B these count as no answer.

## The five misses

All five are portrait takes: four from playlist B2 and one from B1. All have "no shared detail named" as the reason, and the clips have no usable sound.

| re-film | original | band, aligned | verdict |
|---|---|---|---|
| rf12 | b20_T | unresolved, 0.503 | different |
| rf16 | b18_N | unresolved, 0.506 | different |
| rf30 | b19_N | unresolved, 0.505 | different |
| rf21 | b18_T | merged, 0.597 | abstain (demoted) |
| rf22 | b22_T | merged, 0.611 | abstain (demoted) |

None of these is a false merge. Each one leaves its re-film in a recording of its own (or `unresolved`) for a person to decide, which is the safe failure.

## What this says

- On real phone re-films of fresh recordings, sent through WhatsApp and filmed tight with no bezel, the pipeline joined 84% of re-films to their own original and joined nothing wrongly. Landscape re-films were all found.
- **The weak spot is the verifier on portrait re-films.** The matcher's scores for the missed pairs (0.50 to 0.61) are near those of true pairs that were found. The cheap 180 px judge said `different` or abstained without naming a detail. A portrait re-film of a landscape original, shrunk to 180 px on its short side, leaves very little picture. Without the verifier, the matcher alone would have found 23/32, so the verifier added 6 and removed 2.
- Verifying merged pairs (fix b) cost 2 own-original pairs and 5 re-film pairs here, and caught nothing, because no negative reached `merged`. On this set its price was recall without a safety gain. That is the trade-off it was chosen for, and it is now measured.
- A rule that sends portrait clips, or `different` verdicts that name no detail, to the full-fidelity judge could recover these misses. That is a hypothesis for new data, not something this split can test.

## Limits

One person, one phone, one screen and one room. 32 re-films of 16 originals, and re-films of one take are not independent: 4 of the 5 misses share the B2 take. WhatsApp only. The verifier ran on the frozen code plus the Addendum B patch, not on main (main also has the reason and `verify_same_event` changes, which do not affect verdicts). Run once.
