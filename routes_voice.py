# routes_voice.py
import io, os
from flask import Blueprint, request, jsonify
from openai import OpenAI

voice_bp = Blueprint("voice_bp", __name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@voice_bp.route("/voice/stt", methods=["POST"])
def voice_stt():
    """
    Accepts multipart/form-data with field 'audio' (webm/ogg/m4a/wav).
    Returns: {"text":"..."} on success.
    """
    if "audio" not in request.files:
        return jsonify({"error":"no file"}), 400

    f = request.files["audio"]
    # Let OpenAI handle format; pass file-like object
    try:
        # whisper-1 remains widely available; adjust if you prefer a newer transcribe model
        tr = client.audio.transcriptions.create(
            model="whisper-1",
            file=(f.filename, f.stream, f.mimetype or "application/octet-stream")
        )
        return jsonify({"text": tr.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
