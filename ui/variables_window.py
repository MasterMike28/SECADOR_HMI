# -*- coding: utf-8 -*-
from collections.abc import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QHeaderView,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class VariablesWindow(QDialog):
    def __init__(self, data_provider: Callable[[], list[tuple[str, str, object, str]]], parent=None):
        super().__init__(parent)
        self.data_provider = data_provider
        self.setWindowTitle("Variables del sistema")
        self.resize(700, 520)
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.setStyleSheet("""
            QDialog { background-color: #111827; color: #F3F4F6; }
            QLineEdit, QTableWidget {
                background-color: #1F2937;
                color: #F3F4F6;
                border: 1px solid #374151;
                selection-background-color: #2563EB;
            }
            QHeaderView::section {
                background-color: #374151;
                color: #FFFFFF;
                padding: 5px;
                border: 1px solid #4B5563;
                font-weight: bold;
            }
        """)

        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filtrar por grupo, variable o valor...")
        self.search.textChanged.connect(self._filter_rows)
        layout.addWidget(self.search)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Grupo", "Variable", "Valor", "Unidad"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(500)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def refresh(self):
        if not self.isVisible():
            return

        rows = self.data_provider()
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(rows))
        for row_index, (group, name, value, unit) in enumerate(rows):
            if isinstance(value, bool):
                display_value = "Sí" if value else "No"
            elif value is None:
                display_value = "No disponible"
            elif isinstance(value, float):
                display_value = f"{value:g}"
            else:
                display_value = str(value)

            values = (group, name, display_value, unit)
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                if column == 2:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row_index, column, item)

        self.table.setUpdatesEnabled(True)
        self._filter_rows(self.search.text())

    def _filter_rows(self, text: str):
        query = text.casefold().strip()
        for row in range(self.table.rowCount()):
            row_text = " ".join(
                self.table.item(row, column).text()
                for column in range(self.table.columnCount())
                if self.table.item(row, column) is not None
            ).casefold()
            self.table.setRowHidden(row, query not in row_text)
