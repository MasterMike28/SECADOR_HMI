# -*- coding: utf-8 -*-
import logging
import config

try:
    from gpiozero import Button
    GPIOZERO_AVAILABLE = True
except ImportError:
    GPIOZERO_AVAILABLE = False
    logging.warning("[GPIO] gpiozero no detectado. Modo SIMULACIÓN activo.")

class CameraOpticalSensor:
    def __init__(self, pin=config.SENSOR_GPIO, bounce_time=0.03):
        self.pin = pin
        self.contador_pulsos = 0
        self.sensor = None

        if GPIOZERO_AVAILABLE:
            try:
                self.sensor = Button(self.pin, pull_up=True, bounce_time=bounce_time)
                self.sensor.when_pressed = self._pulso_detectado
            except Exception as e:
                logging.error(f"[GPIO] Error en GPIO {self.pin}: {e}")

    def _pulso_detectado(self):
        self.contador_pulsos += 1
        logging.info(f"[SENSOR ÓPTICO] Pulso detectado! Total: {self.contador_pulsos}")

    def reiniciar(self):
        self.contador_pulsos = 0