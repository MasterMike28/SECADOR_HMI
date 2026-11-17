"""
=========================================================
CONFIGURACIÓN GENERAL DEL HMI Y HARDWARE
Proyecto : LIOFILIZADOR ATMOSFÉRICO UBB
Versión  : 1.0
=========================================================
"""
import os

# --- INFORMACIÓN DEL SISTEMA ---
APP_NAME = "LIOFILIZADOR ATMOSFÉRICO"
APP_VERSION = "1.0"

# --- RUTAS DE DIRECTORIOS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RESOURCES_DIR = os.path.join(BASE_DIR, "resources")
STYLES_DIR = os.path.join(BASE_DIR, "styles")

# --- PARÁMETROS DE PANTALLA ---
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 480
REFRESH_TIME = 100  # ms (Frecuencia de lectura)

# --- PALETA DE COLORES TIPO SCADA ---
BACKGROUND = "#111827"
HEADER = "#1F2937"
PANEL = "#374151"
TEXT = "#FFFFFF"

GREEN = "#10B981"
RED = "#EF4444"
YELLOW = "#F59E0B"
BLUE = "#3B82F6"
GRAY = "#6B7280"

# --- COMUNICACIÓN MODBUS RS485 (VARIADOR ELIMEX) ---
RS485_PORT = None    # Se asigna cuando el operador selecciona el puerto en CONFIG
SLAVE_ID = 8         # ID configurado en el parámetro P100 del Elimex
BAUDRATE = 9600

# ==========================================================
# REGISTROS MODBUS VERIFICADOS DEL VARIADOR ELIMEX
# ==========================================================
P00 = 40000
P01 = 40001
P102 = 40102
P103 = 40103         # Control de marcha (1 = RUN/FWD, 3 = REV, 0 = STOP)

REG_STATUS   = 40180  # Estado del Inversor (FC03)
REG_FREQ_SET = 40102  # Consigna de Frecuencia Target (FC06 / FC03)
REG_FREQ_OUT = 40182  # Frecuencia Real de Salida (FC03)
REG_CURRENT  = 40183  # Corriente de Salida A (FC03)
REG_DC_BUS   = 40184  # Voltaje Bus DC (FC03)
REG_TEMP     = 40185  # Temperatura Inversor (FC03)
REG_INPUTS   = 40188  # Estado de Entradas Digitales (FC03)
REG_ALARM    = 40189  # Código de Alarma / Falla (FC03)

# Aliases de compatibilidad
REG_ELIMEX_CONTROL   = P103
REG_ELIMEX_SET_FREQ  = P102
REG_ELIMEX_STATUS    = REG_STATUS
REG_ELIMEX_READ_FREQ = REG_FREQ_OUT
REG_ELIMEX_READ_CURR = REG_CURRENT
REG_ELIMEX_ALARM     = REG_ALARM

# --- GPIO Y EXPANSOR I2C (PCF8575) ---
SENSOR_GPIO = 23      # Sensor NPN (GPIO 23 / Pin 16)
I2C_BUS_ID = 1
PCF8575_I2C_ADDR = 0x20

# CANALES DE RELÉS EN PCF8575
CH_BOMBA_VACIO        = 0
CH_COMPRESOR          = 1
CH_CALENTADOR_PRIM    = 2
CH_CALENTADOR_SEC     = 3
CH_VALVULA_DEFROST    = 4
CH_VALVULA_VENTEO     = 5
