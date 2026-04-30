"""HTML templates for the transparent overlay window.

These templates target QtWebEngine (Chromium), so modern CSS — backdrop-filter,
custom properties, keyframes — works without polyfills.
"""

from __future__ import annotations

import hashlib
import html

from .config import POSITION_PRESETS, Settings


BLANK_HTML = (
    "<!DOCTYPE html><html><body "
    "style='background-color: transparent !important; overflow: hidden;'></body></html>"
)


# Pleasant palette for auto-coloured speaker pills. Colours are hue-rotated so
# each name lands on a stable, distinct value across runs.
_SPEAKER_PALETTE = [
    "#7C5CFF", "#22D3EE", "#34D399", "#F59E0B",
    "#F472B6", "#A78BFA", "#FB7185", "#60A5FA",
    "#FACC15", "#4ADE80", "#FCA5A5", "#2DD4BF",
]


def _speaker_color(speaker: str) -> str:
    if not speaker:
        return _SPEAKER_PALETTE[0]
    h = int(hashlib.sha1(speaker.encode("utf-8")).hexdigest(), 16)
    return _SPEAKER_PALETTE[h % len(_SPEAKER_PALETTE)]


def _layout_css(cfg: Settings) -> str:
    align_items, justify, padding = POSITION_PRESETS.get(
        cfg.caption_position, POSITION_PRESETS["Bottom"]
    )
    return (
        f"  display: flex; align-items: {align_items}; "
        f"justify-content: {justify}; padding: {padding};"
    )


STARTUP_HTML = """
<!DOCTYPE html>
<html><head><style>
  body {
    background-color: transparent !important; overflow: hidden;
    margin: 0; height: 100vh;
    display: flex; align-items: flex-end; justify-content: center;
    padding-bottom: 8vh;
    font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, -apple-system, sans-serif;
  }
  .pill {
    color: #fff;
    background: linear-gradient(135deg, rgba(124,92,255,0.85), rgba(34,211,238,0.85));
    border: 1px solid rgba(255,255,255,0.18);
    backdrop-filter: blur(14px) saturate(140%);
    -webkit-backdrop-filter: blur(14px) saturate(140%);
    padding: 10px 22px; border-radius: 999px;
    font-size: 18px; font-weight: 600; letter-spacing: 0.3px;
    box-shadow: 0 12px 40px rgba(0,0,0,0.45);
    display: inline-flex; align-items: center; gap: 10px;
    animation: rise 420ms cubic-bezier(.2,.8,.2,1) both;
  }
  .dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #4ade80; box-shadow: 0 0 12px #4ade80;
    animation: pulse 1.6s ease-in-out infinite;
  }
  @keyframes rise { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; } }
  @keyframes pulse {
    0%,100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.55; transform: scale(0.85); }
  }
</style></head>
<body><div class="pill"><span class="dot"></span>Lumen is listening…</div></body></html>
"""


def render_caption_html(speaker: str, text: str, cfg: Settings) -> str:
    safe_speaker = html.escape(speaker)
    safe_text = html.escape(text)
    speaker_color = _speaker_color(speaker) if cfg.color_speakers else cfg.speaker_color

    plate_bg = (
        "background: rgba(10, 10, 14, 0.55);"
        "backdrop-filter: blur(18px) saturate(160%);"
        "-webkit-backdrop-filter: blur(18px) saturate(160%);"
        "border: 1px solid rgba(255,255,255,0.12);"
        "box-shadow: 0 18px 60px rgba(0,0,0,0.55);"
        if cfg.glass_plate
        else "background: transparent;"
    )

    speaker_html = (
        f"<span class='speaker' style='--sc:{speaker_color}'>{safe_speaker}</span>"
        if cfg.show_speaker
        else ""
    )

    return f"""<!DOCTYPE html>
<html><head><style>
  body {{
    background-color: transparent !important; overflow: hidden;
    margin: 0; height: 100vh;
{_layout_css(cfg)}
    font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, -apple-system, sans-serif;
  }}
  .wrap {{
    max-width: 78%;
    padding: 18px 28px;
    border-radius: 22px;
    {plate_bg}
    animation: rise 320ms cubic-bezier(.2,.8,.2,1) both;
  }}
  .caption {{
    color: {cfg.caption_color};
    font-size: {cfg.caption_font_size}px;
    font-weight: 600; line-height: 1.32; text-align: center;
    text-shadow: 0 2px 8px rgba(0,0,0,0.85), 0 0 1px rgba(0,0,0,0.9);
  }}
  .speaker {{
    display: inline-block;
    color: #fff;
    background: var(--sc, {speaker_color});
    padding: 4px 12px; border-radius: 999px;
    font-size: 0.62em; font-weight: 700;
    letter-spacing: 0.4px; text-transform: uppercase;
    margin-right: 12px; vertical-align: middle;
    box-shadow: 0 4px 12px rgba(0,0,0,0.35);
  }}
  @keyframes rise {{
    from {{ opacity: 0; transform: translateY(14px) scale(0.98); }}
    to   {{ opacity: 1; transform: translateY(0) scale(1); }}
  }}
</style></head>
<body><div class="wrap"><div class="caption">
  {speaker_html}{safe_text}
</div></div></body></html>"""


def render_status_html(message: str, color: str = "#22D3EE", spinner: bool = False) -> str:
    safe = html.escape(message)
    spinner_html = "<span class='spinner'></span>" if spinner else ""
    return f"""<!DOCTYPE html>
<html><head><style>
  body {{
    background-color: transparent !important; overflow: hidden;
    margin: 0; height: 100vh;
    display: flex; justify-content: center; align-items: center;
    font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, -apple-system, sans-serif;
  }}
  .panel {{
    display: inline-flex; align-items: center; gap: 14px;
    padding: 18px 28px; border-radius: 18px;
    background: rgba(10,10,14,0.6);
    backdrop-filter: blur(18px) saturate(160%);
    -webkit-backdrop-filter: blur(18px) saturate(160%);
    border: 1px solid rgba(255,255,255,0.12);
    color: {color}; font-size: 28px; font-weight: 700;
    text-shadow: 0 2px 6px rgba(0,0,0,0.7);
    box-shadow: 0 18px 60px rgba(0,0,0,0.55);
    animation: rise 320ms cubic-bezier(.2,.8,.2,1) both;
  }}
  .spinner {{
    width: 22px; height: 22px; border-radius: 50%;
    border: 3px solid rgba(255,255,255,0.18);
    border-top-color: {color};
    animation: spin 0.9s linear infinite;
  }}
  @keyframes rise {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; }} }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style></head>
<body><div class="panel">{spinner_html}{safe}</div></body></html>"""
