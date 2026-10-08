from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

try:
    import librosa
except Exception:
    librosa = None

FILLERS = [
    "um", "uh", "umm", "uhh", "like", "basically",
    "actually", "you know", "i mean", "sort of", "kind of"
]

WHISPER_MODEL = None


def load_audio(path: str):
    if librosa is not None:
        y, sr = librosa.load(path, sr=16000, mono=True)
    else:
        y, sr = sf.read(path, always_2d=False)
        if y.ndim > 1:
            y = np.mean(y, axis=1)
        y = y.astype(np.float32)
    return y.astype(np.float32), int(sr)


def _segments_from_mask(mask: np.ndarray, sr: int, min_seconds: float = 0.18):
    segments = []
    start = None
    for i, active in enumerate(mask):
        t = i / sr
        if active and start is None:
            start = t
        elif not active and start is not None:
            end = t
            if end - start >= min_seconds:
                segments.append((start, end))
            start = None
    if start is not None:
        end = len(mask) / sr
        if end - start >= min_seconds:
            segments.append((start, end))
    return segments


def analyze_audio(path: str) -> dict[str, Any]:
    y, sr = load_audio(path)
    duration = max(len(y) / sr, 0.01)

    rms = np.sqrt(np.mean(np.square(y)) + 1e-12)
    peak = float(np.max(np.abs(y))) if len(y) else 0.0

    # Frame energy.
    frame = max(int(sr * 0.03), 1)
    hop = max(int(sr * 0.01), 1)
    if len(y) < frame:
        y2 = np.pad(y, (0, frame - len(y)))
    else:
        y2 = y

    energies = []
    starts = []
    for s in range(0, max(len(y2) - frame + 1, 1), hop):
        chunk = y2[s:s+frame]
        if len(chunk) < frame:
            chunk = np.pad(chunk, (0, frame - len(chunk)))
        energies.append(float(np.sqrt(np.mean(chunk * chunk) + 1e-12)))
        starts.append(s / sr)

    energies = np.array(energies, dtype=np.float32)
    threshold = max(float(np.percentile(energies, 20)) * 1.35, 0.008)
    voiced = energies > threshold

    silence_segments = []
    start = None
    for i, active in enumerate(voiced):
        t = starts[i]
        if not active and start is None:
            start = t
        elif active and start is not None:
            end = t
            if end - start >= 0.20:
                silence_segments.append((start, min(end, duration)))
            start = None
    if start is not None:
        silence_segments.append((start, duration))

    pause_seconds = sum(max(0, e - s) for s, e in silence_segments)
    speaking_seconds = max(duration - pause_seconds, 0.1)

    # Estimate speaking rate only when a transcript exists.
    return {
        "duration": round(duration, 2),
        "rms": round(rms, 5),
        "peak": round(peak, 5),
        "pause_count": len(silence_segments),
        "pause_seconds": round(pause_seconds, 2),
        "speaking_seconds": round(speaking_seconds, 2),
        "pauses": [
            {"start": round(s, 2), "end": round(e, 2), "duration": round(e-s, 2)}
            for s, e in silence_segments
        ],
    }


def transcribe_local(path: str):
    global WHISPER_MODEL

    enabled = os.getenv("VOCALENS_WHISPER", "0").lower() in {"1", "true", "yes"}
    if not enabled:
        return None, "Local Whisper is disabled. Enter a transcript manually or enable VOCALENS_WHISPER=1."

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None, "Faster-Whisper is not installed. Run: pip install -r requirements-optional.txt"

    model_name = os.getenv("VOCALENS_WHISPER_MODEL", "tiny")
    if WHISPER_MODEL is None:
        WHISPER_MODEL = WhisperModel(model_name, device="cpu", compute_type="int8")

    segments, info = WHISPER_MODEL.transcribe(path, beam_size=3, vad_filter=True)
    data = []
    texts = []
    for seg in segments:
        txt = seg.text.strip()
        if txt:
            texts.append(txt)
            data.append({
                "start": round(float(seg.start), 2),
                "end": round(float(seg.end), 2),
                "text": txt
            })

    return {
        "text": " ".join(texts),
        "segments": data,
        "language": getattr(info, "language", "unknown")
    }, None


def normalize_words(text: str):
    return re.findall(r"[a-zA-Z']+", text.lower())


def count_fillers(text: str):
    lower = text.lower()
    counts = {}
    for filler in FILLERS:
        pattern = r"\b" + re.escape(filler) + r"\b"
        n = len(re.findall(pattern, lower))
        if n:
            counts[filler] = n
    return counts


def calculate_score(metrics: dict, transcript: str):
    words = normalize_words(transcript)
    word_count = len(words)
    duration = max(metrics["duration"], 0.1)
    wpm = word_count / (duration / 60.0) if word_count else 0.0

    filler_counts = count_fillers(transcript)
    filler_total = sum(filler_counts.values())
    filler_rate = (filler_total / max(word_count, 1)) * 100

    # Fixed reproducible rubric.
    pace = 100.0 if not word_count else max(0, 100 - abs(wpm - 135) * 1.15)
    if wpm < 90 and word_count:
        pace -= (90 - wpm) * 0.20
    pause_ratio = metrics["pause_seconds"] / duration
    pause_score = max(0, 100 - max(0, pause_ratio - 0.12) * 260)
    fluency = max(0, 100 - filler_rate * 7.5)
    clarity = min(100, 60 + pace * 0.20 + fluency * 0.20 + (20 if word_count else 0))
    delivery = min(100, max(0, 55 + min(30, metrics["rms"] * 900) + (15 if metrics["peak"] > 0.15 else 0)))

    rubric = {
        "Clarity": round(clarity),
        "Pace": round(pace),
        "Fluency": round(fluency),
        "Pauses": round(pause_score),
        "Delivery": round(delivery),
    }
    weights = {"Clarity": .20, "Pace": .20, "Fluency": .20, "Pauses": .15, "Delivery": .25}
    overall = round(sum(rubric[k] * weights[k] for k in rubric))

    return {
        "overall": overall,
        "rubric": rubric,
        "word_count": word_count,
        "wpm": round(wpm),
        "filler_counts": filler_counts,
        "filler_total": filler_total,
    }


def build_flaws(metrics: dict, score: dict, transcript_segments=None):
    flaws = []

    for p in metrics["pauses"]:
        if p["duration"] >= 2.0:
            flaws.append({
                "time": p["start"],
                "end": p["end"],
                "type": "Long Pause",
                "severity": "high",
                "message": f"Pause lasted {p['duration']:.1f}s. Use a shorter intentional pause."
            })
        elif p["duration"] >= 1.0:
            flaws.append({
                "time": p["start"],
                "end": p["end"],
                "type": "Pause",
                "severity": "medium",
                "message": f"Noticeable pause of {p['duration']:.1f}s."
            })

    if score["wpm"] > 165:
        flaws.append({
            "time": 0,
            "end": min(10, metrics["duration"]),
            "type": "Fast Pace",
            "severity": "high",
            "message": f"Estimated pace is {score['wpm']} WPM. Slow down for important points."
        })
    elif 0 < score["wpm"] < 95:
        flaws.append({
            "time": 0,
            "end": min(10, metrics["duration"]),
            "type": "Slow Pace",
            "severity": "medium",
            "message": f"Estimated pace is {score['wpm']} WPM. Add energy or shorten pauses."
        })

    if score["filler_total"] > 0:
        # Without word-level timestamps, ground filler feedback to an explicit transcript position.
        flaws.append({
            "time": 0,
            "end": min(8, metrics["duration"]),
            "type": "Filler Words",
            "severity": "medium" if score["filler_total"] < 4 else "high",
            "message": f"Detected {score['filler_total']} filler-word occurrence(s): "
                       + ", ".join(f"{k} ({v})" for k, v in score["filler_counts"].items()) + "."
        })

    return sorted(flaws, key=lambda x: x["time"])


def recommendations(score: dict):
    rec = []
    r = score["rubric"]
    if r["Pace"] < 70:
        rec.append("Slow down and add deliberate pauses before important points.")
    elif r["Pace"] < 85:
        rec.append("Keep your pace steadier, especially during technical explanations.")
    if r["Fluency"] < 80:
        rec.append("Replace filler words with a silent half-second pause.")
    if r["Pauses"] < 75:
        rec.append("Avoid long pauses; rehearse transitions between sections.")
    if r["Delivery"] < 75:
        rec.append("Use more vocal variation and slightly stronger projection.")
    if r["Clarity"] < 75:
        rec.append("Use shorter sentences and emphasize key terms.")
    if not rec:
        rec.append("Strong delivery. Practice once more and aim for consistency.")
    return rec


def demo_result():
    return {
        "mode": "demo",
        "file": "Demo speech",
        "audio": {
            "duration": 96.4,
            "pause_count": 5,
            "pause_seconds": 8.7,
            "speaking_seconds": 87.7,
            "rms": 0.071,
            "peak": 0.64,
            "pauses": [
                {"start": 18.2, "end": 20.0, "duration": 1.8},
                {"start": 33.4, "end": 36.1, "duration": 2.7},
                {"start": 52.7, "end": 53.9, "duration": 1.2},
                {"start": 67.0, "end": 69.6, "duration": 2.6},
                {"start": 81.4, "end": 82.8, "duration": 1.4},
            ]
        },
        "score": {
            "overall": 78,
            "rubric": {"Clarity": 84, "Pace": 71, "Fluency": 75, "Pauses": 78, "Delivery": 82},
            "word_count": 213,
            "wpm": 133,
            "filler_counts": {"um": 3, "like": 2},
            "filler_total": 5,
        },
        "transcript": {
            "text": "Good morning everyone. Today I am going to explain how artificial intelligence can improve everyday productivity. "
                    "AI can summarize documents, organize information, and help people make better decisions. "
                    "However, um, we should also think about privacy. Like, when systems process sensitive information, "
                    "local processing can reduce unnecessary data transfer. Finally, responsible AI should be useful, transparent, and accessible.",
            "segments": [],
            "language": "en"
        },
        "flaws": [
            {"time": 18.2, "end": 20.0, "type": "Pause", "severity": "medium", "message": "Noticeable pause of 1.8s."},
            {"time": 33.4, "end": 36.1, "type": "Long Pause", "severity": "high", "message": "Pause lasted 2.7s. Use a shorter intentional pause."},
            {"time": 52.7, "end": 53.9, "type": "Pause", "severity": "medium", "message": "Noticeable pause of 1.2s."},
            {"time": 0, "end": 8, "type": "Filler Words", "severity": "medium", "message": "Detected 5 filler-word occurrences: um (3), like (2)."},
        ],
        "recommendations": [
            "Replace filler words with a silent half-second pause.",
            "Keep your pace steadier during technical explanations.",
            "Use more deliberate transitions before major points."
        ]
    }
