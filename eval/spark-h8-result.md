# H8 result: reasoning effort on the whole-video judge (Oct 27 2026)

Protocol: `eval/spark-h8.md`. Code: `scripts/spark_h8.py`. 86 pairs (18 expected yes, 68 expected no), arm V, one run per effort. The default is the H1c baseline. Spend about $4.

| Effort | Yes | False yes | Output tokens | Cost per pair | Seconds per call | Bar |
|---|---|---|---|---|---|---|
| default | 18/18 | 0/68 | 1,496 | $0.0185 (100%) | not recorded | baseline |
| minimal | 18/18 | 0/68 | 442 | $0.0140 (76%) | 6.1 | fails cost (bar 70%) |
| low | 18/18 | 0/68 | 772 | $0.0154 (83%) | 9.7 | fails cost |
| high | 18/18 | 0/68 | 1,519 | $0.0186 (101%) | 12.6 | no bar |

- **Accuracy did not move with effort.** Same yes, same zero false yes at every level. Only one `same_footage` answer changed at minimal and low (an "unsure" became "no" on a picture-in-picture pair against an unrelated Starship clip), and high turned one "no" into "unsure". `same_event` answers on the expected-no pairs changed on 2 to 4 pairs per effort; I have not inspected them.
- **Cost fell by a quarter at most**, because the video itself is about 9,700 input tokens ($0.012) of the $0.0185 per pair. By my bar (70%) minimal fails on cost, yet it loses nothing on this data, is about twice as fast as high, and is the sensible default for the many pairs a pile needs. That choice is a judgment, not a pass.
- **High effort buys nothing here** on copy detection. Whether it helps on same-event questions is untested.
- **Chained finding:** a probe showed input tokens track resolution and not frame rate (360p 11,221, 240p 6,901, 180p 3,781, 120p 2,261; audio about 500). That is H10 (`eval/spark-h10.md`).

## Limits

86 pairs, one run per effort, same footage; the default level is model-determined so "low" may not be lower than what it chose; xhigh and max were not tried.
