"""Exclusión mutua de las consultas Modbus desde las ventanas de diagnóstico."""

import threading


RS485_DIAGNOSTIC_LOCK = threading.Lock()
