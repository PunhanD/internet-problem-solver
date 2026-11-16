from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


COLORS = {
    "background": "#0b1220",
    "surface": "#131d2f",
    "surface_alt": "#1b2940",
    "border": "#2b3c58",
    "text": "#f4f7fb",
    "muted": "#9aabc2",
    "accent": "#62d6c7",
    "accent_dark": "#238f89",
    "warning": "#f4c66b",
    "danger": "#ef7d82",
    "success": "#77d69b",
}


def hide_caption_icon(window: QWidget) -> None:
    if sys.platform == "win32":
        # A null icon makes Windows fall back to the default application icon.
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        window.setWindowIcon(QIcon(pixmap))


def stylesheet() -> str:
    return f"""
    QWidget {{ color: {COLORS['text']}; font-family: 'Segoe UI'; font-size: 10pt; }}
    QMainWindow, QDialog {{ background: {COLORS['background']}; }}
    QFrame#Card {{ background: {COLORS['surface']}; border: 1px solid {COLORS['border']}; border-radius: 14px; }}
    QLabel#Title {{ font-size: 22pt; font-weight: 700; }}
    QLabel#Subtitle {{ color: {COLORS['muted']}; font-size: 10.5pt; }}
    QLabel#Section {{ color: {COLORS['accent']}; font-size: 10pt; font-weight: 700; }}
    QLabel#Muted {{ color: {COLORS['muted']}; }}
    QPushButton {{ background: {COLORS['surface_alt']}; border: 1px solid {COLORS['border']}; border-radius: 9px; padding: 9px 15px; }}
    QPushButton:hover {{ border-color: {COLORS['accent']}; }}
    QPushButton#Primary {{ background: {COLORS['accent_dark']}; border-color: {COLORS['accent']}; font-weight: 700; padding: 12px 20px; }}
    QPushButton#Danger {{ color: {COLORS['danger']}; }}
    QComboBox, QLineEdit, QSpinBox, QTableWidget, QListWidget, QPlainTextEdit {{ background: {COLORS['surface']}; border: 1px solid {COLORS['border']}; border-radius: 8px; padding: 7px; }}
    QTableWidget {{ gridline-color: {COLORS['border']}; }}
    QHeaderView::section {{ background: {COLORS['surface_alt']}; color: {COLORS['muted']}; padding: 7px; border: 0; }}
    QProgressBar {{ border: 1px solid {COLORS['border']}; border-radius: 6px; background: {COLORS['surface']}; text-align: center; }}
    QProgressBar::chunk {{ background: {COLORS['accent_dark']}; border-radius: 5px; }}
    QTabBar::tab {{ background: {COLORS['surface']}; padding: 9px 16px; border: 1px solid {COLORS['border']}; }}
    QTabBar::tab:selected {{ color: {COLORS['accent']}; border-bottom-color: {COLORS['accent']}; }}
    """


def card(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(10)
    if title:
        label = QLabel(title)
        label.setObjectName("Section")
        layout.addWidget(label)
    return frame, layout


def primary_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("Primary")
    return button


def logo_pixmap(letter: str, color: str = COLORS["accent_dark"]) -> QPixmap:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(3, 3, 58, 58, 18, 18)
    painter.setPen(QColor(COLORS["text"]))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, letter)
    painter.end()
    return pixmap
