# -*- coding: utf-8 -*-
"""Lectura puntual de las entradas GPIO asignadas en la configuración."""

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

import config

try:
    from gpiozero import DigitalInputDevice
    from gpiozero.exc import GPIOZeroError
    _GPIO_IMPORT_ERROR = ""
except ImportError as exc:
    DigitalInputDevice = None
    GPIOZeroError = RuntimeError
    _GPIO_IMPORT_ERROR = str(exc)

_GPIO_INPUTS = (
    ("Parada de emergencia", config.GPIO_ESTOP),
    ("Sensor inductivo", config.GPIO_INDUCTIVO),
    ("Sensor óptico", config.GPIO_OPTICO),
    ("Sensor de puerta", config.GPIO_DOOR_SW),
)


class _GPIOReadWorker(QThread):
    completed = Signal(bool, object, str)

    def run(self):
        if DigitalInputDevice is None:
            self.completed.emit(
                False,
                [],
                f"gpiozero no está disponible: {_GPIO_IMPORT_ERROR}",
            )
            return
        readings = []
        try:
            for name, pin in _GPIO_INPUTS:
                device = None
                try:
                    device = DigitalInputDevice(
                        pin,
                        pull_up=config.GPIO_PULL_UP,
                        active_state=True,
                    )
                    readings.append((name, pin, bool(device.value)))
                finally:
                    if device is not None:
                        device.close()
        except (GPIOZeroError, OSError, ValueError) as exc:
            self.completed.emit(False, readings, str(exc))
            return
        self.completed.emit(True, readings, "")


class GPIODirectTestWindow(QDialog):
    """Muestra niveles lógicos; no configura salidas ni valida la cadena de E-Stop."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Prueba de entradas GPIO directas")
        self.setFixedSize(600, 350)
        self._worker = None
        self.setStyleSheet(
            "QDialog { background-color: #111827; color: #F3F4F6; }"
            "QLabel { color: #F3F4F6; font-size: 12px; }"
            "QTableWidget { background-color: #1F2937; color: #F3F4F6; "
            "gridline-color: #374151; border: 1px solid #4B5563; }"
            "QHeaderView::section { background-color: #374151; color: white; "
            "padding: 6px; border: 1px solid #4B5563; font-weight: bold; }"
            "QPushButton { background-color: #0F766E; color: white; "
            "border: 1px solid #5EEAD4; border-radius: 5px; padding: 8px; "
            "font-weight: bold; }"
            "QPushButton:disabled { background-color: #374151; color: #9CA3AF; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel(
            "Lectura puntual de GPIO BCM 17, 23, 24 y 27. "
            "No se activan salidas."
        )
        title.setWordWrap(True)
        title.setStyleSheet("font-weight: bold; color: #5EEAD4;")
        layout.addWidget(title)

        warning = QLabel(
            "GPIO de Raspberry Pi: nunca aplicar 5 V; usa solo señales "
            "adaptadas a 3,3 V. Se aplica pull-up según la configuración. "
            "La lectura del pin E-Stop no prueba la cadena cableada de seguridad."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #FBBF24; font-weight: bold;")
        layout.addWidget(warning)

        self.table = QTableWidget(len(_GPIO_INPUTS), 3)
        self.table.setHorizontalHeaderLabels(("Señal", "GPIO BCM", "Nivel"))
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 250)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 180)
        self.table.verticalHeader().setDefaultSectionSize(34)
        for row, (name, pin) in enumerate(_GPIO_INPUTS):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(str(pin)))
            self.table.setItem(row, 2, QTableWidgetItem("Sin leer"))
        layout.addWidget(self.table)

        self.result_label = QLabel(
            "Pulsa LEER PINES para tomar una muestra. Para validar sensores "
            "de pulso, mueve el sensor y compara las lecturas."
        )
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet("color: #FBBF24;")
        layout.addWidget(self.result_label)

        buttons = QHBoxLayout()
        self.read_button = QPushButton("LEER PINES")
        self.read_button.clicked.connect(self.start_read)
        self.close_button = QPushButton("CERRAR")
        self.close_button.setStyleSheet(
            "QPushButton { background-color: #374151; border-color: #6B7280; }"
        )
        self.close_button.clicked.connect(self.close)
        buttons.addWidget(self.read_button)
        buttons.addStretch()
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

    def start_read(self):
        if self._worker is not None and self._worker.isRunning():
            return
        self.read_button.setEnabled(False)
        self.result_label.setText("Leyendo niveles GPIO…")
        self.result_label.setStyleSheet("color: #FBBF24;")
        for row in range(self.table.rowCount()):
            self.table.item(row, 2).setText("Leyendo…")
        self._worker = _GPIOReadWorker(self)
        self._worker.completed.connect(self._show_result)
        self._worker.finished.connect(self._worker_finished)
        self._worker.start()

    def _show_result(self, success, readings, error):
        for row, (_, pin) in enumerate(_GPIO_INPUTS):
            value = next(
                (level for _name, input_pin, level in readings if input_pin == pin),
                None,
            )
            if value is None:
                self.table.item(row, 2).setText(
                    "Sin leer" if success else "Error de lectura"
                )
                self.table.item(row, 2).setForeground(Qt.red)
            else:
                self.table.item(row, 2).setText(
                    "ALTO (~3,3 V)" if value else "BAJO (~0 V)"
                )
                self.table.item(row, 2).setForeground(Qt.green)

        if success:
            self.result_label.setText(
                "Lectura terminada. Los niveles cambian al actuar el sensor; "
                "esta muestra no valida el funcionamiento de la máquina."
            )
            self.result_label.setStyleSheet("color: #34D399;")
        else:
            self.result_label.setText(f"No se pudieron leer los GPIO: {error}")
            self.result_label.setStyleSheet("color: #F87171;")

    def _worker_finished(self):
        self._worker = None
        self.read_button.setEnabled(True)

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self.result_label.setText(
                "Espera a que termine la lectura GPIO antes de cerrar."
            )
            event.ignore()
            return
        event.accept()
