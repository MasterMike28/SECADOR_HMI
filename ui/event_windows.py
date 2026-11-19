# -*- coding: utf-8 -*-
"""Ventanas de consulta de alarmas y eventos de proceso."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ui.theme import DIALOG_STYLESHEET
from ui.theme import ERROR, WARNING


class _EventTableDialog(QDialog):
    def __init__(self, title, headers, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(760, 360)
        self.setStyleSheet(
            DIALOG_STYLESHEET
            + """
                QPushButton {
                    background-color: #374151;
                    color: white;
                    border: 1px solid #6B7280;
                    border-radius: 5px;
                    padding: 8px 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #4B5563;
                }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self.lbl_vacio = QLabel("No hay registros para mostrar.")
        self.lbl_vacio.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_vacio)

        self.table = QTableWidget(0, len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.refresh_button = QPushButton("ACTUALIZAR")
        self.refresh_button.clicked.connect(self.refresh)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.refresh_button)
        layout.addLayout(button_layout)

    def set_records(self, records, values_for_record):
        self._displayed_records = list(reversed(records))
        self.table.setRowCount(len(self._displayed_records))
        self.lbl_vacio.setVisible(not self._displayed_records)
        self.table.setVisible(bool(self._displayed_records))

        for row, record in enumerate(self._displayed_records):
            for column, value in enumerate(values_for_record(record)):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, column, item)

    def refresh(self):
        raise NotImplementedError


class AlarmWindow(_EventTableDialog):
    """Lista de alarmas y avisos de la sesión actual."""

    def __init__(self, records_provider, acknowledge_callback, parent=None):
        self._records_provider = records_provider
        self._acknowledge_callback = acknowledge_callback
        super().__init__(
            "Alarmas y avisos",
            ("Hora", "Prioridad", "Estado de proceso", "Mensaje", "Reconocimiento"),
            parent,
        )

        self.acknowledge_button = QPushButton("RECONOCER SELECCIONADAS")
        self.acknowledge_button.clicked.connect(self.acknowledge_selected)
        self.layout().insertWidget(self.layout().count() - 1, self.acknowledge_button)
        self.refresh()

    def refresh(self):
        self.set_records(
            list(self._records_provider()),
            lambda record: (
                record["timestamp"],
                record["severity"],
                record["state"],
                record["message"],
                "Reconocida" if record["acknowledged"] else "Pendiente",
            ),
        )
        for row in range(self.table.rowCount()):
            severity = self.table.item(row, 1).text()
            color = ERROR if severity == "ALTA" else WARNING
            self.table.item(row, 1).setForeground(QColor(color))

    def acknowledge_selected(self):
        rows = sorted({item.row() for item in self.table.selectedItems()})
        for row in rows:
            if row < len(self._displayed_records):
                record = self._displayed_records[row]
                if not record["acknowledged"]:
                    self._acknowledge_callback(record["id"])
        self.refresh()


class HistoryWindow(_EventTableDialog):
    """Cronología de estados y eventos de proceso de la sesión actual."""

    def __init__(self, records_provider, parent=None):
        self._records_provider = records_provider
        super().__init__(
            "Históricos de proceso",
            ("Hora", "Tipo", "Estado", "Detalle"),
            parent,
        )
        self.refresh()

    def refresh(self):
        self.set_records(
            list(self._records_provider()),
            lambda record: (
                record["timestamp"],
                record["type"],
                record["state"],
                record["detail"],
            ),
        )
