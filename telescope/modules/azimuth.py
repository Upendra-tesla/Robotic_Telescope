import math
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QPushButton, QDoubleSpinBox, QGroupBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QBrush

# Mock Azimuth Thread (NO PIGPIO - simulate 360° rotation)
class AzimuthMotorThread(QThread):
    position_updated = pyqtSignal(float, float)  # current, target (degrees)

    def __init__(self):
        super().__init__()
        self.current_az = 0.0  # Simulated position (no GPIO)
        self.target_az = 0.0
        self.running = True
        self.max_az = 360.0
        self.min_az = 0.0

    def set_target(self, target):
        """Set target azimuth (wrap to 0-360°)"""
        self.target_az = target % 360.0

    def run(self):
        """Simulate 360° rotation (no pigpio - UI only)"""
        while self.running:
            # Simulate movement (handle 360° wrap)
            error = self.target_az - self.current_az
            if abs(error) > 180:
                error = error - 360 if error > 0 else error + 360

            if abs(error) > 0.1:
                step = 0.1 if error > 0 else -0.1
                self.current_az += step
                self.current_az = self.current_az % 360.0

            # Emit position update (UI only)
            self.position_updated.emit(self.current_az, self.target_az)
            self.msleep(50)

    def stop(self):
        """Stop simulation (no pigpio cleanup)"""
        self.running = False

# Compass Rose Widget (FIXED: Float → Int coordinates for PyQt5)
class CompassRose(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(200, 200)
        self.current_az = 0.0

    def set_azimuth(self, az):
        self.current_az = az
        self.update()

    def paintEvent(self, event):
        """Draw compass rose (FIXED: All coordinates converted to int)"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        center = self.rect().center()
        radius = min(center.x(), center.y()) - 10
        painter.setPen(QPen(Qt.white, 2))
        painter.setBrush(QBrush(Qt.black))
        painter.drawEllipse(center, radius, radius)

        # Cardinal directions (FIX: Convert float x/y to int)
        directions = [("N", 0), ("E", 90), ("S", 180), ("W", 270)]
        painter.setPen(QPen(Qt.white, 1))
        for dir_name, az in directions:
            angle = math.radians(90 - az)
            # FIX: Convert float coordinates to integer (required by drawText)
            x = int(center.x() + radius * math.cos(angle) - 10)
            y = int(center.y() - radius * math.sin(angle) - 10)
            painter.drawText(x, y, dir_name)

        # Current azimuth indicator (FIX: Convert float to int)
        painter.setPen(QPen(Qt.red, 3))
        indicator_angle = math.radians(90 - self.current_az)
        # FIX: Convert endpoint coordinates to integer (required by drawLine)
        end_x = int(center.x() + radius * math.cos(indicator_angle))
        end_y = int(center.y() - radius * math.sin(indicator_angle))
        painter.drawLine(center.x(), center.y(), end_x, end_y)

        # Draw azimuth text (keep as float for display, coordinates as int)
        az_text = f"Azimuth: {self.current_az:.1f}°"
        painter.drawText(10, 20, az_text)

# Main Azimuth Widget (NO PIGPIO)
class AzimuthControlWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self._setup_ui()
        self.setLayout(self.layout)

        # Initialize mock motor thread (no pigpio)
        self.motor_thread = AzimuthMotorThread()
        self.motor_thread.position_updated.connect(self._update_display)
        self.motor_thread.start()

    def _setup_ui(self):
        """Create azimuth control UI (no pigpio)"""
        # Title + Emergency Stop (mock)
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("<h2>Azimuth Control (0-360°)</h2>"))
        self.emergency_stop = QPushButton("EMERGENCY STOP")
        self.emergency_stop.setObjectName("emergencyStop")
        self.emergency_stop.clicked.connect(self._emergency_stop)
        top_layout.addWidget(self.emergency_stop)
        self.layout.addLayout(top_layout)

        # Position Display + Compass
        display_layout = QHBoxLayout()
        self.compass = CompassRose()
        display_layout.addWidget(self.compass)

        text_display = QVBoxLayout()
        self.current_az_label = QLabel("Current: 0.0° (0.0 rad)")
        self.target_az_label = QLabel("Target: 0.0° (0.0 rad)")
        self.error_label = QLabel("Error: 0.0°")
        text_display.addWidget(self.current_az_label)
        text_display.addWidget(self.target_az_label)
        text_display.addWidget(self.error_label)
        display_layout.addLayout(text_display)
        self.layout.addLayout(display_layout)

        # Manual Control
        control_group = QGroupBox("Manual Adjustment")
        control_layout = QVBoxLayout()

        # Slider (0-360°)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 3600)  # 0 → 0°, 3600 → 360°
        self.slider.setValue(0)
        self.slider.valueChanged.connect(lambda v: self._set_target(v/10))
        control_layout.addWidget(self.slider)

        # Step Buttons
        step_layout = QHBoxLayout()
        step_layout.addWidget(QPushButton("-5°", clicked=lambda: self._adjust_step(-5)))
        step_layout.addWidget(QPushButton("+5°", clicked=lambda: self._adjust_step(5)))
        step_layout.addWidget(QPushButton("-10°", clicked=lambda: self._adjust_step(-10)))
        step_layout.addWidget(QPushButton("+10°", clicked=lambda: self._adjust_step(10)))
        control_layout.addLayout(step_layout)

        # Target Input
        spin_layout = QHBoxLayout()
        self.target_spin = QDoubleSpinBox()
        self.target_spin.setRange(0, 360)
        self.target_spin.setDecimals(1)
        self.target_spin.valueChanged.connect(self._set_target)
        spin_layout.addWidget(QLabel("Target Azimuth (°):"))
        spin_layout.addWidget(self.target_spin)
        control_layout.addLayout(spin_layout)

        # Park Button
        self.park_btn = QPushButton("Park Telescope (0°)")
        self.park_btn.clicked.connect(lambda: self._set_target(0))
        control_layout.addWidget(self.park_btn)

        control_group.setLayout(control_layout)
        self.layout.addWidget(control_group)

    def _set_target(self, target):
        """Set target azimuth (mock - no hardware)"""
        self.motor_thread.set_target(target)
        self.target_spin.setValue(target % 360.0)
        self.slider.setValue(int((target % 360.0) * 10))

    def _adjust_step(self, step):
        """Adjust azimuth by step (mock)"""
        current_target = self.motor_thread.target_az
        self._set_target(current_target + step)

    def _update_display(self, current, target):
        """Update UI with simulated position (no pigpio)"""
        current_rad = math.radians(current)
        target_rad = math.radians(target)
        error = abs(target - current)
        error = min(error, 360 - error)  # Handle 360° wrap

        self.current_az_label.setText(f"Current: {current:.1f}° ({current_rad:.2f} rad)")
        self.target_az_label.setText(f"Target: {target:.1f}° ({target_rad:.2f} rad)")
        self.error_label.setText(f"Error: {error:.1f}°")
        self.compass.set_azimuth(current)

    def _emergency_stop(self):
        """Mock emergency stop (no hardware)"""
        self.motor_thread.stop()
        self.current_az_label.setText("Current: STOPPED (EMERGENCY)")
        self.error_label.setText("Error: EMERGENCY STOP ACTIVATED")

    def closeEvent(self, event):
        """Clean up mock thread (no pigpio)"""
        self.motor_thread.stop()
        self.motor_thread.wait()
        event.accept()