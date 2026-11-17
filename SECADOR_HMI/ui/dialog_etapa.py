# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                               QLabel, QPushButton, QDoubleSpinBox, QFrame)
from PySide6.QtCore import Qt

class EtapaConfirmDialog(QDialog):
    """Ventana emergente de confirmación de parámetros para el Liofilizador Atmosférico."""
    def __init__(self, nombre_etapa, parametro_nombre, valor_defecto, unidad, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Confirmar: {nombre_etapa}")
        self.setFixedSize(420, 260)
        
        # Estilo Industrial SCADA
        self.setStyleSheet("""
            QDialog {
                background-color: #111827;
                border: 2px solid #374151;
                border-radius: 8px;
            }
            QLabel {
                color: #F3F4F6;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QFrame#card {
                background-color: #1F2937;
                border: 1px solid #4B5563;
                border-radius: 6px;
            }
            QDoubleSpinBox {
                background-color: #111827;
                color: #10B981;
                font-size: 20px;
                font-weight: bold;
                border: 1px solid #10B981;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton {
                font-size: 13px;
                font-weight: bold;
                padding: 10px;
                border-radius: 6px;
                color: white;
            }
            QPushButton#btnConfirm {
                background-color: #10B981;
                border: none;
            }
            QPushButton#btnConfirm:hover {
                background-color: #059669;
            }
            QPushButton#btnCancel {
                background-color: #EF4444;
                border: none;
            }
            QPushButton#btnCancel:hover {
                background-color: #DC2626;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        # Encabezado con título de la etapa
        lbl_titulo = QLabel(f"ETAPA: {nombre_etapa.upper()}")
        lbl_titulo.setStyleSheet("font-size: 15px; font-weight: bold; color: #F59E0B;")
        lbl_titulo.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_titulo)

        # Tarjeta central
        card = QFrame()
        card.setObjectName("card")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)

        lbl_param = QLabel(f"{parametro_nombre}:")
        lbl_param.setStyleSheet("font-size: 13px; font-weight: bold;")
        
        self.spin_valor = QDoubleSpinBox()
        self.spin_valor.setRange(-100.0, 2000.0)
        self.spin_valor.setValue(valor_defecto)
        self.spin_valor.setAlignment(Qt.AlignCenter)

        lbl_unit = QLabel(unidad)
        lbl_unit.setStyleSheet("font-size: 14px; font-weight: bold; color: #9CA3AF;")

        card_layout.addWidget(lbl_param)
        card_layout.addWidget(self.spin_valor)
        card_layout.addWidget(lbl_unit)
        
        layout.addWidget(card)

        # Botones inferiores
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_cancelar = QPushButton("ABORTAR")
        self.btn_cancelar.setObjectName("btnCancel")
        self.btn_confirmar = QPushButton("CONFIRMAR E INICIAR")
        self.btn_confirmar.setObjectName("btnConfirm")

        self.btn_cancelar.clicked.connect(self.reject)
        self.btn_confirmar.clicked.connect(self.accept)

        btn_layout.addWidget(self.btn_cancelar)
        btn_layout.addWidget(self.btn_confirmar)
        
        layout.addLayout(btn_layout)

    def obtener_valor(self) -> float:
        return self.spin_valor.value()
