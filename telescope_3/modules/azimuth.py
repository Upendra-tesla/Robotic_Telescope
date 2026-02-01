import math
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QPushButton, QDoubleSpinBox, QGroupBox, QComboBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor

# Import mock-safe GPIO from main (or local mock)
try:
    from gpiozero import OutputDevice, GPIODeviceClosed
except ImportError:
    # Use mock OutputDevice from main
    class GPIODeviceClosed(Exception):
        pass

# Mock Azimuth Motor Thread (with GPIO control)
class AzimuthMotorThread(QThread):
    position_updated = pyqtSignal(float, float)  # current, target (degrees)

    def __init__(self, left_pin, right_pin):
        super().__init__()
        self.current_az = 0.0
        self.target_az = 0.0
        self.running = True
        self.max_az = 360.0
        self.min_az = 0.0
        
        # --------------------------
        # FIXED: Safe GPIO Initialization
        # --------------------------
        self.left_pin = None
        self.right_pin = None
        try:
            # Initialize GPIO pins (with mock fallback)
            self.left_pin = OutputDevice(left_pin, initial_value=False)
            self.right_pin = OutputDevice(right_pin, initial_value=False)
        except Exception as e:
            print(f"GPIO Initialization Error (Azimuth): {e}")
            # Fallback to None (safe mode)
            self.left_pin = None
            self.right_pin = None

    def set_target(self, target):
        """Set target azimuth (wrap to 0-360°)"""
        self.target_az = target % 360.0

    def run(self):
        """Simulate azimuth rotation + SAFE GPIO control"""
        while self.running:
            # Simulate movement (handle 360° wrap)
            error = self.target_az - self.current_az
            if abs(error) > 180:
                error = error - 360 if error > 0 else error + 360

            if abs(error) > 0.1:
                step = 0.1 if error > 0 else -0.1
                self.current_az += step
                self.current_az = self.current_az % 360.0
                
                # --------------------------
                # FIXED: Safe GPIO Operations (Check + Exception Handling)
                # --------------------------
                try:
                    if self.left_pin and self.right_pin:
                        if step > 0:
                            self.right_pin.on()
                            self.left_pin.off()
                        else:
                            self.right_pin.off()
                            self.left_pin.on()
                except (GPIODeviceClosed, AttributeError) as e:
                    # Ignore GPIO errors (continue simulation)
                    print(f"GPIO Error (Azimuth): {e}")
            else:
                # Stop motors (SAFE)
                try:
                    if self.left_pin and self.right_pin:
                        self.left_pin.off()
                        self.right_pin.off()
                except (GPIODeviceClosed, AttributeError) as e:
                    print(f"GPIO Error (Azimuth Stop): {e}")

            self.position_updated.emit(self.current_az, self.target_az)
            self.msleep(50)

    def stop(self):
        """Stop simulation + SAFE GPIO cleanup"""
        self.running = False
        # --------------------------
        # FIXED: Safe GPIO Cleanup
        # --------------------------
        try:
            if self.left_pin and self.right_pin:
                self.left_pin.off()
                self.right_pin.off()
                self.left_pin.close()
                self.right_pin.close()
        except (GPIODeviceClosed, AttributeError) as e:
            print(f"GPIO Cleanup Error (Azimuth): {e}")

# Compass Rose Widget (Theme-Aware)
class CompassRose(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(200, 200)
        self.current_az = 0.0
        # Default theme colors (will inherit global theme)
        self.theme_colors = {
            "compass_bg": "#000000",
            "compass_text": "#ffffff",
            "compass_indicator": "#ff0000"
        }

    def set_azimuth(self, az):
        self.current_az = az
        self.update()

    def set_theme_colors(self, colors):
        """Update compass colors from global theme"""
        self.theme_colors = {
            "compass_bg": colors.get("compass_bg", "#000000"),
            "compass_text": colors.get("compass_text", "#ffffff"),
            "compass_indicator": colors.get("compass_indicator", "#ff0000")
        }
        self.update()

    def paintEvent(self, event):
        """Draw compass rose with theme-aware colors"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        center = self.rect().center()
        radius = min(center.x(), center.y()) - 10
        
        # Draw compass background
        painter.setPen(QPen(QColor(self.theme_colors["compass_text"]), 2))
        painter.setBrush(QBrush(QColor(self.theme_colors["compass_bg"])))
        painter.drawEllipse(center, radius, radius)

        # Cardinal directions (convert float → int coordinates)
        directions = [("N", 0), ("E", 90), ("S", 180), ("W", 270)]
        painter.setPen(QPen(QColor(self.theme_colors["compass_text"]), 1))
        for dir_name, az in directions:
            angle = math.radians(90 - az)
            x = int(center.x() + radius * math.cos(angle) - 10)
            y = int(center.y() - radius * math.sin(angle) - 10)
            painter.drawText(x, y, dir_name)

        # Current azimuth indicator
        painter.setPen(QPen(QColor(self.theme_colors["compass_indicator"]), 3))
        indicator_angle = math.radians(90 - self.current_az)
        end_x = int(center.x() + radius * math.cos(indicator_angle))
        end_y = int(center.y() - radius * math.sin(indicator_angle))
        painter.drawLine(center.x(), center.y(), end_x, end_y)

        # Azimuth text
        az_text = f"Azimuth: {self.current_az:.1f}°"
        painter.drawText(10, 20, az_text)

# Main Azimuth Control Widget (GPIO + Theme + Compass)
class AzimuthControlWidget(QWidget):
    def __init__(self, config, save_gpio_func, gpio_pin_map):
        super().__init__()
        self.config = config
        self.save_gpio = save_gpio_func
        self.gpio_pin_map = gpio_pin_map
        
        # Safe GPIO Config Access (Fix KeyError)
        gpio_config = config.get("gpio", {})  # Fallback to empty dict
        self.left_pin_label = gpio_config.get("azimuth_left", "27 (Pin 13)")  # Default value
        self.right_pin_label = gpio_config.get("azimuth_right", "22 (Pin 15)")
        
        # Safe pin lookup (fallback to default if label is invalid)
        self.left_pin = self.gpio_pin_map.get(self.left_pin_label, 27)
        self.right_pin = self.gpio_pin_map.get(self.right_pin_label, 22)

        self.layout = QVBoxLayout()
        self._setup_ui()
        self.setLayout(self.layout)

        # Initialize motor thread with GPIO
        self.motor_thread = AzimuthMotorThread(self.left_pin, self.right_pin)
        self.motor_thread.position_updated.connect(self._update_display)
        self.motor_thread.start()

    def _setup_ui(self):
        """Create UI with GPIO + compass + theme"""
        # --------------------------
        # Title + Emergency Stop
        # --------------------------
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("<h2>Azimuth Control (0-360°)</h2>"))
        
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

        # Left Pin Selection
        left_layout = QHBoxLayout()
        left_layout.addWidget(QLabel("Left Motor Pin:"))
        self.left_pin_combo = QComboBox()
        self.left_pin_combo.addItems(self.gpio_pin_map.keys())
        self.left_pin_combo.setCurrentText(self.left_pin_label)
        self.left_pin_combo.currentTextChanged.connect(lambda x: self._on_gpio_change("azimuth", "left", x))
        left_layout.addWidget(self.left_pin_combo)
        gpio_layout.addLayout(left_layout)

        # Right Pin Selection
        right_layout = QHBoxLayout()
        right_layout.addWidget(QLabel("Right Motor Pin:"))
        self.right_pin_combo = QComboBox()
        self.right_pin_combo.addItems(self.gpio_pin_map.keys())
        self.right_pin_combo.setCurrentText(self.right_pin_label)
        self.right_pin_combo.currentTextChanged.connect(lambda x: self._on_gpio_change("azimuth", "right", x))
        right_layout.addWidget(self.right_pin_combo)
        gpio_layout.addLayout(right_layout)

        gpio_group.setLayout(gpio_layout)
        self.layout.addWidget(gpio_group)

        # --------------------------
        # Position Display + Compass
        # --------------------------
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

        # --------------------------
        # Manual Control
        # --------------------------
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
        self.step_btns = [
            QPushButton("-5°", clicked=lambda: self._adjust_step(-5)),
            QPushButton("+5°", clicked=lambda: self._adjust_step(5)),
            QPushButton("-10°", clicked=lambda: self._adjust_step(-10)),
            QPushButton("+10°", clicked=lambda: self._adjust_step(10))
        ]
        for btn in self.step_btns:
            step_layout.addWidget(btn)
        control_layout.addLayout(step_layout)

        # Target Input
        spin_layout = QHBoxLayout()
        self.target_spin = QDoubleSpinBox()
        self.target_spin.setRange(0.0, 360.0)
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

    # --------------------------
    # GPIO Handling
    # --------------------------
    def _on_gpio_change(self, gpio_type, pin_key, pin_label):
        """Update GPIO pin selection + restart motor thread"""
        # Save new pin config
        self.save_gpio(gpio_type, pin_key, pin_label)
        
        # Update pin values
        setattr(self, f"{pin_key}_pin_label", pin_label)
        setattr(self, f"{pin_key}_pin", self.gpio_pin_map.get(pin_label, 27))
        
        # Restart motor thread with new pins
        self.motor_thread.stop()
        self.motor_thread.wait()
        self.motor_thread = AzimuthMotorThread(self.left_pin, self.right_pin)
        self.motor_thread.position_updated.connect(self._update_display)
        self.motor_thread.start()

    # --------------------------
    # Motor Control
    # --------------------------
    def _set_target(self, target):
        """Set target azimuth"""
        self.motor_thread.set_target(target)
        self.target_spin.setValue(target % 360.0)
        self.slider.setValue(int((target % 360.0) * 10))

    def _adjust_step(self, step):
        """Adjust azimuth by step"""
        current_target = self.motor_thread.target_az
        self._set_target(current_target + step)

    def _update_display(self, current, target):
        """Update UI + compass"""
        current_rad = math.radians(current)
        target_rad = math.radians(target)
        error = abs(target - current)
        error = min(error, 360 - error)  # Handle 360° wrap

        self.current_az_label.setText(f"Current: {current:.1f}° ({current_rad:.2f} rad)")
        self.target_az_label.setText(f"Target: {target:.1f}° ({target_rad:.2f} rad)")
        self.error_label.setText(f"Error: {error:.1f}°")
        self.compass.set_azimuth(current)

    def _emergency_stop(self):
        """Emergency stop (stop motors + thread)"""
        self.motor_thread.stop()
        self.current_az_label.setText("Current: STOPPED (EMERGENCY)")
        self.error_label.setText("Error: EMERGENCY STOP ACTIVATED")

    # --------------------------
    # Cleanup
    # --------------------------
    def closeEvent(self, event):
        """Clean up motor thread + GPIO"""
        self.motor_thread.stop()
        self.motor_thread.wait()
        event.accept()