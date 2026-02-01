import time
from threading import Lock
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QSlider, QGroupBox, QSpinBox, QFrame, QMessageBox
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from gpiozero import Motor  # No pigpio import!

# Locked GPIO/Physical Pin Mapping for Altitude (NON-CHANGEABLE)
LOCKED_ALT_PINS = {
    "up": {"gpio": "GPIO17", "physical": 11, "numeric": 17},
    "down": {"gpio": "GPIO18", "physical": 12, "numeric": 18}
}

class AltitudeMotorThread(QThread):
    position_signal = pyqtSignal(float)
    error_signal = pyqtSignal(str)

    def __init__(self, alt_up_pin, alt_down_pin):
        super().__init__()
        self.running = True
        self.lock = Lock()
        self.current_alt = 0.0
        self.target_alt = 0.0
        self.speed = 1.0  # Degrees per second

        # Initialize motor with DEFAULT pin factory (no pigpio!)
        self.alt_up_pin = alt_up_pin
        self.alt_down_pin = alt_down_pin
        try:
            self.motor = Motor(forward=alt_up_pin, backward=alt_down_pin)  # No pin_factory!
            self.motor.stop()
        except Exception as e:
            self.error_signal.emit(f"Altitude Motor Error: {str(e)}")
            self.motor = None

    def set_target(self, target):
        with self.lock:
            self.target_alt = max(0.0, min(90.0, target))

    def set_speed(self, speed):
        with self.lock:
            self.speed = max(0.1, min(5.0, speed))

    def run(self):
        if not self.motor:
            return

        while self.running:
            with self.lock:
                current = self.current_alt
                target = self.target_alt

            # Calculate difference
            diff = target - current
            if abs(diff) < 0.1:
                self.motor.stop()
                time.sleep(0.1)
                continue

            # Move motor
            try:
                if diff > 0:
                    self.motor.forward(self.speed / 5.0)  # Normalize speed (0-1)
                    self.current_alt += self.speed * 0.1
                else:
                    self.motor.backward(self.speed / 5.0)
                    self.current_alt -= self.speed * 0.1

                # Clamp value
                self.current_alt = max(0.0, min(90.0, self.current_alt))
                self.position_signal.emit(self.current_alt)
                time.sleep(0.1)
            except Exception as e:
                self.error_signal.emit(f"Altitude Movement Error: {str(e)}")
                self.motor.stop()
                time.sleep(1)

    def stop(self):
        with self.lock:
            self.running = False
        if self.motor:
            self.motor.stop()
        self.wait()

class AltitudeControlWidget(QWidget):
    def __init__(self, config, save_gpio_config, pin_map):
        super().__init__()
        self.config = config
        self.save_gpio_config = save_gpio_config
        self.pin_map = pin_map

        # FORCE Locked GPIO Pins (ignore config values, use fixed 17/18)
        self.alt_up_gpio = LOCKED_ALT_PINS["up"]["gpio"]
        self.alt_down_gpio = LOCKED_ALT_PINS["down"]["gpio"]
        self.alt_up_physical = LOCKED_ALT_PINS["up"]["physical"]
        self.alt_down_physical = LOCKED_ALT_PINS["down"]["physical"]
        self.alt_up_pin = LOCKED_ALT_PINS["up"]["numeric"]
        self.alt_down_pin = LOCKED_ALT_PINS["down"]["numeric"]

        # Validate (redundant but safe) - ensure no invalid pins
        if self.alt_up_gpio not in pin_map:
            QMessageBox.warning(self, "GPIO Locked", 
                               f"Altitude Up pin forced to {self.alt_up_gpio} (Physical Pin {self.alt_up_physical})")
        if self.alt_down_gpio not in pin_map:
            QMessageBox.warning(self, "GPIO Locked", 
                               f"Altitude Down pin forced to {self.alt_down_gpio} (Physical Pin {self.alt_down_physical})")

        # Motor thread
        self.motor_thread = AltitudeMotorThread(self.alt_up_pin, self.alt_down_pin)
        self.motor_thread.position_signal.connect(self.update_altitude_display)
        self.motor_thread.error_signal.connect(self.show_error)

        # UI Setup (800×480 optimized)
        self.init_ui()

        # Start motor thread
        self.motor_thread.start()

    def init_ui(self):
        layout = QVBoxLayout(self)
        # Small screen optimization: reduced spacing/margins
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title (smaller font for compact display)
        title = QLabel("Altitude Control (0° - 90°)")
        title.setObjectName("title_label")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #3498db;")
        layout.addWidget(title)

        # Current Position
        self.alt_display = QLabel("Current Altitude: 0.0 °")
        self.alt_display.setObjectName("value_label")
        self.alt_display.setAlignment(Qt.AlignCenter)
        self.alt_display.setStyleSheet("font-size: 12px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(self.alt_display)

        # Slider Control (Vertical, optimized size)
        self.alt_slider = QSlider(Qt.Vertical)
        self.alt_slider.setRange(0, 90)
        self.alt_slider.setValue(0)
        self.alt_slider.setTickInterval(10)
        self.alt_slider.setTickPosition(QSlider.TicksBothSides)
        self.alt_slider.setStyleSheet("QSlider { margin: 5px 0; }")
        self.alt_slider.valueChanged.connect(lambda v: self.motor_thread.set_target(float(v)))

        # Manual Buttons (smaller size for 800×480)
        btn_layout = QHBoxLayout()
        self.up_btn = QPushButton("↑ Up")
        self.down_btn = QPushButton("↓ Down")
        self.stop_btn = QPushButton("■ Stop")
        # Button styling for small screen
        btn_style = """
            QPushButton { 
                background-color: #3498db; 
                color: white; 
                border: none; 
                border-radius: 4px; 
                padding: 6px 8px; 
                font-size: 12px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """
        self.up_btn.setStyleSheet(btn_style)
        self.down_btn.setStyleSheet(btn_style)
        self.stop_btn.setStyleSheet(btn_style)

        self.up_btn.clicked.connect(self.move_up)
        self.down_btn.clicked.connect(self.move_down)
        self.stop_btn.clicked.connect(self.stop_motor)

        btn_layout.addWidget(self.up_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.down_btn)

        # Speed Control (compact group box)
        speed_group = QGroupBox("Speed (°/s)")
        speed_group.setStyleSheet("font-size: 12px;")
        speed_layout = QHBoxLayout(speed_group)
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(1, 5)
        self.speed_spin.setValue(1)
        self.speed_spin.setStyleSheet("font-size: 12px; padding: 2px;")
        self.speed_spin.valueChanged.connect(lambda v: self.motor_thread.set_speed(float(v)))
        speed_layout.addWidget(QLabel("Speed:", styleSheet="font-size: 12px;"))
        speed_layout.addWidget(self.speed_spin)

        # Combine Slider + Buttons (compact layout)
        control_layout = QHBoxLayout()
        control_layout.addWidget(self.alt_slider)
        control_layout.addLayout(btn_layout)

        # Add to main layout
        layout.addLayout(control_layout)
        layout.addWidget(speed_group)

        # GPIO Config Frame (CLEAR Physical Pin Display)
        gpio_frame = QFrame()
        gpio_frame.setStyleSheet("background-color: #f8f9fa; border-radius: 4px; padding: 8px;")
        gpio_layout = QVBoxLayout(gpio_frame)
        # Show GPIO + Physical Pin clearly
        gpio_layout.addWidget(QLabel(
            f"Up Pin: {self.alt_up_gpio} (Physical Pin {self.alt_up_physical})",
            styleSheet="font-size: 11px; color: #666;"
        ))
        gpio_layout.addWidget(QLabel(
            f"Down Pin: {self.alt_down_gpio} (Physical Pin {self.alt_down_physical})",
            styleSheet="font-size: 11px; color: #666;"
        ))
        layout.addWidget(gpio_frame)

    def move_up(self):
        current = self.motor_thread.current_alt
        self.motor_thread.set_target(current + 5.0)  # Move 5° up

    def move_down(self):
        current = self.motor_thread.current_alt
        self.motor_thread.set_target(current - 5.0)  # Move 5° down

    def stop_motor(self):
        self.motor_thread.set_target(self.motor_thread.current_alt)  # Stop at current position

    def update_altitude_display(self, value):
        self.alt_display.setText(f"Current Altitude: {value:.1f} °")
        self.alt_slider.setValue(int(round(value)))

    def show_error(self, error_msg):
        QMessageBox.critical(self, "Altitude Error", error_msg)

    def close(self):
        self.motor_thread.stop()
        if self.motor_thread.motor:
            self.motor_thread.motor.close()