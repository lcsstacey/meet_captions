"""Frameless, modern Lumen control window."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable

from PyQt6.QtCore import QPoint, QPropertyAnimation, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QMouseEvent, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import APP_NAME, APP_TAGLINE, APP_VERSION
from .ai import ALL_MODES, has_api_key, load_history, trigger_analysis
from .config import POSITION_PRESETS, TRANSCRIPT_FILE, settings
from .state import AnalysisEvent, CaptionEvent, bus
from .styles import stylesheet

log = logging.getLogger("lumen.dashboard")


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #

def make_logo_icon(size: int = 32, accent: str = "#7C5CFF") -> QIcon:
    """Generate a tiny glowing-orb logo at runtime — no asset files needed."""
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(accent))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(2, 2, size - 4, size - 4)
    inner = QColor("#22D3EE")
    inner.setAlphaF(0.65)
    p.setBrush(inner)
    p.drawEllipse(int(size * 0.28), int(size * 0.22),
                  int(size * 0.32), int(size * 0.32))
    p.end()
    return QIcon(px)


def card(*children: QWidget, spacing: int = 12, padding: int = 18) -> QFrame:
    f = QFrame()
    f.setProperty("class", "Card")
    f.setObjectName("Card")
    f.setStyleSheet("")  # ensure class selector applies
    lay = QVBoxLayout(f)
    lay.setContentsMargins(padding, padding, padding, padding)
    lay.setSpacing(spacing)
    for c in children:
        lay.addWidget(c)
    # apply class selector via dynamic property; restyle after addition
    f.setProperty("class", "Card")
    return f


def labeled(text: str, klass: str = "") -> QLabel:
    lab = QLabel(text)
    if klass:
        lab.setProperty("class", klass)
    return lab


# --------------------------------------------------------------------------- #
# Custom title bar                                                            #
# --------------------------------------------------------------------------- #

class TitleBar(QWidget):
    closed = pyqtSignal()
    minimised = pyqtSignal()

    def __init__(self, parent: "Dashboard") -> None:
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(44)
        self._parent = parent
        self._drag_pos: QPoint | None = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 8, 0)
        lay.setSpacing(10)

        title = QLabel(APP_NAME)
        title.setObjectName("AppTitle")
        tagline = QLabel(APP_TAGLINE)
        tagline.setObjectName("AppTagline")
        lay.addWidget(title)
        lay.addWidget(tagline)
        lay.addStretch(1)

        for label, slot, name in (
            ("—", self.minimised.emit, "TitleButton"),
            ("✕", self.closed.emit, "CloseButton"),
        ):
            b = QPushButton(label)
            b.setObjectName(name)
            if name == "CloseButton":
                b.setProperty("class", "TitleButton")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedSize(36, 28)
            b.clicked.connect(slot)
            lay.addWidget(b)

    # Drag-to-move
    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self._parent.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._drag_pos is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self._parent.move(e.globalPosition().toPoint() - self._drag_pos)
            e.accept()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        self._drag_pos = None


# --------------------------------------------------------------------------- #
# Pages                                                                       #
# --------------------------------------------------------------------------- #

class LivePage(QWidget):
    """Live captions, status header, and a 'Trigger AI' panel."""

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(18)

        # Header
        title = labeled("Live", "SectionTitle")
        sub = labeled(
            "Real-time captions from your meeting are streaming below.",
            "SectionSubtitle",
        )
        outer.addWidget(title)
        outer.addWidget(sub)

        # Stat cards
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        self.stat_status = self._stat_card("Status", "Idle")
        self.stat_count = self._stat_card("Captions", "0")
        self.stat_last = self._stat_card("Last caption", "—")
        self.stat_api = self._stat_card(
            "Gemini", "Connected" if has_api_key() else "Missing key"
        )
        for w in (self.stat_status, self.stat_count, self.stat_last, self.stat_api):
            stats_row.addWidget(w)
        outer.addLayout(stats_row)

        # Live transcript card
        transcript_card = QFrame()
        transcript_card.setProperty("class", "Card")
        tlay = QVBoxLayout(transcript_card)
        tlay.setContentsMargins(18, 18, 18, 18)
        tlay.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.addWidget(labeled("Live transcript"))
        header_row.addStretch(1)

        self.mode_select = QComboBox()
        self.mode_select.addItems(ALL_MODES)
        self.mode_select.setCurrentText(settings().analysis_mode)
        header_row.addWidget(self.mode_select)

        self.analyse_btn = QPushButton("✨ Run")
        self.analyse_btn.setProperty("class", "Primary")
        self.analyse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.analyse_btn.clicked.connect(self._on_analyse)
        header_row.addWidget(self.analyse_btn)

        self.export_btn = QPushButton("⤓ Export")
        self.export_btn.setProperty("class", "Ghost")
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.clicked.connect(self._on_export)
        header_row.addWidget(self.export_btn)
        tlay.addLayout(header_row)

        # Quick-action bar — one click to a coach response.
        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)
        for label, mode in [
            ("✦ Answer", "Answer"),
            ("∿ Shorten", "Shorten"),
            ("≡ Recap", "Recap"),
            ("? Follow-up", "Follow-up"),
            ("ⓘ Define", "Define"),
        ]:
            b = QPushButton(label)
            b.setProperty("class", "Ghost")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, m=mode: trigger_analysis(m))
            actions_row.addWidget(b)
        spot = QPushButton("⌕ Spotlight")
        spot.setProperty("class", "Ghost")
        spot.setCursor(Qt.CursorShape.PointingHandCursor)
        spot.clicked.connect(bus.spotlight_requested.emit)
        actions_row.addWidget(spot)
        actions_row.addStretch(1)
        tlay.addLayout(actions_row)

        self.transcript_list = QListWidget()
        self.transcript_list.setSelectionMode(self.transcript_list.SelectionMode.NoSelection)
        self.transcript_list.setSpacing(2)
        self.transcript_list.setStyleSheet(
            "QListWidget { background: #0B0D12; border: 1px solid #1F2230; "
            "border-radius: 10px; padding: 8px; }"
            "QListWidget::item { padding: 8px 10px; border-radius: 6px; }"
        )
        self.transcript_list.setMinimumHeight(260)
        tlay.addWidget(self.transcript_list, 1)
        outer.addWidget(transcript_card, 1)

        # Wire bus
        bus.caption_received.connect(self._on_caption)
        bus.status_changed.connect(self._on_status)

        QTimer.singleShot(50, self._add_placeholder)

    def _add_placeholder(self) -> None:
        item = QListWidgetItem(
            "  Waiting for the browser extension to start streaming captions…"
        )
        item.setForeground(QColor("#6A7185"))
        self.transcript_list.addItem(item)

    # -- helpers ---------------------------------------------------------- #

    def _stat_card(self, label: str, value: str) -> QFrame:
        f = QFrame()
        f.setProperty("class", "Card")
        v = QVBoxLayout(f)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(4)
        l1 = labeled(label, "StatLabel")
        l2 = labeled(value, "StatValue")
        l2.setObjectName("statValue")
        v.addWidget(l1)
        v.addWidget(l2)
        f._value = l2  # type: ignore[attr-defined]
        return f

    def _set_stat(self, card: QFrame, value: str) -> None:
        card._value.setText(value)  # type: ignore[attr-defined]

    # -- slots ------------------------------------------------------------ #

    def _on_caption(self, ev: CaptionEvent) -> None:
        # Drop the placeholder once real captions arrive.
        if (
            self.transcript_list.count() == 1
            and self.transcript_list.item(0).foreground().color().name() == "#6a7185"
        ):
            self.transcript_list.clear()

        ts = ev.timestamp.strftime("%H:%M:%S")
        text = f"  [{ts}]   {ev.speaker}:   {ev.text}"
        item = QListWidgetItem(text)
        self.transcript_list.addItem(item)
        # Auto-scroll
        self.transcript_list.scrollToBottom()
        # Cap visible items.
        if self.transcript_list.count() > 500:
            self.transcript_list.takeItem(0)

        self._set_stat(self.stat_count, str(self.transcript_list.count()))
        self._set_stat(self.stat_last, ts)
        self._set_stat(self.stat_status, "Live")

    def _on_status(self, level: str, message: str) -> None:
        self._set_stat(self.stat_status, message[:32])

    def _on_analyse(self) -> None:
        mode = self.mode_select.currentText()
        cfg = settings()
        cfg.analysis_mode = mode
        cfg.save()
        trigger_analysis(mode)

    def _on_export(self) -> None:
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Export transcript", "transcript.md",
            "Markdown (*.md);;Text (*.txt);;All Files (*)",
        )
        if not path:
            return
        try:
            content = (
                "# Meeting transcript\n\n"
                + TRANSCRIPT_FILE.read_text("utf-8")
                if TRANSCRIPT_FILE.exists() else "# Meeting transcript\n\n(empty)"
            )
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            bus.status_changed.emit("info", f"Exported to {path}")
        except OSError as e:
            bus.status_changed.emit("error", f"Export failed: {e}")


class InsightsPage(QWidget):
    """History of analyses, plus the latest result rendered in detail."""

    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(18)

        lay.addWidget(labeled("Insights", "SectionTitle"))
        lay.addWidget(labeled(
            "Every Gemini analysis is archived here.", "SectionSubtitle"
        ))

        body = QHBoxLayout()
        body.setSpacing(14)

        self.history_list = QListWidget()
        self.history_list.setStyleSheet(
            "QListWidget { background: #0B0D12; border: 1px solid #1F2230; "
            "border-radius: 10px; padding: 6px; }"
            "QListWidget::item { padding: 10px 12px; border-radius: 6px; }"
            "QListWidget::item:selected { background: #1A1D27; color: #fff; }"
        )
        self.history_list.setMinimumWidth(260)
        self.history_list.itemSelectionChanged.connect(self._on_select)
        body.addWidget(self.history_list, 1)

        detail_card = QFrame()
        detail_card.setProperty("class", "Card")
        dlay = QVBoxLayout(detail_card)
        dlay.setContentsMargins(18, 18, 18, 18)
        dlay.setSpacing(10)
        self.detail_title = labeled("Select an entry", "SectionTitle")
        dlay.addWidget(self.detail_title)
        self.detail_meta = labeled("", "Muted")
        dlay.addWidget(self.detail_meta)
        self.detail_body = QTextEdit()
        self.detail_body.setReadOnly(True)
        dlay.addWidget(self.detail_body, 1)
        body.addWidget(detail_card, 2)

        lay.addLayout(body, 1)

        bus.analysis_completed.connect(self._on_new_analysis)
        self._reload_history()

    def _reload_history(self) -> None:
        self.history_list.clear()
        for entry in load_history():
            ts = entry.get("timestamp", "")
            try:
                dt_obj = datetime.fromisoformat(ts)
                pretty_ts = dt_obj.strftime("%b %d, %H:%M")
            except ValueError:
                pretty_ts = ts
            label = f"  {entry.get('mode', '?')}   ·   {pretty_ts}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.history_list.addItem(item)

    def _on_new_analysis(self, ev: AnalysisEvent) -> None:
        self._reload_history()
        if self.history_list.count() > 0:
            self.history_list.setCurrentRow(0)

    def _on_select(self) -> None:
        items = self.history_list.selectedItems()
        if not items:
            return
        entry = items[0].data(Qt.ItemDataRole.UserRole)
        self.detail_title.setText(entry.get("mode", "?"))
        self.detail_meta.setText(entry.get("timestamp", ""))
        body = entry.get("summary") or "(rendered in the overlay)"
        self.detail_body.setPlainText(body)


class ContextPage(QWidget):
    """Personalised context — resume, role/JD, and free-form notes."""

    def __init__(self) -> None:
        super().__init__()
        cfg = settings()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(14)

        outer.addWidget(labeled("Context", "SectionTitle"))
        outer.addWidget(labeled(
            "Anything you put here is included in every Coach prompt — "
            "your resume, the job description, talking points, anything.",
            "SectionSubtitle",
        ))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        v = QVBoxLayout(host)
        v.setContentsMargins(0, 6, 6, 6)
        v.setSpacing(14)

        self.resume = self._editor(
            "Resume / profile",
            "Paste your CV, projects, achievements…",
            cfg.resume_text,
            "resume_text",
            min_h=160,
        )
        v.addWidget(self.resume)

        self.role = self._editor(
            "Role / job description",
            "What's the role? What does the team value?",
            cfg.role_text,
            "role_text",
            min_h=120,
        )
        v.addWidget(self.role)

        self.notes = self._editor(
            "Live notes",
            "Anything else Lumen should know right now…",
            cfg.notes_text,
            "notes_text",
            min_h=120,
        )
        v.addWidget(self.notes)

        v.addStretch(1)
        scroll.setWidget(host)
        outer.addWidget(scroll, 1)

    def _editor(self, title: str, placeholder: str, value: str,
                attr: str, min_h: int) -> QFrame:
        f = QFrame()
        f.setProperty("class", "Card")
        v = QVBoxLayout(f)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(8)
        v.addWidget(labeled(title))

        edit = QTextEdit()
        edit.setPlaceholderText(placeholder)
        edit.setPlainText(value)
        edit.setMinimumHeight(min_h)

        # Save 600ms after the user stops typing.
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(600)

        def schedule() -> None:
            timer.start()

        def commit() -> None:
            cfg = settings()
            setattr(cfg, attr, edit.toPlainText())
            cfg.save()
            bus.settings_changed.emit()

        edit.textChanged.connect(schedule)
        timer.timeout.connect(commit)
        v.addWidget(edit)
        return f


class SettingsPage(QWidget):
    """All persistent preferences, applied live."""

    def __init__(self) -> None:
        super().__init__()
        cfg = settings()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(18)

        lay.addWidget(labeled("Settings", "SectionTitle"))
        lay.addWidget(labeled(
            "Changes save automatically.", "SectionSubtitle"
        ))

        # ---- Overlay card ---- #
        overlay_card = QFrame()
        overlay_card.setProperty("class", "Card")
        ov = QFormLayout(overlay_card)
        ov.setContentsMargins(20, 20, 20, 20)
        ov.setVerticalSpacing(12)
        ov.setHorizontalSpacing(20)

        ov.addRow(labeled("Overlay", "SectionTitle"))

        self.cb_overlay = QCheckBox("Show overlay over other windows")
        self.cb_overlay.setChecked(cfg.overlay_enabled)
        self.cb_overlay.toggled.connect(
            lambda v: self._update("overlay_enabled", v, _emit_visibility=True)
        )
        ov.addRow(self.cb_overlay)

        self.position = QComboBox()
        self.position.addItems(list(POSITION_PRESETS.keys()))
        self.position.setCurrentText(cfg.caption_position)
        self.position.currentTextChanged.connect(
            lambda v: self._update("caption_position", v)
        )
        ov.addRow("Position", self.position)

        self.font_size = QSpinBox()
        self.font_size.setRange(14, 96)
        self.font_size.setValue(cfg.caption_font_size)
        self.font_size.setSuffix(" px")
        self.font_size.valueChanged.connect(
            lambda v: self._update("caption_font_size", v)
        )
        ov.addRow("Caption size", self.font_size)

        self.ttl = QSpinBox()
        self.ttl.setRange(3, 60)
        self.ttl.setValue(cfg.caption_ttl_seconds)
        self.ttl.setSuffix(" sec")
        self.ttl.valueChanged.connect(
            lambda v: self._update("caption_ttl_seconds", v)
        )
        ov.addRow("Caption time-to-live", self.ttl)

        self.cb_speaker = QCheckBox("Show speaker name")
        self.cb_speaker.setChecked(cfg.show_speaker)
        self.cb_speaker.toggled.connect(
            lambda v: self._update("show_speaker", v)
        )
        ov.addRow(self.cb_speaker)

        self.cb_color = QCheckBox("Auto-colour speaker pills")
        self.cb_color.setChecked(cfg.color_speakers)
        self.cb_color.toggled.connect(
            lambda v: self._update("color_speakers", v)
        )
        ov.addRow(self.cb_color)

        self.cb_glass = QCheckBox("Glassmorphism background plate")
        self.cb_glass.setChecked(cfg.glass_plate)
        self.cb_glass.toggled.connect(
            lambda v: self._update("glass_plate", v)
        )
        ov.addRow(self.cb_glass)

        lay.addWidget(overlay_card)

        # ---- Coach panel card ---- #
        coach_card = QFrame()
        coach_card.setProperty("class", "Card")
        cf = QFormLayout(coach_card)
        cf.setContentsMargins(20, 20, 20, 20)
        cf.setVerticalSpacing(12)
        cf.setHorizontalSpacing(20)
        cf.addRow(labeled("Coach panel", "SectionTitle"))

        self.cb_coach = QCheckBox("Show floating Coach panel")
        self.cb_coach.setChecked(cfg.coach_enabled)
        self.cb_coach.toggled.connect(
            lambda v: (
                self._update("coach_enabled", v),
                bus.coach_visibility_changed.emit(v),
            )
        )
        cf.addRow(self.cb_coach)

        self.coach_opacity = QSpinBox()
        self.coach_opacity.setRange(40, 100)
        self.coach_opacity.setValue(cfg.coach_opacity)
        self.coach_opacity.setSuffix(" %")
        self.coach_opacity.valueChanged.connect(
            lambda v: self._update("coach_opacity", v)
        )
        cf.addRow("Opacity", self.coach_opacity)

        self.cb_auto = QCheckBox("Auto-answer when a question is asked")
        self.cb_auto.setChecked(cfg.auto_answer_questions)
        self.cb_auto.toggled.connect(
            lambda v: self._update("auto_answer_questions", v)
        )
        cf.addRow(self.cb_auto)
        lay.addWidget(coach_card)

        # ---- AI card ---- #
        ai_card = QFrame()
        ai_card.setProperty("class", "Card")
        af = QFormLayout(ai_card)
        af.setContentsMargins(20, 20, 20, 20)
        af.setVerticalSpacing(12)
        af.setHorizontalSpacing(20)
        af.addRow(labeled("AI", "SectionTitle"))

        self.model = QLineEdit(cfg.gemini_model)
        self.model.editingFinished.connect(
            lambda: self._update("gemini_model", self.model.text())
        )
        af.addRow("Gemini model", self.model)

        self.analysis_ttl = QSpinBox()
        self.analysis_ttl.setRange(5, 120)
        self.analysis_ttl.setValue(cfg.analysis_ttl_seconds)
        self.analysis_ttl.setSuffix(" sec")
        self.analysis_ttl.valueChanged.connect(
            lambda v: self._update("analysis_ttl_seconds", v)
        )
        af.addRow("HUD time-to-live", self.analysis_ttl)

        self.default_mode = QComboBox()
        self.default_mode.addItems(ALL_MODES)
        self.default_mode.setCurrentText(cfg.analysis_mode)
        self.default_mode.currentTextChanged.connect(
            lambda v: self._update("analysis_mode", v)
        )
        af.addRow("Default analysis mode", self.default_mode)

        lay.addWidget(ai_card)

        # ---- Hotkeys card ---- #
        hot = QFrame()
        hot.setProperty("class", "Card")
        hf = QFormLayout(hot)
        hf.setContentsMargins(20, 20, 20, 20)
        hf.setVerticalSpacing(12)
        hf.setHorizontalSpacing(20)
        hf.addRow(labeled("Hotkeys", "SectionTitle"))

        self.k_an = QLineEdit(cfg.analysis_hotkey)
        self.k_an.editingFinished.connect(
            lambda: self._update("analysis_hotkey", self.k_an.text())
        )
        hf.addRow("Analyse", self.k_an)

        self.k_tog = QLineEdit(cfg.toggle_overlay_hotkey)
        self.k_tog.editingFinished.connect(
            lambda: self._update("toggle_overlay_hotkey", self.k_tog.text())
        )
        hf.addRow("Toggle overlay", self.k_tog)

        self.k_spot = QLineEdit(cfg.spotlight_hotkey)
        self.k_spot.editingFinished.connect(
            lambda: self._update("spotlight_hotkey", self.k_spot.text())
        )
        hf.addRow("Spotlight", self.k_spot)

        self.k_stealth = QLineEdit(cfg.stealth_hotkey)
        self.k_stealth.editingFinished.connect(
            lambda: self._update("stealth_hotkey", self.k_stealth.text())
        )
        hf.addRow("Stealth (hide all)", self.k_stealth)

        self.k_q = QLineEdit(cfg.quit_hotkey)
        self.k_q.editingFinished.connect(
            lambda: self._update("quit_hotkey", self.k_q.text())
        )
        hf.addRow("Quit", self.k_q)

        note = labeled(
            "Hotkey changes apply on next launch.", "Muted"
        )
        hf.addRow(note)

        lay.addWidget(hot)
        lay.addStretch(1)

    def _update(
        self, attr: str, value, _emit_visibility: bool = False
    ) -> None:
        cfg = settings()
        setattr(cfg, attr, value)
        cfg.save()
        bus.settings_changed.emit()
        if _emit_visibility:
            bus.overlay_visibility_changed.emit(bool(value))


class AboutPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)
        lay.addWidget(labeled("About Lumen", "SectionTitle"))
        cfg = settings()
        info = QLabel(
            f"<p style='color:#E6E8EE; line-height:1.6;'>"
            f"<b>{APP_NAME} v{APP_VERSION}</b><br>"
            f"{APP_TAGLINE}"
            f"</p>"
            f"<p style='color:#8A91A6; line-height:1.6;'>"
            f"Lumen turns a transparent fullscreen layer into a meeting copilot. "
            f"It receives captions from a browser extension on "
            f"<code>http://{cfg.flask_host}:{cfg.flask_port}/api/captions</code> "
            f"and lets Gemini distil what's been said into a HUD, a summary, "
            f"action items, or open questions — all on a hotkey."
            f"</p>"
            f"<p style='color:#8A91A6;'>"
            f"<b>Hotkeys:</b><br>"
            f"<code>{cfg.analysis_hotkey}</code> — run analysis<br>"
            f"<code>{cfg.toggle_overlay_hotkey}</code> — toggle overlay<br>"
            f"<code>{cfg.quit_hotkey}</code> — quit"
            f"</p>"
        )
        info.setWordWrap(True)
        info.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(info)
        lay.addStretch(1)


# --------------------------------------------------------------------------- #
# Dashboard window                                                            #
# --------------------------------------------------------------------------- #

class Dashboard(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(make_logo_icon())
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(1080, 720)

        root = QFrame()
        root.setObjectName("Root")
        self.setCentralWidget(root)

        # subtle drop shadow on the rounded card
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 200))
        root.setGraphicsEffect(shadow)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Title bar
        self.title_bar = TitleBar(self)
        self.title_bar.closed.connect(self._on_close)
        self.title_bar.minimised.connect(self.showMinimized)
        outer.addWidget(self.title_bar)

        # Body: sidebar + stack
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(0, 18, 0, 18)
        sb.setSpacing(2)

        # Brand row inside sidebar
        brand = QHBoxLayout()
        brand.setContentsMargins(20, 4, 20, 22)
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(make_logo_icon(28).pixmap(28, 28))
        brand_text = QLabel(f"<b>{APP_NAME}</b>")
        brand_text.setStyleSheet("color: #fff; font-size: 16px;")
        brand.addWidget(logo)
        brand.addWidget(brand_text)
        brand.addStretch(1)
        wrap = QWidget()
        wrap.setLayout(brand)
        sb.addWidget(wrap)

        self.stack = QStackedWidget()
        self.live_page = LivePage()
        self.context_page = ContextPage()
        self.insights_page = InsightsPage()
        self.settings_page = SettingsPage()
        self.about_page = AboutPage()
        self.stack.addWidget(self.live_page)
        self.stack.addWidget(self.context_page)
        self.stack.addWidget(self.insights_page)
        self.stack.addWidget(self.settings_page)
        self.stack.addWidget(self.about_page)

        nav_items: list[tuple[str, int]] = [
            ("◐  Live", 0),
            ("◆  Context", 1),
            ("✦  Insights", 2),
            ("⚙  Settings", 3),
            ("ⓘ  About", 4),
        ]
        self._nav_buttons: list[QPushButton] = []
        for label, idx in nav_items:
            btn = QPushButton(label)
            btn.setProperty("class", "NavItem")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, i=idx: self._select(i))
            sb.addWidget(btn)
            self._nav_buttons.append(btn)

        sb.addStretch(1)

        version_lab = QLabel(f"v{APP_VERSION}")
        version_lab.setStyleSheet("color: #5A6172; padding: 0 20px 4px 20px;")
        sb.addWidget(version_lab)

        body.addWidget(sidebar)
        body.addWidget(self.stack, 1)
        outer.addLayout(body, 1)

        self.setStyleSheet(stylesheet(settings().accent_color))
        self._select(0)

        # Fade-in
        self.setWindowOpacity(0.0)
        QTimer.singleShot(0, self._fade_in)

    # -- nav -------------------------------------------------------------- #

    def _select(self, idx: int) -> None:
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == idx)
        self.stack.setCurrentIndex(idx)

    # -- window chrome ---------------------------------------------------- #

    def _fade_in(self) -> None:
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(220)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start()
        self._fade_anim = anim  # keep reference

    def _on_close(self) -> None:
        if settings().minimise_to_tray:
            self.hide()
        else:
            QApplication.instance().quit()

    def closeEvent(self, e) -> None:  # type: ignore[override]
        if settings().minimise_to_tray:
            e.ignore()
            self.hide()
        else:
            super().closeEvent(e)
