"""Coach overlay — a movable, resizable, always-on-top suggestion panel.

Unlike `OverlayWindow` (click-through fullscreen captions), the coach panel is
*interactive*: the user can drag it, resize it, scroll its content, and click
the quick-action buttons. It's the closest analogue to Parakeet/Cluely's
"second-screen" cheat panel.
"""

from __future__ import annotations

import logging
from html import escape

from PyQt6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QCursor, QGuiApplication, QMouseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .ai import trigger_analysis
from .config import settings
from .state import bus

log = logging.getLogger("lumen.coach")


_MARKDOWN_TO_HTML_CSS = """
<style>
  body { color: #E8EAF6; font-size: 14px; line-height: 1.55; }
  ul   { padding-left: 20px; margin: 6px 0; }
  li   { margin: 4px 0; }
  code { background: rgba(255,255,255,0.08); padding: 1px 6px;
         border-radius: 5px; font-family: 'Cascadia Mono','Consolas',monospace;
         font-size: 13px; }
  pre  { background: rgba(0,0,0,0.45); border: 1px solid rgba(255,255,255,0.08);
         padding: 10px 12px; border-radius: 8px; overflow-x: auto;
         font-family: 'Cascadia Mono','Consolas',monospace; font-size: 13px; }
  strong { color: #fff; }
  em   { color: #C7CCDD; }
  a    { color: #9579FF; }
</style>
"""


def _markdown_to_html(text: str) -> str:
    """Tiny, safe markdown → HTML conversion (bullets, bold, code, headings)."""
    if not text:
        return f"{_MARKDOWN_TO_HTML_CSS}<p style='color:#8A91A6'>(empty)</p>"

    lines = text.splitlines()
    out: list[str] = []
    in_ul = False
    in_code = False
    code_buf: list[str] = []

    def close_ul() -> None:
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False

    for raw_line in lines:
        if raw_line.strip().startswith("```"):
            if in_code:
                out.append("<pre><code>" + escape("\n".join(code_buf)) + "</code></pre>")
                code_buf = []
                in_code = False
            else:
                close_ul()
                in_code = True
            continue
        if in_code:
            code_buf.append(raw_line)
            continue

        stripped = raw_line.strip()
        if not stripped:
            close_ul()
            out.append("<br>")
            continue

        if stripped.startswith(("• ", "- ", "* ")):
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{_inline(stripped[2:])}</li>")
            continue

        close_ul()
        out.append(f"<p>{_inline(stripped)}</p>")

    close_ul()
    if in_code and code_buf:
        out.append("<pre><code>" + escape("\n".join(code_buf)) + "</code></pre>")

    return _MARKDOWN_TO_HTML_CSS + "\n".join(out)


def _inline(text: str) -> str:
    """Escape, then re-introduce **bold** and `code` spans."""
    s = escape(text)
    # **bold**
    out: list[str] = []
    i = 0
    while i < len(s):
        if s.startswith("**", i):
            j = s.find("**", i + 2)
            if j != -1:
                out.append(f"<strong>{s[i+2:j]}</strong>")
                i = j + 2
                continue
        if s[i] == "`":
            j = s.find("`", i + 1)
            if j != -1:
                out.append(f"<code>{s[i+1:j]}</code>")
                i = j + 1
                continue
        out.append(s[i])
        i += 1
    return "".join(out)


# --------------------------------------------------------------------------- #
# Panel                                                                       #
# --------------------------------------------------------------------------- #

_RESIZE_MARGIN = 8


class CoachOverlay(QWidget):
    """Frameless, draggable, resizable, semi-transparent suggestion panel."""

    def __init__(self) -> None:
        super().__init__(None)
        self.setObjectName("CoachRoot")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.setMinimumSize(320, 180)

        cfg = settings()
        self.setGeometry(cfg.coach_x, cfg.coach_y, cfg.coach_w, cfg.coach_h)
        self.setWindowOpacity(max(0.4, cfg.coach_opacity / 100))

        # Card.
        card = QFrame(self)
        card.setObjectName("CoachCard")
        card.setStyleSheet(self._stylesheet())
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.addWidget(card)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(0, 0, 0, 200))
        card.setGraphicsEffect(shadow)

        body = QVBoxLayout(card)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Header — drag handle + close.
        header = QFrame()
        header.setObjectName("CoachHeader")
        h = QHBoxLayout(header)
        h.setContentsMargins(16, 10, 8, 10)
        h.setSpacing(8)

        self._dot = QLabel("●")
        self._dot.setObjectName("CoachDot")
        self._title = QLabel("Coach")
        self._title.setObjectName("CoachTitle")
        h.addWidget(self._dot)
        h.addWidget(self._title)
        h.addStretch(1)

        self._busy = QLabel("")
        self._busy.setObjectName("CoachBusy")
        h.addWidget(self._busy)

        for label, slot, name in (
            ("✦", lambda: trigger_analysis("Answer"), "CoachIconBtn"),
            ("✕", self.hide, "CoachCloseBtn"),
        ):
            b = QPushButton(label)
            b.setObjectName(name)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedSize(28, 24)
            b.clicked.connect(slot)
            h.addWidget(b)
        body.addWidget(header)

        # Quick-action bar.
        bar = QFrame()
        bar.setObjectName("CoachBar")
        bb = QHBoxLayout(bar)
        bb.setContentsMargins(12, 8, 12, 8)
        bb.setSpacing(6)
        for label in ("Answer", "Shorten", "Recap", "Follow-up", "Define"):
            btn = QPushButton(label)
            btn.setObjectName("CoachActionBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, m=label: trigger_analysis(m))
            bb.addWidget(btn)
        bb.addStretch(1)
        body.addWidget(bar)

        # Body — scroll-contained suggestion text.
        self._body = QTextBrowser()
        self._body.setObjectName("CoachBody")
        self._body.setOpenExternalLinks(True)
        self._body.setHtml(self._placeholder_html())
        body.addWidget(self._body, 1)

        # Footer — hint + size grip.
        footer = QFrame()
        footer.setObjectName("CoachFooter")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(14, 6, 6, 6)
        self._hint = QLabel(
            f"Press {settings().analysis_hotkey} to answer the latest question  ·  "
            f"{settings().spotlight_hotkey.replace('+', ' + ')} for spotlight"
        )
        self._hint.setObjectName("CoachHint")
        fl.addWidget(self._hint)
        fl.addStretch(1)
        grip = QSizeGrip(self)
        grip.setStyleSheet("background: transparent;")
        fl.addWidget(grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        body.addWidget(footer)

        # Drag/resize state.
        self._drag_offset: QPoint | None = None
        self._resize_dir: str | None = None
        self._geom_at_press: QRect | None = None
        self._press_global: QPoint | None = None

        # Persist geometry shortly after each move/resize.
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._persist_geometry)

        # Bus wiring.
        bus.coach_update.connect(self._on_update)
        bus.coach_busy.connect(self._on_busy)
        bus.coach_visibility_changed.connect(self._set_visible)

        if cfg.coach_enabled:
            self.show()

    # ------------------------------------------------------------------ slots
    def _on_update(self, mode: str, text: str) -> None:
        if not settings().coach_enabled:
            return
        self._title.setText(mode)
        self._body.setHtml(_markdown_to_html(text))
        if not self.isVisible():
            self.show()
        self.raise_()

    def _on_busy(self, busy: bool, label: str) -> None:
        self._busy.setText(f"{label}…" if busy else "")
        self._dot.setStyleSheet(
            "color:#FFA726;" if busy else "color:#4ADE80;"
        )

    def _set_visible(self, visible: bool) -> None:
        if visible:
            self.show()
        else:
            self.hide()

    # ----------------------------------------------------------- drag/resize
    def _hit_test(self, pos: QPoint) -> str | None:
        m = _RESIZE_MARGIN
        w, h = self.width(), self.height()
        on_l = pos.x() <= m
        on_r = pos.x() >= w - m
        on_t = pos.y() <= m
        on_b = pos.y() >= h - m
        if on_l and on_t: return "tl"
        if on_r and on_t: return "tr"
        if on_l and on_b: return "bl"
        if on_r and on_b: return "br"
        if on_l: return "l"
        if on_r: return "r"
        if on_t: return "t"
        if on_b: return "b"
        return None

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._drag_offset is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_offset)
            self._save_timer.start(400)
            return
        if self._resize_dir is not None and self._geom_at_press is not None:
            self._do_resize(e.globalPosition().toPoint())
            self._save_timer.start(400)
            return
        # Hover cursor.
        d = self._hit_test(e.position().toPoint())
        cursor = {
            "l": Qt.CursorShape.SizeHorCursor,
            "r": Qt.CursorShape.SizeHorCursor,
            "t": Qt.CursorShape.SizeVerCursor,
            "b": Qt.CursorShape.SizeVerCursor,
            "tl": Qt.CursorShape.SizeFDiagCursor,
            "br": Qt.CursorShape.SizeFDiagCursor,
            "tr": Qt.CursorShape.SizeBDiagCursor,
            "bl": Qt.CursorShape.SizeBDiagCursor,
        }.get(d, Qt.CursorShape.ArrowCursor)
        self.setCursor(cursor)

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() != Qt.MouseButton.LeftButton:
            return
        d = self._hit_test(e.position().toPoint())
        if d:
            self._resize_dir = d
            self._geom_at_press = self.geometry()
            self._press_global = e.globalPosition().toPoint()
        else:
            # Drag only when click hits header area (top 48px).
            if e.position().y() <= 56:
                self._drag_offset = (
                    e.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        self._drag_offset = None
        self._resize_dir = None
        self._geom_at_press = None
        self._press_global = None
        self._persist_geometry()

    def _do_resize(self, pos_global: QPoint) -> None:
        if not (self._geom_at_press and self._press_global and self._resize_dir):
            return
        dx = pos_global.x() - self._press_global.x()
        dy = pos_global.y() - self._press_global.y()
        g = QRect(self._geom_at_press)
        d = self._resize_dir
        if "l" in d: g.setLeft(g.left() + dx)
        if "r" in d: g.setRight(g.right() + dx)
        if "t" in d: g.setTop(g.top() + dy)
        if "b" in d: g.setBottom(g.bottom() + dy)
        if g.width() < self.minimumWidth():
            g.setWidth(self.minimumWidth())
        if g.height() < self.minimumHeight():
            g.setHeight(self.minimumHeight())
        self.setGeometry(g)

    def _persist_geometry(self) -> None:
        cfg = settings()
        cfg.coach_x = self.x()
        cfg.coach_y = self.y()
        cfg.coach_w = self.width()
        cfg.coach_h = self.height()
        cfg.save()

    # ---------------------------------------------------------- placeholder
    def _placeholder_html(self) -> str:
        cfg = settings()
        hot = cfg.analysis_hotkey
        spot = cfg.spotlight_hotkey.replace("+", " + ")
        return f"""{_MARKDOWN_TO_HTML_CSS}
        <p style="color:#C7CCDD;">
          <strong>Coach</strong> is listening. Try one of the buttons above,
          press <code>{hot}</code> to answer the latest question, or
          <code>{spot}</code> to ask anything.
        </p>
        <ul style="color:#8A91A6;">
          <li><strong>Answer</strong> — bullets you can read aloud, now.</li>
          <li><strong>Shorten</strong> — tighten what you just said.</li>
          <li><strong>Recap</strong> — what's been said so far.</li>
          <li><strong>Follow-up</strong> — sharp next questions.</li>
          <li><strong>Define</strong> — the jargon they just used.</li>
        </ul>"""

    # ---------------------------------------------------------------- style
    def _stylesheet(self) -> str:
        accent = settings().accent_color
        return f"""
        QFrame#CoachCard {{
            background: rgba(13,15,22,0.94);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
        }}
        QFrame#CoachHeader {{
            background: transparent;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            border-top-left-radius: 16px; border-top-right-radius: 16px;
        }}
        QLabel#CoachDot {{ color: #4ADE80; font-size: 12px; }}
        QLabel#CoachTitle {{
            color: #fff; font-size: 14px; font-weight: 700;
            letter-spacing: 0.3px;
        }}
        QLabel#CoachBusy {{ color: #FFA726; font-size: 11px; }}
        QPushButton#CoachIconBtn, QPushButton#CoachCloseBtn {{
            background: transparent; color: #8A91A6;
            border: none; border-radius: 6px; font-size: 14px;
        }}
        QPushButton#CoachIconBtn:hover {{ background: rgba(255,255,255,0.06); color: #fff; }}
        QPushButton#CoachCloseBtn:hover {{ background: #E5484D; color: #fff; }}
        QFrame#CoachBar {{
            background: transparent;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }}
        QPushButton#CoachActionBtn {{
            background: rgba(255,255,255,0.04);
            color: #C7CCDD; border: 1px solid rgba(255,255,255,0.06);
            border-radius: 8px; padding: 5px 11px; font-size: 12px; font-weight: 500;
        }}
        QPushButton#CoachActionBtn:hover {{
            background: {accent}; color: #fff; border-color: {accent};
        }}
        QTextBrowser#CoachBody {{
            background: transparent; color: #E8EAF6;
            border: none; padding: 8px 16px;
            selection-background-color: {accent};
        }}
        QFrame#CoachFooter {{
            background: transparent;
            border-top: 1px solid rgba(255,255,255,0.05);
            border-bottom-left-radius: 16px; border-bottom-right-radius: 16px;
        }}
        QLabel#CoachHint {{ color: #6A7185; font-size: 11px; }}
        QScrollBar:vertical {{
            background: transparent; width: 8px; margin: 4px;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(255,255,255,0.18); border-radius: 4px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """


def install(app: QApplication) -> CoachOverlay:
    win = CoachOverlay()
    app.aboutToQuit.connect(win.close)
    return win
