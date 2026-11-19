# -*- coding: utf-8 -*-
"""Puesta en marcha gradual del PCF8575 con controles manuales protegidos."""

import threading
import time
from urllib.parse import quote

from smbus2 import SMBus, i2c_msg
from PySide6.QtCore import QSettings, QThread, Signal, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import config
from instrumentation import INSTRUMENTATION, OPTIONAL_INSTRUMENTATION
from ui.ebyte_pt100_window import EbytePT100Window
from ui.gpio_test_window import GPIODirectTestWindow
from ui.rs485_test_window import RS485TestWindow
from ui.theme import (
    ACCENT_TEXT,
    DIALOG_STYLESHEET,
    ERROR,
    SUCCESS,
    WARNING,
)
from ui.waveshare_analog_window import WaveshareAnalogWindow

_I2C_LOCK = threading.Lock()
_RELAY_INPUT_COUNT = 8
_MAX_HOLD_DURATION_S = 5.0
_TEST_RESULTS = ("Pendiente", "Correcto", "Falla", "Por definir", "No aplica")


def _build_test_inventory():
    inventory = [
        (
            "PCF8575 / I2C",
            f"Leer el expansor en bus {config.I2C_BUS}, "
            f"dirección 0x{config.PCF8575_ADDR:02X}; sin escribir.",
            "Pendiente",
        ),
        (
            "Adaptador y bus RS485",
            "Verificar puerto, alimentación, polaridad A/B y respuesta de un "
            "esclavo a la vez.",
            "Pendiente",
        ),
        (
            "EBYTE ME31-XDXX0800-485",
            "Leer los ocho registros PT100 por FC04; revisar sensores "
            "desconectados y temperatura.",
            "Pendiente",
        ),
        (
            "Waveshare Analog Input 8CH (SKU 25821)",
            "Leer ocho entradas por FC04 en modo corriente 0–20 mA; "
            "comprobar la conversión µA a mA.",
            "Pendiente",
        ),
        (
            "VFD tambor / GK610 (ID 1)",
            "Consultar frecuencia, corriente y bus DC; prueba de solo lectura.",
            "Pendiente",
        ),
        (
            "VFD ventilador / GK610 (ID 2)",
            "Consultar frecuencia, corriente y bus DC; prueba de solo lectura.",
            "Pendiente",
        ),
    ]

    for channel in range(_RELAY_INPUT_COUNT):
        inventory.append(
            (
                f"Salida P{channel} → ULN → K{channel + 1}",
                "Con cargas aisladas: pulsar la salida, observar LED/relé y "
                "confirmar que se desactiva al soltar.",
                "Pendiente",
            )
        )

    inventory.extend(
        (
            (
                "Sensor óptico / tacómetro",
                f"Confirmar pulsos en GPIO {config.GPIO_OPTICO} al pasar la marca.",
                "Pendiente",
            ),
            (
                "Sensor inductivo / referencia",
                f"Confirmar cambio de estado en GPIO {config.GPIO_INDUCTIVO}.",
                "Pendiente",
            ),
            (
                "Segundo sensor inductivo",
                f"Confirmar cambio de estado en GPIO {config.GPIO_INDUCTIVO_2}.",
                "Pendiente",
            ),
            (
                "Encoder incremental A/B",
                f"Verificar conteo y sentido en GPIO A={config.GPIO_ENCODER_A}, "
                f"B={config.GPIO_ENCODER_B}.",
                "Pendiente",
            ),
            (
                "Sensor de puerta",
                f"Confirmar detección abierta/cerrada en GPIO {config.GPIO_DOOR_SW}.",
                "Pendiente",
            ),
            (
                "Parada de emergencia (E-Stop)",
                f"Validar GPIO {config.GPIO_ESTOP} y, por separado, "
                "la cadena cableada de seguridad.",
                "Pendiente",
            ),
            (
                "Máquina de estados del proceso",
                "Recorrer la secuencia en modo simulado; no acciona hardware.",
                "Pendiente",
            ),
        )
    )

    for instrument in INSTRUMENTATION + OPTIONAL_INSTRUMENTATION:
        unresolved = any(
            term in f"{instrument.signal_type} {instrument.acquisition}".lower()
            for term in ("pendiente", "por definir")
        )
        initial_status = "Por definir" if unresolved else "Pendiente"
        inventory.append(
            (
                f"{instrument.tag} — {instrument.variable}",
                f"Posición {instrument.position}; rango "
                f"{instrument.range_text} {instrument.units}; "
                f"señal/adquisición: {instrument.signal_type} / "
                f"{instrument.acquisition}.",
                initial_status,
            )
        )
    return inventory


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
    """Reúne pruebas individuales y el inventario de componentes de la máquina."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modo de pruebas - Puesta en marcha")
        self.setFixedSize(760, 440)
        self._i2c_worker = None
        self._pulse_worker = None
        self._rs485_test_window = None
        self._ebyte_pt100_window = None
        self._waveshare_analog_window = None
        self._gpio_test_window = None
        self._active_channel = None
        self._output_state_unknown = False
        self._channel_buttons = []
        self._settings = QSettings("SECADOR_HMI", "PuestaEnMarcha")
        self.setStyleSheet(DIALOG_STYLESHEET)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(5, 5, 5, 5)
        self.tabs = QTabWidget()
        root_layout.addWidget(self.tabs)

        self.io_tab = QWidget()
        layout = QVBoxLayout(self.io_tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)

        title = QLabel(
            "PRUEBA MANUAL — mantén pulsado para activar; suelta para apagar. "
            "ULN activo con nivel alto."
        )
        title.setWordWrap(True)
        title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {ACCENT_TEXT};")
        layout.addWidget(title)

        caution = QLabel(
            "Antes de pulsar: alimentación de las cargas en K1–K8 aislada y "
            "verificada sin tensión. El relé interno sí conmutará. "
            "Los nombres de las funciones son provisionales."
        )
        caution.setWordWrap(True)
        caution.setStyleSheet(f"color: {ERROR}; font-weight: bold;")
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
        self.result_label.setStyleSheet(f"color: {WARNING};")
        layout.addWidget(self.result_label)

        buttons = QHBoxLayout()
        self.read_i2c_button = QPushButton("LEER I2C (NO ESCRIBE)")
        self.read_i2c_button.clicked.connect(self.test_pcf8575_read_only)
        self.read_i2c_button.setMaximumWidth(165)
        self.read_rs485_button = QPushButton("PROBAR RS485 (LECTURA)")
        self.read_rs485_button.clicked.connect(self.open_rs485_test)
        self.read_rs485_button.setMaximumWidth(185)
        self.read_pt100_button = QPushButton("PT100 EBYTE")
        self.read_pt100_button.clicked.connect(self.open_ebyte_pt100_test)
        self.read_pt100_button.setMaximumWidth(120)
        self.close_button = QPushButton("CERRAR")
        self.close_button.setStyleSheet(
            "QPushButton { background-color: #303740; border-color: #414B57; }"
        )
        self.close_button.clicked.connect(self.close)
        buttons.addWidget(self.read_i2c_button)
        buttons.addWidget(self.read_rs485_button)
        buttons.addWidget(self.read_pt100_button)
        buttons.addStretch()
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.tabs.addTab(self.io_tab, "I/O Y COMUNICACIONES")
        self._create_analog_gpio_tab()
        self._create_inventory_tab()

    def _create_analog_gpio_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        title = QLabel(
            "Pruebas puntuales de las entradas analógicas Waveshare y de los "
            "pines GPIO de la Raspberry Pi."
        )
        title.setWordWrap(True)
        title.setStyleSheet(
            f"font-weight: bold; color: {ACCENT_TEXT}; font-size: 13px;"
        )
        layout.addWidget(title)

        analog_info = QLabel(
            "Waveshare SKU 25821: lectura FC04 de 8 canales, en modo corriente "
            "0–20 mA. Confirma los jumpers y el rango configurado; no se "
            "escribe ninguna configuración. Requiere alimentación de 7–36 V "
            "y un adaptador RS485; no conectes el bus A/B directamente al UART "
            "de la Raspberry. Su ID de ejemplo 1 coincide con el EBYTE y el "
            "VFD del tambor: prueba un equipo a la vez."
        )
        analog_info.setWordWrap(True)
        analog_info.setStyleSheet(f"color: {WARNING};")
        layout.addWidget(analog_info)

        self.read_waveshare_button = QPushButton("LEER WAVESHARE — 8 CANALES")
        self.read_waveshare_button.clicked.connect(self.open_waveshare_analog_test)
        self.read_waveshare_button.setMaximumWidth(320)
        layout.addWidget(self.read_waveshare_button)

        gpio_info = QLabel(
            f"Entradas directas: inductivos BCM {config.GPIO_INDUCTIVO} y "
            f"{config.GPIO_INDUCTIVO_2}; encoder A/B BCM "
            f"{config.GPIO_ENCODER_A}/{config.GPIO_ENCODER_B}. Usa solo "
            "señales adaptadas a 3,3 V. La prueba del encoder cuenta pasos "
            "cuadratura con signo; invertir A/B invierte el sentido mostrado."
        )
        gpio_info.setWordWrap(True)
        gpio_info.setStyleSheet(f"color: {WARNING};")
        layout.addWidget(gpio_info)

        self.read_gpio_button = QPushButton("LEER GPIO DIRECTOS")
        self.read_gpio_button.clicked.connect(self.open_gpio_direct_test)
        self.read_gpio_button.setMaximumWidth(260)
        layout.addWidget(self.read_gpio_button)
        layout.addStretch()
        self.tabs.addTab(page, "ANALÓGICO / GPIO")

    def _create_inventory_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)

        guidance = QLabel(
            "Lista de los componentes previstos. Actualiza el resultado y "
            "anota mediciones o fallas. Los datos se guardan en este equipo; "
            "copia el informe para compartirlo."
        )
        guidance.setWordWrap(True)
        guidance.setStyleSheet(f"color: {WARNING}; font-weight: bold;")
        layout.addWidget(guidance)

        self.inventory_table = QTableWidget()
        self.inventory_table.setColumnCount(4)
        self.inventory_table.setHorizontalHeaderLabels(
            ("Componente / TAG", "Verificación sugerida", "Resultado", "Observación")
        )
        inventory = _build_test_inventory()
        self.inventory_table.setRowCount(len(inventory))
        self.inventory_table.verticalHeader().setVisible(False)
        self.inventory_table.setAlternatingRowColors(True)
        self.inventory_table.setStyleSheet(
            "QTableWidget { alternate-background-color: #29313B; }"
        )
        self.inventory_table.setWordWrap(True)
        self.inventory_table.setColumnWidth(0, 185)
        self.inventory_table.setColumnWidth(2, 105)
        self.inventory_table.setColumnWidth(3, 200)
        self.inventory_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        self.inventory_table.setMinimumHeight(285)
        self.inventory_table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.EditKeyPressed
            | QTableWidget.EditTrigger.AnyKeyPressed
        )
        self._inventory_rows = []
        for row, (component, test_description, initial_status) in enumerate(inventory):
            component_item = QTableWidgetItem(component)
            component_item.setFlags(component_item.flags() & ~Qt.ItemIsEditable)
            self.inventory_table.setItem(row, 0, component_item)
            test_item = QTableWidgetItem(test_description)
            test_item.setFlags(test_item.flags() & ~Qt.ItemIsEditable)
            self.inventory_table.setItem(row, 1, test_item)
            status = QComboBox()
            status.addItems(_TEST_RESULTS)
            settings_key = self._inventory_settings_key(component)
            saved_status = self._settings.value(
                f"{settings_key}/status", initial_status
            )
            status.setCurrentText(
                saved_status if saved_status in _TEST_RESULTS else initial_status
            )
            self.inventory_table.setCellWidget(row, 2, status)
            observation = QTableWidgetItem(
                self._settings.value(f"{settings_key}/observation", "", type=str)
            )
            self.inventory_table.setItem(row, 3, observation)
            self._inventory_rows.append((component, test_description, status, observation))
            status.currentTextChanged.connect(
                lambda _value, item=component: self._save_inventory_result(item)
            )
        self.inventory_table.itemChanged.connect(self._inventory_item_changed)
        layout.addWidget(self.inventory_table)

        footer = QHBoxLayout()
        self.inventory_result_label = QLabel(
            f"{len(self._inventory_rows)} elementos registrados; "
            "las pruebas físicas se anotan manualmente."
        )
        self.inventory_result_label.setWordWrap(True)
        footer.addWidget(self.inventory_result_label, 1)
        self.copy_report_button = QPushButton("COPIAR INFORME")
        self.copy_report_button.clicked.connect(self.copy_test_report)
        footer.addWidget(self.copy_report_button)
        self.tabs.addTab(page, "INVENTARIO Y RESULTADOS")

    @staticmethod
    def _inventory_settings_key(component):
        return f"inventory/{quote(component, safe='')}"

    def _inventory_item_changed(self, item):
        if item.column() != 3:
            return
        component = self.inventory_table.item(item.row(), 0).text()
        self._save_inventory_result(component)

    def _save_inventory_result(self, component):
        row = next(
            row
            for row, entry in enumerate(self._inventory_rows)
            if entry[0] == component
        )
        _, _, status, observation = self._inventory_rows[row]
        settings_key = self._inventory_settings_key(component)
        self._settings.setValue(f"{settings_key}/status", status.currentText())
        self._settings.setValue(f"{settings_key}/observation", observation.text())
        self._settings.sync()
        if self._settings.status() != QSettings.Status.NoError:
            self.inventory_result_label.setText(
                "Error: no se pudieron guardar los resultados en este equipo."
            )
            self.inventory_result_label.setStyleSheet(f"color: {ERROR};")
            return
        self.inventory_result_label.setText(f"Resultado guardado: {component}.")
        self.inventory_result_label.setStyleSheet(f"color: {SUCCESS};")

    def copy_test_report(self):
        counts = {result: 0 for result in _TEST_RESULTS}
        report_lines = [
            "INFORME DE PRUEBAS — SECADOR_HMI",
            "Resultados anotados por el usuario; no son una confirmación "
            "automática de hardware.",
        ]
        for component, test_description, status, observation in self._inventory_rows:
            result = status.currentText()
            counts[result] += 1
            note = observation.text().strip() or "sin observación"
            report_lines.append(
                f"- {component}: {result}. {note} "
                f"(prueba: {test_description})"
            )
        summary = ", ".join(
            f"{result}: {count}"
            for result, count in counts.items()
            if count
        )
        report_lines.insert(2, f"Resumen: {summary}.")
        QApplication.clipboard().setText("\n".join(report_lines))
        self.inventory_result_label.setText(
            "Informe copiado. Pégalo en el chat e indica el componente "
            "que probaste."
        )

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

    def open_ebyte_pt100_test(self):
        if self._ebyte_pt100_window is None:
            self._ebyte_pt100_window = EbytePT100Window(self)
        self._ebyte_pt100_window.show()
        self._ebyte_pt100_window.raise_()
        self._ebyte_pt100_window.activateWindow()

    def open_waveshare_analog_test(self):
        if self._waveshare_analog_window is None:
            self._waveshare_analog_window = WaveshareAnalogWindow(self)
        self._waveshare_analog_window.show()
        self._waveshare_analog_window.raise_()
        self._waveshare_analog_window.activateWindow()

    def open_gpio_direct_test(self):
        if self._gpio_test_window is None:
            self._gpio_test_window = GPIODirectTestWindow(self)
        self._gpio_test_window.show()
        self._gpio_test_window.raise_()
        self._gpio_test_window.activateWindow()

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
            self.result_label.setStyleSheet(f"color: {ERROR};")
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
        self.result_label.setStyleSheet(f"color: {WARNING};")
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
        self.table.item(channel, 4).setForeground(QColor(SUCCESS))
        self.result_label.setText(
            f"P{channel} alto; ULN X{channel + 1}/K{channel + 1} activado. "
            "Suelta el botón para apagar."
        )
        self.result_label.setStyleSheet(
            f"color: {SUCCESS}; font-weight: bold;"
        )

    def _show_i2c_result(self, success, message):
        if success:
            message = (
                f"{message}. Esto confirma comunicación I2C solamente; "
                "no confirma la respuesta eléctrica del ULN ni del relé."
            )
        self.result_label.setText(message)
        self.result_label.setStyleSheet(
            f"color: {WARNING};" if success else f"color: {ERROR};"
        )

    def _show_pulse_result(self, channel, success, timed_out, message):
        status = "Auto-apagada" if timed_out else ("Apagada" if success else "DESCONOCIDO")
        self.table.item(channel, 4).setText(status)
        self.table.item(channel, 4).setForeground(
            QColor(SUCCESS) if success else QColor(ERROR)
        )
        if not success:
            self._output_state_unknown = True
        self.result_label.setText(message)
        self.result_label.setStyleSheet(
            f"color: {SUCCESS};" if success else f"color: {ERROR};"
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
            (
                self._ebyte_pt100_window._worker
                if self._ebyte_pt100_window is not None
                else None
            ),
            (
                self._waveshare_analog_window._worker
                if self._waveshare_analog_window is not None
                else None
            ),
            (
                self._gpio_test_window._worker
                if self._gpio_test_window is not None
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
