from pathlib import Path
from flask import Blueprint, current_app, jsonify, render_template, request
from werkzeug.utils import secure_filename

from .audio_engine import (
    analyze_audio,
    transcribe_local,
    calculate_score,
    build_flaws,
    recommendations,
    demo_result,
)

main = Blueprint("main", __name__)

ALLOWED = {"wav", "mp3", "m4a", "ogg", "flac", "aac"}


@main.get("/")
def index():
    return render_template("index.html")


@main.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "VocaLens AI"})


@main.get("/api/demo")
def demo():
    return jsonify(demo_result())


@main.post("/api/analyze")
def analyze():
    audio = request.files.get("audio")
    transcript = request.form.get("transcript", "").strip()

    if not audio:
        return jsonify({"error": "Please upload an audio file."}), 400

    ext = Path(audio.filename or "").suffix.lower().replace(".", "")
    if ext not in ALLOWED:
        return jsonify({"error": "Unsupported audio format. Use WAV, MP3, M4A, OGG, FLAC or AAC."}), 400

    filename = secure_filename(audio.filename)
    save_path = Path(current_app.config["UPLOAD_FOLDER"]) / filename
    audio.save(save_path)

    try:
        metrics = analyze_audio(str(save_path))

        transcription = None
        if not transcript:
            transcription, warning = transcribe_local(str(save_path))
            if transcription:
                transcript = transcription["text"]
            else:
                transcript = ""
        else:
            transcription = {"text": transcript, "segments": [], "language": "manual"}

        score = calculate_score(metrics, transcript)
        flaws = build_flaws(metrics, score, transcription.get("segments", []) if transcription else [])
        result = {
            "mode": "analysis",
            "file": filename,
            "audio": metrics,
            "score": score,
            "transcript": transcription or {"text": transcript, "segments": [], "language": "manual"},
            "flaws": flaws,
            "recommendations": recommendations(score),
        }

        if not transcript:
            result["warning"] = (
                "No transcript was supplied. Install/enable Faster-Whisper for automatic local transcription, "
                "or paste a transcript into the dashboard for full filler-word and WPM analysis."
            )

        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": f"Analysis failed: {type(exc).__name__}: {exc}"}), 500
