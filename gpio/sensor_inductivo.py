# -*- coding: utf-8 -*-
import logging
import config

try:
    from gpiozero import Button
    GPIOZERO_AVAILABLE = True
except ImportError:
    GPIOZERO_AVAILABLE = False
    logging.warning("[GPIO] gpiozero no detectado para inductivo. Modo SIMULACIÓN activo.")

class SensorPuertaInductivo:
    """Sensor inductivo configurado para detectar si la compuerta metálica está cerrada."""
    def __init__(self, pin=config.SENSOR_INDUCTIVO_GPIO, bounce_time=0.05):
        self.pin = pin
        self.sensor = None

        if GPIOZERO_AVAILABLE:
            try:
                # pull_up=True hace que al detectar metal y cerrar el circuito a GND, is_pressed sea True
                self.sensor = Button(self.pin, pull_up=True, bounce_time=bounce_time)
            except Exception as e:
                logging.error(f"[GPIO] Error en GPIO inductivo {self.pin}: {e}")

    def esta_cerrada(self) -> bool:
        """Devuelve True si el sensor detecta el metal de la puerta (Cerrada)."""
        if self.sensor and GPIOZERO_AVAILABLE:
            return self.sensor.is_pressed
        # En simulación de escritorio asumimos que está cerrada para poder probar
        return True