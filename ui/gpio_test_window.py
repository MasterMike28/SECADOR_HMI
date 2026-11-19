# -*- coding: utf-8 -*-
"""Prueba continua de dos entradas inductivas y un encoder incremental."""

import threading
from contextlib import ExitStack

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QColor
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
from ui.theme import (
    ACCENT_TEXT,
    DIALOG_STYLESHEET,
    ERROR,
    SUCCESS,
    WARNING,
)

try:
    from gpiozero import DigitalInputDevice, RotaryEncoder
    from gpiozero.exc import GPIOZeroError

    _GPIO_IMPORT_ERROR = ""
except ImportError as exc:
    DigitalInputDevice = None
    RotaryEncoder = None
    GPIOZeroError = RuntimeError
    _GPIO_IMPORT_ERROR = str(exc)

_INDUCTIVE_INPUTS = (
    ("Sensor inductivo 1", config.GPIO_INDUCTIVO),
    ("Sensor inductivo 2", config.GPIO_INDUCTIVO_2),
)
_GPIO_ROWS = (
    ("Sensor inductivo 1", str(config.GPIO_INDUCTIVO)),
    ("Sensor inductivo 2", str(config.GPIO_INDUCTIVO_2)),
    (
        "Encoder incremental A/B",
        f"A={config.GPIO_ENCODER_A} / B={config.GPIO_ENCODER_B}",
    ),
)


class _GPIOReadWorker(QThread):
    readings_updated = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop_requested = threading.Event()

    def request_stop(self):
        self._stop_requested.set()

    def run(self):
        if DigitalInputDevice is None or RotaryEncoder is None:
            self.error_occurred.emit(
                f"gpiozero no está disponible: {_GPIO_IMPORT_ERROR}"
            )
            return

        try:
            with ExitStack() as devices:
                inductive_sensors = []
                for name, pin in _INDUCTIVE_INPUTS:
                    sensor = DigitalInputDevice(
                        pin,
                        pull_up=config.GPIO_PULL_UP,
                        active_state=True,
                    )
                    devices.callback(sensor.close)
                    inductive_sensors.append((name, pin, sensor))

                encoder = RotaryEncoder(
                    config.GPIO_ENCODER_A,
                    config.GPIO_ENCODER_B,
                    max_steps=0,
                    bounce_time=None,
                )
                devices.callback(encoder.close)
                previous_steps = encoder.steps
                direction = "Sin movimiento"

                while not self._stop_requested.is_set():
                    steps = encoder.steps
                    if steps > previous_steps:
                        direction = "Horario"
                    elif steps < previous_steps:
                        direction = "Antihorario"
                    previous_steps = steps

                    self.readings_updated.emit(
                        {
                            "inductive_levels": tuple(
                                (pin, bool(sensor.value))
                                for _name, pin, sensor in inductive_sensors
                            ),
                            "encoder_a": bool(encoder.a.pin.state),
                            "encoder_b": bool(encoder.b.pin.state),
                            "encoder_steps": steps,
                            "encoder_direction": direction,
                        }
                    )
                    self._stop_requested.wait(0.1)
        except (GPIOZeroError, OSError, ValueError) as exc:
            self.error_occurred.emit(str(exc))


class GPIODirectTestWindow(QDialog):
    """Muestra niveles de inductivos y pasos/dirección del encoder."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Prueba de entradas GPIO directas")
        self.setFixedSize(600, 370)
        self._worker = None
        self._worker_failed = False
        self.setStyleSheet(DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel(
            f"Entradas BCM {config.GPIO_INDUCTIVO} y "
            f"{config.GPIO_INDUCTIVO_2} para inductivos; BCM "
            f"{config.GPIO_ENCODER_A} y {config.GPIO_ENCODER_B} para encoder A/B."
        )
        title.setWordWrap(True)
        title.setStyleSheet(f"font-weight: bold; color: {ACCENT_TEXT};")
        layout.addWidget(title)

        warning = QLabel(
            "Usa señales adaptadas a 3,3 V; nunca conectes 5 V ni la salida "
            "industrial del sensor directamente. La lectura no valida "
            "interlocks ni sustituye la cadena cableada de seguridad."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet(f"color: {WARNING}; font-weight: bold;")
        layout.addWidget(warning)

        self.table = QTableWidget(len(_GPIO_ROWS), 3)
        self.table.setHorizontalHeaderLabels(("Señal", "GPIO BCM", "Nivel"))
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 245)
        self.table.setColumnWidth(1, 125)
        self.table.setColumnWidth(2, 190)
        self.table.verticalHeader().setDefaultSectionSize(34)
        for row, (name, pins) in enumerate(_GPIO_ROWS):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(pins))
            self.table.setItem(row, 2, QTableWidgetItem("Sin leer"))
        layout.addWidget(self.table)

        self.result_label = QLabel(
            "Inicia la lectura y gira el encoder para verificar sentido y pasos "
            "decodificados (un ciclo A/B completo por paso)."
        )
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet(f"color: {WARNING};")
        layout.addWidget(self.result_label)

        buttons = QHBoxLayout()
        self.read_button = QPushButton("INICIAR LECTURA")
        self.read_button.clicked.connect(self.start_read)
        self.stop_button = QPushButton("DETENER")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_read)
        self.close_button = QPushButton("CERRAR")
        self.close_button.setStyleSheet(
            "QPushButton { background-color: #303740; border-color: #414B57; }"
        )
        self.close_button.clicked.connect(self.close)
        buttons.addWidget(self.read_button)
        buttons.addWidget(self.stop_button)
        buttons.addStretch()
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

    def start_read(self):
        if self._worker is not None and self._worker.isRunning():
            return
        self._worker_failed = False
        self.read_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.result_label.setText("Iniciando lectura continua de GPIO…")
        self.result_label.setStyleSheet(f"color: {WARNING};")
        for row in range(self.table.rowCount()):
            self.table.item(row, 2).setText("Leyendo…")
            self.table.item(row, 2).setForeground(QColor(WARNING))

        self._worker = _GPIOReadWorker(self)
        self._worker.readings_updated.connect(self._show_readings)
        self._worker.error_occurred.connect(self._show_error)
        self._worker.finished.connect(self._worker_finished)
        self._worker.start()

    def stop_read(self):
        if self._worker is not None and self._worker.isRunning():
            self.stop_button.setEnabled(False)
            self.result_label.setText("Deteniendo lectura…")
            self._worker.request_stop()

    def _show_readings(self, readings):
        levels = dict(readings["inductive_levels"])
        for row, (_name, pin) in enumerate(_INDUCTIVE_INPUTS):
            level = levels.get(pin)
            self._set_level(row, level)

        self.table.item(2, 2).setText(
            f"A {'ALTO' if readings['encoder_a'] else 'BAJO'} / "
            f"B {'ALTO' if readings['encoder_b'] else 'BAJO'}"
        )
        self.table.item(2, 2).setForeground(QColor(SUCCESS))
        self.result_label.setText(
            f"Encoder: {readings['encoder_steps']:+d} pasos; "
            f"último sentido: {readings['encoder_direction']}. "
            "Cada paso es un ciclo A/B completo; el sentido depende del orden "
            "de conexión A/B."
        )
        self.result_label.setStyleSheet(f"color: {SUCCESS};")

    def _set_level(self, row, value):
        if value is None:
            self.table.item(row, 2).setText("Sin leer")
            self.table.item(row, 2).setForeground(QColor(ERROR))
            return
        self.table.item(row, 2).setText("ALTO (~3,3 V)" if value else "BAJO (~0 V)")
        self.table.item(row, 2).setForeground(QColor(SUCCESS))

    def _show_error(self, error):
        self._worker_failed = True
        self.result_label.setText(f"No se pudieron leer los GPIO: {error}")
        self.result_label.setStyleSheet(f"color: {ERROR};")
        for row in range(self.table.rowCount()):
            self.table.item(row, 2).setText("Error de lectura")
            self.table.item(row, 2).setForeground(QColor(ERROR))

    def _worker_finished(self):
        self._worker = None
        self.read_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        if not self._worker_failed:
            self.result_label.setText("Lectura detenida.")
            self.result_label.setStyleSheet(f"color: {WARNING};")

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self.result_label.setText(
                "Detén la lectura GPIO antes de cerrar esta ventana."
            )
            self._worker.request_stop()
            event.ignore()
            return
        event.accept()
