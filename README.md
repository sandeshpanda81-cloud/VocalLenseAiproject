# VocaLens AI — Speak. Analyze. Improve.

VocaLens AI is a hackathon-ready speech analytics dashboard based on Track C:
**Contrastive Speech Analytics & Temporal Flaw Grounding**.

It analyzes a speech recording and produces:
- Speech duration and speaking rate
- Pause / silence analysis
- Filler-word detection
- Energy and delivery indicators
- Timestamped temporal flaws
- Reproducible rubric-based score
- Actionable improvement recommendations
- Attempt history stored locally in the browser
- Optional local transcription with Faster-Whisper
- Demo mode for presentations without an audio file

## 1. Requirements

- Windows / macOS / Linux
- Python 3.10+
- Internet is NOT required for the basic demo/analytics mode.
- Optional Faster-Whisper transcription requires downloading a model the first time.

## 2. Run

### Windows

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open:
http://127.0.0.1:5000

### Optional local transcription

```bat
pip install -r requirements-optional.txt
```

Then set:

```bat
set VOCALENS_WHISPER=1
set VOCALENS_WHISPER_MODEL=base
python app.py
```

For a lower-end laptop, use:

```bat
set VOCALENS_WHISPER_MODEL=tiny
```

On first transcription, Faster-Whisper downloads the selected model.

## 3. How to use

1. Open the dashboard.
2. Upload a WAV/MP3/M4A/OGG/FLAC file.
3. Enter a transcript if you already have one. This is the fastest and most reliable demo route.
4. Click Analyze Speech.
5. Review:
   - Overall score
   - Rubric scores
   - Timeline flaws
   - Transcript
   - Recommendations
6. Use Demo Analysis if you need a guaranteed presentation result.

## 4. Contrastive dataset

The starter dataset is in:

`data/contrastive_dataset.csv`

It contains ideal/flawed speech examples and rubric labels. Expand it with your own recordings for the hackathon.

## 5. Architecture

Browser
  -> Flask API
  -> Audio feature extraction
  -> Optional local Whisper transcription
  -> Rule/rubric engine
  -> JSON result
  -> Dashboard visualization

The MVP intentionally avoids paid APIs and API keys.

## 6. Important hackathon note

This is a working prototype/MVP. For a competition submission, improve the custom dataset and replace/augment the heuristic rubric engine with a trained classifier or embedding-based contrastive model. Keep the rubric definitions fixed and document the evaluation protocol so scores remain reproducible.
