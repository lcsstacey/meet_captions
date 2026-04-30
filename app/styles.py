"""Qt stylesheet for the dashboard. Modern dark theme with accent colour."""

from __future__ import annotations


def stylesheet(accent: str = "#7C5CFF") -> str:
    return f"""
    /* ==== Base ============================================================ */
    QWidget {{
        background: #0F1115;
        color: #E6E8EE;
        font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, -apple-system, sans-serif;
        font-size: 13px;
    }}
    QWidget#Root {{
        background: #0F1115;
        border: 1px solid #1F2230;
        border-radius: 14px;
    }}

    /* ==== Title bar ======================================================= */
    QWidget#TitleBar {{
        background: transparent;
        border-top-left-radius: 14px;
        border-top-right-radius: 14px;
    }}
    QLabel#AppTitle {{
        font-size: 14px; font-weight: 700; color: #E6E8EE;
        letter-spacing: 0.3px;
    }}
    QLabel#AppTagline {{
        font-size: 11px; color: #8A91A6; padding-left: 6px;
    }}
    QPushButton#TitleButton {{
        background: transparent; border: none; color: #8A91A6;
        font-size: 16px; padding: 4px 12px; border-radius: 6px;
    }}
    QPushButton#TitleButton:hover {{ background: #1A1D27; color: #fff; }}
    QPushButton#CloseButton:hover {{ background: #E5484D; color: #fff; }}

    /* ==== Sidebar ========================================================= */
    QFrame#Sidebar {{
        background: #0B0D12;
        border-right: 1px solid #1A1D27;
        border-bottom-left-radius: 14px;
    }}
    QPushButton.NavItem {{
        text-align: left;
        padding: 12px 18px;
        font-size: 13px; font-weight: 500;
        background: transparent;
        color: #8A91A6;
        border: none;
        border-left: 3px solid transparent;
        border-radius: 0;
    }}
    QPushButton.NavItem:hover {{
        background: #12151D;
        color: #E6E8EE;
    }}
    QPushButton.NavItem:checked {{
        background: #14171F;
        color: #fff;
        border-left: 3px solid {accent};
    }}

    /* ==== Cards =========================================================== */
    QFrame.Card {{
        background: #14171F;
        border: 1px solid #1F2230;
        border-radius: 12px;
    }}
    QLabel.SectionTitle {{
        font-size: 18px; font-weight: 700; color: #fff;
    }}
    QLabel.SectionSubtitle {{
        color: #8A91A6; font-size: 12px;
    }}
    QLabel.StatLabel {{
        color: #8A91A6; font-size: 11px;
        text-transform: uppercase; letter-spacing: 0.6px;
    }}
    QLabel.StatValue {{
        color: #fff; font-size: 22px; font-weight: 700;
    }}
    QLabel.StatusDot {{
        font-size: 11px; padding: 4px 10px; border-radius: 999px;
        background: #16321F; color: #4ADE80;
    }}
    QLabel.StatusDotWarn {{
        font-size: 11px; padding: 4px 10px; border-radius: 999px;
        background: #3a2a14; color: #FFA726;
    }}
    QLabel.StatusDotErr {{
        font-size: 11px; padding: 4px 10px; border-radius: 999px;
        background: #3a1818; color: #FF5252;
    }}

    /* ==== Buttons ========================================================= */
    QPushButton.Primary {{
        background: {accent};
        color: white; border: none; border-radius: 9px;
        padding: 10px 18px; font-weight: 600; font-size: 13px;
    }}
    QPushButton.Primary:hover {{ background: #9579FF; }}
    QPushButton.Primary:pressed {{ background: #6B4CE0; }}
    QPushButton.Primary:disabled {{ background: #2A2D38; color: #5A6172; }}

    QPushButton.Ghost {{
        background: transparent; color: #E6E8EE;
        border: 1px solid #2A2D38; border-radius: 9px;
        padding: 9px 16px; font-weight: 500;
    }}
    QPushButton.Ghost:hover {{ border-color: {accent}; color: #fff; }}

    /* ==== Inputs ========================================================== */
    QLineEdit, QComboBox, QSpinBox {{
        background: #0B0D12;
        border: 1px solid #1F2230;
        border-radius: 8px;
        padding: 8px 10px;
        color: #E6E8EE;
        selection-background-color: {accent};
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
        border-color: {accent};
    }}
    QComboBox::drop-down {{ border: none; width: 20px; }}
    QComboBox::down-arrow {{ image: none; }}
    QComboBox QAbstractItemView {{
        background: #14171F; border: 1px solid #2A2D38;
        selection-background-color: {accent}; color: #E6E8EE;
        padding: 4px;
    }}

    QCheckBox {{ spacing: 8px; }}
    QCheckBox::indicator {{
        width: 18px; height: 18px;
        border: 1px solid #2A2D38; border-radius: 5px;
        background: #0B0D12;
    }}
    QCheckBox::indicator:checked {{
        background: {accent}; border-color: {accent};
    }}

    /* ==== Lists / scroll ================================================== */
    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{
        background: transparent; width: 8px; margin: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: #2A2D38; border-radius: 4px; min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{ background: #3a3d4a; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

    /* ==== Misc ============================================================ */
    QLabel.Muted {{ color: #8A91A6; }}
    QFrame.Divider {{ background: #1F2230; max-height: 1px; min-height: 1px; }}
    QTextEdit {{
        background: #0B0D12; border: 1px solid #1F2230; border-radius: 10px;
        padding: 10px;
    }}
    """
