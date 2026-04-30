"""Flask endpoint that ingests captions from the browser extension."""

from __future__ import annotations

import datetime as dt
import logging
import threading

from flask import Flask, jsonify, request
from flask_cors import CORS

from .config import TRANSCRIPT_FILE, settings
from .overlay_render import render_caption_html
from .state import CaptionEvent, bus, is_analyzing

log = logging.getLogger("lumen.server")
logging.getLogger("werkzeug").setLevel(logging.WARNING)

MAX_SPEAKER_LEN = 200
MAX_TEXT_LEN = 2_000

app = Flask(__name__)
CORS(app)

# Stats exposed on the dashboard.
stats = {
    "captions_received": 0,
    "last_caption_at": None,  # datetime | None
    "started_at": dt.datetime.now(),
}


@app.route("/api/captions", methods=["POST"])
def save_caption():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"status": "error", "reason": "invalid json"}), 400

    speaker = str(data.get("speaker") or "Unknown")[:MAX_SPEAKER_LEN]
    text = str(data.get("text") or "")[:MAX_TEXT_LEN]

    if not text.strip():
        return jsonify({"status": "ok", "noop": True}), 200

    cfg = settings()
    event = CaptionEvent(speaker=speaker, text=text)

    # Live overlay (skipped while AI summary is on-screen).
    if cfg.overlay_enabled and not is_analyzing():
        bus.overlay_update.emit(
            render_caption_html(speaker, text, cfg), cfg.caption_ttl_seconds
        )

    # Dashboard live feed.
    bus.caption_received.emit(event)

    # Stats.
    stats["captions_received"] += 1
    stats["last_caption_at"] = event.timestamp

    # Persist.
    timestamp = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with TRANSCRIPT_FILE.open("a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [{speaker}] {text}\n")
    except OSError:
        log.exception("Could not write to %s", TRANSCRIPT_FILE)

    return jsonify({"status": "ok"}), 200


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify(
        {
            "status": "ok",
            "captions_received": stats["captions_received"],
            "last_caption_at": (
                stats["last_caption_at"].isoformat()
                if stats["last_caption_at"]
                else None
            ),
        }
    )


def start_in_background() -> threading.Thread:
    cfg = settings()

    def _run() -> None:
        log.info(
            "Caption API listening on http://%s:%d/api/captions",
            cfg.flask_host,
            cfg.flask_port,
        )
        app.run(
            host=cfg.flask_host,
            port=cfg.flask_port,
            debug=False,
            use_reloader=False,
            threaded=True,
        )

    t = threading.Thread(target=_run, daemon=True, name="lumen-flask")
    t.start()
    return t
