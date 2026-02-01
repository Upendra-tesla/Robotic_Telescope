import math
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QPushButton, QDoubleSpinBox, QGroupBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

# Mock Motor Thread (NO PIGPIO - just simulates position for UI)
class AltitudeMotorThread(QThread):
    position_updated = pyqtSignal(float, float)  # current, target (degrees)

    def __init__(self):
        super().__init__()
        self.current_alt = 0.0  # Simulated position (no GPIO)
        self.target_alt = 0.0
        self.running = True
        self.max_alt = 90.0
        self.min_alt = 0.0

    def set_target(self, target):
        """Set target altitude (clamped to 0-90°)"""
        self.target_alt = max(self.min_alt, min(self.max_alt, target))

    def run(self):
        """Simulate motor movement (no pigpio - just UI feedback)"""
        while self.running:
            # Simulate slow movement to target (like real motor)
            if abs(self.current_alt - self.target_alt) > 0.1:
                step = 0.1 if self.current_alt < self.target_alt else -0.1
                self.current_alt += step
            # Emit position update (UI only - no hardware)
            self.position_updated.emit(self.current_alt, self.target_alt)
            self.msleep(50)  # 20Hz update (UI-friendly)

    def stop(self):
        """Stop simulation (no pigpio cleanup needed)"""
        self.running = False

# Main Altitude Widget (NO PIGPIO)
class AltitudeControlWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self._setup_ui()
        self.setLayout(self.layout)

        # Initialize mock motor thread (no pigpio)
        self.motor_thread = AltitudeMotorThread()
        self.motor_thread.position_updated.connect(self._update_display)
        self.motor_thread.start()

    def _setup_ui(self):
        """Create altitude control UI (no pigpio)"""
        # Title + Emergency Stop (mock - no hardware)
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("<h2>Altitude Control (0-90°)</h2>"))
        self.emergency_stop = QPushButton("EMERGENCY STOP")
        self.emergency_stop.setObjectName("emergencyStop")
        self.emergency_stop.clicked.connect(self._emergency_stop)
        top_layout.addWidget(self.emergency_stop)
        self.layout.addLayout(top_layout)

        # Position Display
        display_layout = QHBoxLayout()
        self.current_alt_label = QLabel("Current: 0.0° (0.0 rad)")
        self.target_alt_label = QLabel("Target: 0.0° (0.0 rad)")
        self.error_label = QLabel("Error: 0.0°")
        display_layout.addWidget(self.current_alt_label)
        display_layout.addWidget(self.target_alt_label)
        display_layout.addWidget(self.error_label)
        self.layout.addLayout(display_layout)

        # Manual Control
        control_group = QGroupBox("Manual Adjustment")
        control_layout = QVBoxLayout()

        # Slider (0-90° with 0.1° precision)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 900)  # 0 → 0°, 900 → 90°
        self.slider.setValue(0)
        self.slider.valueChanged.connect(lambda v: self._set_target(v/10))
        control_layout.addWidget(self.slider)

        # Step Buttons
        step_layout = QHBoxLayout()
        step_layout.addWidget(QPushButton("-1°", clicked=lambda: self._adjust_step(-1)))
        step_layout.addWidget(QPushButton("+1°", clicked=lambda: self._adjust_step(1)))
        step_layout.addWidget(QPushButton("-5°", clicked=lambda: self._adjust_step(-5)))
        step_layout.addWidget(QPushButton("+5°", clicked=lambda: self._adjust_step(5)))
        control_layout.addLayout(step_layout)

        # Target Input
        spin_layout = QHBoxLayout()
        self.target_spin = QDoubleSpinBox()
        self.target_spin.setRange(0, 90)
        self.target_spin.setDecimals(1)
        self.target_spin.valueChanged.connect(self._set_target)
        spin_layout.addWidget(QLabel("Target Altitude (°):"))
        spin_layout.addWidget(self.target_spin)
        control_layout.addLayout(spin_layout)

        # Park Button
        self.park_btn = QPushButton("Park Telescope (0°)")
        self.park_btn.clicked.connect(lambda: self._set_target(0))
        control_layout.addWidget(self.park_btn)

        control_group.setLayout(control_layout)
        self.layout.addWidget(control_group)

    def _set_target(self, target):
        """Set target altitude (mock - no hardware)"""
        self.motor_thread.set_target(target)
        self.target_spin.setValue(target)
        self.slider.setValue(int(target * 10))

    def _adjust_step(self, step):
        """Adjust altitude by step (mock)"""
        current_target = self.motor_thread.target_alt
        self._set_target(current_target + step)

    def _update_display(self, current, target):
        """Update UI with simulated position (no pigpio)"""
        current_rad = math.radians(current)
        target_rad = math.radians(target)
        error = abs(current - target)

        self.current_alt_label.setText(f"Current: {current:.1f}° ({current_rad:.2f} rad)")
        self.target_alt_label.setText(f"Target: {target:.1f}° ({target_rad:.2f} rad)")
        self.error_label.setText(f"Error: {error:.1f}°")

    def _emergency_stop(self):
        """Mock emergency stop (no hardware - just stop simulation)"""
        self.motor_thread.stop()
        self.current_alt_label.setText("Current: STOPPED (EMERGENCY)")
        self.error_label.setText("Error: EMERGENCY STOP ACTIVATED")

    def closeEvent(self, event):
        """Clean up mock thread (no pigpio)"""
        self.motor_thread.stop()
        self.motor_thread.wait()
        event.accept()