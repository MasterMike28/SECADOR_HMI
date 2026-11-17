# -*- coding: utf-8 -*-
"""Controlador simulado del mapa PCF8575 -> ULN2803 -> módulo de relés.

Esta versión no importa smbus2 ni abre el bus I2C. Modela el registro de
salidas en memoria usando la polaridad configurada y conserva una API
intercambiable para una futura implementación física validada.
"""

import logging
import threading

import config


class PCF8575RelayController:
    """Simula los canales de relé definidos en ``config.RELAY_CHANNELS``."""

    simulation_only = True

    def __init__(self):
        self.address = config.PCF8575_ADDR
        self.bus_id = config.I2C_BUS
        self.bus = None
        self.state_mask = config.PCF8575_SAFE_STATE
        self._lock = threading.Lock()
        logging.info(
            "[SIMULACIÓN I2C] PCF8575 0x%02X inicializado en estado seguro 0x%04X",
            self.address,
            self.state_mask,
        )

    def _write_simulated_state(self):
        logging.info(
            "[SIMULACIÓN I2C] PCF8575 0x%02X <- 0x%04X",
            self.address,
            self.state_mask,
        )

    def set_relay(self, canal_idx, estado_bool):
        if canal_idx not in config.RELAY_CHANNELS:
            raise ValueError(f"Canal PCF8575 no configurado: {canal_idx}")
        if not isinstance(estado_bool, bool):
            raise TypeError("estado_bool debe ser bool.")

        with self._lock:
            bit_mask = 1 << canal_idx
            bit_high = estado_bool != config.PCF8575_RELAY_ACTIVE_LOW
            if bit_high:
                self.state_mask |= bit_mask
            else:
                self.state_mask &= ~bit_mask
            self.state_mask &= config.PCF8575_REGISTER_MASK
            self._write_simulated_state()
            return self.state_mask

    def apagar_todo(self):
        with self._lock:
            self.state_mask = config.PCF8575_SAFE_STATE
            self._write_simulated_state()
            return self.state_mask

    def relay_activo(self, canal_idx):
        if canal_idx not in config.RELAY_CHANNELS:
            raise ValueError(f"Canal PCF8575 no configurado: {canal_idx}")
        with self._lock:
            bit_is_high = bool(self.state_mask & (1 << canal_idx))
            return (
                not bit_is_high
                if config.PCF8575_RELAY_ACTIVE_LOW
                else bit_is_high
            )

    # Aliases para la interfaz y el controlador heredados.
    def set_canal(self, canal, activar):
        return self.set_relay(canal, activar)
