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


_PREAMBLE = """\
You are Lumen, a real-time interview & meeting copilot whispering into the
user's ear. You see the live transcript and the user's personal context.
Be terse, concrete, and immediately useful. Never invent facts about the
user beyond what is in the context. Never apologise. Never preface answers.
"""


_TEXT_PROMPTS = {
    "Answer": """\
{preamble}

The most recent thing said — likely a question directed at the user — is at
the very end of the transcript. Help the user answer it RIGHT NOW.

Output 3–5 short bullet points (each ≤14 words) the user can read aloud,
in priority order. Use markdown bullets ("• "). No preamble, no closer.
If the question is technical and code is appropriate, include one fenced
code block AFTER the bullets.

--- USER PROFILE / RESUME ---
{resume}
--- ROLE / JOB DESCRIPTION ---
{role}
--- USER NOTES ---
{notes}
--- BACKGROUND CONTEXT ---
{context}
--- LIVE TRANSCRIPT ---
{transcript}
""",
    "Shorten": """\
{preamble}

Re-state the user's most recent answer (the latest thing in the transcript
spoken by the user) in 1–2 crisp sentences. Plain text. No preamble.

--- USER PROFILE / RESUME ---
{resume}
--- TRANSCRIPT ---
{transcript}
""",
    "Recap": """\
{preamble}

Summarise the conversation so far in ≤6 short bullets. Cover what was
discussed, what was decided, and what's still open. Markdown bullets only.

--- BACKGROUND CONTEXT ---
{context}
--- TRANSCRIPT ---
{transcript}
""",
    "Follow-up": """\
{preamble}

Suggest 4 sharp follow-up questions the user could ask next. They should
push the conversation forward and reference specifics from the transcript.
Markdown bullets only. No preamble.

--- ROLE / JOB DESCRIPTION ---
{role}
--- TRANSCRIPT ---
{transcript}
""",
    "Define": """\
{preamble}

Identify the most jargon-y term used in the last few utterances and define
it in two sentences for a generalist. Format:
**<term>** — <definition>

--- TRANSCRIPT ---
{transcript}
""",
    "Summary": """\
{preamble}

Summarise the meeting below in 4–6 sentences. Plain text only — no markdown.

--- BACKGROUND CONTEXT ---
{context}
--- TRANSCRIPT ---
{transcript}
""",
    "Action items": """\
{preamble}

Extract concrete action items from the meeting below. Output a JSON array of
strings, each item phrased as a clear next step. Output ONLY the JSON array.

--- TRANSCRIPT ---
{transcript}
""",
    "Questions": """\
{preamble}

List the open questions and unresolved decisions raised. Output a JSON array
of strings. Output ONLY the JSON array.

--- TRANSCRIPT ---
{transcript}
""",
}


# Modes that route to the coach panel rather than the fullscreen HUD.
COACH_MODES = {"Answer", "Shorten", "Recap", "Follow-up", "Define"}
TEXT_MODES = COACH_MODES | {"Summary", "Action items", "Questions"}
ALL_MODES = ["Answer", "Shorten", "Recap", "Follow-up", "Define",
             "Summary", "Action items", "Questions", "HUD"]


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
    """Pretty-print a text-mode response for archive/dashboard display."""
    candidate = _strip_markdown_fences(text)
    if mode in {"Answer", "Recap", "Follow-up", "Define", "Shorten", "Summary"}:
        return candidate.strip()

    # Action items / Questions — JSON list expected, fall back to lines.
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, list):
            items = [str(x) for x in parsed if str(x).strip()]
            return "\n".join(f"• {it}" for it in items)
    except (ValueError, json.JSONDecodeError):
        pass
    return candidate.strip()


def _build_prompt(mode: str, custom: str | None = None) -> str | None:
    """Assemble the prompt for the given mode. Returns None if no transcript."""
    cfg = settings()
    context_text = _read_text_safely(CONTEXT_FILE)
    transcript_text = _read_text_safely(
        TRANSCRIPT_FILE, tail_chars=cfg.max_transcript_chars
    )
    if not transcript_text.strip() and mode != "Custom":
        return None

    fields = {
        "preamble": _PREAMBLE,
        "context": context_text or "(none)",
        "transcript": transcript_text or "(empty)",
        "resume": cfg.resume_text or "(none)",
        "role": cfg.role_text or "(none)",
        "notes": cfg.notes_text or "(none)",
    }

    if mode == "HUD":
        return _HUD_PROMPT.format(context=context_text, transcript=transcript_text)
    if mode == "Custom":
        return f"""{_PREAMBLE}

The user just typed this question into the spotlight bar:
"{custom}"

Use the live transcript and personal context below to answer them
right now in 3–6 short markdown bullets. No preamble.

--- USER PROFILE / RESUME ---
{cfg.resume_text or "(none)"}
--- ROLE / JOB DESCRIPTION ---
{cfg.role_text or "(none)"}
--- USER NOTES ---
{cfg.notes_text or "(none)"}
--- BACKGROUND CONTEXT ---
{context_text or "(none)"}
--- LIVE TRANSCRIPT ---
{transcript_text or "(empty)"}
"""
    return _TEXT_PROMPTS[mode].format(**fields)


# --------------------------------------------------------------------------- #
# Public entry point                                                          #
# --------------------------------------------------------------------------- #

def trigger_analysis(mode: str | None = None, custom_prompt: str | None = None) -> None:
    """Run an analysis pass. Safe to call from any thread (incl. hotkey)."""
    threading.Thread(
        target=_run_analysis,
        args=(mode, custom_prompt),
        daemon=True,
        name="lumen-ai",
    ).start()


def _run_analysis(requested_mode: str | None, custom_prompt: str | None = None) -> None:
    cfg = settings()
    mode = "Custom" if custom_prompt else (requested_mode or cfg.analysis_mode)
    is_hud = mode == "HUD"
    is_coach = mode in COACH_MODES or mode == "Custom"

    if not analysis_lock.acquire(blocking=False):
        log.info("Analysis already in progress; ignoring trigger.")
        return

    hold_seconds = 0
    try:
        # Busy indicators in whichever surface the user will see results in.
        if is_hud and cfg.overlay_enabled:
            bus.overlay_update.emit(
                render_status_html("Thinking…", spinner=True), 0
            )
        if is_coach:
            bus.coach_busy.emit(True, mode)
        bus.status_changed.emit("info", f"Running {mode}…")

        if _client is None:
            msg = "GEMINI_API_KEY missing in .env"
            bus.status_changed.emit("error", msg)
            if is_hud and cfg.overlay_enabled:
                bus.overlay_update.emit(render_status_html(msg, "#FF5252"), ERROR_TTL)
                hold_seconds = ERROR_TTL
            if is_coach:
                bus.coach_update.emit(mode, f"⚠ {msg}")
            return

        prompt = _build_prompt(mode, custom_prompt)
        if prompt is None:
            msg = "No transcript captured yet."
            bus.status_changed.emit("warn", msg)
            if is_hud and cfg.overlay_enabled:
                bus.overlay_update.emit(
                    render_status_html("No transcript yet", "#FFA726"), ERROR_TTL
                )
                hold_seconds = ERROR_TTL
            if is_coach:
                bus.coach_update.emit(mode, f"⚠ {msg}")
            return

        try:
            response = _client.models.generate_content(
                model=cfg.gemini_model, contents=prompt
            )
        except Exception as e:  # noqa: BLE001
            log.exception("Gemini API call failed")
            bus.status_changed.emit("error", f"API error: {e}")
            if is_hud and cfg.overlay_enabled:
                bus.overlay_update.emit(
                    render_status_html(f"API error: {e}", "#FF5252"), ERROR_TTL
                )
                hold_seconds = ERROR_TTL
            if is_coach:
                bus.coach_update.emit(mode, f"⚠ API error: {e}")
            return

        raw = (getattr(response, "text", "") or "").strip()
        if not raw:
            bus.status_changed.emit("error", "Empty response from model.")
            if is_hud and cfg.overlay_enabled:
                bus.overlay_update.emit(
                    render_status_html("Empty response", "#FF5252"), ERROR_TTL
                )
                hold_seconds = ERROR_TTL
            if is_coach:
                bus.coach_update.emit(mode, "⚠ Empty response")
            return

        if is_hud:
            html_blob = _strip_markdown_fences(raw)
            event = AnalysisEvent(mode=mode, raw_html=html_blob, plain_summary="(HUD)")
            if cfg.overlay_enabled:
                bus.overlay_update.emit(html_blob, cfg.analysis_ttl_seconds)
                hold_seconds = cfg.analysis_ttl_seconds
        else:
            pretty = _format_text_result(mode, raw)
            event = AnalysisEvent(mode=mode, raw_html="", plain_summary=pretty)
            if is_coach:
                bus.coach_update.emit(mode, pretty)

        _append_history(event)
        bus.analysis_completed.emit(event)
        bus.status_changed.emit("info", f"{mode} ready.")

    finally:
        if is_coach:
            bus.coach_busy.emit(False, mode)
        if hold_seconds > 0:
            time.sleep(hold_seconds)
        analysis_lock.release()
