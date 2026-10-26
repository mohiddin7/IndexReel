# Dev split result (Oct 26)

Diagnostic only. Dev is where I set theta and where I may look; the verdict is the gate split.

| Arm | PiP (of 4) | Simulated re-film (of 4) | False merges |
|---|---|---|---|
| OpenCV control (theta 0.9) | 4 | 3 | 0 |
| SAM 3.1, open weights, as returned | 4 | 0 | 0 |

How SAM got there, on the 4 target clips with PiP and re-film (PDQ threshold 0.5):
- Prompt `video inset` returned a mask on 48 to 50 of 50 frames of every PiP clip, at about 0.7 probability, and it passed the quad rule. That is the 4 of 4.
- Prompt `screen` returned no mask at all on 3 of 4 simulated re-films. It returned one valid quad, on the dark night clip, which still did not match. The quad rule rejected nothing here; there was nothing to convert.
- On the plain originals both prompts return nothing, so SAM leaves them alone (the control needed theta for that).

Cost and speed: NVIDIA L40S, 13 s model load, 5.8 s per prompt on average (max 6.6 s), peak 21.6 GB GPU memory.

What this does and does not say: the simulated re-film is a flat render with synthetic moire on a noise background. SAM not calling it a screen is a fair result on that fixture. It says nothing about real phone footage of a real monitor, which I score separately and which does not decide the gate.
