import time
from threading import Lock
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QSlider, QGroupBox, QSpinBox, QFrame, QMessageBox
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from gpiozero import Motor  # No pigpio import (Pi 5 native)

# Locked GPIO/Physical Pin Mapping for Altitude (NON-CHANGEABLE)
# Pi 5 Optimized - Fixed to GPIO17/18 (no configuration allowed)
LOCKED_ALT_PINS = {
    "up": {"gpio": "GPIO17", "physical": 11, "numeric": 17},
    "down": {"gpio": "GPIO18", "physical": 12, "numeric": 18}
}

class AltitudeMotorThread(QThread):
    """Thread-safe altitude motor control (Pi 5 optimized)"""
    position_signal = pyqtSignal(float)
    error_signal = pyqtSignal(str)

    def __init__(self, alt_up_pin, alt_down_pin):
        super().__init__()
        self.running = True
        self.lock = Lock()
        self.current_alt = 0.0
        self.target_alt = 0.0
        self.speed = 1.0  # Degrees per second (0.1-5.0 range)

        # Initialize motor with Pi 5 native pin factory (no pigpio!)
        self.alt_up_pin = alt_up_pin
        self.alt_down_pin = alt_down_pin
        try:
            self.motor = Motor(forward=alt_up_pin, backward=alt_down_pin)
            self.motor.stop()  # Ensure motor starts in stopped state
        except Exception as e:
            self.error_signal.emit(f"Altitude Motor Error: {str(e)}")
            self.motor = None

    def set_target(self, target):
        """Set target altitude (clamped 0-90°)"""
        with self.lock:
            self.target_alt = max(0.0, min(90.0, target))

    def set_speed(self, speed):
        """Set motor speed (clamped 0.1-5.0 °/s)"""
        with self.lock:
            self.speed = max(0.1, min(5.0, speed))

    def run(self):
        """Main motor control loop (low CPU, thread-safe)"""
        if not self.motor:
            return

        while self.running:
            with self.lock:
                current = self.current_alt
                target = self.target_alt

            # Calculate position difference
            diff = target - current
            if abs(diff) < 0.1:  # Stop if within 0.1° of target
                self.motor.stop()
                time.sleep(0.1)
                continue

            # Move motor (normalized speed 0-1 for gpiozero)
            try:
                speed_normalized = self.speed / 5.0  # Convert 1-5 → 0.2-1.0
                if diff > 0:
                    self.motor.forward(speed_normalized)
                    self.current_alt += self.speed * 0.1
                else:
                    self.motor.backward(speed_normalized)
                    self.current_alt -= self.speed * 0.1

                # Clamp altitude to 0-90°
                self.current_alt = max(0.0, min(90.0, self.current_alt))
                self.position_signal.emit(self.current_alt)
                time.sleep(0.1)  # Pi 5 optimized sleep (reduces CPU usage)
            except Exception as e:
                self.error_signal.emit(f"Altitude Movement Error: {str(e)}")
                self.motor.stop()
                time.sleep(1)  # Pause before retrying

    def stop(self):
        """Safe motor stop (thread-safe)"""
        with self.lock:
            self.running = False
        if self.motor:
            self.motor.stop()
        self.wait()

class AltitudeControlWidget(QWidget):
    """Compact altitude control widget (800×480 optimized)"""
    def __init__(self, config, save_gpio_config, pin_map):
        super().__init__()
        self.config = config
        self.save_gpio_config = save_gpio_config
        self.pin_map = pin_map

        # FORCE Locked GPIO Pins (ignore config - Pi 5 stability)
        self.alt_up_gpio = LOCKED_ALT_PINS["up"]["gpio"]
        self.alt_down_gpio = LOCKED_ALT_PINS["down"]["gpio"]
        self.alt_up_physical = LOCKED_ALT_PINS["up"]["physical"]
        self.alt_down_physical = LOCKED_ALT_PINS["down"]["physical"]
        self.alt_up_pin = LOCKED_ALT_PINS["up"]["numeric"]
        self.alt_down_pin = LOCKED_ALT_PINS["down"]["numeric"]

        # Validate locked pins (redundant but safe)
        if self.alt_up_gpio not in pin_map:
            QMessageBox.warning(self, "GPIO Locked", 
                               f"Altitude Up pin forced to {self.alt_up_gpio} (Physical Pin {self.alt_up_physical})")
        if self.alt_down_gpio not in pin_map:
            QMessageBox.warning(self, "GPIO Locked", 
                               f"Altitude Down pin forced to {self.alt_down_gpio} (Physical Pin {self.alt_down_physical})")

        # Initialize motor thread
        self.motor_thread = AltitudeMotorThread(self.alt_up_pin, self.alt_down_pin)
        self.motor_thread.position_signal.connect(self.update_altitude_display)
        self.motor_thread.error_signal.connect(self.show_error)

        # Initialize compact UI (800×480 optimized)
        self.init_ui()

        # Start motor thread
        self.motor_thread.start()

    def init_ui(self):
        """Create compact UI for 800×480 display"""
        layout = QVBoxLayout(self)
        # TIGHT spacing/margins (critical for small screen)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # 1. Title (compact, high contrast)
        title = QLabel("Altitude (0°-90°)")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 12px; font-weight: bold; color: #3498db;")
        layout.addWidget(title)

        # 2. Current Position (compact display)
        self.alt_display = QLabel("Current: 0.0 °")
        self.alt_display.setAlignment(Qt.AlignCenter)
        self.alt_display.setStyleSheet("font-size: 10px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(self.alt_display)

        # 3. Control Layout (slider + buttons - compact)
        control_layout = QHBoxLayout()
        control_layout.setSpacing(5)

        # Vertical Slider (compact size)
        self.alt_slider = QSlider(Qt.Vertical)
        self.alt_slider.setRange(0, 90)
        self.alt_slider.setValue(0)
        self.alt_slider.setTickInterval(15)  # Fewer ticks = less clutter
        self.alt_slider.setTickPosition(QSlider.TicksBothSides)
        self.alt_slider.setStyleSheet("""
            QSlider::groove:vertical {
                width: 8px;
                background: #ddd;
                border-radius: 4px;
            }
            QSlider::handle:vertical {
                height: 12px;
                width: 16px;
                background: #3498db;
                border-radius: 8px;
                margin: 0 -4px;
            }
        """)
        self.alt_slider.valueChanged.connect(lambda v: self.motor_thread.set_target(float(v)))
        control_layout.addWidget(self.alt_slider)

        # Manual Buttons (compact size)
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(4)
        
        # Button style (compact, touch-friendly)
        btn_style = """
            QPushButton { 
                background-color: #3498db; 
                color: white; 
                border: none; 
                border-radius: 3px; 
                padding: 4px 6px; 
                font-size: 10px;
                min-height: 25px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """
        
        self.up_btn = QPushButton("↑ Up")
        self.down_btn = QPushButton("↓ Down")
        self.stop_btn = QPushButton("■ Stop")
        
        self.up_btn.setStyleSheet(btn_style)
        self.down_btn.setStyleSheet(btn_style)
        self.stop_btn.setStyleSheet(btn_style)

        self.up_btn.clicked.connect(self.move_up)
        self.down_btn.clicked.connect(self.move_down)
        self.stop_btn.clicked.connect(self.stop_motor)

        btn_layout.addWidget(self.up_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.down_btn)
        control_layout.addLayout(btn_layout)

        layout.addLayout(control_layout)

        # 4. Speed Control (ultra-compact)
        speed_group = QGroupBox("Speed (°/s)")
        speed_group.setStyleSheet("font-size: 10px;")
        speed_layout = QHBoxLayout(speed_group)
        speed_layout.setSpacing(4)
        
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(1, 5)
        self.speed_spin.setValue(1)
        self.speed_spin.setStyleSheet("font-size: 10px; padding: 2px; min-width: 50px;")
        self.speed_spin.valueChanged.connect(lambda v: self.motor_thread.set_speed(float(v)))
        
        speed_layout.addWidget(QLabel("Speed:", styleSheet="font-size: 10px;"))
        speed_layout.addWidget(self.speed_spin)
        layout.addWidget(speed_group)

        # 5. GPIO Info (compact, non-intrusive)
        gpio_frame = QFrame()
        gpio_frame.setStyleSheet("background-color: #f8f9fa; border-radius: 3px; padding: 4px;")
        gpio_layout = QVBoxLayout(gpio_frame)
        gpio_layout.setSpacing(2)
        
        gpio_layout.addWidget(QLabel(
            f"Up: {self.alt_up_gpio} (Pin {self.alt_up_physical})",
            styleSheet="font-size: 9px; color: #666;"
        ))
        gpio_layout.addWidget(QLabel(
            f"Down: {self.alt_down_gpio} (Pin {self.alt_down_physical})",
            styleSheet="font-size: 9px; color: #666;"
        ))
        layout.addWidget(gpio_frame)

    def move_up(self):
        """Move 5° up (compact step size)"""
        current = self.motor_thread.current_alt
        self.motor_thread.set_target(current + 5.0)

    def move_down(self):
        """Move 5° down (compact step size)"""
        current = self.motor_thread.current_alt
        self.motor_thread.set_target(current - 5.0)

    def stop_motor(self):
        """Stop at current position"""
        self.motor_thread.set_target(self.motor_thread.current_alt)

    def update_altitude_display(self, value):
        """Update position display (compact format)"""
        self.alt_display.setText(f"Current: {value:.1f} °")
        self.alt_slider.setValue(int(round(value)))

    def show_error(self, error_msg):
        """Show compact error dialog"""
        QMessageBox.critical(self, "Altitude Error", error_msg[:60], QMessageBox.Ok)

    def close(self):
        """Safe cleanup on close"""
        self.motor_thread.stop()
        if self.motor_thread.motor:
            self.motor_thread.motor.close()