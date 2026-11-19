# -*- coding: utf-8 -*-
import serial
import minimalmodbus
from collections import deque
from datetime import datetime
from serial.tools import list_ports

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QDialog, QComboBox, 
    QMessageBox, QDoubleSpinBox, QGroupBox
)
from PySide6.QtCore import Qt, QTimer

import config
from ui.theme import (
    BORDER,
    DIALOG_STYLESHEET,
    ERROR,
    ERROR_BG,
    SUCCESS,
    SUCCESS_BG,
    SURFACE,
    TEXT,
    TEXT_MUTED,
    WARNING,
    WARNING_BG,
    WINDOW,
    status_label_style,
)
from ui.process_view import ProcessView
from ui.dialog_etapa import EtapaConfirmDialog
from ui.event_windows import AlarmWindow, HistoryWindow
from ui.test_mode_window import TestModeWindow
from ui.variables_window import VariablesWindow
from gpio.state_machine import LiofilizadoraWorker


class ConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración de Puerto RS485")
        self.setFixedSize(360, 180)
        self.setStyleSheet(DIALOG_STYLESHEET)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Seleccione el puerto RS485 detectado:"))
        
        self.combo_puertos = QComboBox()
        self.refresh_ports()
        layout.addWidget(self.combo_puertos)
        
        btn_layout = QHBoxLayout()
        btn_actualizar = QPushButton("🔄 Re-escanear Puertos")
        btn_actualizar.setStyleSheet("background-color: #374151; color: white;")
        
        btn_conectar = QPushButton("🔌 Conectar Puerto")
        btn_conectar.setStyleSheet("background-color: #10B981; color: white;")
        
        btn_actualizar.clicked.connect(self.refresh_ports)
        btn_conectar.clicked.connect(self.accept)
        
        btn_layout.addWidget(btn_actualizar)
        btn_layout.addWidget(btn_conectar)
        layout.addLayout(btn_layout)

    def refresh_ports(self):
        self.combo_puertos.clear()
        puertos = [p.device for p in list_ports.comports()]
        if puertos:
            self.combo_puertos.addItems(puertos)
        else:
            self.combo_puertos.addItem("Sin puertos detectados")

    def get_selected_port(self):
        return self.combo_puertos.currentText()


class ControlMotorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("Control Motor - Tambor Liofilizador")
        self.setFixedSize(460, 320)
        self.setStyleSheet(DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)

        grupo_freq = QGroupBox("Ajuste de Velocidad")
        layout_freq = QHBoxLayout()
        self.input_hz = QDoubleSpinBox()
        self.input_hz.setRange(0.0, 50.0)
        self.input_hz.setValue(10.0)
        self.input_hz.setSuffix(" Hz")
        self.input_hz.setSingleStep(1.0)
        self.input_hz.setMinimumHeight(35)
        self.input_hz.setStyleSheet(
            f"background-color: {SURFACE}; color: #10B981; font-weight: bold;"
        )
        
        btn_set_hz = QPushButton("Enviar Frecuencia")
        btn_set_hz.setStyleSheet(
            "background-color: #10B981; color: white; font-weight: bold; "
            "border-radius: 4px;"
        )
        btn_set_hz.setMinimumHeight(35)
        btn_set_hz.clicked.connect(self.enviar_frecuencia)
        
        layout_freq.addWidget(QLabel("Target:"))
        layout_freq.addWidget(self.input_hz)
        layout_freq.addWidget(btn_set_hz)
        grupo_freq.setLayout(layout_freq)

        grupo_giro = QGroupBox("Sentido de Giro (Marcha)")
        layout_giro = QHBoxLayout()
        btn_fwd = QPushButton("▶ Adelante (FWD)")
        btn_fwd.setStyleSheet(
            "background-color: #10B981; color: white; font-weight: bold; "
            "padding: 10px; border-radius: 4px;"
        )
        btn_rev = QPushButton("◀ Reversa (REV)")
        btn_rev.setStyleSheet(
            "background-color: #F59E0B; color: black; font-weight: bold; "
            "padding: 10px; border-radius: 4px;"
        )
        
        btn_fwd.clicked.connect(lambda: self.enviar_comando(1))
        btn_rev.clicked.connect(lambda: self.enviar_comando(3))
        
        layout_giro.addWidget(btn_fwd)
        layout_giro.addWidget(btn_rev)
        grupo_giro.setLayout(layout_giro)

        grupo_stop = QGroupBox("Detención")
        layout_stop = QHBoxLayout()
        btn_stop = QPushButton("🛑 Parar Motor (STOP)")
        btn_stop.setStyleSheet(
            "background-color: #EF4444; color: white; font-weight: bold; "
            "padding: 10px; border-radius: 4px;"
        )
        btn_stop.clicked.connect(lambda: self.enviar_comando(0))
        layout_stop.addWidget(btn_stop)
        grupo_stop.setLayout(layout_stop)

        layout.addWidget(grupo_freq)
        layout.addWidget(grupo_giro)
        layout.addWidget(grupo_stop)

    def enviar_frecuencia(self):
        hz = self.input_hz.value()
        if self.parent_window.vfd.instrument is not None:
            try:
                valor = int(hz * 100)
                self.parent_window.vfd.write_register(config.P102, valor, number_of_decimals=0, functioncode=6)
                print(f"[MODBUS OK] Frecuencia enviada: {hz} Hz -> Reg {config.P102} (P102) = {valor}")
            except Exception as e:
                QMessageBox.critical(self, "Error RS485", f"Fallo al enviar frecuencia a P102: {e}")
        else:
            QMessageBox.warning(self, "Sin Conexión", "Primero debe seleccionar y conectar el puerto RS485 desde 'CONFIG'.")

    def enviar_comando(self, comando):
        if self.parent_window.vfd.instrument is not None:
            try:
                self.parent_window.vfd.write_register(config.P103, comando, number_of_decimals=0, functioncode=6)
                print(f"[MODBUS OK] Comando enviado: {comando} -> Reg {config.P103} (P103)")
                if comando == 1:
                    self.parent_window.vfd.sentido_actual = "FWD"
                elif comando == 3:
                    self.parent_window.vfd.sentido_actual = "REV"
                else:
                    self.parent_window.vfd.sentido_actual = "STOP"
            except Exception as e:
                QMessageBox.critical(self, "Error RS485", f"Fallo al enviar comando a P103: {e}")
        else:
            QMessageBox.warning(self, "Sin Conexión", "Primero debe seleccionar y conectar el puerto RS485 desde 'CONFIG'.")


class SetPointDialog(QDialog):
    def __init__(self, sensor_id, nombre, valor_actual, parent=None):
        super().__init__(parent)
        self.sensor_id = sensor_id
        self.setWindowTitle(f"Ajustar: {nombre}")
        self.setFixedSize(320, 160)
        self.setStyleSheet(DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Ingrese nuevo Set Point para {nombre}:"))

        self.input_val = QDoubleSpinBox()
        self.input_val.setRange(-1000.0, 5000.0) 
        self.input_val.setValue(valor_actual)
        self.input_val.setDecimals(1)
        self.input_val.setMinimumHeight(38)
        self.input_val.setStyleSheet(
            f"background-color: {SURFACE}; color: {TEXT};"
        )
        layout.addWidget(self.input_val)

        btn_layout = QHBoxLayout()
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setStyleSheet(
            "background-color: #374151; color: white; padding: 6px;"
        )
        self.btn_guardar = QPushButton("Guardar")
        self.btn_guardar.setStyleSheet(
            "background-color: #10B981; color: white; "
            "font-weight: bold; padding: 6px;"
        )
        
        btn_cancelar.clicked.connect(self.reject)
        self.btn_guardar.clicked.connect(self.accept)

        btn_layout.addWidget(btn_cancelar)
        btn_layout.addWidget(self.btn_guardar)
        layout.addLayout(btn_layout)

    def get_value(self):
        return self.input_val.value()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(DIALOG_STYLESHEET)
        self.setWindowTitle(f"{config.APP_NAME} UBB")
        self.setFixedSize(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        self.setStyleSheet(DIALOG_STYLESHEET)

        # Hilo de la Máquina de Estados
        self.worker = LiofilizadoraWorker()
        self.worker.solicitar_confirmacion.connect(self.mostrar_popup_etapa)
        self.worker.estado_cambiado.connect(self.registrar_estado_proceso)
        self.worker.alerta_emitida.connect(self.registrar_alerta)
        
        # --- SOLUCIÓN: COMPARTIMOS EL MISMO VFD Y SEMÁFORO ---
        self.vfd = self.worker.vfd
        self.variables_window = None
        self.alarm_window = None
        self.history_window = None
        self.test_mode_window = None
        self._alarm_records = deque(maxlen=2000)
        self._history_records = deque(maxlen=5000)
        self._next_alarm_id = 1
        self._last_recorded_state = None
        self._record_history("Sistema", "Aplicación iniciada en modo simulación")

        self.create_ui()

        # Timer para lectura continua
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.monitor_loop)
        self.timer.start(config.REFRESH_TIME)

    def create_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        central.setLayout(layout)

        header = QFrame()
        header.setFixedHeight(52)
        header.setStyleSheet(
            f"background: {WINDOW}; border-bottom: 1px solid {BORDER};"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 4, 10, 4)
        header_layout.setSpacing(8)

        titulo = QLabel(
            f"LIOFILIZADOR UBB  <span style='color:{TEXT_MUTED};"
            f"font-size:11px'>v{config.APP_VERSION}</span>"
        )
        titulo.setTextFormat(Qt.RichText)
        titulo.setMinimumWidth(190)
        titulo.setStyleSheet(
            f"color: {TEXT}; font-size: 15px; font-weight: bold;"
        )

        self.lbl_estado_proceso = QLabel("●  REPOSO")
        self.lbl_estado_proceso.setAlignment(Qt.AlignCenter)
        self.lbl_estado_proceso.setMinimumHeight(34)
        self.lbl_estado_proceso.setMinimumWidth(190)
        self.lbl_estado_proceso.setStyleSheet(
            f"{status_label_style(WARNING, WARNING_BG, '#B45309')} "
            "font-size: 13px;"
        )

        self.estado = QLabel("●  RS485 SIN CONEXIÓN")
        self.estado.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.estado.setMinimumHeight(34)
        self.estado.setMinimumWidth(180)
        self.estado.setStyleSheet(
            f"{status_label_style(ERROR, ERROR_BG, '#B91C1C')} font-size: 12px;"
        )
        self.estado.setToolTip("Variador no conectado. Configure el puerto RS485.")

        header_layout.addWidget(titulo, 0)
        header_layout.addWidget(self.lbl_estado_proceso, 1)
        header_layout.addWidget(self.estado, 0)
        layout.addWidget(header)

        self.process = ProcessView()
        layout.addWidget(self.process)

        footer = QFrame()
        footer.setFixedHeight(112)
        footer.setStyleSheet(
            f"background: {WINDOW}; border-top: 1px solid {BORDER};"
        )
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(8, 6, 8, 6)
        footer_layout.setSpacing(6)

        self.btn_iniciar = QPushButton("INICIAR PROCESO")
        self.btn_iniciar.setMinimumHeight(48)
        self.btn_iniciar.setStyleSheet(
            "font-size: 15px; font-weight: bold; background-color: #059669; "
            "color: white; border: 2px solid #34D399; border-radius: 7px; "
            "padding: 0 12px;"
        )
        self.btn_iniciar.setToolTip("Iniciar el ciclo de proceso")
        self.btn_iniciar.clicked.connect(self.iniciar_proceso_secado)

        self.btn_stop = QPushButton("PARADA DE EMERGENCIA")
        self.btn_stop.setMinimumHeight(48)
        self.btn_stop.setStyleSheet(
            "font-size: 15px; font-weight: bold; background-color: #B91C1C; "
            "color: white; border: 2px solid #F87171; border-radius: 7px; "
            "padding: 0 12px;"
        )
        self.btn_stop.setToolTip("Detener el proceso y apagar las salidas controladas")
        self.btn_stop.clicked.connect(self.detener_proceso)

        acciones_layout = QHBoxLayout()
        acciones_layout.setSpacing(8)
        acciones_layout.addWidget(self.btn_iniciar, 1)
        acciones_layout.addWidget(self.btn_stop, 1)
        footer_layout.addLayout(acciones_layout)

        botones_nav = [
            "MOTOR CÁMARA", "CONFIG", "ALARMAS",
            "HISTÓRICOS", "VARIABLES", "PRUEBAS", "PANTALLA",
        ]
        self.btns = {}

        for texto in botones_nav:
            boton = QPushButton(texto)
            boton.setMinimumHeight(44)
            boton.setStyleSheet(
                "QPushButton { font-size: 13px; font-weight: bold; "
                "background-color: #374151; color: white; "
                "border: 1px solid #6B7280; border-radius: 6px; padding: 0 5px; }"
                "QPushButton:hover { background-color: #4B5563; }"
                "QPushButton:pressed { background-color: #1F2937; }"
            )
            nav_colors = {
                "MOTOR CÁMARA": ("#1D4ED8", "#60A5FA", "#2563EB", "#1E40AF"),
                "CONFIG": ("#B45309", "#FBBF24", "#D97706", "#92400E"),
                "ALARMAS": ("#991B1B", "#F87171", "#B91C1C", "#7F1D1D"),
                "HISTÓRICOS": ("#0F766E", "#5EEAD4", "#0D9488", "#115E59"),
            }
            if texto in nav_colors:
                background, border, hover, pressed = nav_colors[texto]
                boton.setStyleSheet(
                    "QPushButton { font-size: 13px; font-weight: bold; "
                    f"background-color: {background}; color: white; "
                    f"border: 1px solid {border}; border-radius: 6px; padding: 0 5px; }}"
                    f"QPushButton:hover {{ background-color: {hover}; }}"
                    f"QPushButton:pressed {{ background-color: {pressed}; }}"
                )
            boton.setToolTip({
                "MOTOR CÁMARA": "Abrir control manual del motor de cámara",
                "CONFIG": "Configurar la conexión RS485",
                "ALARMAS": "Consultar y reconocer alarmas y avisos de esta sesión",
                "HISTÓRICOS": "Consultar los estados y eventos de proceso de esta sesión",
                "VARIABLES": "Ver las variables disponibles del sistema",
                "PRUEBAS": "Control manual de salidas; solo probar con las cargas aisladas",
                "PANTALLA": "Alternar entre ventana y pantalla completa",
            }[texto])
            self.btns[texto] = boton

        navegacion_layout = QHBoxLayout()
        navegacion_layout.setSpacing(6)
        for texto in botones_nav:
            navegacion_layout.addWidget(self.btns[texto], 1)
        footer_layout.addLayout(navegacion_layout)

        layout.addWidget(footer)

        self.btns["CONFIG"].clicked.connect(self.abrir_configuracion)
        self.btns["MOTOR CÁMARA"].clicked.connect(self.abrir_control_motor)
        self.btns["ALARMAS"].clicked.connect(self.abrir_ventana_alarmas)
        self.btns["HISTÓRICOS"].clicked.connect(self.abrir_ventana_historicos)
        self.btns["VARIABLES"].clicked.connect(self.abrir_ventana_variables)
        self.btns["PRUEBAS"].clicked.connect(self.abrir_modo_pruebas)
        self.btns["PANTALLA"].clicked.connect(self.alternar_pantalla_completa)
        
        self.process.motorClicked.connect(self.abrir_control_motor)
        self.process.setPointRequested.connect(self.abrir_dialogo_setpoint)

    def abrir_configuracion(self):
        dialogo = ConfigDialog(self)
        if dialogo.exec() == QDialog.Accepted:
            puerto = dialogo.get_selected_port()
            if "Sin puertos" not in puerto:
                self.conectar_vfd_real(puerto)

    def conectar_vfd_real(self, puerto):
        """Conexión Modbus unificada a través del driver protegido."""
        if self.vfd.conectar(puerto):
            try:
                self.vfd.read_register(config.REG_FREQ_OUT, number_of_decimals=0, functioncode=3)
                
                self._actualizar_estado_conexion(puerto, conectado=True)
                QMessageBox.information(self, "Conexión Exitosa", f"Variador Elimex respondiendo en puerto {puerto}")

            except Exception as e:
                self.vfd.instrument = None 
                self._actualizar_estado_conexion("ERROR DE COMUNICACIÓN", conectado=False)
                QMessageBox.critical(self, "Error Modbus", f"No hubo respuesta del variador Elimex en {puerto}:\n{e}")
        else:
            self._actualizar_estado_conexion("ERROR AL ABRIR PUERTO", conectado=False)
            QMessageBox.critical(self, "Error Modbus", f"Fallo al abrir el puerto {puerto}.")

    def _actualizar_estado_conexion(self, detalle=None, conectado=False):
        if conectado:
            puerto = detalle or getattr(self.vfd, "port", None) or "ACTIVO"
            self.estado.setText("●  RS485 CONECTADO")
            self.estado.setStyleSheet(
                f"{status_label_style(SUCCESS, SUCCESS_BG, '#059669')} "
                "font-size: 12px;"
            )
            self.estado.setToolTip(f"Comunicación Modbus activa por {puerto}.")
            return

        self.estado.setText("●  RS485 SIN CONEXIÓN")
        self.estado.setStyleSheet(
            f"{status_label_style(ERROR, ERROR_BG, '#B91C1C')} font-size: 12px;"
        )
        self.estado.setToolTip(f"Revise la conexión RS485 y el variador. {detalle or ''}".strip())

    def abrir_control_motor(self):
        dialogo = ControlMotorDialog(self)
        dialogo.exec()

    def abrir_dialogo_setpoint(self, sensor_id, nombre, valor_actual):
        dialogo = SetPointDialog(sensor_id, nombre, valor_actual, self)
        if dialogo.exec() == QDialog.Accepted:
            nuevo_valor = dialogo.get_value()
            self.process.sensores[sensor_id]["valor"] = nuevo_valor
            self.process.update() 

    def monitor_loop(self):
        """Lectura en tiempo real de la telemetría del variador y sensores GPIO."""
        
        # 1. Leemos siempre los sensores físicos locales
        vueltas = self.worker.sensor_optico.obtener_vueltas()
        puerta = self.worker.sensor_puerta.esta_cerrada()
        
        datos_frescos = {
            "freq_real": 0.0,
            "rpm_real": 0.0,
            "current": 0.0,
            "alarm": 0,
            "status": 0,
            "sentido": self.vfd.sentido_actual if self.vfd else "STOP",
            "vueltas": vueltas,
            "puerta_cerrada": puerta
        }

        # 2. Si el Modbus está conectado, agregamos la info del motor
        if self.vfd.instrument is not None:
            try:
                status = self.vfd.read_register(config.REG_STATUS, functioncode=3)
                freq_out = self.vfd.read_register(config.REG_FREQ_OUT, functioncode=3)
                current = self.vfd.read_register(config.REG_CURRENT, functioncode=3)
                alarm = self.vfd.read_register(config.REG_ALARM, functioncode=3)

                freq_hz = freq_out / 100.0
                rpm_sync = (120 * freq_hz) / 4
                rpm_real = rpm_sync * (1 - 0.03)

                datos_frescos.update({
                    "freq_real": freq_hz,
                    "rpm_real": rpm_real,
                    "current": current,
                    "alarm": alarm,
                    "status": status,
                    "sentido": self.vfd.sentido_actual
                })

            except Exception:
                self.vfd.instrument = None
                self._actualizar_estado_conexion("TIEMPO DE ESPERA AGOTADO", conectado=False)

        # 3. Enviamos toda la información para que la pantalla se dibuje
        self.process.update_telemetry(datos_frescos)

    def abrir_ventana_variables(self):
        if self.variables_window is None:
            self.variables_window = VariablesWindow(self.obtener_variables_sistema, self)
        self.variables_window.show()
        self.variables_window.raise_()
        self.variables_window.activateWindow()

    def abrir_ventana_alarmas(self):
        if self.alarm_window is None:
            self.alarm_window = AlarmWindow(
                lambda: self._alarm_records,
                self.reconocer_alarma,
                self,
            )
        self.alarm_window.refresh()
        self.alarm_window.show()
        self.alarm_window.raise_()
        self.alarm_window.activateWindow()

    def abrir_ventana_historicos(self):
        if self.history_window is None:
            self.history_window = HistoryWindow(lambda: self._history_records, self)
        self.history_window.refresh()
        self.history_window.show()
        self.history_window.raise_()
        self.history_window.activateWindow()

    def abrir_modo_pruebas(self):
        if self.test_mode_window is None:
            self.test_mode_window = TestModeWindow(self)
        self.test_mode_window.show()
        self.test_mode_window.raise_()
        self.test_mode_window.activateWindow()

    @staticmethod
    def _event_timestamp():
        return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")

    def _record_history(self, event_type, detail, state=None):
        current_state = state
        if current_state is None:
            current_state = getattr(self.worker.estado_actual, "name", "DESCONOCIDO")
        self._history_records.append({
            "timestamp": self._event_timestamp(),
            "type": event_type,
            "state": str(current_state),
            "detail": str(detail),
        })
        if self.history_window is not None:
            self.history_window.refresh()

    def registrar_estado_proceso(self, state_text):
        if state_text != self._last_recorded_state:
            self._record_history("Estado", state_text, state_text)
            self._last_recorded_state = state_text
        self.actualizar_estado_barra(state_text)

    def registrar_alerta(self, message):
        state = getattr(self.worker.estado_actual, "name", "DESCONOCIDO")
        severity = (
            "ALTA"
            if any(term in message.lower() for term in ("falla", "emergencia", "interlock"))
            else "AVISO"
        )
        record = {
            "id": self._next_alarm_id,
            "timestamp": self._event_timestamp(),
            "severity": severity,
            "state": state,
            "message": str(message),
            "acknowledged": False,
        }
        self._next_alarm_id += 1
        self._alarm_records.append(record)
        self._record_history("Alarma" if severity == "ALTA" else "Aviso", message, state)
        if self.alarm_window is not None:
            self.alarm_window.refresh()

    def reconocer_alarma(self, alarm_id):
        for record in self._alarm_records:
            if record["id"] == alarm_id:
                record["acknowledged"] = True
                self._record_history(
                    "Reconocimiento",
                    f"Alarma reconocida: {record['message']}",
                    record["state"],
                )
                if self.alarm_window is not None:
                    self.alarm_window.refresh()
                return

    def obtener_variables_sistema(self):
        """Prepara una instantánea de las variables disponibles sin leer hardware."""
        rows = [
            ("Sistema", "Aplicación", config.APP_NAME, ""),
            ("Sistema", "Versión", config.APP_VERSION, ""),
            ("Sistema", "Actualización HMI", config.REFRESH_TIME, "ms"),
            ("Proceso", "Estado", self.lbl_estado_proceso.text().removeprefix("Estado: "), ""),
            ("Proceso", "En ejecución", self.worker.ejecutando, ""),
            ("Proceso", "Último valor confirmado", self.worker.valor_confirmado, ""),
            ("Modbus", "Puerto", getattr(self.vfd, "port", config.RS485_PORT), ""),
            ("Modbus", "Conectado", self.vfd.instrument is not None, ""),
            ("Modbus", "ID esclavo", config.SLAVE_ID, ""),
            ("Modbus", "Velocidad serial", config.BAUDRATE, "baud"),
        ]

        datos_vfd = self.process.vfd_data
        unidades_vfd = {
            "freq_real": "Hz",
            "rpm_real": "RPM",
            "current": "A",
            "alarm": "",
            "status": "",
            "sentido": "",
            "vueltas": "rev",
            "puerta_cerrada": "",
        }
        for nombre, unidad in unidades_vfd.items():
            rows.append(("Variador / telemetría", nombre, datos_vfd.get(nombre), unidad))

        for sensor_id, sensor in self.process.sensores.items():
            rows.append((
                "Sensores / proceso",
                f"{sensor_id} ({sensor['nombre']})",
                sensor.get("valor"),
                sensor.get("unidad", ""),
            ))

        sensor_puerta_disponible = self.worker.sensor_puerta.sensor is not None
        rows.extend([
            ("GPIO", "Sensor óptico / GPIO", config.SENSOR_GPIO, "BCM"),
            ("GPIO", "Pulsos ópticos", self.worker.sensor_optico.obtener_vueltas(), "pulsos"),
            ("GPIO", "Sensor inductivo / GPIO", config.SENSOR_INDUCTIVO_GPIO, "BCM"),
            (
                "GPIO",
                "Puerta cerrada",
                self.worker.sensor_puerta.esta_cerrada() if sensor_puerta_disponible else None,
                "",
            ),
            ("GPIO", "Sensor inductivo inicializado", sensor_puerta_disponible, ""),
            ("GPIO", "Sensor óptico inicializado", self.worker.sensor_optico.sensor is not None, ""),
            ("I2C", "Bus", config.I2C_BUS_ID, ""),
            ("I2C", "Dirección PCF8575", f"0x{config.PCF8575_I2C_ADDR:02X}", ""),
            ("I2C", "PCF8575 inicializado", self.worker.outputs.bus is not None, ""),
        ])

        output_mask = self.worker.outputs.state_mask
        for nombre in sorted(name for name in vars(config) if name.startswith("CH_")):
            canal = getattr(config, nombre)
            bit_high = bool(output_mask & (1 << canal))
            activo = (
                not bit_high
                if config.PCF8575_RELAY_ACTIVE_LOW
                else bit_high
            )
            rows.append(("Relés / PCF8575", nombre, activo, f"canal {canal}"))

        nombres_registros = (
            name for name in vars(config)
            if name.startswith("REG_") or (name.startswith("P") and name[1:].isdigit())
        )
        for nombre in sorted(nombres_registros):
            valor = getattr(config, nombre)
            if isinstance(valor, int):
                rows.append(("Registros Modbus", nombre, valor, "registro"))

        return rows

    def iniciar_proceso_secado(self):
        if not self.worker.isRunning():
            self._record_history("Operación", "Inicio de proceso solicitado")
            self.worker.start()

    def detener_proceso(self):
        if self.worker.isRunning():
            self._record_history("Operación", "Parada solicitada por el operador")
            self.worker.detener()

    def actualizar_estado_barra(self, texto_estado):
        estado = texto_estado.removeprefix("ETAPA: ").strip()
        self.lbl_estado_proceso.setText(f"●  {estado}")
        if "EMERGENCIA" in estado or "ABORTADO" in estado or "FALLA" in estado:
            self.lbl_estado_proceso.setStyleSheet(
                status_label_style("#FECACA", "#7F1D1D", "#EF4444")
                + " font-size: 13px;"
            )
        elif "FINALIZADO" in estado:
            self.lbl_estado_proceso.setStyleSheet(
                status_label_style("#A7F3D0", "#064E3B", "#059669")
                + " font-size: 13px;"
            )
        else:
            self.lbl_estado_proceso.setStyleSheet(
                status_label_style(WARNING, WARNING_BG, "#B45309")
                + " font-size: 13px;"
            )

    def mostrar_popup_etapa(self, etapa, parametro, valor, unidad):
        dialog = EtapaConfirmDialog(etapa, parametro, valor, unidad, parent=self)
        if dialog.exec() == QDialog.Accepted:
            confirmed_value = dialog.obtener_valor()
            self._record_history(
                "Confirmación",
                f"{etapa}: {parametro} = {confirmed_value:g} {unidad}".strip(),
            )
            self.worker.recibir_respuesta_usuario(True, confirmed_value)
        else:
            self._record_history("Operación", f"Etapa cancelada por el operador: {etapa}")
            self.worker.detener()
            self.worker.recibir_respuesta_usuario(False, 0.0)

    def alternar_pantalla_completa(self):
        """Alterna entre ventana normal y pantalla completa para la demostración."""
        if self.isFullScreen():
            self.showNormal()
            self.setFixedSize(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        else:
            self.showFullScreen()