# -*- coding: utf-8 -*-
import logging
import config

try:
    import minimalmodbus
    import serial
    MODBUS_AVAILABLE = True
except ImportError:
    MODBUS_AVAILABLE = False
    logging.warning("[MODBUS] minimalmodbus/pyserial no detectado. Modo SIMULACIÓN activo.")

class VariadorElimex:
    """Driver de control Modbus RTU para Variador Elimex."""
    def __init__(self, port=None, slave_id=config.SLAVE_ID, baudrate=config.BAUDRATE):
        self.port = port or getattr(config, 'RS485_PORT', None)
        self.slave_id = slave_id
        self.baudrate = baudrate
        self.instrument = None
        self.sentido_actual = "STOP"
        
        if self.port and MODBUS_AVAILABLE:
            try:
                self.instrument = minimalmodbus.Instrument(self.port, self.slave_id)
                self.instrument.serial.baudrate = self.baudrate
                self.instrument.serial.bytesize = 8
                self.instrument.serial.parity = serial.PARITY_NONE
                self.instrument.serial.stopbits = 1
                self.instrument.serial.timeout = 0.3
                self.instrument.mode = minimalmodbus.MODE_RTU
                self.instrument.clear_buffers_before_each_transaction = True
                self.instrument.close_port_after_each_call = False
                logging.info(f"[MODBUS] Variador Elimex conectado en {self.port} (ID: {self.slave_id})")
            except Exception as e:
                logging.error(f"[MODBUS] Error al conectar en puerto {self.port}: {e}")

    def comando_marcha_fwd(self):
        """Envia comando Adelante (1) al registro P103 (40103)."""
        self.sentido_actual = "FWD"
        self._escribir(config.P103, 1)

    def comando_marcha_rev(self):
        """Envia comando Reversa (3) al registro P103 (40103)."""
        self.sentido_actual = "REV"
        self._escribir(config.P103, 3)

    def comando_parada(self):
        """Envia comando Detener (0) al registro P103 (40103)."""
        self.sentido_actual = "STOP"
        self._escribir(config.P103, 0)

    def fijar_frecuencia_hz(self, hz: float):
        """Envia consigna de velocidad al registro REG_FREQ_SET (40181) escalado x100."""
        valor_modbus = int(hz * 100)
        logging.info(f"[MODBUS] Ajustando frecuencia a {hz} Hz -> Reg {config.REG_FREQ_SET} = {valor_modbus}")
        self._escribir(config.REG_FREQ_SET, valor_modbus)

    def _escribir(self, registro: int, valor: int) -> bool:
        """Escribe un registro de 16 bits usando la función Modbus FC06."""
        if self.instrument and MODBUS_AVAILABLE:
            try:
                self.instrument.write_register(registro, valor, number_of_decimals=0, functioncode=6)
                logging.info(f"[MODBUS OK] Escritura Reg {registro} <- {valor}")
                return True
            except Exception as e:
                logging.error(f"[MODBUS ERROR] Fallo al escribir Reg {registro}: {e}")
                return False
        else:
            logging.info(f"[SIMULACIÓN MODBUS] Reg {registro} <- {valor}")
            return True
