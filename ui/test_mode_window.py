# -*- coding: utf-8 -*-
"""Puesta en marcha gradual del PCF8575 con controles manuales protegidos."""

import threading
import time

from smbus2 import SMBus, i2c_msg
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

import config
from ui.rs485_test_window import RS485TestWindow

_I2C_LOCK = threading.Lock()
_RELAY_INPUT_COUNT = 8
_MAX_HOLD_DURATION_S = 5.0


def _write_pcf8575_word(bus, value):
    message = i2c_msg.write(
        config.PCF8575_ADDR,
        (value & 0xFF, (value >> 8) & 0xFF),
    )
    bus.i2c_rdwr(message)


class _PCF8575ReadWorker(QThread):
    completed = Signal(bool, str)

    def run(self):
        try:
            request = i2c_msg.read(config.PCF8575_ADDR, 2)
            with _I2C_LOCK, SMBus(config.I2C_BUS) as bus:
                bus.i2c_rdwr(request)
            data = list(request)
            if len(data) != 2:
                raise OSError(f"Lectura incompleta del expansor: {len(data)} bytes.")
            self.completed.emit(
                True,
                f"Bus {config.I2C_BUS}, dirección 0x{config.PCF8575_ADDR:02X}: "
                f"{data[0]:02X} {data[1]:02X}",
            )
        except (OSError, ValueError) as exc:
            self.completed.emit(False, f"Lectura I2C fallida: {exc}")


class _PCF8575HoldWorker(QThread):
    activated = Signal(int)
    completed = Signal(int, bool, bool, str)

    def __init__(self, channel, parent=None):
        super().__init__(parent)
        self.channel = channel
        self._release_requested = threading.Event()

    def request_release(self):
        self._release_requested.set()

    def run(self):
        activation_error = None
        safe_state_error = None
        timed_out = False
        try:
            with _I2C_LOCK, SMBus(config.I2C_BUS) as bus:
                try:
                    _write_pcf8575_word(bus, config.PCF8575_SAFE_STATE)
                    if not self._release_requested.is_set():
                        active_state = (
                            config.PCF8575_SAFE_STATE | (1 << self.channel)
                        )
                        _write_pcf8575_word(bus, active_state)
                        self.activated.emit(self.channel)
                        timed_out = not self._release_requested.wait(
                            _MAX_HOLD_DURATION_S
                        )
                except (OSError, ValueError) as exc:
                    activation_error = exc
                finally:
                    try:
                        _write_pcf8575_word(bus, config.PCF8575_SAFE_STATE)
                    except (OSError, ValueError) as exc:
                        safe_state_error = exc
        except (OSError, ValueError) as exc:
            activation_error = exc

        errors = []
        if activation_error is not None:
            errors.append(f"falló la comunicación I2C: {activation_error}")
        if safe_state_error is not None:
            errors.append(f"no se pudo confirmar el estado seguro: {safe_state_error}")

        success = not errors
        if errors:
            message = (
                f"X{self.channel + 1}: {'; '.join(errors)}. Estado eléctrico "
                "desconocido; no continúes probando y verifica el módulo."
            )
        elif timed_out:
            message = (
                f"X{self.channel + 1} se apagó automáticamente tras "
                f"{_MAX_HOLD_DURATION_S:.0f} s. Se solicitó nivel bajo al ULN."
            )
        elif self._release_requested.is_set():
            message = f"X{self.channel + 1} liberada. Se solicitó nivel bajo al ULN."
        else:
            message = f"X{self.channel + 1} no llegó a activarse. Se solicitó nivel bajo al ULN."

        self.completed.emit(self.channel, success, timed_out, message)


class TestModeWindow(QDialog):
    """Permite leer el PCF8575 y accionar una entrada mientras se mantiene pulsada."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modo de pruebas - Puesta en marcha")
        self.setFixedSize(760, 440)
        self._i2c_worker = None
        self._pulse_worker = None
        self._rs485_test_window = None
        self._active_channel = None
        self._output_state_unknown = False
        self._channel_buttons = []
        self.setStyleSheet(
            "QDialog { background-color: #111827; color: #F3F4F6; }"
            "QLabel { color: #F3F4F6; font-size: 11px; }"
            "QTableWidget { background-color: #1F2937; color: #F3F4F6; "
            "gridline-color: #374151; border: 1px solid #4B5563; }"
            "QHeaderView::section { background-color: #374151; color: white; "
            "padding: 6px; border: 1px solid #4B5563; font-weight: bold; }"
            "QPushButton { background-color: #0F766E; color: white; "
            "border: 1px solid #5EEAD4; border-radius: 5px; padding: 5px; "
            "font-weight: bold; font-size: 10px; }"
            "QPushButton:disabled { background-color: #374151; color: #9CA3AF; }"
            "QCheckBox { color: #FBBF24; font-size: 11px; font-weight: bold; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)

        title = QLabel(
            "PRUEBA MANUAL — mantén pulsado para activar; suelta para apagar. "
            "ULN activo con nivel alto."
        )
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #5EEAD4;")
        layout.addWidget(title)

        caution = QLabel(
            "Antes de pulsar: alimentación de las cargas en K1–K8 aislada y "
            "verificada sin tensión. El relé interno sí conmutará. "
            "Los nombres de las funciones son provisionales."
        )
        caution.setWordWrap(True)
        caution.setStyleSheet("color: #F87171; font-weight: bold;")
        layout.addWidget(caution)

        self.contact_loads_isolated = QCheckBox(
            "Confirmo que todas las cargas conectadas a K1–K8 están aisladas "
            "y sin tensión."
        )
        self.contact_loads_isolated.toggled.connect(
            self._update_pulse_buttons_enabled
        )
        layout.addWidget(self.contact_loads_isolated)

        self.table = QTableWidget(_RELAY_INPUT_COUNT, 6)
        self.table.setHorizontalHeaderLabels(
            ("PCF", "Entrada", "Relé", "Uso previsto*", "Estado", "Prueba")
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 62)
        self.table.setColumnWidth(2, 55)
        self.table.setColumnWidth(3, 245)
        self.table.setColumnWidth(4, 80)
        self.table.setColumnWidth(5, 135)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setFixedHeight(222)
        for channel in range(_RELAY_INPUT_COUNT):
            relay_name = config.RELAY_CHANNELS.get(channel, "Sin asignar")
            for column, value in enumerate(
                (
                    f"P{channel}",
                    f"X{channel + 1}",
                    f"K{channel + 1}",
                    relay_name,
                    "Pendiente",
                )
            ):
                self.table.setItem(channel, column, QTableWidgetItem(value))
            button = QPushButton("MANTENER")
            button.setEnabled(False)
            button.pressed.connect(
                lambda output=channel: self.activate_output(output)
            )
            button.released.connect(
                lambda output=channel: self.release_output(output)
            )
            self._channel_buttons.append(button)
            self.table.setCellWidget(channel, 5, button)
        layout.addWidget(self.table)

        self.result_label = QLabel(
            "Las señales P0–P7 se prueban como X1–X8. "
            "La entrada del ULN es activa-alta: nivel bajo en reposo y nivel alto "
            "al activar. Mantén aisladas las cargas de los contactos."
        )
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet("color: #FBBF24;")
        layout.addWidget(self.result_label)

        buttons = QHBoxLayout()
        self.read_i2c_button = QPushButton("LEER I2C (NO ESCRIBE)")
        self.read_i2c_button.clicked.connect(self.test_pcf8575_read_only)
        self.read_i2c_button.setMaximumWidth(185)
        self.read_rs485_button = QPushButton("PROBAR RS485 (LECTURA)")
        self.read_rs485_button.clicked.connect(self.open_rs485_test)
        self.read_rs485_button.setMaximumWidth(205)
        self.close_button = QPushButton("CERRAR")
        self.close_button.setStyleSheet(
            "QPushButton { background-color: #374151; border-color: #6B7280; }"
        )
        self.close_button.clicked.connect(self.close)
        buttons.addWidget(self.read_i2c_button)
        buttons.addWidget(self.read_rs485_button)
        buttons.addStretch()
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

    def _update_pulse_buttons_enabled(self, isolated):
        can_pulse = (
            isolated
            and self._pulse_worker is None
            and self._i2c_worker is None
            and not self._output_state_unknown
        )
        for channel, button in enumerate(self._channel_buttons):
            button.setEnabled(
                can_pulse
                and (self._active_channel is None or channel == self._active_channel)
            )

    def test_pcf8575_read_only(self):
        if self._i2c_worker is not None and self._i2c_worker.isRunning():
            return
        if self._pulse_worker is not None:
            return
        self.read_i2c_button.setEnabled(False)
        self.result_label.setText("Leyendo dos bytes del expansor; no se escribe ningún dato…")
        self._i2c_worker = _PCF8575ReadWorker(self)
        self._i2c_worker.completed.connect(self._show_i2c_result)
        self._i2c_worker.finished.connect(self._i2c_finished)
        self._i2c_worker.start()

    def open_rs485_test(self):
        if self._rs485_test_window is None:
            self._rs485_test_window = RS485TestWindow(self)
        self._rs485_test_window.show()
        self._rs485_test_window.raise_()
        self._rs485_test_window.activateWindow()

    def activate_output(self, channel):
        if not 0 <= channel < _RELAY_INPUT_COUNT:
            raise ValueError(f"Canal de prueba fuera de rango: {channel}")
        if not self.contact_loads_isolated.isChecked():
            return
        if self._i2c_worker is not None or self._pulse_worker is not None:
            return

        parent_window = self.parent()
        process_worker = getattr(parent_window, "worker", None)
        if process_worker is not None and process_worker.isRunning():
            self.result_label.setText(
                "Prueba bloqueada: detén primero el proceso en la HMI."
            )
            self.result_label.setStyleSheet("color: #F87171;")
            return

        for button in self._channel_buttons:
            button.setEnabled(False)
        self._channel_buttons[channel].setEnabled(True)
        self.read_i2c_button.setEnabled(False)
        self.contact_loads_isolated.setEnabled(False)
        self._active_channel = channel
        self._channel_buttons[channel].setText("SUELTA PARA APAGAR")
        self.table.item(channel, 4).setText("Conectando…")
        self.result_label.setText(
            f"Preparando P{channel}/X{channel + 1}/K{channel + 1}; "
            f"mantén pulsado. Corte automático a los {_MAX_HOLD_DURATION_S:.0f} s."
        )
        self.result_label.setStyleSheet("color: #FBBF24;")
        self._pulse_worker = _PCF8575HoldWorker(channel, self)
        self._pulse_worker.activated.connect(self._show_output_active)
        self._pulse_worker.completed.connect(self._show_pulse_result)
        self._pulse_worker.finished.connect(self._pulse_finished)
        self._pulse_worker.start()

    def release_output(self, channel):
        if self._pulse_worker is None or self._active_channel != channel:
            return
        self._channel_buttons[channel].setText("SOLTANDO…")
        self._channel_buttons[channel].setEnabled(False)
        self.table.item(channel, 4).setText("Apagando…")
        self._pulse_worker.request_release()

    def _show_output_active(self, channel):
        self.table.item(channel, 4).setText("ACTIVA")
        self.table.item(channel, 4).setForeground(Qt.green)
        self.result_label.setText(
            f"P{channel} alto; ULN X{channel + 1}/K{channel + 1} activado. "
            "Suelta el botón para apagar."
        )
        self.result_label.setStyleSheet("color: #34D399; font-weight: bold;")

    def _show_i2c_result(self, success, message):
        if success:
            message = (
                f"{message}. Esto confirma comunicación I2C solamente; "
                "no confirma la respuesta eléctrica del ULN ni del relé."
            )
        self.result_label.setText(message)
        self.result_label.setStyleSheet(
            "color: #FBBF24;" if success else "color: #F87171;"
        )

    def _show_pulse_result(self, channel, success, timed_out, message):
        status = "Auto-apagada" if timed_out else ("Apagada" if success else "DESCONOCIDO")
        self.table.item(channel, 4).setText(status)
        self.table.item(channel, 4).setForeground(
            Qt.green if success else Qt.red
        )
        if not success:
            self._output_state_unknown = True
        self.result_label.setText(message)
        self.result_label.setStyleSheet(
            "color: #34D399;" if success else "color: #F87171;"
        )

    def _i2c_finished(self):
        self.read_i2c_button.setEnabled(True)
        self._i2c_worker = None
        self._update_pulse_buttons_enabled(
            self.contact_loads_isolated.isChecked()
        )

    def _pulse_finished(self):
        self._pulse_worker = None
        self._active_channel = None
        for button in self._channel_buttons:
            button.setText("MANTENER")
        self.read_i2c_button.setEnabled(True)
        self.contact_loads_isolated.setEnabled(True)
        self._update_pulse_buttons_enabled(
            self.contact_loads_isolated.isChecked()
        )

    def closeEvent(self, event):
        workers = [
            self._i2c_worker,
            self._pulse_worker,
            (
                self._rs485_test_window._worker
                if self._rs485_test_window is not None
                else None
            ),
        ]
        if any(worker is not None and worker.isRunning() for worker in workers):
            if self._pulse_worker is not None:
                self._pulse_worker.request_release()
            self.result_label.setText(
                "Espera a que terminen las pruebas I2C/RS485 antes de cerrar."
            )
            event.ignore()
            return
        event.accept()
