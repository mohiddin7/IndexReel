# Gate result (Oct 26): FAIL

Rules: `eval/gate.md` with Amendments 1 to 3, frozen before this run. One pass of the open SAM 3.1 weights on a rented GPU decided it (Amendment 2). Nothing was changed after I saw these numbers.

**Verdict: FAIL.** SAM recovered 4 of 4 picture-in-picture targets but only 1 of 4 simulated re-films; the rule needs at least 3 of 4 on each.

| Arm | PiP | Simulated re-film | False merges |
|---|---|---|---|
| OpenCV control (theta 0.9, set on dev) | 3/4 (Wilson 95% 0.30 to 0.95) | 4/4 (0.51 to 1.00) | 0 |
| SAM 3.1 open weights, as returned | 4/4 (0.51 to 1.00) | 1/4 (0.05 to 0.70) | 0 |

Paired outcomes, PDQ score against the 0.5 threshold:

| Target | PiP control | PiP SAM | Re-film control | Re-film SAM |
|---|---|---|---|---|
| T05 | 0.901 hit | 0.501 hit | 1.001 hit | 0.001 miss |
| T06 | 0.401 miss | 1.001 hit | 0.801 hit | 0.001 miss |
| T07 | 0.701 hit | 0.901 hit | 0.601 hit | 0.001 miss |
| T08 | 0.901 hit | 0.501 hit | 0.601 hit | 0.701 hit |

Two SAM PiP hits (T05, T08) sit at 0.501, a hair above the threshold. Highest false-pair score: control 0.0006, SAM 0.0007.

Why SAM missed the re-films: for T05, T06 and T07 neither prompt returned a mask on any frame, so nothing reached the quad rule. For T08 the `screen` prompt returned a mask on 46 of 50 frames. Mean full-frame fallbacks per 50 frames: SAM 38.0 on re-film, 6.1 on PiP, 50 on plain originals (nothing to find); control 8.0, 0.0 and 49.9.

Cost and speed: NVIDIA L40S, 5.7 s per prompt on average, 24 clips with two prompts each.

What I conclude, and what I do not:
- On these 4 gate targets, SAM does not beat a fair OpenCV control. It finds PiP insets reliably and the control missed one that SAM caught (T06). On re-film the control wins.
- The control's theta was set on dev and the gate split confirms it holds: 7 of 8 targets.
- The simulated re-film is a flat render with synthetic moire. A miss here does not show that SAM fails on a real phone filming a real monitor, which I score separately. Four targets per transform cannot show statistical superiority either way.

Decision, as written in advance: the OpenCV localiser is the default localiser and SAM 3.1 stays in the project as a measured ablation with this red cell shown. The product does not pivot to another idea.
