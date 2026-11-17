# -*- coding: utf-8 -*-
"""Matriz preliminar de instrumentación de la planta piloto.

TAG, posición y rangos proceden de los documentos compartidos. Las opciones de
señal, modelo y rango que aún no están aprobadas se identifican explícitamente
como alternativas; no hay canales DAQ ni esclavos Modbus asignados aquí.
Este módulo solo describe señales y no inicializa ni lee hardware.
"""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class InstrumentTag:
    tag: str
    variable: str
    position: str
    signal_type: str
    range_text: str
    units: str
    acquisition: str
    notes: str
    channel: Optional[str] = None
    modbus_slave_id: Optional[int] = None
    modbus_register: Optional[int] = None


_POSITIONS = (2, 4, 6, 7, 8, 9, 11, 12)

_humidity_and_temperature = []
for position in _POSITIONS:
    _humidity_and_temperature.extend((
        InstrumentTag(
            tag=f"HT-{position:02d}",
            variable="Humedad relativa",
            position=str(position),
            signal_type="Pendiente: 4-20 mA, 0-1 V o interfaz digital",
            range_text="0 a 100",
            units="%RH",
            acquisition="DAQ por definir",
            notes=(
                "Propuesta: 4 a 8 sondas HR/T industriales. Confirmar modelo, "
                "salida, montaje y protección contra condensación."
            ),
        ),
        InstrumentTag(
            tag=f"TT-{position:02d}",
            variable="Temperatura",
            position=str(position),
            signal_type="Pendiente: Pt100/Pt1000 o transmisor 4-20 mA",
            range_text="-30 a 80",
            units="°C",
            acquisition="DAQ RTD/analógico por definir",
            notes=(
                "Rango preliminar de la propuesta; confirmar clase, conexión, "
                "transmisor y calibración."
            ),
        ),
    ))


INSTRUMENTATION: Tuple[InstrumentTag, ...] = tuple(_humidity_and_temperature) + (
    InstrumentTag(
        tag="PT-VAC-01",
        variable="Presión absoluta de cámara",
        position="2",
        signal_type="4-20 mA o RS485 (pendiente de selección)",
        range_text="0 a 10 mbar abs preferido; alternativas 0-20 o 0-100",
        units="mbar abs",
        acquisition="DAQ 4-20 mA o Modbus por definir",
        notes=(
            "La consigna preliminar es ~6.11 mbar abs. Confirmar resolución, "
            "sobrepresión admisible y aislamiento durante la presurización."
        ),
    ),
    InstrumentTag(
        tag="O2-01",
        variable="Oxígeno residual",
        position="2",
        signal_type="4-20 mA o Modbus (pendiente de selección)",
        range_text="0 a 5 % preferido; alternativa 0-10 o 0-25",
        units="% O2",
        acquisition="DAQ 4-20 mA o Modbus por definir",
        notes=(
            "Gas de inertización: N2. Criterio acordado para simulación: "
            "O2 <= 1.12 %. Calibración con aire y N2 por definir."
        ),
    ),
    InstrumentTag(
        tag="TS-01",
        variable="Tacómetro del ventilador",
        position="1",
        signal_type="Pulso NPN/PNP; acondicionamiento por definir",
        range_text="Pendiente de RPM máximas",
        units="RPM",
        acquisition="Entrada de pulsos aislada por definir",
        notes="Definir número de pulsos por vuelta y montaje mecánico.",
    ),
    InstrumentTag(
        tag="TS-02",
        variable="Tacómetro de cámara rotatoria",
        position="3",
        signal_type="Pulso NPN/PNP; acondicionamiento por definir",
        range_text="Pendiente de RPM máximas",
        units="RPM",
        acquisition="Entrada de pulsos aislada por definir",
        notes="Definir número de pulsos por vuelta y montaje mecánico.",
    ),
    InstrumentTag(
        tag="FT-01",
        variable="Caudal de gas de recirculación",
        position="2",
        signal_type="Presión diferencial 4-20 mA; caudal calculado",
        range_text="500 a 750",
        units="m³/h",
        acquisition="DPT-FT-01; entrada analógica por definir",
        notes=(
            "Pitot promediador para tubería 6 in (ID aprox. 141 mm). Usar "
            "curva del fabricante/calibración; no asumir constante Q=sqrt(DP)."
        ),
    ),
    InstrumentTag(
        tag="PG-05",
        variable="Presión indicada por manómetro local",
        position="5",
        signal_type="Indicación analógica local, sin salida eléctrica definida",
        range_text="Pendiente según fluido y presión esperada",
        units="Pendiente",
        acquisition="Lectura local; no asignar a DAQ por ahora",
        notes="Confirmar si corresponde al circuito de gas o refrigeración.",
    ),
    InstrumentTag(
        tag="PG-10",
        variable="Presión indicada por manómetro local",
        position="10",
        signal_type="Indicación analógica local, sin salida eléctrica definida",
        range_text="Pendiente según fluido y presión esperada",
        units="Pendiente",
        acquisition="Lectura local; no asignar a DAQ por ahora",
        notes="Confirmar si corresponde al circuito de gas o refrigeración.",
    ),
    InstrumentTag(
        tag="PG-13",
        variable="Presión indicada por manómetro local",
        position="13",
        signal_type="Indicación analógica local, sin salida eléctrica definida",
        range_text="Pendiente según fluido y presión esperada",
        units="Pendiente",
        acquisition="Lectura local; no asignar a DAQ por ahora",
        notes="Confirmar si corresponde al circuito de gas o refrigeración.",
    ),
)

# Medición diferencial adicional de diagnóstico propuesta en la cotización;
# no forma parte del conteo original de 24 instrumentos.
OPTIONAL_INSTRUMENTATION: Tuple[InstrumentTag, ...] = (
    InstrumentTag(
        tag="DPT-CAM-01",
        variable="Presión diferencial de cámara",
        position="Entrada y salida de cámara",
        signal_type="4-20 mA",
        range_text="0 a 250 Pa preferido; alternativa 0-500 Pa",
        units="Pa",
        acquisition="DAQ analógico por definir",
        notes="Medición de diagnóstico; rango final sujeto a validación.",
    ),
)


def validate_instrumentation():
    """Comprueba unicidad de TAG y que la matriz base conserve sus 24 puntos."""
    tags = [instrument.tag for instrument in INSTRUMENTATION]
    if len(tags) != 24:
        raise ValueError(f"Se esperaban 24 instrumentos base; hay {len(tags)}.")
    if len(set(tags)) != len(tags):
        raise ValueError("Hay TAG duplicados en la matriz de instrumentación.")
    return True


validate_instrumentation()
