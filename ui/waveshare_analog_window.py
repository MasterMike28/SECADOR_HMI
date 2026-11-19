# -*- coding: utf-8 -*-
"""Lectura Modbus RTU de las ocho entradas analógicas Waveshare."""

import serial
from minimalmodbus import MODE_RTU, Instrument, ModbusException
from serial.tools import list_ports
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

import config
from modbus.diagnostic_lock import RS485_DIAGNOSTIC_LOCK
from ui.theme import (
    ACCENT_TEXT,
    DIALOG_STYLESHEET,
    ERROR,
    SUCCESS,
    WARNING,
)


class _WaveshareAnalogReadWorker(QThread):
    completed = Signal(bool, object, str)

    def __init__(self, port, slave_id, parent=None):
        super().__init__(parent)
        self.port = port
        self.slave_id = slave_id

    def run(self):
        instrument = None
        raw_values = None
        error = ""
        parity_by_name = {
            "N": serial.PARITY_NONE,
            "E": serial.PARITY_EVEN,
            "O": serial.PARITY_ODD,
        }
        parity = parity_by_name.get(config.RS485_PARITY)
        if parity is None:
            self.completed.emit(
                False,
                None,
                f"Paridad configurada no reconocida: {config.RS485_PARITY!r}.",
            )
            return

        try:
            with RS485_DIAGNOSTIC_LOCK:
                try:
                    instrument = Instrument(self.port, self.slave_id, mode=MODE_RTU)
                    instrument.serial.baudrate = config.BAUDRATE
                    instrument.serial.bytesize = config.RS485_BYTESIZE
                    instrument.serial.parity = parity
                    instrument.serial.stopbits = config.RS485_STOPBITS
                    instrument.serial.timeout = config.RS485_TIMEOUT
                    instrument.clear_buffers_before_each_transaction = True
                    instrument.close_port_after_each_call = False

                    raw_values = instrument.read_registers(
                        config.WAVESHARE_AI_REGISTER,
                        config.WAVESHARE_AI_CHANNEL_COUNT,
                        functioncode=config.WAVESHARE_AI_READ_FUNCTION_CODE,
                    )
                    if len(raw_values) != config.WAVESHARE_AI_CHANNEL_COUNT:
                        raise OSError(
                            f"Respuesta incompleta: se esperaban "
                            f"{config.WAVESHARE_AI_CHANNEL_COUNT} registros y se "
                            f"recibieron {len(raw_values)}."
                        )
                except (
                    ModbusException,
                    serial.SerialException,
                    OSError,
                    ValueError,
                ) as exc:
                    error = str(exc)
                finally:
                    if instrument is not None:
                        try:
                            instrument.serial.close()
                        except (serial.SerialException, OSError) as exc:
                            error = (
                                f"{error}; " if error else ""
                            ) + f"no se pudo cerrar el puerto serie: {exc}"

        except (serial.SerialException, OSError, ValueError) as exc:
            error = str(exc)

        success = raw_values is not None and not error
        self.completed.emit(success, raw_values, error)


class WaveshareAnalogWindow(QDialog):
    """Interfaz de lectura única; no cambia el rango ni escribe registros."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Waveshare Modbus RTU Analog Input 8CH")
        self.setFixedSize(760, 400)
        self._worker = None
        self.setStyleSheet(DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(7)

        title = QLabel(
            "Lectura de 8 canales por Modbus FC04. En modo corriente los "
            "registros representan µA; se muestran también en mA. Solo lectura."
        )
        title.setWordWrap(True)
        title.setStyleSheet(f"font-weight: bold; color: {ACCENT_TEXT};")
        layout.addWidget(title)

        connection_layout = QHBoxLayout()
        connection_layout.addWidget(QLabel("Puerto:"))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(180)
        connection_layout.addWidget(self.port_combo)
        self.refresh_button = QPushButton("ACTUALIZAR")
        self.refresh_button.clicked.connect(self.refresh_ports)
        connection_layout.addWidget(self.refresh_button)
        connection_layout.addSpacing(12)
        connection_layout.addWidget(QLabel("ID esclavo:"))
        self.slave_id_spin = QSpinBox()
        self.slave_id_spin.setRange(1, 247)
        self.slave_id_spin.setValue(config.WAVESHARE_AI_DEFAULT_SLAVE_ID)
        self.slave_id_spin.setFixedWidth(75)
        connection_layout.addWidget(self.slave_id_spin)
        connection_layout.addStretch()
        layout.addLayout(connection_layout)

        self.settings_label = QLabel(
            f"{config.BAUDRATE} baud, {config.RS485_BYTESIZE}"
            f"{config.RS485_PARITY}{config.RS485_STOPBITS}; registro inicial "
            f"0x{config.WAVESHARE_AI_REGISTER:04X}, "
            f"FC{config.WAVESHARE_AI_READ_FUNCTION_CODE}, "
            f"{config.WAVESHARE_AI_CHANNEL_COUNT} registros consecutivos. "
            "Confirma jumpers en modo corriente y rango 0–20 mA en cada canal; "
            "la ventana no configura el módulo."
        )
        self.settings_label.setWordWrap(True)
        layout.addWidget(self.settings_label)

        self.table = QTableWidget(config.WAVESHARE_AI_CHANNEL_COUNT, 5)
        self.table.setHorizontalHeaderLabels(
            ("Canal", "Registro", "Dato bruto", "Corriente", "Estado")
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 70)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 130)
        self.table.setColumnWidth(3, 140)
        self.table.setColumnWidth(4, 230)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setFixedHeight(222)
        for channel in range(config.WAVESHARE_AI_CHANNEL_COUNT):
            register = config.WAVESHARE_AI_REGISTER + channel
            values = (
                f"AI {channel + 1}",
                f"0x{register:04X}",
                "—",
                "—",
                "Pendiente",
            )
            for column, value in enumerate(values):
                self.table.setItem(channel, column, QTableWidgetItem(value))
        layout.addWidget(self.table)

        self.result_label = QLabel(
            "El ID de ejemplo es 1, que también está asignado al EBYTE y al "
            "VFD del tambor. Prueba un dispositivo a la vez hasta configurar "
            "IDs únicos."
        )
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet(f"color: {WARNING};")
        layout.addWidget(self.result_label)

        buttons = QHBoxLayout()
        self.read_button = QPushButton("LEER 8 CANALES")
        self.read_button.clicked.connect(self.start_read)
        self.close_button = QPushButton("CERRAR")
        self.close_button.setStyleSheet(
            "QPushButton { background-color: #303740; border-color: #414B57; }"
        )
        self.close_button.clicked.connect(self.close)
        buttons.addWidget(self.read_button)
        buttons.addStretch()
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.refresh_ports()

    def refresh_ports(self):
        selected = self.port_combo.currentData()
        available = [port.device for port in list_ports.comports()]
        if config.RS485_PORT not in available:
            available.append(config.RS485_PORT)

        self.port_combo.clear()
        for port_name in available:
            self.port_combo.addItem(port_name, port_name)

        selected_index = self.port_combo.findData(selected or config.RS485_PORT)
        if selected_index >= 0:
            self.port_combo.setCurrentIndex(selected_index)

    def start_read(self):
        if self._worker is not None and self._worker.isRunning():
            return
        port = self.port_combo.currentData()
        if not port:
            self.result_label.setText("No hay un puerto serie seleccionado.")
            self.result_label.setStyleSheet(f"color: {ERROR};")
            return

        self.read_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.port_combo.setEnabled(False)
        self.slave_id_spin.setEnabled(False)
        self.result_label.setText(
            f"Leyendo 8 entradas analógicas por {port}, "
            f"ID {self.slave_id_spin.value()}…"
        )
        self.result_label.setStyleSheet(f"color: {WARNING};")
        for channel in range(config.WAVESHARE_AI_CHANNEL_COUNT):
            self.table.item(channel, 2).setText("—")
            self.table.item(channel, 3).setText("—")
            self.table.item(channel, 4).setText("Consultando…")

        self._worker = _WaveshareAnalogReadWorker(
            port,
            self.slave_id_spin.value(),
            self,
        )
        self._worker.completed.connect(self._show_result)
        self._worker.finished.connect(self._worker_finished)
        self._worker.start()

    def _show_result(self, success, raw_values, error):
        if not success:
            for channel in range(config.WAVESHARE_AI_CHANNEL_COUNT):
                self.table.item(channel, 4).setText("Sin respuesta / error")
                self.table.item(channel, 4).setForeground(QColor(ERROR))
            self.result_label.setText(
                f"No se pudieron leer las entradas: {error or 'respuesta no válida'}"
            )
            self.result_label.setStyleSheet(f"color: {ERROR};")
            return

        in_range_count = 0
        for channel, raw_value in enumerate(raw_values):
            self.table.item(channel, 2).setText(f"{raw_value} µA")
            current_ma = raw_value * config.WAVESHARE_AI_SCALE_MA_PER_REGISTER
            self.table.item(channel, 3).setText(f"{current_ma:.3f} mA")
            in_range = 0 <= raw_value <= 20_000
            if in_range:
                in_range_count += 1
            self.table.item(channel, 4).setText(
                "En rango 0–20 mA" if in_range else "Fuera de rango 0–20 mA"
            )
            self.table.item(channel, 4).setForeground(
                QColor(SUCCESS) if in_range else QColor(ERROR)
            )

        self.result_label.setText(
            f"Waveshare ID {self.slave_id_spin.value()} respondió; "
            f"{in_range_count}/{config.WAVESHARE_AI_CHANNEL_COUNT} canales "
            "dentro de 0–20 mA. La lectura no verifica por sí sola el sensor "
            "ni el rango seleccionado físicamente."
        )
        self.result_label.setStyleSheet(f"color: {SUCCESS};")

    def _worker_finished(self):
        self._worker = None
        self.read_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.port_combo.setEnabled(True)
        self.slave_id_spin.setEnabled(True)

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self.result_label.setText(
                "Espera a que termine la consulta Modbus antes de cerrar."
            )
            event.ignore()
            return
        event.accept()
