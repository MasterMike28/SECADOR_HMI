# -*- coding: utf-8 -*-
"""Diagnóstico manual de variadores Modbus RTU con lecturas únicamente."""

import serial
import time
from minimalmodbus import MODE_RTU, Instrument, ModbusException
from serial.tools import list_ports
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

import config
from modbus.diagnostic_lock import RS485_DIAGNOSTIC_LOCK


_VFD_DEVICES = (
    (config.SLAVE_ID_TAMBOR, "Variador tambor"),
    (config.SLAVE_ID_VENTILADOR, "Variador ventilador"),
)


class _VFDReadWorker(QThread):
    device_result = Signal(int, str, str, str, str, str)
    finished_message = Signal(str)

    def __init__(self, port, parent=None):
        super().__init__(parent)
        self.port = port

    def run(self):
        parity_by_name = {
            "N": serial.PARITY_NONE,
            "E": serial.PARITY_EVEN,
            "O": serial.PARITY_ODD,
        }
        parity = parity_by_name.get(config.RS485_PARITY)
        if parity is None:
            for slave_id, _ in _VFD_DEVICES:
                self.device_result.emit(
                    slave_id,
                    "CONFIG. INVÁLIDA",
                    "—",
                    "—",
                    "—",
                    f"Paridad no reconocida: {config.RS485_PARITY!r}",
                )
            self.finished_message.emit(
                f"Paridad configurada no reconocida: {config.RS485_PARITY!r}."
            )
            return

        for slave_id, _ in _VFD_DEVICES:
            instrument = None
            values = {}
            errors = []
            try:
                with RS485_DIAGNOSTIC_LOCK:
                    instrument = Instrument(self.port, slave_id, mode=MODE_RTU)
                    instrument.serial.baudrate = config.BAUDRATE
                    instrument.serial.bytesize = config.RS485_BYTESIZE
                    instrument.serial.parity = parity
                    instrument.serial.stopbits = config.RS485_STOPBITS
                    instrument.serial.timeout = config.RS485_TIMEOUT
                    instrument.clear_buffers_before_each_transaction = True
                    instrument.close_port_after_each_call = False

                    for key, register in (
                        ("frequency_raw", config.REG_GK610_FREQ_OUT),
                        ("current_raw", config.REG_GK610_CURRENT),
                        ("dc_bus_raw", config.REG_GK610_DC_BUS),
                    ):
                        try:
                            values[key] = instrument.read_register(
                                register,
                                number_of_decimals=0,
                                functioncode=3,
                                signed=False,
                            )
                        except (ModbusException, serial.SerialException, OSError, ValueError) as exc:
                            errors.append(f"0x{register:04X}: {exc}")
                        time.sleep(config.RS485_INTER_FRAME_DELAY)
            except (ModbusException, serial.SerialException, OSError, ValueError) as exc:
                errors.append(str(exc))
            finally:
                if instrument is not None:
                    try:
                        with RS485_DIAGNOSTIC_LOCK:
                            instrument.serial.close()
                    except (serial.SerialException, OSError):
                        errors.append("No se pudo cerrar el puerto serie limpiamente.")

            if values:
                frequency = self._format_scaled(
                    values.get("frequency_raw"),
                    config.VFD_OUTPUT_FREQUENCY_SCALE_HZ,
                    " Hz",
                )
                current = self._format_scaled(
                    values.get("current_raw"),
                    config.VFD_CURRENT_SCALE_A,
                    " A",
                )
                dc_bus = self._format_scaled(
                    values.get("dc_bus_raw"),
                    1,
                    " V",
                )
                status = "RESPONDE" if not errors else "RESPUESTA PARCIAL"
            else:
                frequency = current = dc_bus = "—"
                status = "SIN RESPUESTA"

            self.device_result.emit(
                slave_id,
                status,
                frequency,
                current,
                dc_bus,
                "; ".join(errors),
            )

        self.finished_message.emit(
            "Consulta terminada. Solo se leyeron registros de telemetría; "
            "no se enviaron comandos ni escrituras."
        )

    @staticmethod
    def _format_scaled(raw_value, scale, unit):
        if raw_value is None:
            return "—"
        return f"{raw_value * scale:.2f}{unit}"


class RS485TestWindow(QDialog):
    """Interfaz para consultar IDs VFD conocidos sin transmitir escrituras."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Prueba RS485 / Modbus - solo lectura")
        self.setFixedSize(760, 340)
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
            "QComboBox { background-color: #1F2937; color: white; padding: 6px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel(
            "Lectura puntual de esclavos conocidos. No escanea otras direcciones "
            "ni escribe registros."
        )
        title.setWordWrap(True)
        title.setStyleSheet("font-weight: bold; color: #5EEAD4;")
        layout.addWidget(title)

        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Puerto RS485:"))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(210)
        port_layout.addWidget(self.port_combo)
        self.refresh_button = QPushButton("ACTUALIZAR PUERTOS")
        self.refresh_button.clicked.connect(self.refresh_ports)
        port_layout.addWidget(self.refresh_button)
        port_layout.addStretch()
        layout.addLayout(port_layout)

        self.settings_label = QLabel(
            f"{config.BAUDRATE} baud, {config.RS485_BYTESIZE} bits, "
            f"paridad {config.RS485_PARITY}, {config.RS485_STOPBITS} stop bit(s), "
            f"timeout {config.RS485_TIMEOUT:.2f} s. Confirma estos parámetros "
            "con el manual/configuración de los variadores."
        )
        self.settings_label.setWordWrap(True)
        layout.addWidget(self.settings_label)

        self.table = QTableWidget(len(_VFD_DEVICES), 7)
        self.table.setHorizontalHeaderLabels(
            ("ID", "Equipo", "Resultado", "Frecuencia", "Corriente", "Bus DC", "Detalle")
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 90)
        self.table.setColumnWidth(4, 80)
        self.table.setColumnWidth(5, 80)
        for row, (slave_id, name) in enumerate(_VFD_DEVICES):
            for column, value in enumerate(
                (str(slave_id), name, "Pendiente", "—", "—", "—", "")
            ):
                self.table.setItem(row, column, QTableWidgetItem(value))
        layout.addWidget(self.table)

        self.result_label = QLabel(
            "Se consultarán 0x7000 (frecuencia), 0x7004 (corriente) y "
            "0x7002 (bus DC), en los IDs 1 y 2."
        )
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet("color: #FBBF24;")
        layout.addWidget(self.result_label)

        buttons = QHBoxLayout()
        self.read_button = QPushButton("PROBAR LECTURA")
        self.read_button.clicked.connect(self.start_read_test)
        self.close_button = QPushButton("CERRAR")
        self.close_button.setStyleSheet(
            "QPushButton { background-color: #374151; border-color: #6B7280; }"
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

    def start_read_test(self):
        if self._worker is not None and self._worker.isRunning():
            return
        port = self.port_combo.currentData()
        if not port:
            self.result_label.setText("No hay un puerto serie seleccionado.")
            self.result_label.setStyleSheet("color: #F87171;")
            return

        for row in range(self.table.rowCount()):
            for column in range(2, self.table.columnCount()):
                self.table.item(row, column).setText(
                    "Consultando…" if column == 2 else "—"
                )

        self.read_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.port_combo.setEnabled(False)
        self.result_label.setText(f"Leyendo telemetría en {port}…")
        self.result_label.setStyleSheet("color: #FBBF24;")

        self._worker = _VFDReadWorker(port, self)
        self._worker.device_result.connect(self._show_device_result)
        self._worker.finished_message.connect(self._show_finished_message)
        self._worker.finished.connect(self._worker_finished)
        self._worker.start()

    def _show_device_result(self, slave_id, status, frequency, current, dc_bus, detail):
        row = next(
            index
            for index in range(self.table.rowCount())
            if self.table.item(index, 0).text() == str(slave_id)
        )
        for column, value in enumerate(
            (status, frequency, current, dc_bus, detail),
            start=2,
        ):
            self.table.item(row, column).setText(value)
        self.table.item(row, 2).setForeground(
            Qt.green if status == "RESPONDE" else Qt.yellow
            if status == "RESPUESTA PARCIAL" else Qt.red
        )

    def _show_finished_message(self, message):
        self.result_label.setText(message)
        self.result_label.setStyleSheet("color: #34D399;")

    def _worker_finished(self):
        self._worker = None
        self.read_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.port_combo.setEnabled(True)

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self.result_label.setText(
                "Espera a que termine la consulta Modbus antes de cerrar."
            )
            event.ignore()
            return
        event.accept()
