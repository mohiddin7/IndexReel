# Spark pilot: can Muse Spark tell a copy from another camera on the same event?

Written Oct 26 2026 before the first Spark call. Exploratory pilot, not the gate, and not a result I will quote as a rate. Its job is to decide whether the "disagreement workbench" idea is worth building.

## Question

Given two short videos, does Muse Spark 1.3 (Standard mode) separate three cases that the pixel matcher cannot: the same recording re-encoded or overlaid, a different camera on the same event, and an unrelated event?

## Data (real, rights stated on Wikimedia Commons)

Two real events, three cameras each. Licences are as Commons states them; I have not verified them upstream.

| Id | Event | Source on Commons | Licence |
|---|---|---|---|
| Y | Chelyabinsk meteor 2013-02-15, fixed security camera | Chelyabinsk meteor security camera footage, Yekaterinburg | Public domain |
| M | same, dashcam | 2013 Russian meteor event (Magnitogorsk) | Public domain |
| I | same, dashcam | Взрыв метеорита над Челябинском 15 02 2013 (Aleksandr Ivanov) | CC BY 3.0 |
| C0 | SpaceX Starship IFT-1 2023-04-20, NASA WB-57 camera | SpaceX Starship IFT-1 NASA WB-57 Cam 0 | Public domain |
| C4 | same, second WB-57 camera | SpaceX Starship IFT-1 NASA WB-57 Cam 4 | Public domain |
| MA | same, ground view from Matamoros, liftoff phase | SpaceX Starship IFT-1 Matamoros | CC BY 3.0 |

Each source is cut to a 24 to 30 second window around the key moment (chosen by eye from contact sheets, before any Spark call), scaled to 640x360 mp4. Derived copies of Y, I, C0 and MA: `_reenc` (240p, heavy compression) and `_banner` (85% centre crop, scaled back up, red bar and white block overlaid).

## Pairs (23), each asked once, A/B order fixed by seed

- copy (8): each of Y, I, C0, MA against its `_reenc` and its `_banner`. Expect same_footage yes.
- other camera, same moment (4): Y-M, Y-I, M-I, C0-C4. Expect same_event yes, same_footage no.
- same event, no shared moment (2): MA-C0, MA-C4. Expect same_event yes or unsure, same_footage no.
- different event (9): each of Y, M, I against each of C0, C4, MA. Expect same_event no, same_footage no.

Note: burned-in clocks differ between the Chelyabinsk cameras (09:10, 09:20) and the NASA clips carry a UTC overlay. I report whether Spark relies on them; I do not hide them in this run.

## Prompt and output

One prompt, frozen in `scripts/spark_pilot.py`. Spark returns JSON with same_event, same_footage (yes, no or unsure), up to three observations and a reason for any "unsure". Model `muse-spark-1.3`, Standard mode, default reasoning, no tools. No reruns, no prompt edits after the first full run.

## Pass bar (decided now)

1. Copies: same_footage yes on at least 7 of 8.
2. Different event: same_event no on at least 8 of 9, and never same_footage yes.
3. Other camera, same moment: same_event yes on at least 3 of 4, and same_footage no on all 4.
4. Never same_footage yes on any non-copy pair (a false merge).

PASS needs all four. If rule 3 or 4 fails, "Spark as a second reader" is not the hero. The provenance strip and the SAM ablation stay.

With 23 pairs this shows feasibility and failure modes only. It does not give a rate, and I do not claim one.

## Cost

Unknown until the first call. I run one pair first, record the tokens and dollars, and stop if the full run would cost more than $5.

## Report

Per pair: expected, Spark's answer, observations, tokens, cost. Plus whether it cited the on-screen clock, and how often it answered "unsure".
