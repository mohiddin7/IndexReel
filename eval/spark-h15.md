# H15: escalate conflicts to the full-fidelity judge

Written Oct 27 2026 before the run. In H14 one missed copy pair made the consistency rule mistake `B2` for a compilation. A cheap judge will sometimes miss; the harness should not turn a miss into a merge decision. Escalation: when the rule sees a conflict (a clip yes-linked to two clips judged "no" or "unsure" against each other), the conflicting pair is re-asked with the full-fidelity judge before the clip is called a compilation.

## Design

From the H14 answers (`data/spark_h14/results.jsonl`): every conflicting pair (x, y) around a flagged clip. Each is asked again at **native size (360 px), default reasoning effort, prompt v3 (one pair per request), in both orders** (the pile test's judge). A conflict is **cleared** if either order says yes (x and y are the same recording, so the clip is not a compilation); otherwise it stands. A clip is a compilation only if at least one conflict stands. Then merges, components and the count as in H14. The merge of a cleared pair is added as a yes link.

## Pass bar (decided now)

1. **18** recordings.
2. **0** false merges, compilation merged with nothing.
3. Extra cost at most $0.50.

## Reported

The conflicts raised, their answers in both orders, and which were cleared.

## Limits

Chosen after seeing the failure on this same pile, so a pass is development evidence only; a clearing yes from the full-fidelity judge could itself be wrong (it had 0 false yes in 169 non-copy pairs on layout-edited clips, 0 in 202 for the cheap settings).
