from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QCheckBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from shared.theme import card, primary_button, stylesheet
from shared.theme import hide_caption_icon
from .diagnostics import CheckResult, HistoryStore, diagnose, flush_dns, open_network_settings, open_proxy_settings, summarize


class DiagnosisWorker(QObject):
    finished = Signal(list, str)

    def __init__(self, mode: str, selected: set[str] | None = None):
        super().__init__()
        self.mode = mode
        self.selected = selected
        self.cancelled = False

    def run(self) -> None:
        try:
            results = diagnose(self.mode, lambda: self.cancelled, self.selected)
        except Exception as exc:
            self.finished.emit([], f"Diagnosis failed: {exc}")
        else:
            self.finished.emit(results, "Diagnosis cancelled" if self.cancelled else "")


class SolverWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Internet Problem Solver")
        self.setMinimumSize(920, 650)
        self.setStyleSheet(stylesheet())
        self.history = HistoryStore(Path.home() / "AppData" / "Local" / "InternetProblemSolver" / "history.jsonl")
        self.thread: QThread | None = None
        self.worker: DiagnosisWorker | None = None
        self.results: list[CheckResult] = []
        self.mode = QComboBox()
        self.mode.addItem("Quick Check", "quick")
        self.mode.addItem("Standard Check", "standard")
        self.mode.addItem("Deep Check", "deep")
        self.mode.addItem("Manual Check", "manual")
        self.manual_checks: dict[str, QCheckBox] = {}
        self.run_button = primary_button("Run diagnosis")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        self.summary_title = QLabel("Ready to check")
        self.summary_title.setObjectName("Title")
        self.summary_body = QLabel("Choose a mode and run a diagnosis. The first screen stays simple.")
        self.summary_body.setWordWrap(True)
        self.action_button = QPushButton("Open network settings")
        self.action_button.hide()
        self.results_list = QListWidget()
        self.history_list = QListWidget()
        self._build()

    def _build(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 24)
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Internet Problem Solver")
        title.setObjectName("Title")
        subtitle = QLabel("Find the bottleneck. Fix the connection.")
        subtitle.setObjectName("Subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()
        layout.addLayout(header)
        controls, controls_layout = card("Diagnosis mode")
        row = QHBoxLayout()
        row.addWidget(self.mode)
        row.addWidget(self.run_button)
        row.addWidget(self.cancel_button)
        row.addStretch()
        for control in (self.mode, self.run_button, self.cancel_button):
            control.setMinimumHeight(40)
        controls_layout.addLayout(row)
        controls_layout.addWidget(self.progress)
        manual = QHBoxLayout()
        for key, label in (("adapter", "Adapter"), ("dns", "DNS"), ("internet", "Internet"), ("https", "HTTPS"), ("gateway", "Gateway"), ("proxy", "Proxy"), ("route", "Route"), ("ipv6", "IPv6")):
            checkbox = QCheckBox(label)
            checkbox.setChecked(True)
            self.manual_checks[key] = checkbox
            manual.addWidget(checkbox)
        self.manual_options = QWidget()
        self.manual_options.setLayout(manual)
        self.manual_options.hide()
        controls_layout.addWidget(self.manual_options)
        layout.addWidget(controls)
        summary, summary_layout = card("What is wrong")
        summary_layout.addWidget(self.summary_title)
        summary_layout.addWidget(self.summary_body)
        summary_layout.addWidget(self.action_button)
        layout.addWidget(summary)
        details, details_layout = card("Technical results")
        details_layout.addWidget(self.results_list)
        layout.addWidget(details, 1)
        history, history_layout = card("Recent checks")
        history_layout.addWidget(self.history_list)
        layout.addWidget(history)
        self.setCentralWidget(root)
        self.run_button.clicked.connect(self.start_diagnosis)
        self.cancel_button.clicked.connect(self.cancel_diagnosis)
        self.action_button.clicked.connect(self.apply_action)
        self.mode.currentIndexChanged.connect(lambda: self.manual_options.setVisible(self.mode.currentData() == "manual"))

    def start_diagnosis(self) -> None:
        if self.thread is not None:
            return
        self.results_list.clear()
        self.summary_title.setText("Checking…")
        self.summary_body.setText("Testing your adapter, DNS and internet path.")
        self.run_button.setEnabled(False)
        self.mode.setEnabled(False)
        self.manual_options.setEnabled(False)
        self.action_button.hide()
        self.cancel_button.setEnabled(True)
        self.progress.show()
        self.thread = QThread(self)
        selected = {key for key, checkbox in self.manual_checks.items() if checkbox.isChecked()}
        self.worker = DiagnosisWorker(self.mode.currentData(), selected)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.finish_diagnosis)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.clear_thread)
        self.thread.start()

    def cancel_diagnosis(self) -> None:
        if self.worker:
            self.worker.cancelled = True
            self.summary_body.setText("Cancelling after the current check…")

    def closeEvent(self, event):
        if self.thread is not None:
            self.cancel_diagnosis()
            event.ignore()
            return
        super().closeEvent(event)

    def clear_thread(self) -> None:
        self.thread = None
        self.worker = None

    def finish_diagnosis(self, results: list[CheckResult], message: str) -> None:
        self.results = results
        self.results_list.clear()
        for result in results:
            item = QListWidgetItem(f"{result.status.upper():7}  {result.title}  ·  {result.value}")
            item.setToolTip(result.explanation)
            self.results_list.addItem(item)
        title, body, action = summarize(results)
        if message:
            title, body, action = message, "Completed checks are shown below.", ""
        else:
            try:
                self.history.append(self.mode.currentData(), results)
            except OSError:
                body += " History could not be saved."
            self.history_list.insertItem(0, f"{self.mode.currentText()} · {title}")
        self.summary_title.setText(title)
        self.summary_body.setText(body)
        self.action_button.setVisible(bool(action))
        self.cancel_button.setEnabled(False)
        self.run_button.setEnabled(True)
        self.mode.setEnabled(True)
        self.manual_options.setEnabled(True)
        self.progress.hide()

    def apply_action(self) -> None:
        failed = next((result for result in self.results if result.status in {"fail", "warn"} and result.action), None)
        if failed and failed.action == "Flush DNS cache":
            if QMessageBox.question(self, "Confirm action", "Flush the Windows DNS cache now?") == QMessageBox.StandardButton.Yes:
                flush_dns()
                self.summary_body.setText("DNS cache flush requested. Run the diagnosis again to verify the result.")
        elif failed and failed.action == "Open proxy settings":
            open_proxy_settings()
        else:
            open_network_settings()


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Internet Problem Solver")
    window = SolverWindow()
    window.show()
    hide_caption_icon(window)
    raise SystemExit(app.exec())
