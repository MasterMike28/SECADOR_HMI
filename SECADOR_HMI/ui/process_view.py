# -*- coding: utf-8 -*-
import os
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPixmap, QFont, QColor, QPen
from PySide6.QtCore import Qt, QRect, Signal, QPoint, QPropertyAnimation

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
        
        self.sensores = {
            "P_VALV_01_OUT": {"nombre": "PE 01", "x": 57, "y": 73, "valor": 1013.0, "unidad": "Pa", "color": "#00FFFF"},
            "T_VALV_01_OUT": {"nombre": "HE 01", "x": 126, "y": 139, "valor": 50.5, "unidad": "%RH", "color": "#FFD700"},
            "T_PROD_OUT":    {"nombre": "TE 08", "x": 132, "y": 281, "valor": 25.0, "unidad": "°C", "color": "#FFC000"},
            "M1_HZ":         {"nombre": "M1 Freq", "x": 24, "y": 185, "valor": 0.0, "unidad": "Hz", "color": "#00BFFF"},
            "M1_RPM":        {"nombre": "M1 Vel",  "x": 24, "y": 215, "valor": 0.0, "unidad": "RPM", "color": "#00BFFF"},
            "M1_AMP":        {"nombre": "M1 Corr", "x": 24, "y": 245, "valor": 0.0, "unidad": "A", "color": "#00BFFF"},
            "M2_RPM":        {"nombre": "M2 Vel",  "x": 644, "y": 184, "valor": 0.0, "unidad": "RPM", "color": "#FFFFFF"},
            "T_COND_01_OUT": {"nombre": "TT 01", "x": 280, "y": 40, "valor": 5.0, "unidad": "°C", "color": "#00FF00"},
            "P_COND_01_OUT": {"nombre": "PT 01", "x": 280, "y": 80, "valor": 10.5, "unidad": "bar", "color": "#00FFFF"},
            "T_COND_02_OUT": {"nombre": "TT 03", "x": 429, "y": 26, "valor": -20.0, "unidad": "°C", "color": "#00FF00"},
            "H_COND_02_OUT": {"nombre": "HT 01", "x": 430, "y": 80, "valor": 10.0, "unidad": "%RH", "color": "#FFD700"},
            "P_PUMP_IN":     {"nombre": "PT 02", "x": 320, "y": 380, "valor": 1013.0, "unidad": "Pa", "color": "#00FFFF"},
            "O2_NIVEL_PUMP": {"nombre": "AE 01", "x": 420, "y": 380, "valor": 20.9, "unidad": "%", "color": "#FFFF00"},
            "T_HEATER_OUT":  {"nombre": "TT 07", "x": 613, "y": 269, "valor": 45.0, "unidad": "°C", "color": "#00FF00"},
        }
        
        self.actuadores = {
            "M1_CAMARA": {"nombre": "M1 Tambor", "x": 145, "y": 120, "estado": False, "giro": "FWD"},
            "M2_VENT":   {"nombre": "M2 Vent.",  "x": 745, "y": 185, "estado": False, "giro": "FWD"},
            "BOMBA_VAC": {"nombre": "Bomba Vac", "x": 380, "y": 350, "estado": False, "giro": None},
            "HEATER":    {"nombre": "Heater",    "x": 550, "y": 270, "estado": False, "giro": None}
        }

        self.hitboxes = {}
        self.dragged_sensor = None
        self.drag_start_pos = None
        self.offset_x = 0
        self.offset_y = 0

        self.image_path = os.path.join("resources", "hmi_background2.png")
        if os.path.exists(self.image_path):
            self.background_pixmap = QPixmap(self.image_path)
        else:
            self.background_pixmap = None

        self.area_motor_camara = QRect(250, 150, 200, 180) 

        # ==============================================================
        # AJUSTE DE FLECHAS DE FLUJO (Edita estos números en el futuro)
        # Formato: (Inicio_X, Inicio_Y, Fin_X, Fin_Y, Color, Velocidad_ms)
        # ==============================================================
        self.flechas = []
        self.timer_blink = 0 
        self.frame_giro = 0 # Animador de rotación
        
        # Flecha Frío (Celeste)
        self.crear_flecha(300, 150, 180, 150, "#00BFFF", 2500) 
        # Flecha Calor (Rojo)
        self.crear_flecha(650, 250, 650, 100, "#FF0000", 2000) 
        # Flecha Vacío (Amarillo)
        self.crear_flecha(300, 300, 300, 380, "#FFFF00", 2000) 

    def crear_flecha(self, start_x, start_y, end_x, end_y, color, duracion_ms):
        arrow = FlowArrowWidget(color, self)
        arrow.hide()
        anim = QPropertyAnimation(arrow, b"pos")
        anim.setDuration(duracion_ms)
        anim.setStartValue(QPoint(start_x, start_y))
        anim.setEndValue(QPoint(end_x, end_y))
        anim.setLoopCount(-1)
        self.flechas.append((arrow, anim))

    def update_telemetry(self, data):
        self.vfd_data = data
        self.timer_blink = (self.timer_blink + 1) % 2 
        self.frame_giro = (self.frame_giro + 1) % 4 # Animación 4 frames para los motores

        if "M1_HZ" in self.sensores: self.sensores["M1_HZ"]["valor"] = round(data["freq_real"], 1)
        if "M1_RPM" in self.sensores: self.sensores["M1_RPM"]["valor"] = round(data["rpm_real"], 0)
        if "M1_AMP" in self.sensores: self.sensores["M1_AMP"]["valor"] = round(data["current"], 1)

        motor_en_marcha = self.vfd_data['freq_real'] > 0.5
        self.actuadores["M1_CAMARA"]["estado"] = motor_en_marcha
        self.actuadores["M2_VENT"]["estado"] = motor_en_marcha
        self.actuadores["BOMBA_VAC"]["estado"] = motor_en_marcha

        if motor_en_marcha:
            for arrow, anim in self.flechas:
                if not arrow.isVisible(): arrow.show(); anim.start()
        else:
            for arrow, anim in self.flechas:
                if arrow.isVisible(): arrow.hide(); anim.stop()
                    
        self.update() 

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#000000"))

        if self.background_pixmap:
            scaled_pixmap = self.background_pixmap.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(0, 0, scaled_pixmap)

        if self.vfd_data["alarm"] != 0:
            painter.setFont(QFont("Consolas", 11, QFont.Bold))
            rect_alarma = QRect(200, 5, 400, 25)
            if self.timer_blink == 0:
                painter.setBrush(QColor("#D32F2F")) 
                painter.setPen(Qt.NoPen)
                painter.drawRect(rect_alarma)
                painter.setPen(QPen(Qt.white))
                painter.drawText(rect_alarma, Qt.AlignCenter, f"ALERTA: FALLA EN VARIADOR [COD: {self.vfd_data['alarm']}]")
            else:
                painter.setBrush(QColor("#000000"))
                painter.setPen(QPen(QColor("#D32F2F"), 2))
                painter.drawRect(rect_alarma)
                painter.drawText(rect_alarma, Qt.AlignCenter, "!!! REVISAR CODIGO DE ERROR EN ELIMEX !!!")

        # --- DIBUJAR PILOTOS LED Y SENTIDO DE GIRO ---
        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        iconos_giro = ['|', '/', '-', '\\'] # Símbolos para animar rotación

        for key, data in self.actuadores.items():
            color_led = QColor("#00FF00") if data["estado"] else QColor("#8B0000")
            painter.setBrush(color_led)
            painter.setPen(QPen(Qt.black, 1))
            painter.drawEllipse(data["x"], data["y"], 12, 12)
            
            painter.setPen(QPen(Qt.white))
            
            # Si el actuador tiene propiedad de giro (Motores)
            if data["giro"] is not None:
                if data["estado"]: # Motor girando
                    simbolo = iconos_giro[self.frame_giro] if data["giro"] == "FWD" else iconos_giro[-(self.frame_giro)-1]
                    texto = f"{data['nombre']} [{simbolo} {data['giro']}]"
                    painter.setPen(QPen(QColor("#00FF00"))) # Letras verdes para rotación
                else: # Motor Detenido
                    texto = f"{data['nombre']} [🛑 STOP]"
                    painter.setPen(QPen(QColor("#A0A0A0"))) # Letras grises
            else:
                # Actuador normal (Calentador, Bomba)
                texto = data["nombre"]

            painter.drawText(data["x"] + 18, data["y"] + 11, texto)

        # --- DIBUJAR DISPLAYS DIGITALES ---
        painter.setFont(QFont("Consolas", 10, QFont.Bold))
        for key, data in self.sensores.items():
            texto_display = f"{data['nombre']}: {data['valor']} {data['unidad']}"
            
            metrics = painter.fontMetrics()
            width = metrics.horizontalAdvance(texto_display)
            height = metrics.height()
            
            rect_caja = QRect(int(data['x']), int(data['y']), int(width + 10), int(height + 4))
            self.hitboxes[key] = rect_caja  
            
            painter.setBrush(QColor(25, 25, 25, 240))
            if self.dragged_sensor == key:
                painter.setPen(QPen(Qt.white, 2)) 
            else:
                painter.setPen(QPen(QColor("#404040"), 1))
            
            painter.drawRect(rect_caja)
            painter.setPen(QPen(QColor(data['color'])))
            painter.drawText(rect_caja, Qt.AlignCenter, texto_display)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            self.drag_start_pos = pos

            for sensor_id, rect in self.hitboxes.items():
                if rect.contains(pos):
                    self.dragged_sensor = sensor_id
                    self.offset_x = pos.x() - self.sensores[sensor_id]["x"]
                    self.offset_y = pos.y() - self.sensores[sensor_id]["y"]
                    return

            if self.area_motor_camara.contains(pos):
                self.motorClicked.emit()

    def mouseMoveEvent(self, event):
        if self.dragged_sensor is not None:
            pos = event.pos()
            self.sensores[self.dragged_sensor]["x"] = pos.x() - self.offset_x
            self.sensores[self.dragged_sensor]["y"] = pos.y() - self.offset_y
            self.update() 

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.dragged_sensor is not None:
            pos = event.pos()
            distancia_movida = (pos - self.drag_start_pos).manhattanLength()

            if distancia_movida < 10:
                nombre = self.sensores[self.dragged_sensor]["nombre"]
                valor_actual = self.sensores[self.dragged_sensor]["valor"]
                self.setPointRequested.emit(self.dragged_sensor, nombre, valor_actual)
            else:
                x_final = self.sensores[self.dragged_sensor]["x"]
                y_final = self.sensores[self.dragged_sensor]["y"]
                print(f"-> POSICION GUARDADA '{self.dragged_sensor}': x: {int(x_final)}, y: {int(y_final)}")
            
            self.dragged_sensor = None
            self.update()
