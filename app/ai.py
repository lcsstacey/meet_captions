"""Gemini-driven analysis of the running transcript.

Supports four modes:
  * HUD          — fullscreen transparent HTML overlay (the original behaviour).
  * Summary      — a compact prose summary, shown on the dashboard.
  * Action items — bulleted list, shown on the dashboard.
  * Questions    — open questions / decisions to revisit.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

try:
    from google import genai
except BaseException:  # noqa: BLE001 — any failure here means AI is unavailable.
    genai = None  # type: ignore[assignment]

from .config import CONTEXT_FILE, HISTORY_FILE, TRANSCRIPT_FILE, settings
from .overlay_render import render_status_html
from .state import AnalysisEvent, analysis_lock, bus, is_analyzing

log = logging.getLogger("lumen.ai")

load_dotenv()
_API_KEY = os.getenv("GEMINI_API_KEY")
_client: "genai.Client | None" = (
    genai.Client(api_key=_API_KEY) if (_API_KEY and genai is not None) else None
)


ERROR_TTL = 8


def has_api_key() -> bool:
    return _client is not None


# --------------------------------------------------------------------------- #
# Prompts                                                                     #
# --------------------------------------------------------------------------- #

_HUD_PROMPT = """\
You are designing a transparent, fullscreen HUD overlay (1920x1080) that
summarises the meeting below for the wearer at a glance.

--- CONTEXT (background notes) ---
{context}

--- LIVE TRANSCRIPT ---
{transcript}

Surface, in order of priority:
  • Key concepts as short tags (single words or short phrases — NOT sentences)
  • Action items as concise bullets
  • Decisions and open questions, if any

Hard requirements (failure to comply breaks the overlay):
  1. Output VALID, RAW HTML only. No markdown fences, no commentary.
  2. Include a <style> block.
  3. body MUST include: background-color: transparent !important; overflow: hidden;
  4. Every text element must remain readable over a busy desktop. Use either
     strong text-shadow OR rgba(0,0,0,0.6) padded plates with backdrop-filter blur.
  5. Center content in the viewport. Assume 1920x1080.
  6. Use system-ui or other web-safe fonts only.
  7. Use a modern visual style: glassmorphism, subtle gradients, rounded corners.
"""


_TEXT_PROMPTS = {
    "Summary": """\
Summarise the meeting below in 4–6 sentences. Plain text only — no markdown.

--- CONTEXT ---
{context}

--- TRANSCRIPT ---
{transcript}
""",
    "Action items": """\
Extract concrete action items from the meeting below. Output a JSON array of
strings, each item phrased as a clear next step. Output ONLY the JSON array.

--- CONTEXT ---
{context}

--- TRANSCRIPT ---
{transcript}
""",
    "Questions": """\
List the open questions and unresolved decisions raised in this meeting.
Output a JSON array of strings. Output ONLY the JSON array.

--- CONTEXT ---
{context}

--- TRANSCRIPT ---
{transcript}
""",
}


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #

def _read_text_safely(path: Path, tail_chars: int | None = None) -> str:
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        log.exception("Could not read %s", path)
        return ""
    if tail_chars is not None and len(text) > tail_chars:
        text = "…[earlier transcript truncated]…\n" + text[-tail_chars:]
    return text


def _strip_markdown_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else ""
    if s.endswith("```"):
        s = s[:-3]
    return s.strip()


def _append_history(event: AnalysisEvent) -> None:
    record = {
        "mode": event.mode,
        "summary": event.plain_summary,
        "raw_html": event.raw_html,
        "timestamp": event.timestamp.isoformat(),
    }
    try:
        history = []
        if HISTORY_FILE.exists():
            history = json.loads(HISTORY_FILE.read_text("utf-8"))
        history.insert(0, record)
        history = history[:50]  # cap retained history
        HISTORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")
    except (OSError, json.JSONDecodeError):
        log.exception("Could not update history file")


def load_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def _format_text_result(mode: str, text: str) -> str:
    """Pretty-print a text-mode response for the dashboard."""
    if mode == "Summary":
        return text.strip()

    # Action items / Questions — try to parse a JSON list, fall back to lines.
    candidate = _strip_markdown_fences(text)
    items: list[str]
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, list):
            items = [str(x) for x in parsed if str(x).strip()]
        else:
            raise ValueError("not a list")
    except (ValueError, json.JSONDecodeError):
        items = [
            ln.lstrip("-•* ").strip()
            for ln in candidate.splitlines()
            if ln.strip()
        ]
    return "\n".join(f"• {it}" for it in items) if items else candidate.strip()


# --------------------------------------------------------------------------- #
# Public entry point                                                          #
# --------------------------------------------------------------------------- #

def trigger_analysis(mode: str | None = None) -> None:
    """Run an analysis pass. Safe to call from any thread (incl. hotkey)."""
    threading.Thread(
        target=_run_analysis, args=(mode,), daemon=True, name="lumen-ai"
    ).start()


def _run_analysis(requested_mode: str | None) -> None:
    cfg = settings()
    mode = requested_mode or cfg.analysis_mode

    if not analysis_lock.acquire(blocking=False):
        log.info("Analysis already in progress; ignoring trigger.")
        return

    hold_seconds = 0
    try:
        if mode == "HUD" and cfg.overlay_enabled:
            bus.overlay_update.emit(
                render_status_html("Analysing meeting…", spinner=True), 0
            )
        bus.status_changed.emit("info", f"Running {mode} analysis…")

        if _client is None:
            bus.status_changed.emit("error", "GEMINI_API_KEY missing in .env")
            if mode == "HUD" and cfg.overlay_enabled:
                bus.overlay_update.emit(
                    render_status_html("GEMINI_API_KEY missing", "#FF5252"),
                    ERROR_TTL,
                )
                hold_seconds = ERROR_TTL
            return

        context_text = _read_text_safely(CONTEXT_FILE)
        transcript_text = _read_text_safely(
            TRANSCRIPT_FILE, tail_chars=cfg.max_transcript_chars
        )
        if not transcript_text.strip():
            bus.status_changed.emit("warn", "No transcript captured yet.")
            if mode == "HUD" and cfg.overlay_enabled:
                bus.overlay_update.emit(
                    render_status_html("No transcript yet", "#FFA726"),
                    ERROR_TTL,
                )
                hold_seconds = ERROR_TTL
            return

        prompt = (
            _HUD_PROMPT.format(context=context_text, transcript=transcript_text)
            if mode == "HUD"
            else _TEXT_PROMPTS[mode].format(
                context=context_text, transcript=transcript_text
            )
        )

        try:
            response = _client.models.generate_content(
                model=cfg.gemini_model, contents=prompt
            )
        except Exception as e:  # noqa: BLE001 — surface SDK error to the UI.
            log.exception("Gemini API call failed")
            bus.status_changed.emit("error", f"API error: {e}")
            if mode == "HUD" and cfg.overlay_enabled:
                bus.overlay_update.emit(
                    render_status_html(f"API error: {e}", "#FF5252"), ERROR_TTL
                )
                hold_seconds = ERROR_TTL
            return

        raw = (getattr(response, "text", "") or "").strip()
        if not raw:
            bus.status_changed.emit("error", "Empty response from model.")
            if mode == "HUD" and cfg.overlay_enabled:
                bus.overlay_update.emit(
                    render_status_html("Empty response", "#FF5252"), ERROR_TTL
                )
                hold_seconds = ERROR_TTL
            return

        if mode == "HUD":
            html_blob = _strip_markdown_fences(raw)
            event = AnalysisEvent(
                mode=mode, raw_html=html_blob, plain_summary="(HUD overlay)"
            )
            if cfg.overlay_enabled:
                bus.overlay_update.emit(html_blob, cfg.analysis_ttl_seconds)
                hold_seconds = cfg.analysis_ttl_seconds
        else:
            pretty = _format_text_result(mode, raw)
            event = AnalysisEvent(mode=mode, raw_html="", plain_summary=pretty)

        _append_history(event)
        bus.analysis_completed.emit(event)
        bus.status_changed.emit("info", f"{mode} ready.")

    finally:
        if hold_seconds > 0:
            time.sleep(hold_seconds)
        analysis_lock.release()
