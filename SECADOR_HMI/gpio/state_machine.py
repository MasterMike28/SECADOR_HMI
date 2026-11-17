# -*- coding: utf-8 -*-
import time
import logging
from PySide6.QtCore import QThread, Signal, QEventLoop
import config

from gpio.pcf8575 import PCF8575OutputController
from modbus.rs485 import VariadorElimex

class LiofilizadoraWorker(QThread):
    # Señal enviada a la Ventana Principal para pedir confirmación visual
    solicitar_confirmacion = Signal(str, str, float, str) # etapa, parametro, valor, unidad
    estado_cambiado = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.outputs = PCF8575OutputController()
        self.vfd = VariadorElimex()
        self.ejecutando = False
        self.confirmado = False
        self.valor_confirmado = 0.0

    def recibir_respuesta_usuario(self, exito: bool, valor: float):
        """Llamado desde la GUI cuando presionas Aceptar o Cancelar en la ventana."""
        self.confirmado = exito
        self.valor_confirmado = valor

    def run(self):
        self.ejecutando = True

        # --- ETAPA 1: CONGELACIÓN IQF ---
        if not self._esperar_confirmacion_gui("Congelación IQF", "Temperatura Objetivo", -40.0, "°C"):
            return

        self.estado_cambiado.emit("ETAPA: CONGELACIÓN EN PROCESO")
        self.outputs.set_canal(config.CH_COMPRESOR, True)
        self.vfd.arrancar()
        time.sleep(3) # Simulación de tiempo de congelación

        # --- ETAPA 2: GENERACIÓN DE VACÍO ---
        if not self._esperar_confirmacion_gui("Generación de Vacío", "Presión Máxima", 0.85, "mBar"):
            return

        self.estado_cambiado.emit("ETAPA: VACÍO EN PROCESO")
        self.outputs.set_canal(config.CH_BOMBA_VACIO, True)
        time.sleep(3)

        # --- ETAPA 3: SECADO PRIMARIO ---
        if not self._esperar_confirmacion_gui("Secado Primario", "Temperatura Calentador", 20.0, "°C"):
            return

        self.estado_cambiado.emit("ETAPA: SECADO PRIMARIO EN PROCESO")
        self.outputs.set_canal(config.CH_CALENTADOR_PRIM, True)
        time.sleep(3)
        self.outputs.set_canal(config.CH_CALENTADOR_PRIM, False)

        # --- ETAPA 4: DEFROST ---
        if not self._esperar_confirmacion_gui("Descongelamiento", "Tiempo de Válvula", 300.0, "seg"):
            return

        self.estado_cambiado.emit("ETAPA: DEFROST EN PROCESO")
        self.outputs.apagar_todo()
        self.vfd.detener()
        self.outputs.set_canal(config.CH_VALVULA_DEFROST, True)
        time.sleep(3)
        self.outputs.set_canal(config.CH_VALVULA_DEFROST, False)

        self.estado_cambiado.emit("PROCESO FINALIZADO EXITOSAMENTE")
        self.ejecutando = False

    def _esperar_confirmacion_gui(self, etapa, parametro, valor_defecto, unidad) -> bool:
        """Pausa el hilo y solicita la apertura de la ventana emergente en la GUI."""
        self.confirmado = False
        self.solicitar_confirmacion.emit(etapa, parametro, valor_defecto, unidad)

        # Esperar respuesta del usuario
        while self.ejecutando and not self.confirmado:
            time.sleep(0.1)

        if not self.ejecutando:
            self.outputs.apagar_todo()
            self.vfd.detener()
            self.estado_cambiado.emit("PROCESO ABORTADO")
            return False

        logging.info(f"[MÁQUINA DE ESTADOS] Etapa '{etapa}' confirmada con valor: {self.valor_confirmado} {unidad}")
        return True

    def detener(self):
        self.ejecutando = False
        self.outputs.apagar_todo()
        self.vfd.detener()