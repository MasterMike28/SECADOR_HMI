# -*- coding: utf-8 -*-
import logging
import config

try:
    import smbus2
    I2C_AVAILABLE = True
except ImportError:
    I2C_AVAILABLE = False
    logging.warning("[PCF8575] smbus2 no detectado. Modo SIMULACIÓN activo.")

class PCF8575OutputController:
    """
    Maneja las 16 salidas a través del PCF8575 y ULN2803.
    Recuerda: Los ULN2803 invierten la lógica. 
    Bit 0 = Relé ON | Bit 1 = Relé OFF.
    """
    def __init__(self, bus_id=config.I2C_BUS_ID, address=config.PCF8575_I2C_ADDR):
        self.address = address
        self.state_mask = 0xFFFF  # Todos los relés apagados
        self.bus = None

        if I2C_AVAILABLE:
            try:
                self.bus = smbus2.SMBus(bus_id)
                self.apagar_todo()
            except Exception as e:
                logging.error(f"[PCF8575] Error al conectar bus I2C: {e}")

    def set_canal(self, canal: int, activar: bool):
        if not (0 <= canal <= 15):
            return

        if activar:
            self.state_mask &= ~(1 << canal) # 0 activa relé vía ULN
        else:
            self.state_mask |= (1 << canal)  # 1 apaga relé vía ULN

        self._escribir()

    def apagar_todo(self):
        self.state_mask = 0xFFFF
        self._escribir()

    def _escribir(self):
        if self.bus and I2C_AVAILABLE:
            try:
                byte_low = self.state_mask & 0xFF
                byte_high = (self.state_mask >> 8) & 0xFF
                self.bus.write_i2c_block_data(self.address, byte_low, [byte_high])
            except Exception as e:
                logging.error(f"[PCF8575] Error escritura I2C: {e}")
        else:
            logging.info(f"[SIMULACIÓN PCF8575] Estado bits: {self.state_mask:016b}")