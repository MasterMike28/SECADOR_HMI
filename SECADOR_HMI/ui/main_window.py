# -*- coding: utf-8 -*-
import serial
import minimalmodbus
from serial.tools import list_ports

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QDialog, QComboBox, 
    QMessageBox, QDoubleSpinBox, QGroupBox
)
from PySide6.QtCore import Qt, QTimer

import config
from ui.process_view import ProcessView
from ui.dialog_etapa import EtapaConfirmDialog
from gpio.state_machine import LiofilizadoraWorker


class ConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración de Puerto RS485")
        self.setFixedSize(360, 180)
        self.setStyleSheet("""
            QDialog { background-color: #111827; color: white; border: 2px solid #374151; }
            QLabel { color: #F3F4F6; font-size: 13px; font-weight: bold; }
            QComboBox { background-color: #1F2937; color: #10B981; padding: 8px; font-size: 14px; font-weight: bold; border: 1px solid #4B5563; border-radius: 4px; }
            QPushButton { padding: 8px; font-weight: bold; border-radius: 4px; font-size: 12px; }
        """)
        
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
        self.setStyleSheet("background-color: #111827; color: white; font-size: 14px;")

        layout = QVBoxLayout(self)

        # 1. Ajuste de Frecuencia
        grupo_freq = QGroupBox("Ajuste de Velocidad")
        layout_freq = QHBoxLayout()
        self.input_hz = QDoubleSpinBox()
        self.input_hz.setRange(0.0, 50.0)
        self.input_hz.setValue(10.0)
        self.input_hz.setSuffix(" Hz")
        self.input_hz.setSingleStep(1.0)
        self.input_hz.setMinimumHeight(35)
        self.input_hz.setStyleSheet("background-color: #1F2937; color: #10B981; font-weight: bold;")
        
        btn_set_hz = QPushButton("Enviar Frecuencia")
        btn_set_hz.setStyleSheet("background-color: #10B981; color: white; font-weight: bold; border-radius: 4px;")
        btn_set_hz.setMinimumHeight(35)
        btn_set_hz.clicked.connect(self.enviar_frecuencia)
        
        layout_freq.addWidget(QLabel("Target:"))
        layout_freq.addWidget(self.input_hz)
        layout_freq.addWidget(btn_set_hz)
        grupo_freq.setLayout(layout_freq)

        # 2. Sentido de Giro
        grupo_giro = QGroupBox("Sentido de Giro (Marcha)")
        layout_giro = QHBoxLayout()
        btn_fwd = QPushButton("▶ Adelante (FWD)")
        btn_fwd.setStyleSheet("background-color: #10B981; color: white; font-weight: bold; padding: 10px; border-radius: 4px;")
        btn_rev = QPushButton("◀ Reversa (REV)")
        btn_rev.setStyleSheet("background-color: #F59E0B; color: black; font-weight: bold; padding: 10px; border-radius: 4px;")
        
        btn_fwd.clicked.connect(lambda: self.enviar_comando(1))  # 1 = FWD (Reg 40103)
        btn_rev.clicked.connect(lambda: self.enviar_comando(3))  # 3 = REV (Reg 40103)
        
        layout_giro.addWidget(btn_fwd)
        layout_giro.addWidget(btn_rev)
        grupo_giro.setLayout(layout_giro)

        # 3. Parada
        grupo_stop = QGroupBox("Detención")
        layout_stop = QHBoxLayout()
        btn_stop = QPushButton("🛑 Parar Motor (STOP)")
        btn_stop.setStyleSheet("background-color: #EF4444; color: white; font-weight: bold; padding: 10px; border-radius: 4px;")
        btn_stop.clicked.connect(lambda: self.enviar_comando(0))  # 0 = STOP (Reg 40103)
        layout_stop.addWidget(btn_stop)
        grupo_stop.setLayout(layout_stop)

        layout.addWidget(grupo_freq)
        layout.addWidget(grupo_giro)
        layout.addWidget(grupo_stop)

    def enviar_frecuencia(self):
        hz = self.input_hz.value()
        if self.parent_window.vfd:
            try:
                valor = int(hz * 100)
                # FC06 al registro P102 (40102)
                self.parent_window.vfd.write_register(config.P102, valor, number_of_decimals=0, functioncode=6)
                print(f"[MODBUS OK] Frecuencia enviada: {hz} Hz -> Reg {config.P102} (P102) = {valor}")
            except Exception as e:
                QMessageBox.critical(self, "Error RS485", f"Fallo al enviar frecuencia a P102: {e}")
        else:
            QMessageBox.warning(self, "Sin Conexión", "Primero debe seleccionar y conectar el puerto RS485 desde 'CONFIG'.")

    def enviar_comando(self, comando):
        if self.parent_window.vfd:
            try:
                # FC06 al registro P103 (40103)
                self.parent_window.vfd.write_register(config.P103, comando, number_of_decimals=0, functioncode=6)
                print(f"[MODBUS OK] Comando enviado: {comando} -> Reg {config.P103} (P103)")
                if comando == 1:
                    self.parent_window.sentido_actual = "FWD"
                elif comando == 3:
                    self.parent_window.sentido_actual = "REV"
                else:
                    self.parent_window.sentido_actual = "STOP"
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
        self.setStyleSheet("background-color: #111827; color: white; font-size: 14px;")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Ingrese nuevo Set Point para {nombre}:"))

        self.input_val = QDoubleSpinBox()
        self.input_val.setRange(-1000.0, 5000.0) 
        self.input_val.setValue(valor_actual)
        self.input_val.setDecimals(1)
        self.input_val.setMinimumHeight(38)
        self.input_val.setStyleSheet("background-color: #1F2937; color: white;")
        layout.addWidget(self.input_val)

        btn_layout = QHBoxLayout()
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setStyleSheet("background-color: #374151; color: white; padding: 6px;")
        self.btn_guardar = QPushButton("Guardar")
        self.btn_guardar.setStyleSheet("background-color: #10B981; color: white; font-weight: bold; padding: 6px;")
        
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
        self.setWindowTitle(f"{config.APP_NAME} UBB")
        self.setFixedSize(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        self.setStyleSheet("QMainWindow { background-color: #111827; color: #FFFFFF; }")

        self.vfd = None
        self.sentido_actual = "STOP"

        # Hilo de la Máquina de Estados
        self.worker = LiofilizadoraWorker()
        self.worker.solicitar_confirmacion.connect(self.mostrar_popup_etapa)
        self.worker.estado_cambiado.connect(self.actualizar_estado_barra)

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

        # --- HEADER / BARRA SUPERIOR ---
        header = QFrame()
        header.setFixedHeight(45)
        header.setStyleSheet("background: #111827; border-bottom: 2px solid #374151;")
        header_layout = QHBoxLayout(header)

        titulo = QLabel(f"LIOFILIZADOR ATMOSFÉRICO UBB v{config.APP_VERSION}")
        titulo.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold;")

        self.lbl_estado_proceso = QLabel("Estado: REPOSO")
        self.lbl_estado_proceso.setStyleSheet("color: #F59E0B; font-size: 14px; font-weight: bold; margin-right: 15px;")

        self.estado = QLabel("● DESCONECTADO (CONFIGURAR RS485)")
        self.estado.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.estado.setStyleSheet("color: #EF4444; font-size: 13px; font-weight: bold;")

        header_layout.addWidget(titulo)
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_estado_proceso)
        header_layout.addWidget(self.estado)
        layout.addWidget(header)

        # --- VISTA P&ID PRINCIPAL ---
        self.process = ProcessView()
        layout.addWidget(self.process)

        # --- FOOTER / NAVEGACIÓN ---
        footer = QFrame()
        footer.setFixedHeight(60)
        footer.setStyleSheet("background: #111827; border-top: 2px solid #374151;")
        footer_layout = QHBoxLayout(footer)

        self.btn_iniciar = QPushButton("INICIAR PROCESO")
        self.btn_iniciar.setMinimumHeight(40)
        self.btn_iniciar.setStyleSheet("font-size: 13px; font-weight: bold; background-color: #10B981; color: white; border-radius: 5px; padding: 0 15px;")
        self.btn_iniciar.clicked.connect(self.iniciar_proceso_secado)

        self.btn_stop = QPushButton("PARADA EMERGENCIA")
        self.btn_stop.setMinimumHeight(40)
        self.btn_stop.setStyleSheet("font-size: 13px; font-weight: bold; background-color: #EF4444; color: white; border-radius: 5px; padding: 0 15px;")
        self.btn_stop.clicked.connect(self.detener_proceso)

        footer_layout.addWidget(self.btn_iniciar)
        footer_layout.addWidget(self.btn_stop)
        footer_layout.addSpacing(15)

        botones_nav = ["MOTOR CÁMARA", "CONFIG", "ALARMAS", "HISTÓRICOS"]
        self.btns = {}

        for texto in botones_nav:
            boton = QPushButton(texto)
            boton.setMinimumHeight(40)
            if texto == "MOTOR CÁMARA":
                boton.setStyleSheet("font-size: 13px; font-weight: bold; background-color: #3B82F6; color: white; border-radius: 5px;")
            elif texto == "CONFIG":
                boton.setStyleSheet("font-size: 13px; font-weight: bold; background-color: #F59E0B; color: black; border-radius: 5px;")
            else:
                boton.setStyleSheet("font-size: 13px; font-weight: bold; background-color: #374151; color: white; border-radius: 5px;")
            self.btns[texto] = boton
            footer_layout.addWidget(boton)

        layout.addWidget(footer)

        # --- EVENTOS ---
        self.btns["CONFIG"].clicked.connect(self.abrir_configuracion)
        self.btns["MOTOR CÁMARA"].clicked.connect(self.abrir_control_motor)
        
        self.process.motorClicked.connect(self.abrir_control_motor)
        self.process.setPointRequested.connect(self.abrir_dialogo_setpoint)

    def abrir_configuracion(self):
        dialogo = ConfigDialog(self)
        if dialogo.exec() == QDialog.Accepted:
            puerto = dialogo.get_selected_port()
            if "Sin puertos" not in puerto:
                self.conectar_vfd_real(puerto)

    def conectar_vfd_real(self, puerto):
        """Conexión Modbus con verificación FC03."""
        try:
            self.vfd = minimalmodbus.Instrument(puerto, config.SLAVE_ID)
            self.vfd.serial.baudrate = config.BAUDRATE
            self.vfd.serial.bytesize = 8
            self.vfd.serial.parity = serial.PARITY_NONE
            self.vfd.serial.stopbits = 1
            self.vfd.serial.timeout = 0.3
            self.vfd.mode = minimalmodbus.MODE_RTU
            self.vfd.clear_buffers_before_each_transaction = True
            self.vfd.close_port_after_each_call = False

            # Probar lectura de frecuencia real (Reg 40182)
            self.vfd.read_register(config.REG_FREQ_OUT, number_of_decimals=0, functioncode=3)
            
            self.estado.setText(f"● CONECTADO ({puerto})")
            self.estado.setStyleSheet("color:#10B981; font-size:13px; font-weight:bold;")
            QMessageBox.information(self, "Conexión Exitosa", f"Variador Elimex respondiendo en puerto {puerto}")

        except Exception as e:
            self.vfd = None
            self.estado.setText("● ERROR RS485")
            self.estado.setStyleSheet("color:#EF4444; font-size:13px; font-weight:bold;")
            QMessageBox.critical(self, "Error Modbus", f"No hubo respuesta del variador Elimex en {puerto}:\n{e}")

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
        """Lectura en tiempo real de la telemetría del variador Elimex."""
        if self.vfd is not None:
            try:
                status = self.vfd.read_register(config.REG_STATUS, functioncode=3)
                freq_out = self.vfd.read_register(config.REG_FREQ_OUT, functioncode=3)
                current = self.vfd.read_register(config.REG_CURRENT, functioncode=3)
                alarm = self.vfd.read_register(config.REG_ALARM, functioncode=3)

                freq_hz = freq_out / 100.0
                rpm_sync = (120 * freq_hz) / 4
                rpm_real = rpm_sync * (1 - 0.03)

                datos_frescos = {
                    "freq_real": freq_hz,
                    "rpm_real": rpm_real,
                    "current": current,
                    "alarm": alarm,
                    "status": status,
                    "sentido": self.sentido_actual
                }
                self.process.update_telemetry(datos_frescos)

            except Exception:
                self.vfd = None
                self.estado.setText("● DESCONECTADO (TIMEOUT)")
                self.estado.setStyleSheet("color:#EF4444; font-size:13px; font-weight:bold;")

    def iniciar_proceso_secado(self):
        if not self.worker.isRunning():
            self.worker.start()

    def detener_proceso(self):
        if self.worker.isRunning():
            self.worker.detener()

    def actualizar_estado_barra(self, texto_estado):
        self.lbl_estado_proceso.setText(f"Estado: {texto_estado}")

    def mostrar_popup_etapa(self, etapa, parametro, valor, unidad):
        dialog = EtapaConfirmDialog(etapa, parametro, valor, unidad, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.worker.recibir_respuesta_usuario(True, dialog.obtener_valor())
        else:
            self.worker.detener()
            self.worker.recibir_respuesta_usuario(False, 0.0)
