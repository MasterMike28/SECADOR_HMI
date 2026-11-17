# -*- coding: utf-8 -*-
import random
from PySide6.QtCore import QObject, Signal
import config

try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False

class SensorDAQ(QObject):
    """
    Gestor de Adquisición de Datos.
    Escalable: Se adapta automáticamente si está en MODO DEMO o MODO PRODUCCION.
    """
    telemetria_completa = Signal(dict)

    def __init__(self, modo="DEMO"):
        super().__init__()
        self.modo = modo
        self.pin_optico = config.PIN_SENSOR_OPTICO
        self.pin_inductivo = config.PIN_SENSOR_INDUCTIVO

        self.count_optico = 0
        self.count_inductivo = 0

        # Variables base para simulación en la DEMO
        self.presion_vacio = 101325.0
        self.temp_producto = 18.5

        self.setup_gpio()

    def setup_gpio(self):
        """Configura los sensores reales en la mesa (Óptico e Inductivo)"""
        if HAS_GPIO:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            
            # Pull-up interno para sensores NPN
            GPIO.setup(self.pin_optico, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(self.pin_inductivo, GPIO.IN, pull_up_down=GPIO.PUD_UP)

            # Interrupciones reales
            GPIO.add_event_detect(self.pin_optico, GPIO.FALLING, callback=self._cb_optico, bouncetime=20)
            GPIO.add_event_detect(self.pin_inductivo, GPIO.FALLING, callback=self._cb_inductivo, bouncetime=50)

    def _cb_optico(self, channel):
        self.count_optico += 1

    def _cb_inductivo(self, channel):
        self.count_inductivo += 1

    def read_all_sensors(self, estado_proceso="IDLE"):
        """
        Esta es la función que permite la escalabilidad del proyecto.
        Separa claramente la DEMO de la VERSIÓN FINAL.
        """
        data = {}

        if self.modo == "DEMO":
            # ---------------------------------------------------------
            # MODO DEMO: Hardware Parcial + Simulación
            # ---------------------------------------------------------
            # Leemos los contadores reales conectados a la Raspberry Pi
            data['OPTICO_PULSOS'] = self.count_optico
            data['INDUCTIVO_PULSOS'] = self.count_inductivo
            
            # Simulamos el resto de variables para que el SCADA se vea vivo
            self.temp_producto += random.uniform(-0.1, 0.1)
            data['T_PROD_OUT'] = f"{self.temp_producto:.1f} °C"
            data['PE_01'] = f"1013.2 mBar" # Simulación

        elif self.modo == "PRODUCCION":
            # ---------------------------------------------------------
            # MODO PRODUCCION (ESCALABILIDAD A FUTURO)
            # ---------------------------------------------------------
            # Aquí el futuro programador agregará las lecturas reales del Modbus
            # de los transmisores Dwyer, los Pt100 y el módulo de 8 canales 4-20mA.
            
            # data['PE_01'] = leer_presion_dwyer_real()
            # data['T_PROD_OUT'] = leer_pt100_real_modbus()
            
            # Por ahora, como es esqueleto, devolvemos lectura real de GPIO
            data['OPTICO_PULSOS'] = self.count_optico
            data['INDUCTIVO_PULSOS'] = self.count_inductivo

        return data

    def cleanup(self):
        if HAS_GPIO:
            GPIO.cleanup()
