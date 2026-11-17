# ui/widgets/control_panel.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                               QComboBox, QPushButton, QLabel, QGroupBox, QMessageBox)
from serial.tools import list_ports

class ControlPanelWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.refresh_ports() # Busca los puertos al iniciar

    def setup_ui(self):
        layout_principal = QVBoxLayout(self)

        # --- GRUPO: CONEXIÓN MODBUS ---
        grupo_conexion = QGroupBox("Conexión Modbus RS485")
        layout_conexion = QHBoxLayout()

        self.label_puerto = QLabel("Puerto:")
        self.combo_puertos = QComboBox()
        self.combo_puertos.setMinimumWidth(150)
        
        self.btn_actualizar = QPushButton("Actualizar")
        self.btn_conectar = QPushButton("Conectar")

        # Señales (Eventos)
        self.btn_actualizar.clicked.connect(self.refresh_ports)
        self.btn_conectar.clicked.connect(self.connect_modbus)

        layout_conexion.addWidget(self.label_puerto)
        layout_conexion.addWidget(self.combo_puertos)
        layout_conexion.addWidget(self.btn_actualizar)
        layout_conexion.addWidget(self.btn_conectar)
        grupo_conexion.setLayout(layout_conexion)

        # --- GRUPO: CONTROL DEL MOTOR ---
        grupo_motor = QGroupBox("Control de Motor")
        layout_motor = QHBoxLayout()

        self.btn_run_adelante = QPushButton("RUN Adelante")
        self.btn_run_reversa = QPushButton("RUN Reversa")
        self.btn_stop = QPushButton("STOP")
        self.btn_stop.setStyleSheet("background-color: #D32F2F; color: white; font-weight: bold;")

        # Señales (Eventos simulados por ahora)
        self.btn_run_adelante.clicked.connect(lambda: self.comando_motor("RUN ADELANTE"))
        self.btn_stop.clicked.connect(lambda: self.comando_motor("STOP"))

        layout_motor.addWidget(self.btn_run_adelante)
        layout_motor.addWidget(self.btn_run_reversa)
        layout_motor.addWidget(self.btn_stop)
        grupo_motor.setLayout(layout_motor)

        # Añadir grupos al layout principal
        layout_principal.addWidget(grupo_conexion)
        layout_principal.addWidget(grupo_motor)
        layout_principal.addStretch() # Empuja todo hacia arriba

    def refresh_ports(self):
        """Busca puertos seriales disponibles en la Raspberry Pi / PC"""
        self.combo_puertos.clear()
        puertos = list(list_ports.comports())
        nombres_puertos = [p.device for p in puertos]
        
        if nombres_puertos:
            self.combo_puertos.addItems(nombres_puertos)
        else:
            self.combo_puertos.addItem("No se encontraron puertos")

    def connect_modbus(self):
        """Aquí irá la lógica Modbus que tenías en Tkinter"""
        puerto_seleccionado = self.combo_puertos.currentText()
        if "No se encontraron" in puerto_seleccionado:
            QMessageBox.warning(self, "Error", "No hay puertos disponibles para conectar.")
            return
        
        # TODO: En la Versión 0.3 aquí instanciaremos minimalmodbus.Instrument [cite: 31]
        QMessageBox.information(self, "Conexión", f"Intentando conectar a {puerto_seleccionado}...")

    def comando_motor(self, accion):
        # TODO: Aquí escribiremos en el registro P103 [cite: 23]
        print(f"Comando enviado al variador: {accion}")