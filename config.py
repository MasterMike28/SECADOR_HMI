# -*- coding: utf-8 -*-
"""Configuración central del HMI y del prototipo de liofilizadora.

Las asignaciones de GPIO, canales I2C y parámetros de comunicación son la
configuración de diseño y deben verificarse contra el cableado y el firmware
antes de accionar hardware real.
"""

import os
from enum import Enum, IntEnum


# ---------------------------------------------------------------------------
# Identidad de la aplicación y rutas
# ---------------------------------------------------------------------------
APP_NAME = "LIOFILIZADOR ATMOSFÉRICO"
APP_VERSION = "1.0"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RESOURCES_DIR = os.path.join(BASE_DIR, "resources")
STYLES_DIR = os.path.join(BASE_DIR, "styles")


# ---------------------------------------------------------------------------
# Pantalla y tema Dark Mode
# ---------------------------------------------------------------------------
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 480
REFRESH_TIME = 250  # ms; refresco de interfaz y telemetría.

BACKGROUND = "#111827"
HEADER = "#1F2937"
PANEL = "#374151"
TEXT = "#FFFFFF"

GREEN = "#10B981"
RED = "#EF4444"
YELLOW = "#F59E0B"
BLUE = "#3B82F6"
GRAY = "#6B7280"

COLOR_IDLE = GRAY
COLOR_RUNNING = BLUE
COLOR_WARNING = YELLOW
COLOR_COMPLETE = GREEN
COLOR_EMERGENCY = RED
COLOR_DISCONNECTED = RED
COLOR_CONNECTED = GREEN


# ---------------------------------------------------------------------------
# RS485 / Modbus RTU
# ---------------------------------------------------------------------------
RS485_PORT = "/dev/ttyUSB0"
BAUDRATE = 9600
RS485_BYTESIZE = 8
RS485_PARITY = "N"
# Valor inicial 8N1; confirmar en el manual/firmware del GK610 si requiere 8N2.
RS485_STOPBITS = 1
RS485_TIMEOUT = 0.15  # s
RS485_INTER_FRAME_DELAY = 0.05  # s

SLAVE_ID_TAMBOR = 1
SLAVE_ID_VENTILADOR = 2
SLAVE_ID_DAQ_420MA = 3
SLAVE_ID_PT100 = 4

# Diagnóstico del módulo EBYTE ME31-XDXX0800-485 según su manual V1.0.
EBYTE_PT100_DEFAULT_SLAVE_ID = 1
EBYTE_PT100_TEMP_REGISTER = 0x0190
EBYTE_PT100_CHANNEL_COUNT = 8
EBYTE_PT100_READ_FUNCTION_CODE = 4
EBYTE_PT100_SCALE_C_PER_COUNT = 0.1
EBYTE_PT100_SENSOR_FAULT_RAW = 0xFC19


# ---------------------------------------------------------------------------
# Variadores GTAKE GK610
# ---------------------------------------------------------------------------
REG_GK610_CONTROL = 0x2000
REG_GK610_FREQ_SET = 0x1000
REG_GK610_FREQ_OUT = 0x7000
REG_GK610_CURRENT = 0x7004
REG_GK610_DC_BUS = 0x7002

# Alias con prefijo GTAKE para uso de nuevos drivers.
REG_GTAKE_CONTROL = REG_GK610_CONTROL
REG_GTAKE_FREQ_SET = REG_GK610_FREQ_SET
REG_GTAKE_FREQ_OUT = REG_GK610_FREQ_OUT
REG_GTAKE_CURRENT = REG_GK610_CURRENT
REG_GTAKE_DC_BUS = REG_GK610_DC_BUS

CMD_RUN_FWD = 0x0001
CMD_RUN_REV = 0x0002
CMD_STOP = 0x0005
CMD_RESET = 0x0007

VFD_BASE_FREQUENCY_HZ = 50.0
VFD_MAX_FREQUENCY_HZ = 50.0
VFD_FREQUENCY_SCALE = 10000  # 100.00 % de la frecuencia base.
VFD_NORMALIZED_MIN = -10000
VFD_NORMALIZED_MAX = 10000
VFD_CURRENT_SCALE_A = 0.1
VFD_OUTPUT_FREQUENCY_SCALE_HZ = 0.01


# ---------------------------------------------------------------------------
# I2C y expansor PCF8575
# ---------------------------------------------------------------------------
I2C_BUS = 1
PCF8575_ADDR = 0x20
PCF8575_REGISTER_MASK = 0xFFFF
# La etapa PCF8575 -> ULN2803 activa el driver con nivel alto en su entrada.
# Nivel bajo mantiene apagado el ULN; confirmar el comportamiento final del
# módulo de relés y las cargas antes de habilitar una puesta en marcha real.
PCF8575_SAFE_STATE = 0x0000
PCF8575_RELAY_ACTIVE_LOW = False

RELAY_VACUUM_PUMP = 0
RELAY_VACUUM_VALVE = 1
RELAY_N2_VALVE = 2
RELAY_HEAT_PUMP_COMPRESSOR = 3
RELAY_INERT_GAS_HEATER = 4
RELAY_COOLER_1_DEFROST = 5
RELAY_COOLER_2_DEFROST = 6
RELAY_CONDENSATE_DRAIN = 7
RELAY_VAC_GAUGE_ISO = 8

RELAY_CHANNELS = {
    RELAY_VACUUM_PUMP: "Bomba de vacío",
    RELAY_VACUUM_VALVE: "Válvula de vacío",
    RELAY_N2_VALVE: "Válvula de inyección de N2",
    RELAY_HEAT_PUMP_COMPRESSOR: "Compresor de bomba de calor",
    RELAY_INERT_GAS_HEATER: "Calentador de gas inerte",
    RELAY_COOLER_1_DEFROST: "Conmutación / defrost enfriador 1",
    RELAY_COOLER_2_DEFROST: "Conmutación / defrost enfriador 2",
    RELAY_CONDENSATE_DRAIN: "Drenaje de condensado",
    RELAY_VAC_GAUGE_ISO: "Aislamiento de vacuómetro",
}


# ---------------------------------------------------------------------------
# Entradas GPIO BCM
# Las asignaciones son preliminares y se deben verificar físicamente.
# ---------------------------------------------------------------------------
GPIO_INDUCTIVO = 23
GPIO_OPTICO = 24
GPIO_ESTOP = 17
GPIO_DOOR_SW = 27
GPIO_PULL_UP = True

BOUNCE_OPTICO = 0.005  # s; preservar pulsos rápidos del tacómetro.
BOUNCE_INDUCTIVO = 0.010  # s.
BOUNCE_ESTOP = 0.050  # s; no sustituye un circuito E-Stop cableado.
BOUNCE_DOOR_SW = 0.050  # s.

# Alias para gpiozero y código existente.
GPIO_BOUNCE_OPTICO = BOUNCE_OPTICO
GPIO_BOUNCE_INDUCTIVO = BOUNCE_INDUCTIVO
GPIO_BOUNCE_ESTOP = BOUNCE_ESTOP
GPIO_BOUNCE_DOOR_SW = BOUNCE_DOOR_SW


# ---------------------------------------------------------------------------
# Umbrales de proceso e interlocks
# ---------------------------------------------------------------------------
VACUUM_CRITICAL_PA = 611.0
VACUUM_TARGET_MBAR = 6.11
VACUUM_STABILIZATION_S = 30
VACUUM_TIMEOUT_S = 900
VACUUM_PUMP_WARMUP_S = 600
ANTI_SUCKBACK_DELAY_S = 0.5

N2_TARGET_PRESSURE_MBAR = 1000.0
N2_GAUGE_ISOLATION_THRESHOLD_MBAR = 500.0
N2_TIMEOUT_S = 600
O2_TARGET_MIN_PERCENT = 0.62
O2_TARGET_MAX_PERCENT = 1.12
# Criterio preliminar acordado: menor concentración es mejor; aceptar O2 <= 1.12 %.
O2_ACCEPTANCE_MAX_PERCENT = O2_TARGET_MAX_PERCENT

IQF_TARGET_TEMPERATURE_C = -20.0
IQF_HOLD_TIME_S = 3600
IQF_REACH_TIMEOUT_S = 5400

PRIMARY_DRYING_GAS_TARGET_C = -5.0
PRIMARY_DRYING_GAS_MIN_C = -10.0
PRIMARY_DRYING_GAS_MAX_C = -5.0
PRIMARY_DRYING_MAX_TEMPERATURE_C = 0.0
PRIMARY_DRYING_DURATION_S = 14400

DEFROST_INTERVAL_S = 3600
DEFROST_ACTIVE_TIME_S = 300
DEFROST_DRAIN_TIME_S = 120

SECONDARY_DRYING_GAS_TARGET_C = 25.0
SECONDARY_DRYING_GAS_MAX_C = 40.0
SECONDARY_DRYING_HUMIDITY_TARGET_PERCENT = 15.0
SECONDARY_DRYING_DURATION_S = 7200

POST_HEATER_COOLDOWN_S = 45
DRUM_POSITION_TIMEOUT_S = 60
DRUM_POSITION_SEARCH_FREQUENCY_HZ = 8.0
DRUM_POSITION_APPROACH_FREQUENCY_HZ = 3.0

COMPRESSOR_MIN_OFF_TIME_S = 180
HEATER_MIN_FAN_FREQUENCY_HZ = 10.0


# ---------------------------------------------------------------------------
# Secuencia de estados principales y subestado paralelo de defrost
# La iteración de IntEnum conserva el orden operativo definido.
# ---------------------------------------------------------------------------
class EstadoLiofilizadora(IntEnum):
    IDLE = 0
    PRE_CHECK = 1
    WARMUP_BOMBA = 2
    EVACUACION_VACIO = 3
    INERTIZACION_N2 = 4
    CONGELACION_IQF = 5
    SECADO_PRIMARIO = 6
    SECADO_SECUNDARIO = 7
    ENFRIAMIENTO_FINAL = 8
    POSICIONAMIENTO_TAMBOR = 9
    COMPLETADO = 10
    FALLA_EMERGENCIA = 11


class SubEstadoLiofilizadora(Enum):
    DEFROST_ALTERNADO = "DEFROST_ALTERNADO"


# ---------------------------------------------------------------------------
# Receta inicial editable por el operador en el diálogo de cada etapa.
# Esta estructura contiene consignas sugeridas; el controlador debe validar
# límites e interlocks independientemente antes de aplicar cualquier valor.
# ---------------------------------------------------------------------------
RECETA_DEFAULT = {
    EstadoLiofilizadora.IDLE: {
        "nombre": "Reposo seguro",
        "frecuencia_m1_hz": 0.0,
        "frecuencia_m2_hz": 0.0,
        "estado_seguro_pcf8575": PCF8575_SAFE_STATE,
    },
    EstadoLiofilizadora.PRE_CHECK: {
        "nombre": "Autodiagnóstico",
        "duracion_s": None,
        "verificaciones": (
            "PCF8575 I2C 0x20",
            "GPIO configurados",
            "Puerta cerrada",
            "E-Stop libre",
            "Modbus VFD tambor ID 1",
            "Modbus VFD ventilador ID 2",
        ),
        "frecuencia_m1_hz": 0.0,
        "frecuencia_m2_hz": 0.0,
    },
    EstadoLiofilizadora.WARMUP_BOMBA: {
        "nombre": "Precalentamiento de bomba de vacío",
        "duracion_s": VACUUM_PUMP_WARMUP_S,
        "frecuencia_m1_hz": 0.0,
        "frecuencia_m2_hz": 0.0,
        "bomba_vacio": True,
        "valvula_vacio_abierta": False,
    },
    EstadoLiofilizadora.EVACUACION_VACIO: {
        "nombre": "Evacuación de vacío",
        "presion_objetivo_pa": VACUUM_CRITICAL_PA,
        "presion_objetivo_mbar": VACUUM_TARGET_MBAR,
        "estabilizacion_s": VACUUM_STABILIZATION_S,
        "timeout_s": VACUUM_TIMEOUT_S,
        "retardo_anti_suckback_s": ANTI_SUCKBACK_DELAY_S,
        "cerrar_valvula_antes_de_apagar_bomba": True,
        "frecuencia_m1_hz": 0.0,
        "frecuencia_m2_hz": 0.0,
        "valvula_vacio_abierta": True,
    },
    EstadoLiofilizadora.INERTIZACION_N2: {
        "nombre": "Inertización con nitrógeno",
        "presion_objetivo_mbar": N2_TARGET_PRESSURE_MBAR,
        "presion_aislamiento_vacuometro_mbar": N2_GAUGE_ISOLATION_THRESHOLD_MBAR,
        "oxigeno_max_percent": O2_ACCEPTANCE_MAX_PERCENT,
        "timeout_s": N2_TIMEOUT_S,
        "bomba_vacio_encendida": False,
        "valvula_vacio_abierta": False,
        "frecuencia_m1_hz": 5.0,
        "frecuencia_m2_inicio_hz": 0.0,
        "frecuencia_m2_post_umbral_hz": 15.0,
    },
    EstadoLiofilizadora.CONGELACION_IQF: {
        "nombre": "Congelación rápida IQF",
        "temperatura_objetivo_c": IQF_TARGET_TEMPERATURE_C,
        "mantenimiento_s": IQF_HOLD_TIME_S,
        "timeout_alcance_s": IQF_REACH_TIMEOUT_S,
        "frecuencia_m1_hz": 20.0,
        "frecuencia_m2_hz": 45.0,
        "enfriador_activo": 1,
    },
    EstadoLiofilizadora.SECADO_PRIMARIO: {
        "nombre": "Secado primario",
        "temperatura_gas_objetivo_c": PRIMARY_DRYING_GAS_TARGET_C,
        "temperatura_gas_min_c": PRIMARY_DRYING_GAS_MIN_C,
        "temperatura_gas_max_c": PRIMARY_DRYING_GAS_MAX_C,
        "duracion_s": PRIMARY_DRYING_DURATION_S,
        "frecuencia_m1_hz": 12.0,
        "frecuencia_m2_hz": 35.0,
        "frecuencia_minima_m2_para_calentador_hz": HEATER_MIN_FAN_FREQUENCY_HZ,
        "subestado": SubEstadoLiofilizadora.DEFROST_ALTERNADO,
    },
    EstadoLiofilizadora.SECADO_SECUNDARIO: {
        "nombre": "Secado secundario",
        "temperatura_gas_objetivo_c": SECONDARY_DRYING_GAS_TARGET_C,
        "temperatura_gas_max_c": SECONDARY_DRYING_GAS_MAX_C,
        "humedad_relativa_objetivo_percent": SECONDARY_DRYING_HUMIDITY_TARGET_PERCENT,
        "duracion_s": SECONDARY_DRYING_DURATION_S,
        "frecuencia_m1_hz": 10.0,
        "frecuencia_m2_hz": 30.0,
        "frecuencia_minima_m2_para_calentador_hz": HEATER_MIN_FAN_FREQUENCY_HZ,
    },
    EstadoLiofilizadora.ENFRIAMIENTO_FINAL: {
        "nombre": "Enfriamiento final",
        "duracion_s": POST_HEATER_COOLDOWN_S,
        "frecuencia_m1_hz": 5.0,
        "frecuencia_m2_hz": 40.0,
        "calentador_encendido": False,
        "compresor_encendido": False,
        "ventilador_encendido_durante_enfriamiento": True,
        "frecuencia_m2_al_final_hz": 0.0,
    },
    EstadoLiofilizadora.POSICIONAMIENTO_TAMBOR: {
        "nombre": "Posicionamiento del tambor",
        "timeout_s": DRUM_POSITION_TIMEOUT_S,
        "frecuencia_busqueda_m1_hz": DRUM_POSITION_SEARCH_FREQUENCY_HZ,
        "frecuencia_aproximacion_m1_hz": DRUM_POSITION_APPROACH_FREQUENCY_HZ,
        "frecuencia_m2_hz": 0.0,
        "gpio_inductivo_referencia": GPIO_INDUCTIVO,
        "gpio_optico_marca_parada": GPIO_OPTICO,
    },
    EstadoLiofilizadora.COMPLETADO: {
        "nombre": "Completado",
        "frecuencia_m1_hz": 0.0,
        "frecuencia_m2_hz": 0.0,
        "descarga_habilitada": True,
    },
    EstadoLiofilizadora.FALLA_EMERGENCIA: {
        "nombre": "Falla / emergencia",
        "frecuencia_m1_hz": 0.0,
        "frecuencia_m2_hz": 0.0,
        "estado_seguro_pcf8575": PCF8575_SAFE_STATE,
        "orden_apagado_vacio": (
            "cerrar_valvula_vacio",
            "esperar_confirmacion_cierre",
            "apagar_bomba_vacio",
        ),
        "requiere_rearme_manual": True,
    },
    SubEstadoLiofilizadora.DEFROST_ALTERNADO: {
        "nombre": "Desescarche alternado en línea",
        "intervalo_s": DEFROST_INTERVAL_S,
        "tiempo_activo_s": DEFROST_ACTIVE_TIME_S,
        "tiempo_escurrido_s": DEFROST_DRAIN_TIME_S,
        "cambiar_por_delta_de_presion_o_temperatura": True,
        "frecuencia_m1_hz": 12.0,
        "frecuencia_m2_hz": 35.0,
    },
}


# Los tiempos DEMO solo sirven para pruebas de interfaz/lógica en mesa.
# No omiten umbrales, interlocks ni verificaciones de seguridad.
MODO_DEMO_RAPIDO = False
DEMO_PERMITE_SALIDAS_HARDWARE = False
RECETA_DEMO_RAPIDO = {
    EstadoLiofilizadora.PRE_CHECK: {"duracion_s": 5},
    EstadoLiofilizadora.WARMUP_BOMBA: {"duracion_s": 10},
    EstadoLiofilizadora.EVACUACION_VACIO: {"timeout_s": 15, "estabilizacion_s": 5},
    EstadoLiofilizadora.INERTIZACION_N2: {"timeout_s": 15},
    EstadoLiofilizadora.CONGELACION_IQF: {"mantenimiento_s": 10, "timeout_alcance_s": 15},
    EstadoLiofilizadora.SECADO_PRIMARIO: {"duracion_s": 15},
    SubEstadoLiofilizadora.DEFROST_ALTERNADO: {
        "intervalo_s": 15,
        "tiempo_activo_s": 5,
        "tiempo_escurrido_s": 5,
    },
    EstadoLiofilizadora.SECADO_SECUNDARIO: {"duracion_s": 15},
    EstadoLiofilizadora.ENFRIAMIENTO_FINAL: {"duracion_s": 5},
    EstadoLiofilizadora.POSICIONAMIENTO_TAMBOR: {"timeout_s": 15},
}


# ---------------------------------------------------------------------------
# Alias de compatibilidad para la versión inicial del HMI.
# Los registros de estado y alarma no están incluidos en el mapa GK610
# suministrado; se dejan sin asignar hasta documentar su dirección real.
# ---------------------------------------------------------------------------
SLAVE_ID = SLAVE_ID_TAMBOR
I2C_BUS_ID = I2C_BUS
PCF8575_I2C_ADDR = PCF8575_ADDR

SENSOR_GPIO = GPIO_OPTICO
SENSOR_INDUCTIVO_GPIO = GPIO_DOOR_SW  # El módulo heredado lo usa como puerta.
PIN_SENSOR_OPTICO = GPIO_OPTICO
PIN_SENSOR_INDUCTIVO = GPIO_INDUCTIVO

CH_BOMBA_VACIO = RELAY_VACUUM_PUMP
CH_COMPRESOR = RELAY_HEAT_PUMP_COMPRESSOR
CH_CALENTADOR_PRIM = RELAY_INERT_GAS_HEATER
CH_CALENTADOR_SEC = RELAY_INERT_GAS_HEATER
CH_VALVULA_DEFROST = RELAY_COOLER_1_DEFROST
CH_VALVULA_VENTEO = RELAY_N2_VALVE

# Alias heredados para que las vistas actuales puedan importar la configuración.
P102 = REG_GK610_FREQ_SET
P103 = REG_GK610_CONTROL
REG_FREQ_SET = REG_GK610_FREQ_SET
REG_FREQ_OUT = REG_GK610_FREQ_OUT
REG_CURRENT = REG_GK610_CURRENT
REG_DC_BUS = REG_GK610_DC_BUS
REG_STATUS = None
REG_TEMP = None
REG_INPUTS = None
REG_ALARM = None

REG_ELIMEX_CONTROL = REG_GK610_CONTROL
REG_ELIMEX_SET_FREQ = REG_GK610_FREQ_SET
REG_ELIMEX_STATUS = REG_STATUS
REG_ELIMEX_READ_FREQ = REG_GK610_FREQ_OUT
REG_ELIMEX_READ_CURR = REG_GK610_CURRENT
REG_ELIMEX_ALARM = REG_ALARM
