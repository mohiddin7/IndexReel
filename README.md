# IndexReel

IndexReel takes the clips behind a breaking-news claim and tells me how many distinct recordings are behind them. It shows aligned evidence for each match, and shows which claims lose their video support when I withdraw one recording. It never says a clip is true or fake.

I'm building it for the Meta Global AI Developer Hackathon (Oct 26 to Nov 4, 2026, Indie track).

## Status

Planning. The code starts on Oct 26.

## How it will work

- Meta's SSCD and PDQ do the matching.
- SAM 3.1 only localises: it finds a screen to rectify, a picture-in-picture inset to crop, and captions or logos to mask.
- Muse Spark and Muse Voice Transcribe extract claims, each tied to a caption span or a speech turn.
- I approve every merge by hand, and a clip can stay "unresolved".

## Author

Mohiddin ([@mohiddin7](https://github.com/mohiddin7))
