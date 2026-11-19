# -*- coding: utf-8 -*-
"""Lectura Modbus RTU de las ocho entradas PT100 del EBYTE ME31-XDXX0800-485."""

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


class _EbytePT100ReadWorker(QThread):
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
                        config.EBYTE_PT100_TEMP_REGISTER,
                        config.EBYTE_PT100_CHANNEL_COUNT,
                        functioncode=config.EBYTE_PT100_READ_FUNCTION_CODE,
                    )
                    if len(raw_values) != config.EBYTE_PT100_CHANNEL_COUNT:
                        raise OSError(
                            f"Respuesta incompleta: se esperaban "
                            f"{config.EBYTE_PT100_CHANNEL_COUNT} registros y se "
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


class EbytePT100Window(QDialog):
    """Interfaz de lectura única bajo demanda; no escribe registros Modbus."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("EBYTE ME31-XDXX0800-485 - PT100")
        self.setFixedSize(760, 400)
        self._worker = None
        self.setStyleSheet(DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(7)

        title = QLabel(
            "Lectura de los 8 canales PT100. Solo función Modbus 04; "
            "no se escriben parámetros ni salidas."
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
        self.slave_id_spin.setValue(config.EBYTE_PT100_DEFAULT_SLAVE_ID)
        self.slave_id_spin.setFixedWidth(75)
        connection_layout.addWidget(self.slave_id_spin)
        connection_layout.addStretch()
        layout.addLayout(connection_layout)

        self.settings_label = QLabel(
            f"Parámetros de fábrica: {config.BAUDRATE} baud, "
            f"{config.RS485_BYTESIZE}{config.RS485_PARITY}"
            f"{config.RS485_STOPBITS}; registro inicial "
            f"0x{config.EBYTE_PT100_TEMP_REGISTER:04X}, "
            f"FC{config.EBYTE_PT100_READ_FUNCTION_CODE}, "
            f"{config.EBYTE_PT100_CHANNEL_COUNT} registros, "
            f"{config.EBYTE_PT100_SCALE_C_PER_COUNT:g} °C/cuenta. "
            "ID de fábrica 1; debe ser único en el bus."
        )
        self.settings_label.setWordWrap(True)
        layout.addWidget(self.settings_label)

        self.table = QTableWidget(config.EBYTE_PT100_CHANNEL_COUNT, 5)
        self.table.setHorizontalHeaderLabels(
            ("Canal", "Registro", "Dato bruto", "Temperatura", "Estado")
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 70)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 150)
        self.table.setColumnWidth(4, 230)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setFixedHeight(222)
        for channel in range(config.EBYTE_PT100_CHANNEL_COUNT):
            register = config.EBYTE_PT100_TEMP_REGISTER + channel
            values = (
                f"PT100 {channel + 1}",
                f"0x{register:04X}",
                "—",
                "—",
                "Pendiente",
            )
            for column, value in enumerate(values):
                self.table.setItem(channel, column, QTableWidgetItem(value))
        layout.addWidget(self.table)

        self.result_label = QLabel(
            "Conecta solo el EBYTE a este bus durante la primera prueba: "
            "su ID de fábrica 1 coincide con el ID previsto para el VFD del tambor."
        )
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet(f"color: {WARNING};")
        layout.addWidget(self.result_label)

        buttons = QHBoxLayout()
        self.read_button = QPushButton("LEER PT100")
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
            f"Leyendo 8 canales PT100 por {port}, ID {self.slave_id_spin.value()}…"
        )
        self.result_label.setStyleSheet(f"color: {WARNING};")
        for channel in range(config.EBYTE_PT100_CHANNEL_COUNT):
            self.table.item(channel, 2).setText("—")
            self.table.item(channel, 3).setText("—")
            self.table.item(channel, 4).setText("Consultando…")

        self._worker = _EbytePT100ReadWorker(
            port,
            self.slave_id_spin.value(),
            self,
        )
        self._worker.completed.connect(self._show_result)
        self._worker.finished.connect(self._worker_finished)
        self._worker.start()

    def _show_result(self, success, raw_values, error):
        if not success:
            for channel in range(config.EBYTE_PT100_CHANNEL_COUNT):
                self.table.item(channel, 4).setText("Sin respuesta / error")
                self.table.item(channel, 4).setForeground(QColor(ERROR))
            self.result_label.setText(
                f"No se pudieron leer las PT100: {error or 'respuesta no válida'}"
            )
            self.result_label.setStyleSheet(f"color: {ERROR};")
            return

        disconnected_count = 0
        for channel, raw_value in enumerate(raw_values):
            raw_value &= 0xFFFF
            self.table.item(channel, 2).setText(f"0x{raw_value:04X}")
            if raw_value == config.EBYTE_PT100_SENSOR_FAULT_RAW:
                disconnected_count += 1
                self.table.item(channel, 3).setText("—")
                self.table.item(channel, 4).setText("PT100 desconectada")
                self.table.item(channel, 4).setForeground(QColor(WARNING))
                continue

            signed_value = (
                raw_value - 0x10000 if raw_value & 0x8000 else raw_value
            )
            temperature = (
                signed_value * config.EBYTE_PT100_SCALE_C_PER_COUNT
            )
            self.table.item(channel, 3).setText(f"{temperature:.1f} °C")
            in_range = -200.0 <= temperature <= 850.0
            self.table.item(channel, 4).setText(
                "OK" if in_range else "Dato fuera de rango"
            )
            self.table.item(channel, 4).setForeground(
                QColor(SUCCESS) if in_range else QColor(ERROR)
            )

        summary = (
            f"EBYTE ID {self.slave_id_spin.value()} respondió. "
            f"{config.EBYTE_PT100_CHANNEL_COUNT - disconnected_count}/"
            f"{config.EBYTE_PT100_CHANNEL_COUNT} canales tienen sensor conectado."
        )
        if error:
            summary += f" Advertencia: {error}"
        self.result_label.setText(summary)
        self.result_label.setStyleSheet(
            f"color: {SUCCESS};" if not error else f"color: {WARNING};"
        )

    def _worker_finished(self):
        self._worker = None
        self.read_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.port_combo.setEnabled(True)
        self.slave_id_spin.setEnabled(True)

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self.result_label.setText(
                "Espera a que termine la lectura Modbus antes de cerrar."
            )
            event.ignore()
            return
        event.accept()
