# -*- coding: utf-8 -*-
"""Paleta oscura de bajo deslumbramiento para la HMI."""

WINDOW = "#181C22"
SURFACE = "#222831"
SURFACE_ALT = "#29313B"
BORDER = "#414B57"
TEXT = "#D5D9DE"
TEXT_MUTED = "#A8B0B9"
ACCENT_TEXT = "#C7D8D0"
SUCCESS = "#34D399"
SUCCESS_BG = "#064E3B"
WARNING = "#FBBF24"
WARNING_BG = "#422006"
ERROR = "#F87171"
ERROR_BG = "#450A0A"

DARK_THEME_STYLESHEET = f"""
    QMainWindow, QDialog, QMessageBox {{
        background-color: {WINDOW};
        color: {TEXT};
    }}
    QWidget {{
        color: {TEXT};
    }}
    QLabel {{
        color: {TEXT};
    }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit,
    QDateTimeEdit, QPlainTextEdit, QTextEdit {{
        background-color: {SURFACE};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 4px;
        padding: 5px;
        selection-background-color: {BORDER};
        selection-color: {TEXT};
    }}
    QComboBox QAbstractItemView {{
        background-color: {SURFACE};
        color: {TEXT};
        selection-background-color: {BORDER};
        selection-color: {TEXT};
        border: 1px solid {BORDER};
    }}
    QTableWidget, QTreeWidget, QListWidget {{
        background-color: {SURFACE};
        alternate-background-color: {SURFACE_ALT};
        color: {TEXT};
        gridline-color: {BORDER};
        border: 1px solid {BORDER};
        selection-background-color: {BORDER};
        selection-color: {TEXT};
    }}
    QHeaderView::section {{
        background-color: {SURFACE_ALT};
        color: {TEXT};
        padding: 6px;
        border: 1px solid {BORDER};
        font-weight: bold;
    }}
    QPushButton {{
        background-color: #0F766E;
        color: #FFFFFF;
        border: 1px solid #5EEAD4;
        border-radius: 5px;
        padding: 6px 9px;
    }}
    QPushButton:hover {{
        background-color: #0D9488;
    }}
    QPushButton:pressed {{
        background-color: #115E59;
    }}
    QPushButton:disabled {{
        background-color: {SURFACE_ALT};
        color: {TEXT_MUTED};
        border-color: {BORDER};
    }}
    QCheckBox, QRadioButton {{
        color: {TEXT};
        spacing: 6px;
    }}
    QCheckBox::indicator, QRadioButton::indicator {{
        background-color: {SURFACE};
        border: 1px solid #59636D;
        width: 14px;
        height: 14px;
    }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background-color: #53675C;
        border-color: #718579;
    }}
    QGroupBox {{
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 5px;
        margin-top: 8px;
        padding-top: 8px;
    }}
    QTabWidget::pane {{
        background-color: {WINDOW};
        border: 1px solid {BORDER};
    }}
    QTabBar::tab {{
        background-color: {SURFACE_ALT};
        color: {TEXT_MUTED};
        border: 1px solid {BORDER};
        padding: 6px 9px;
    }}
    QTabBar::tab:selected {{
        background-color: {SURFACE};
        color: {TEXT};
    }}
    QToolTip {{
        background-color: {SURFACE_ALT};
        color: {TEXT};
        border: 1px solid {BORDER};
        padding: 4px;
    }}
    QMenu {{
        background-color: {SURFACE};
        color: {TEXT};
        border: 1px solid {BORDER};
    }}
    QMenu::item:selected {{
        background-color: {SURFACE_ALT};
    }}
    QScrollBar:vertical {{
        background-color: {WINDOW};
        width: 12px;
        margin: 0;
    }}
    QScrollBar:horizontal {{
        background-color: {WINDOW};
        height: 12px;
        margin: 0;
    }}
    QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
        background-color: #59636D;
        border-radius: 5px;
        min-height: 24px;
        min-width: 24px;
    }}
    QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
        background-color: #68737E;
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{
        background: {WINDOW};
        border: none;
    }}
"""

DIALOG_STYLESHEET = DARK_THEME_STYLESHEET


def status_label_style(foreground, background, border):
    return (
        f"color: {foreground}; background-color: {background}; "
        f"border: 1px solid {border}; border-radius: 6px; "
        "padding: 0 8px; font-weight: bold;"
    )
