# -*- coding: utf-8 -*-
"""Secuencia de proceso ejecutada exclusivamente contra dispositivos simulados.

No se inicializa GPIO, I2C ni RS485. La máquina modela el orden y las
interdependencias de la receta para probar la UI y el flujo de estados. No es
un controlador de seguridad ni puede operar una liofilizadora real.
"""

import logging
import threading
import time

from PySide6.QtCore import QThread, Signal, Slot

import config
from gpio.pcf8575 import PCF8575RelayController
from modbus.rs485 import GtakeRS485Master


class _SimulatedInput:
    def __init__(self, value):
        self._value = value
        self.sensor = None

    def is_active(self):
        return self._value


class _SimulatedDoorSensor(_SimulatedInput):
    def esta_cerrada(self):
        return self.is_active()


class _SimulatedOpticalSensor(_SimulatedInput):
    def __init__(self):
        super().__init__(False)
        self._pulses = 0

    def obtener_vueltas(self):
        return self._pulses

    def reiniciar(self):
        self._pulses = 0

    def simular_marca(self):
        self._pulses += 1


class LiofilizadoraWorker(QThread):
    """Ejecuta la receta configurada en memoria, sin accionar hardware."""

    estado_cambiado = Signal(str)
    progreso_etapa = Signal(str, int, int)
    solicitar_confirmacion = Signal(str, str, float, str)
    alerta_emitida = Signal(str)

    simulation_only = True

    _CONFIRMATION_FIELDS = {
        config.EstadoLiofilizadora.WARMUP_BOMBA: (
            "duracion_s", "Tiempo de precalentamiento", "s"
        ),
        config.EstadoLiofilizadora.EVACUACION_VACIO: (
            "presion_objetivo_pa", "Presión objetivo", "Pa"
        ),
        config.EstadoLiofilizadora.INERTIZACION_N2: (
            "oxigeno_max_percent", "Límite máximo de oxígeno residual", "%"
        ),
        config.EstadoLiofilizadora.CONGELACION_IQF: (
            "temperatura_objetivo_c", "Temperatura objetivo", "°C"
        ),
        config.EstadoLiofilizadora.SECADO_PRIMARIO: (
            "temperatura_gas_objetivo_c", "Temperatura de gas", "°C"
        ),
        config.EstadoLiofilizadora.SECADO_SECUNDARIO: (
            "temperatura_gas_objetivo_c", "Temperatura de gas", "°C"
        ),
        config.EstadoLiofilizadora.ENFRIAMIENTO_FINAL: (
            "duracion_s", "Tiempo de enfriamiento", "s"
        ),
        config.EstadoLiofilizadora.POSICIONAMIENTO_TAMBOR: (
            "timeout_s", "Timeout de posicionamiento", "s"
        ),
    }

    _PROCESS_STATES = (
        config.EstadoLiofilizadora.WARMUP_BOMBA,
        config.EstadoLiofilizadora.EVACUACION_VACIO,
        config.EstadoLiofilizadora.INERTIZACION_N2,
        config.EstadoLiofilizadora.CONGELACION_IQF,
        config.EstadoLiofilizadora.SECADO_PRIMARIO,
        config.EstadoLiofilizadora.SECADO_SECUNDARIO,
        config.EstadoLiofilizadora.ENFRIAMIENTO_FINAL,
        config.EstadoLiofilizadora.POSICIONAMIENTO_TAMBOR,
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.outputs = PCF8575RelayController()
        self.vfd = GtakeRS485Master()
        self.sensor_puerta = _SimulatedDoorSensor(True)
        self.sensor_optico = _SimulatedOpticalSensor()

        self.ejecutando = False
        self.confirmado = False
        self.valor_confirmado = 0.0
        self.estado_actual = config.EstadoLiofilizadora.IDLE
        self.subestado_actual = None
        self._stop_requested = False
        self._confirmation_lock = threading.Lock()
        self._confirmed_value = None
        self._compressor_on = False
        self._last_compressor_off_at = None
        self._heater_on = False

    @Slot(bool, float)
    def recibir_respuesta_usuario(self, exito, valor):
        with self._confirmation_lock:
            self.confirmado = True
            self._confirmed_value = float(valor)
            self.valor_confirmado = float(valor)
            if not exito:
                self._stop_requested = True

    def run(self):
        self.ejecutando = True
        self._stop_requested = False
        self._set_state(config.EstadoLiofilizadora.PRE_CHECK)
        try:
            if not self._precheck_simulado():
                raise RuntimeError("Falló el autodiagnóstico simulado.")

            for state in self._PROCESS_STATES:
                if self._stop_requested:
                    return
                if not self._confirm_stage(state):
                    return
                self._set_state(state)
                self._apply_simulated_phase(state)
                if not self._run_simulated_duration(state):
                    return

                if state == config.EstadoLiofilizadora.EVACUACION_VACIO:
                    if not self._close_vacuum_safely():
                        return
                elif state == config.EstadoLiofilizadora.INERTIZACION_N2:
                    self.outputs.set_relay(config.RELAY_N2_VALVE, False)
                elif state == config.EstadoLiofilizadora.SECADO_PRIMARIO:
                    if config.MODO_DEMO_RAPIDO and not self._simulate_defrost_cycle():
                        return
                elif state == config.EstadoLiofilizadora.SECADO_SECUNDARIO:
                    self._set_heater(False)
                elif state == config.EstadoLiofilizadora.ENFRIAMIENTO_FINAL:
                    self._set_heater(False)
                    self._set_compressor(False)
                    self._stop_fan()

            if not self._stop_requested:
                self._set_state(config.EstadoLiofilizadora.COMPLETADO)
                self.estado_cambiado.emit("PROCESO FINALIZADO (SIMULACIÓN)")
        except Exception as exc:
            logging.exception("Fallo en la secuencia simulada.")
            self.alerta_emitida.emit(f"Falla de simulación: {exc}")
            self._set_state(config.EstadoLiofilizadora.FALLA_EMERGENCIA)
        finally:
            self._safe_shutdown_simulated()
            self.ejecutando = False

    def _precheck_simulado(self):
        state = config.EstadoLiofilizadora.PRE_CHECK
        self.progreso_etapa.emit(state.name, 0, 1)

        checks = (
            ("PCF8575 simulado", self.outputs.state_mask == config.PCF8575_SAFE_STATE),
            ("puerta simulada cerrada", self.sensor_puerta.esta_cerrada()),
            ("E-Stop simulado libre", True),
            ("VFD tambor simulado", self.vfd.simulation_only),
            ("VFD ventilador simulado", self.vfd.simulation_only),
        )
        failed = [name for name, result in checks if not result]
        if failed:
            self.alerta_emitida.emit(
                "Autodiagnóstico simulado falló: " + ", ".join(failed)
            )
            return False

        self.progreso_etapa.emit(state.name, 1, 1)
        return True

    def _confirm_stage(self, state):
        field, label, unit = self._CONFIRMATION_FIELDS[state]
        recipe = config.RECETA_DEFAULT[state]
        default_value = float(recipe[field])
        self.confirmado = False
        self._confirmed_value = None
        self.solicitar_confirmacion.emit(
            recipe["nombre"],
            label,
            default_value,
            unit,
        )

        while self.ejecutando and not self._stop_requested:
            with self._confirmation_lock:
                confirmed = self.confirmado
                accepted = self._confirmed_value
            if confirmed:
                if accepted is None:
                    self.alerta_emitida.emit(
                        f"Confirmación sin valor para {recipe['nombre']}."
                    )
                    return False
                self.valor_confirmado = accepted
                return True
            self.msleep(25)
        return False

    def _set_state(self, state):
        self.estado_actual = state
        self.estado_cambiado.emit(state.name)

    def _phase_duration(self, state):
        if not config.MODO_DEMO_RAPIDO:
            return 0
        fast_values = config.RECETA_DEMO_RAPIDO.get(state, {})
        return int(fast_values.get("duracion_s", fast_values.get("timeout_s", 5)))

    def _run_simulated_duration(self, state):
        duration_s = self._phase_duration(state)
        if duration_s <= 0:
            self.progreso_etapa.emit(state.name, 1, 1)
            return not self._stop_requested

        started_at = time.time()
        duration_ms = duration_s * 1000
        last_progress = -1
        while self.ejecutando and not self._stop_requested:
            elapsed_ms = min(int((time.time() - started_at) * 1000), duration_ms)
            progress = min(100, elapsed_ms * 100 // duration_ms)
            if progress != last_progress:
                self.progreso_etapa.emit(state.name, progress, 100)
                last_progress = progress

            if self._heater_on and not self._heater_interlock_ok():
                self._set_heater(False)
                raise RuntimeError(
                    "Calentador simulado desconectado por baja frecuencia de ventilador."
                )
            if elapsed_ms >= duration_ms:
                self.progreso_etapa.emit(state.name, 100, 100)
                return True
            self.msleep(100)
        return False

    def _apply_simulated_phase(self, state):
        recipe = config.RECETA_DEFAULT[state]
        self._set_fan_frequency(recipe.get("frecuencia_m2_hz", 0.0))
        self._set_drum_frequency(recipe.get("frecuencia_m1_hz", 0.0))

        if state == config.EstadoLiofilizadora.WARMUP_BOMBA:
            self.outputs.set_relay(config.RELAY_VACUUM_VALVE, False)
            self.outputs.set_relay(config.RELAY_VACUUM_PUMP, True)
        elif state == config.EstadoLiofilizadora.EVACUACION_VACIO:
            if not self.outputs.relay_activo(config.RELAY_VACUUM_PUMP):
                raise RuntimeError("Bomba simulada apagada al iniciar evacuación.")
            self.outputs.set_relay(config.RELAY_N2_VALVE, False)
            self.outputs.set_relay(config.RELAY_VACUUM_VALVE, True)
        elif state == config.EstadoLiofilizadora.INERTIZACION_N2:
            if self.outputs.relay_activo(config.RELAY_VACUUM_VALVE):
                raise RuntimeError("No se permite N2 con la válvula de vacío abierta.")
            if self.outputs.relay_activo(config.RELAY_VACUUM_PUMP):
                raise RuntimeError("No se permite N2 con la bomba de vacío succionando.")
            self.outputs.set_relay(config.RELAY_N2_VALVE, True)
        elif state == config.EstadoLiofilizadora.CONGELACION_IQF:
            self._set_compressor(True)
        elif state == config.EstadoLiofilizadora.SECADO_SECUNDARIO:
            if not self._heater_interlock_ok():
                raise RuntimeError("Interlock: ventilador por debajo de frecuencia mínima.")
            self._set_heater(True)
        elif state == config.EstadoLiofilizadora.ENFRIAMIENTO_FINAL:
            self._set_heater(False)
            self._set_compressor(False)
            self._set_fan_frequency(recipe["frecuencia_m2_hz"])
        elif state == config.EstadoLiofilizadora.POSICIONAMIENTO_TAMBOR:
            self.sensor_optico.reiniciar()
            self._set_drum_frequency(recipe["frecuencia_busqueda_m1_hz"])
            self.sensor_puerta._value = True
            self._set_drum_frequency(recipe["frecuencia_aproximacion_m1_hz"])
            self.sensor_optico.simular_marca()
            self._stop_drum()

    def _set_drum_frequency(self, frequency_hz):
        self.vfd.fijar_frecuencia(config.SLAVE_ID_TAMBOR, frequency_hz)
        if frequency_hz > 0:
            self.vfd.enviar_comando(config.SLAVE_ID_TAMBOR, config.CMD_RUN_FWD)
        else:
            self.vfd.enviar_comando(config.SLAVE_ID_TAMBOR, config.CMD_STOP)

    def _stop_drum(self):
        self.vfd.enviar_comando(config.SLAVE_ID_TAMBOR, config.CMD_STOP)

    def _set_fan_frequency(self, frequency_hz):
        self.vfd.fijar_frecuencia(config.SLAVE_ID_VENTILADOR, frequency_hz)
        if frequency_hz > 0:
            self.vfd.enviar_comando(config.SLAVE_ID_VENTILADOR, config.CMD_RUN_FWD)
        else:
            self.vfd.enviar_comando(config.SLAVE_ID_VENTILADOR, config.CMD_STOP)

    def _stop_fan(self):
        self.vfd.enviar_comando(config.SLAVE_ID_VENTILADOR, config.CMD_STOP)

    def _heater_interlock_ok(self):
        fan_telemetry = self.vfd.leer_telemetria(config.SLAVE_ID_VENTILADOR)
        return (
            fan_telemetry["freq_hz"]
            >= config.HEATER_MIN_FAN_FREQUENCY_HZ
        )

    def _set_heater(self, enabled):
        if enabled and not self._heater_interlock_ok():
            raise RuntimeError("Interlock de calentador no satisfecho.")
        self.outputs.set_relay(config.RELAY_INERT_GAS_HEATER, enabled)
        self._heater_on = enabled

    def _set_compressor(self, enabled):
        now = time.time()
        was_on = self._compressor_on
        if enabled and not self._compressor_on and self._last_compressor_off_at is not None:
            elapsed = now - self._last_compressor_off_at
            if elapsed < config.COMPRESSOR_MIN_OFF_TIME_S:
                raise RuntimeError(
                    "Interlock anti-ciclo corto del compresor simulado."
                )
        self.outputs.set_relay(config.RELAY_HEAT_PUMP_COMPRESSOR, enabled)
        self._compressor_on = enabled
        if was_on and not enabled:
            self._last_compressor_off_at = now

    def _close_vacuum_safely(self):
        self.outputs.set_relay(config.RELAY_VACUUM_VALVE, False)
        delay_ms = round(config.ANTI_SUCKBACK_DELAY_S * 1000)
        elapsed_ms = 0
        while elapsed_ms < delay_ms:
            step_ms = min(25, delay_ms - elapsed_ms)
            self.msleep(step_ms)
            elapsed_ms += step_ms
        self.outputs.set_relay(config.RELAY_VACUUM_PUMP, False)
        return not self._stop_requested

    def _simulate_defrost_cycle(self):
        self.subestado_actual = config.SubEstadoLiofilizadora.DEFROST_ALTERNADO
        self.estado_cambiado.emit(self.subestado_actual.value)
        recipe = config.RECETA_DEFAULT[self.subestado_actual]
        fast = config.RECETA_DEMO_RAPIDO.get(self.subestado_actual, {})
        active_s = fast.get("tiempo_activo_s", recipe["tiempo_activo_s"])
        drain_s = fast.get("tiempo_escurrido_s", recipe["tiempo_escurrido_s"])

        self.outputs.set_relay(config.RELAY_COOLER_1_DEFROST, False)
        self.outputs.set_relay(config.RELAY_COOLER_2_DEFROST, True)
        if not self._wait_simulated_seconds(active_s):
            return False
        self.outputs.set_relay(config.RELAY_CONDENSATE_DRAIN, True)
        if not self._wait_simulated_seconds(drain_s):
            return False
        self.outputs.set_relay(config.RELAY_CONDENSATE_DRAIN, False)
        self.outputs.set_relay(config.RELAY_COOLER_2_DEFROST, False)
        self.outputs.set_relay(config.RELAY_COOLER_1_DEFROST, True)
        self.subestado_actual = None
        return True

    def _wait_simulated_seconds(self, seconds):
        deadline = time.time() + seconds
        while self.ejecutando and not self._stop_requested:
            remaining_ms = int((deadline - time.time()) * 1000)
            if remaining_ms <= 0:
                return True
            self.msleep(min(100, remaining_ms))
        return False

    def _safe_shutdown_simulated(self):
        if self.outputs.relay_activo(config.RELAY_VACUUM_VALVE):
            self.outputs.set_relay(config.RELAY_VACUUM_VALVE, False)
            delay_ms = round(config.ANTI_SUCKBACK_DELAY_S * 1000)
            self.msleep(delay_ms)
        self.outputs.set_relay(config.RELAY_VACUUM_PUMP, False)
        self.outputs.set_relay(config.RELAY_N2_VALVE, False)
        self._set_heater(False)
        self._set_compressor(False)
        self.outputs.apagar_todo()
        self.vfd.comando_parada_todos()

    def detener(self):
        self._stop_requested = True
        self.ejecutando = False
        self.alerta_emitida.emit("Parada solicitada en simulación.")
        if not self.isRunning():
            self._safe_shutdown_simulated()
            self._set_state(config.EstadoLiofilizadora.FALLA_EMERGENCIA)
