# -*- coding: utf-8 -*-
import os
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPixmap, QFont, QColor, QPen
from PySide6.QtCore import Qt, QRect, Signal, QPoint, QPropertyAnimation
from ui.theme import (
    ERROR,
    SUCCESS,
    WINDOW,
)

class FlowArrowWidget(QWidget):
    def __init__(self, color_str, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.color = QColor(color_str)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.color)
        points = [QPoint(0, 4), QPoint(16, 8), QPoint(0, 12)]
        painter.drawPolygon(points)


class ProcessView(QWidget):
    motorClicked = Signal()
    setPointRequested = Signal(str, str, float) 

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(320) 
        
        self.vfd_data = {"freq_real": 0.0, "rpm_real": 0, "current": 0, "alarm": 0, "status": 0}
        
        # --- NUEVOS INDICADORES DE SENSORES FÍSICOS AGREGADOS ---
        self.sensores = {
            "P_VALV_01_OUT": {"nombre": "PE 01", "valor": 1013.0, "unidad": "Pa", "color": "#00FFFF", "pos": (0.90, 0.24)},
            "T_VALV_01_OUT": {"nombre": "HE 01", "valor": 50.5, "unidad": "%RH", "color": "#FFD700", "pos": (0.65, 0.48)},
            "T_PROD_OUT":    {"nombre": "TE 08", "valor": 25.0, "unidad": "°C", "color": "#FFC000", "pos": (0.08, 0.46)},
            "M1_HZ":         {"nombre": "M1 Freq", "valor": 0.0, "unidad": "Hz", "color": "#00BFFF", "pos": (0.09, 0.08)},
            "M1_RPM":        {"nombre": "M1 Vel", "valor": 0.0, "unidad": "RPM", "color": "#00BFFF", "pos": (0.09, 0.18)},
            "M1_AMP":        {"nombre": "M1 Corr", "valor": 0.0, "unidad": "A", "color": "#00BFFF", "pos": (0.09, 0.28)},
            "OPTICO_REV":    {"nombre": "VUELTAS", "valor": 0, "unidad": "rev", "color": "#FF00FF", "pos": (0.09, 0.72)},
            "PUERTA":        {"nombre": "PUERTA", "valor": "CERRADA", "unidad": "", "color": "#00FF00", "pos": (0.09, 0.82)},
            "M2_RPM":        {"nombre": "M2 Vel", "valor": 0.0, "unidad": "RPM", "color": "#FFFFFF", "pos": (0.90, 0.08)},
            "T_COND_01_OUT": {"nombre": "TT 01", "valor": 5.0, "unidad": "°C", "color": "#00FF00", "pos": (0.36, 0.57)},
            "P_COND_01_OUT": {"nombre": "PT 01", "valor": 10.5, "unidad": "bar", "color": "#00FFFF", "pos": (0.90, 0.52)},
            "T_COND_02_OUT": {"nombre": "TT 03", "valor": -20.0, "unidad": "°C", "color": "#00FF00", "pos": (0.34, 0.88)},
            "H_COND_02_OUT": {"nombre": "HT 01", "valor": 10.0, "unidad": "%RH", "color": "#FFD700", "pos": (0.51, 0.88)},
            "P_PUMP_IN":     {"nombre": "PT 02", "valor": 1013.0, "unidad": "Pa", "color": "#00FFFF", "pos": (0.11, 0.63)},
            "O2_NIVEL_PUMP": {"nombre": "AE 01", "valor": 20.9, "unidad": "%", "color": "#FFFF00", "pos": (0.90, 0.69)},
            "T_HEATER_OUT":  {"nombre": "TT 07", "valor": 45.0, "unidad": "°C", "color": "#00FF00", "pos": (0.80, 0.88)},
        }
        
        self.actuadores = {
            "M1_CAMARA": {"nombre": "M1 Tambor", "pos": (0.30, 0.53), "estado": False},
            "M2_VENT":   {"nombre": "M2 Vent.",  "pos": (0.70, 0.03), "estado": False},
            "BOMBA_VAC": {"nombre": "Bomba Vac", "pos": (0.81, 0.69), "estado": False},
            "HEATER":    {"nombre": "Heater",    "pos": (0.55, 0.68), "estado": False},
        }

        self.sensor_hitboxes = {}
        self.sensor_presionado = None

        self.image_path = os.path.join("resources", "hmi_background2.png")
        if os.path.exists(self.image_path):
            self.background_pixmap = QPixmap(self.image_path)
        else:
            self.background_pixmap = None

        self.flechas = []
        self.timer_blink = 0 
        self.frame_giro = 0 
        self.flow_active = False

        self.crear_flecha((0.78, 0.42), (0.25, 0.42), "#00BFFF", 2500)
        self.crear_flecha((0.70, 0.76), (0.70, 0.28), "#FF0000", 2000)
        self.crear_flecha((0.38, 0.80), (0.38, 0.94), "#FFFF00", 2000)

    def crear_flecha(self, start_ratio, end_ratio, color, duracion_ms):
        arrow = FlowArrowWidget(color, self)
        arrow.hide()
        anim = QPropertyAnimation(arrow, b"pos")
        anim.setDuration(duracion_ms)
        anim.setLoopCount(-1)
        self.flechas.append((arrow, anim, start_ratio, end_ratio))

    def _image_rect(self):
        return self.rect()

    def _motor_hitbox(self):
        image_rect = self._image_rect()
        return QRect(
            image_rect.x() + int(image_rect.width() * 0.43),
            image_rect.y() + int(image_rect.height() * 0.27),
            int(image_rect.width() * 0.27),
            int(image_rect.height() * 0.38),
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        image_rect = self._image_rect()
        for arrow, anim, start_ratio, end_ratio in self.flechas:
            was_running = anim.state() == QPropertyAnimation.Running
            if was_running:
                anim.stop()
            start = QPoint(
                image_rect.x() + int(image_rect.width() * start_ratio[0]),
                image_rect.y() + int(image_rect.height() * start_ratio[1]),
            )
            end = QPoint(
                image_rect.x() + int(image_rect.width() * end_ratio[0]),
                image_rect.y() + int(image_rect.height() * end_ratio[1]),
            )
            anim.setStartValue(start)
            anim.setEndValue(end)
            if was_running and self.flow_active:
                anim.start()

    def update_telemetry(self, data):
        self.vfd_data = data
        self.timer_blink = (self.timer_blink + 1) % 2 
        self.frame_giro = (self.frame_giro + 1) % 4 

        if "M1_HZ" in self.sensores: self.sensores["M1_HZ"]["valor"] = round(data.get("freq_real", 0), 1)
        if "M1_RPM" in self.sensores: self.sensores["M1_RPM"]["valor"] = round(data.get("rpm_real", 0), 0)
        if "M1_AMP" in self.sensores: self.sensores["M1_AMP"]["valor"] = round(data.get("current", 0), 1)
        
        # Actualizamos los sensores físicos en la UI
        if "OPTICO_REV" in self.sensores: 
            self.sensores["OPTICO_REV"]["valor"] = data.get("vueltas", 0)
            
        if "PUERTA" in self.sensores:
            estado_puerta = "CERRADA" if data.get("puerta_cerrada", True) else "ABIERTA"
            self.sensores["PUERTA"]["valor"] = estado_puerta
            self.sensores["PUERTA"]["color"] = (
                SUCCESS if estado_puerta == "CERRADA" else ERROR
            )

        motor_en_marcha = self.vfd_data.get('freq_real', 0) > 0.5
        self.actuadores["M1_CAMARA"]["estado"] = motor_en_marcha
        self.actuadores["M2_VENT"]["estado"] = motor_en_marcha
        self.actuadores["BOMBA_VAC"]["estado"] = motor_en_marcha

        self.flow_active = motor_en_marcha
        if motor_en_marcha:
            for arrow, anim, _, _ in self.flechas:
                if not arrow.isVisible(): arrow.show(); anim.start()
        else:
            for arrow, anim, _, _ in self.flechas:
                if arrow.isVisible(): arrow.hide(); anim.stop()
                    
        self.update() 

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(WINDOW))

        image_rect = self._image_rect()
        if self.background_pixmap:
            painter.drawPixmap(image_rect, self.background_pixmap)

        if self.vfd_data.get("alarm", 0) != 0:
            painter.setFont(QFont("DejaVu Sans", 9, QFont.Bold))
            rect_alarma = QRect(image_rect.x() + 4, image_rect.y() + 5, image_rect.width() - 8, 25)
            if self.timer_blink == 0:
                painter.setBrush(QColor("#D32F2F"))
                painter.setPen(Qt.NoPen)
                painter.drawRect(rect_alarma)
                painter.setPen(QPen(Qt.white))
                painter.drawText(rect_alarma, Qt.AlignCenter, f"ALERTA: FALLA EN VARIADOR [COD: {self.vfd_data['alarm']}]")
            else:
                painter.setBrush(QColor(WINDOW))
                painter.setPen(QPen(QColor("#D32F2F"), 2))
                painter.drawRect(rect_alarma)
                painter.setPen(QPen(QColor("#FCA5A5")))
                painter.drawText(rect_alarma, Qt.AlignCenter, "!!! REVISAR CODIGO DE ERROR EN ELIMEX !!!")

        self.sensor_hitboxes.clear()
        self._draw_floating_sensors(painter)
        self._draw_actuators(painter)

    def _draw_floating_sensors(self, painter):
        painter.setFont(QFont("DejaVu Sans", 7, QFont.Bold))
        metrics = painter.fontMetrics()
        for sensor_id, data in self.sensores.items():
            value = data.get("valor")
            value_text = f"{value:.1f}" if isinstance(value, float) else str(value) if value is not None else "--"
            if data["unidad"]:
                value_text = f"{value_text} {data['unidad']}"

            width = min(124, max(94, metrics.horizontalAdvance(data["nombre"]) + metrics.horizontalAdvance(value_text) + 16))
            height = 20
            x_ratio, y_ratio = data["pos"]
            x = int(x_ratio * self.width() - width / 2)
            y = int(y_ratio * self.height() - height / 2)
            rect = QRect(x, y, width, height)
            if rect.left() < 2:
                rect.moveLeft(2)
            if rect.right() >= self.width() - 2:
                rect.moveRight(self.width() - 3)
            if rect.top() < 2:
                rect.moveTop(2)
            if rect.bottom() >= self.height() - 2:
                rect.moveBottom(self.height() - 3)

            painter.setPen(QPen(QColor(data["color"]), 2))
            painter.setBrush(QColor(19, 23, 29, 220))
            painter.drawRoundedRect(rect, 3, 3)
            painter.setPen(QColor("#B7C0C9"))
            label_rect = rect.adjusted(5, 0, -2, 0)
            label_rect.setWidth(metrics.horizontalAdvance(data["nombre"]) + 2)
            value_rect = QRect(label_rect.right() + 2, rect.y(), rect.right() - label_rect.right() - 5, rect.height())
            painter.drawText(label_rect, Qt.AlignVCenter | Qt.AlignLeft, data["nombre"])
            painter.setPen(QColor("#F9FAFB"))
            painter.drawText(value_rect, Qt.AlignVCenter | Qt.AlignRight, value_text)
            self.sensor_hitboxes[sensor_id] = rect

    def _draw_actuators(self, painter):
        painter.setFont(QFont("DejaVu Sans", 6, QFont.Bold))
        for actuator in self.actuadores.values():
            active = actuator["estado"]
            x = int(actuator["pos"][0] * self.width())
            y = int(actuator["pos"][1] * self.height())
            painter.setPen(QPen(QColor("#111827"), 1))
            painter.setBrush(QColor(SUCCESS if active else "#707984"))
            painter.drawEllipse(QPoint(x, y), 4, 4)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            for sensor_id, rect in self.sensor_hitboxes.items():
                if rect.contains(event.pos()):
                    self.sensor_presionado = sensor_id
                    return

            if self._motor_hitbox().contains(event.pos()):
                self.motorClicked.emit()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or self.sensor_presionado is None:
            return

        sensor_id = self.sensor_presionado
        self.sensor_presionado = None
        rect = self.sensor_hitboxes.get(sensor_id)
        if rect is not None and rect.contains(event.pos()):
            data = self.sensores[sensor_id]
            value = data["valor"]
            if isinstance(value, (int, float)):
                self.setPointRequested.emit(sensor_id, data["nombre"], value)
