# H8: reasoning effort on the whole-video judge

Written Oct 27 2026 before any call at a non-default effort. Follows H1c, where output (reasoning) tokens turned out to be a large share of the cost. The Meta docs list `reasoning.effort`: none (not supported by Spark), minimal, low, medium, high, xhigh, max. Every earlier pilot ran with the default.

## Hypothesis

At lower effort the whole-video judge keeps its accuracy on copy detection and costs and takes less. At higher effort it may change the "unsure" behaviour on same-event questions.

## Design

The same 86 pairs and clips as H1c (`data/spark_h1c`), arm V only, prompt v3 unchanged, `reasoning={"effort": e}` for e in minimal, low, high. The default-effort answers from H1c are the baseline (not re-asked). Each pair asked once per effort, same orientation. Time per call recorded.

## Pass bar for minimal and for low (decided now)

1. Yes on at least 17 of 18 expected-yes pairs.
2. **0** false yes on 68 expected-no pairs.
3. Cost per pair at most 70% of the default's.

`high` has no bar. It is reported: yes, false yes, cost, time, and how many `same_event` answers on the hard-negative pairs change from unsure to yes or no.

## Reported

Output tokens per call at each effort, seconds per call, answer changes against the default, every false yes.

## Limits

86 pairs, one run per effort, same footage; the default effort is model-determined, so "low" may not be lower than what it chose; `max` and `xhigh` are not tried.
