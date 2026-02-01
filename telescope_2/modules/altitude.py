import math
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QPushButton, QDoubleSpinBox, QGroupBox, QComboBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor

# GPIO Setup (fallback for non-Pi)
try:
    from gpiozero import OutputDevice
    GPIO_AVAILABLE = True
except ImportError:
    class OutputDevice:
        def __init__(self, pin, active_high=True, initial_value=False):
            self.pin = pin
            self.value = initial_value
        def on(self): self.value = True
        def off(self): self.value = False
    GPIO_AVAILABLE = False

# Mock Altitude Motor Thread (with GPIO control)
class AltitudeMotorThread(QThread):
    position_updated = pyqtSignal(float, float)  # current, target (degrees)

    def __init__(self, up_pin, down_pin):
        super().__init__()
        self.current_alt = 0.0
        self.target_alt = 0.0
        self.running = True
        self.max_alt = 90.0
        self.min_alt = 0.0
        
        # GPIO Setup
        self.up_pin = OutputDevice(up_pin, initial_value=False) if GPIO_AVAILABLE else None
        self.down_pin = OutputDevice(down_pin, initial_value=False) if GPIO_AVAILABLE else None

    def set_target(self, target):
        """Set target altitude (clamped to min/max)"""
        self.target_alt = max(self.min_alt, min(self.max_alt, target))

    def run(self):
        """Simulate altitude movement + GPIO control"""
        while self.running:
            # Simulate movement (0.1° step)
            if abs(self.target_alt - self.current_alt) > 0.1:
                step = 0.1 if self.target_alt > self.current_alt else -0.1
                self.current_alt += step
                
                # Control GPIO pins
                if self.up_pin and self.down_pin:
                    if step > 0:
                        self.up_pin.on()
                        self.down_pin.off()
                    else:
                        self.up_pin.off()
                        self.down_pin.on()
            else:
                # Stop motors
                if self.up_pin and self.down_pin:
                    self.up_pin.off()
                    self.down_pin.off()

            self.position_updated.emit(self.current_alt, self.target_alt)
            self.msleep(50)

    def stop(self):
        """Stop simulation + GPIO cleanup"""
        self.running = False
        if self.up_pin and self.down_pin:
            self.up_pin.off()
            self.down_pin.off()

# Main Altitude Control Widget (GPIO + Theme)
class AltitudeControlWidget(QWidget):
    def __init__(self, config, save_gpio_func, gpio_pin_map):
        super().__init__()
        self.config = config
        self.save_gpio = save_gpio_func
        self.gpio_pin_map = gpio_pin_map
        
        # --------------------------
        # Safe GPIO Config Access (Fix KeyError)
        # --------------------------
        gpio_config = config.get("gpio", {})  # Fallback to empty dict
        self.up_pin_label = gpio_config.get("altitude_up", "17 (Pin 11)")  # Default value
        self.down_pin_label = gpio_config.get("altitude_down", "18 (Pin 12)")
        
        # Safe pin lookup (fallback to default if label is invalid)
        self.up_pin = self.gpio_pin_map.get(self.up_pin_label, 17)
        self.down_pin = self.gpio_pin_map.get(self.down_pin_label, 18)

        self.layout = QVBoxLayout()
        self._setup_ui()
        self.setLayout(self.layout)

        # Initialize motor thread with GPIO
        self.motor_thread = AltitudeMotorThread(self.up_pin, self.down_pin)
        self.motor_thread.position_updated.connect(self._update_display)
        self.motor_thread.start()

    def _setup_ui(self):
        """Create UI with GPIO pin selection + altitude control"""
        # --------------------------
        # Title + Emergency Stop
        # --------------------------
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("<h2>Altitude Control (0-90°)</h2>"))
        
        self.emergency_stop = QPushButton("EMERGENCY STOP")
        self.emergency_stop.setObjectName("emergencyStop")
        self.emergency_stop.clicked.connect(self._emergency_stop)
        top_layout.addWidget(self.emergency_stop)
        self.layout.addLayout(top_layout)

        # --------------------------
        # GPIO Pin Configuration
        # --------------------------
        gpio_group = QGroupBox("GPIO Pin Configuration")
        gpio_layout = QVBoxLayout()

        # Up Pin Selection
        up_layout = QHBoxLayout()
        up_layout.addWidget(QLabel("Up Motor Pin:"))
        self.up_pin_combo = QComboBox()
        self.up_pin_combo.addItems(self.gpio_pin_map.keys())
        self.up_pin_combo.setCurrentText(self.up_pin_label)
        self.up_pin_combo.currentTextChanged.connect(lambda x: self._on_gpio_change("altitude", "up", x))
        up_layout.addWidget(self.up_pin_combo)
        gpio_layout.addLayout(up_layout)

        # Down Pin Selection
        down_layout = QHBoxLayout()
        down_layout.addWidget(QLabel("Down Motor Pin:"))
        self.down_pin_combo = QComboBox()
        self.down_pin_combo.addItems(self.gpio_pin_map.keys())
        self.down_pin_combo.setCurrentText(self.down_pin_label)
        self.down_pin_combo.currentTextChanged.connect(lambda x: self._on_gpio_change("altitude", "down", x))
        down_layout.addWidget(self.down_pin_combo)
        gpio_layout.addLayout(down_layout)

        gpio_group.setLayout(gpio_layout)
        self.layout.addWidget(gpio_group)

        # --------------------------
        # Position Display
        # --------------------------
        display_layout = QHBoxLayout()
        self.current_alt_label = QLabel("Current: 0.0° (0.0 rad)")
        self.target_alt_label = QLabel("Target: 0.0° (0.0 rad)")
        self.error_label = QLabel("Error: 0.0°")
        
        display_col = QVBoxLayout()
        display_col.addWidget(self.current_alt_label)
        display_col.addWidget(self.target_alt_label)
        display_col.addWidget(self.error_label)
        display_layout.addLayout(display_col)
        self.layout.addLayout(display_layout)

        # --------------------------
        # Manual Control
        # --------------------------
        control_group = QGroupBox("Manual Adjustment")
        control_layout = QVBoxLayout()

        # Slider (0-90°)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 900)  # 0 → 0°, 900 → 90°
        self.slider.setValue(0)
        self.slider.valueChanged.connect(lambda v: self._set_target(v/10))
        control_layout.addWidget(self.slider)

        # Step Buttons
        step_layout = QHBoxLayout()
        self.step_btns = [
            QPushButton("-5°", clicked=lambda: self._adjust_step(-5)),
            QPushButton("+5°", clicked=lambda: self._adjust_step(5)),
            QPushButton("-1°", clicked=lambda: self._adjust_step(-1)),
            QPushButton("+1°", clicked=lambda: self._adjust_step(1))
        ]
        for btn in self.step_btns:
            step_layout.addWidget(btn)
        control_layout.addLayout(step_layout)

        # Target Input
        spin_layout = QHBoxLayout()
        self.target_spin = QDoubleSpinBox()
        self.target_spin.setRange(0.0, 90.0)
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

    # --------------------------
    # GPIO Handling
    # --------------------------
    def _on_gpio_change(self, gpio_type, pin_key, pin_label):
        """Update GPIO pin selection + restart motor thread"""
        # Save new pin config
        self.save_gpio(gpio_type, pin_key, pin_label)
        
        # Update pin values
        setattr(self, f"{pin_key}_pin_label", pin_label)
        setattr(self, f"{pin_key}_pin", self.gpio_pin_map.get(pin_label, 17))
        
        # Restart motor thread with new pins
        self.motor_thread.stop()
        self.motor_thread.wait()
        self.motor_thread = AltitudeMotorThread(self.up_pin, self.down_pin)
        self.motor_thread.position_updated.connect(self._update_display)
        self.motor_thread.start()

    # --------------------------
    # Motor Control
    # --------------------------
    def _set_target(self, target):
        """Set target altitude (mock - no hardware)"""
        self.motor_thread.set_target(target)
        self.target_spin.setValue(target)
        self.slider.setValue(int(target * 10))

    def _adjust_step(self, step):
        """Adjust altitude by step"""
        current_target = self.motor_thread.target_alt
        self._set_target(current_target + step)

    def _update_display(self, current, target):
        """Update UI with simulated position"""
        current_rad = math.radians(current)
        target_rad = math.radians(target)
        error = abs(target - current)

        self.current_alt_label.setText(f"Current: {current:.1f}° ({current_rad:.2f} rad)")
        self.target_alt_label.setText(f"Target: {target:.1f}° ({target_rad:.2f} rad)")
        self.error_label.setText(f"Error: {error:.1f}°")

    def _emergency_stop(self):
        """Emergency stop (stop motors + thread)"""
        self.motor_thread.stop()
        self.current_alt_label.setText("Current: STOPPED (EMERGENCY)")
        self.error_label.setText("Error: EMERGENCY STOP ACTIVATED")

    # --------------------------
    # Cleanup
    # --------------------------
    def closeEvent(self, event):
        """Clean up motor thread + GPIO"""
        self.motor_thread.stop()
        self.motor_thread.wait()
        event.accept()