# -*- coding: utf-8 -*-
"""Master Modbus simulado para variadores GTAKE GK610.

Esta implementación no importa minimalmodbus, no abre puertos seriales y no
puede enviar comandos al hardware. Conserva una API pequeña para facilitar la
sustitución futura por un transporte real, después de validar el equipo.
"""

import logging
import math
import threading
import time

import config


class GtakeRS485Master:
    """Simula los dos VFD GK610 sin acceder al puerto RS485 físico."""

    simulation_only = True

    def __init__(self, port=None):
        self.port = port or config.RS485_PORT
        self.instrument = None
        self.sentido_actual = "STOP"
        self._lock = threading.Lock()
        self._slaves = {
            config.SLAVE_ID_TAMBOR: self._new_slave_state(),
            config.SLAVE_ID_VENTILADOR: self._new_slave_state(),
        }

    @staticmethod
    def _new_slave_state():
        return {
            "command": config.CMD_STOP,
            "frequency_percent": 0,
            "frequency_hz": 0.0,
            "current_a": 0.0,
            "dc_bus_v": 0.0,
        }

    def _get_slave(self, slave_id):
        try:
            return self._slaves[slave_id]
        except KeyError as exc:
            raise ValueError(f"Esclavo VFD no configurado para simulación: {slave_id}") from exc

    def _finish_simulated_frame(self):
        time.sleep(config.RS485_INTER_FRAME_DELAY)

    def enviar_comando(self, slave_id, comando):
        valid_commands = (
            config.CMD_RUN_FWD,
            config.CMD_RUN_REV,
            config.CMD_STOP,
            config.CMD_RESET,
        )
        if comando not in valid_commands:
            raise ValueError(f"Código de mando GK610 no admitido: {comando}")

        self._lock.acquire()
        try:
            state = self._get_slave(slave_id)
            state["command"] = comando
            if comando in (config.CMD_STOP, config.CMD_RESET):
                state["frequency_hz"] = 0.0
                if comando == config.CMD_RESET:
                    state["current_a"] = 0.0
            if slave_id == config.SLAVE_ID_TAMBOR:
                self.sentido_actual = {
                    config.CMD_RUN_FWD: "FWD",
                    config.CMD_RUN_REV: "REV",
                    config.CMD_STOP: "STOP",
                    config.CMD_RESET: "STOP",
                }[comando]
            logging.info(
                "[SIMULACIÓN RS485] esclavo=%s registro=0x%04X comando=%s",
                slave_id,
                config.REG_GTAKE_CONTROL,
                comando,
            )
        finally:
            try:
                self._finish_simulated_frame()
            finally:
                self._lock.release()

    def fijar_frecuencia(self, slave_id, freq_hz):
        if not isinstance(freq_hz, (int, float)) or not math.isfinite(freq_hz):
            raise ValueError("La frecuencia debe ser un número finito.")
        if abs(freq_hz) > config.VFD_BASE_FREQUENCY_HZ:
            raise ValueError(
                f"Frecuencia fuera de rango: debe estar entre "
                f"{-config.VFD_BASE_FREQUENCY_HZ} y {config.VFD_BASE_FREQUENCY_HZ} Hz."
            )

        normalized = round(
            freq_hz * config.VFD_FREQUENCY_SCALE / config.VFD_BASE_FREQUENCY_HZ
        )
        if not config.VFD_NORMALIZED_MIN <= normalized <= config.VFD_NORMALIZED_MAX:
            raise ValueError("La consigna normalizada queda fuera del rango GK610.")

        self._lock.acquire()
        try:
            state = self._get_slave(slave_id)
            state["frequency_percent"] = normalized
            state["frequency_hz"] = (
                abs(normalized)
                * config.VFD_BASE_FREQUENCY_HZ
                / config.VFD_FREQUENCY_SCALE
            )
            logging.info(
                "[SIMULACIÓN RS485] esclavo=%s registro=0x%04X frecuencia=%s Hz consigna=%s",
                slave_id,
                config.REG_GTAKE_FREQ_SET,
                freq_hz,
                normalized,
            )
            return normalized
        finally:
            try:
                self._finish_simulated_frame()
            finally:
                self._lock.release()

    def leer_telemetria(self, slave_id):
        self._lock.acquire()
        try:
            state = self._get_slave(slave_id)
            frequency_hz = state["frequency_hz"]
            if state["command"] in (config.CMD_STOP, config.CMD_RESET):
                frequency_hz = 0.0
            return {
                "freq_hz": frequency_hz,
                "current_a": state["current_a"],
                "dc_bus_v": state["dc_bus_v"],
                "freq_real": frequency_hz,
                "current": state["current_a"],
                "simulado": True,
            }
        finally:
            try:
                self._finish_simulated_frame()
            finally:
                self._lock.release()

    def conectar(self, port=None):
        """Impide que la UI actual abra el puerto durante la etapa simulada."""
        logging.warning(
            "[SIMULACIÓN RS485] Conexión física deshabilitada; puerto solicitado: %s",
            port or self.port,
        )
        return False

    def comando_marcha_fwd(self):
        self.enviar_comando(config.SLAVE_ID_TAMBOR, config.CMD_RUN_FWD)

    def comando_marcha_rev(self):
        self.enviar_comando(config.SLAVE_ID_TAMBOR, config.CMD_RUN_REV)

    def comando_parada(self):
        self.enviar_comando(config.SLAVE_ID_TAMBOR, config.CMD_STOP)

    def comando_parada_todos(self):
        for slave_id in (config.SLAVE_ID_TAMBOR, config.SLAVE_ID_VENTILADOR):
            self.enviar_comando(slave_id, config.CMD_STOP)

    def fijar_frecuencia_hz(self, hz):
        return self.fijar_frecuencia(config.SLAVE_ID_TAMBOR, hz)

    def write_register(self, register, value, number_of_decimals=0, functioncode=6):
        """Adaptador heredado, limitado a registros de escritura conocidos."""
        if register == config.REG_GTAKE_CONTROL:
            self.enviar_comando(config.SLAVE_ID_TAMBOR, int(value))
            return
        if register == config.REG_GTAKE_FREQ_SET:
            frequency_hz = (
                float(value)
                * config.VFD_BASE_FREQUENCY_HZ
                / config.VFD_FREQUENCY_SCALE
            )
            self.fijar_frecuencia(config.SLAVE_ID_TAMBOR, frequency_hz)
            return
        raise ValueError(f"Registro GK610 no disponible para escritura simulada: {register!r}")

    def read_register(self, register, number_of_decimals=0, functioncode=3):
        telemetry = self.leer_telemetria(config.SLAVE_ID_TAMBOR)
        register_values = {
            config.REG_GTAKE_FREQ_OUT: round(
                telemetry["freq_hz"] / config.VFD_OUTPUT_FREQUENCY_SCALE_HZ
            ),
            config.REG_GTAKE_CURRENT: round(
                telemetry["current_a"] / config.VFD_CURRENT_SCALE_A
            ),
            config.REG_GTAKE_DC_BUS: telemetry["dc_bus_v"],
        }
        try:
            return register_values[register]
        except KeyError as exc:
            raise ValueError(
                f"Registro GK610 sin dato de telemetría simulado: {register!r}"
            ) from exc
