import time
from threading import Lock
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QSlider, QGroupBox, QSpinBox, QFrame, QMessageBox
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from gpiozero import Motor  # No pigpio import!

# Locked GPIO/Physical Pin Mapping for Azimuth (NON-CHANGEABLE)
LOCKED_AZ_PINS = {
    "left": {"gpio": "GPIO22", "physical": 15, "numeric": 22},
    "right": {"gpio": "GPIO23", "physical": 16, "numeric": 23}
}

class AzimuthMotorThread(QThread):
    position_signal = pyqtSignal(float)
    error_signal = pyqtSignal(str)

    def __init__(self, az_left_pin, az_right_pin):
        super().__init__()
        self.running = True
        self.lock = Lock()
        self.current_az = 0.0
        self.target_az = 0.0
        self.speed = 1.0  # Degrees per second

        # Initialize motor with DEFAULT pin factory (no pigpio!)
        self.az_left_pin = az_left_pin
        self.az_right_pin = az_right_pin
        try:
            self.motor = Motor(forward=az_right_pin, backward=az_left_pin)  # No pin_factory!
            self.motor.stop()
        except Exception as e:
            self.error_signal.emit(f"Azimuth Motor Error: {str(e)}")
            self.motor = None

    def set_target(self, target):
        with self.lock:
            self.target_az = target % 360.0  # Wrap 0-360°

    def set_speed(self, speed):
        with self.lock:
            self.speed = max(0.1, min(5.0, speed))

    def run(self):
        if not self.motor:
            return

        while self.running:
            with self.lock:
                current = self.current_az
                target = self.target_az

            # Calculate shortest path (0-360° wrap)
            diff = target - current
            if abs(diff) > 180:
                diff = diff - 360 if diff > 0 else diff + 360

            if abs(diff) < 0.1:
                self.motor.stop()
                time.sleep(0.1)
                continue

            # Move motor
            try:
                if diff > 0:
                    self.motor.forward(self.speed / 5.0)  # Normalize speed (0-1)
                    self.current_az = (self.current_az + self.speed * 0.1) % 360.0
                else:
                    self.motor.backward(self.speed / 5.0)
                    self.current_az = (self.current_az - self.speed * 0.1) % 360.0

                self.position_signal.emit(self.current_az)
                time.sleep(0.1)
            except Exception as e:
                self.error_signal.emit(f"Azimuth Movement Error: {str(e)}")
                self.motor.stop()
                time.sleep(1)

    def stop(self):
        with self.lock:
            self.running = False
        if self.motor:
            self.motor.stop()
        self.wait()

class AzimuthControlWidget(QWidget):
    def __init__(self, config, save_gpio_config, pin_map):
        super().__init__()
        self.config = config
        self.save_gpio_config = save_gpio_config
        self.pin_map = pin_map

        # FORCE Locked GPIO Pins (ignore config values, use fixed 22/23)
        self.az_left_gpio = LOCKED_AZ_PINS["left"]["gpio"]
        self.az_right_gpio = LOCKED_AZ_PINS["right"]["gpio"]
        self.az_left_physical = LOCKED_AZ_PINS["left"]["physical"]
        self.az_right_physical = LOCKED_AZ_PINS["right"]["physical"]
        self.az_left_pin = LOCKED_AZ_PINS["left"]["numeric"]
        self.az_right_pin = LOCKED_AZ_PINS["right"]["numeric"]

        # Validate (redundant but safe) - ensure no invalid pins
        if self.az_left_gpio not in pin_map:
            QMessageBox.warning(self, "GPIO Locked", 
                               f"Azimuth Left pin forced to {self.az_left_gpio} (Physical Pin {self.az_left_physical})")
        if self.az_right_gpio not in pin_map:
            QMessageBox.warning(self, "GPIO Locked", 
                               f"Azimuth Right pin forced to {self.az_right_gpio} (Physical Pin {self.az_right_physical})")

        # Motor thread
        self.motor_thread = AzimuthMotorThread(self.az_left_pin, self.az_right_pin)
        self.motor_thread.position_signal.connect(self.update_azimuth_display)
        self.motor_thread.error_signal.connect(self.show_error)

        # UI Setup (800×480 optimized, matches altitude widget)
        self.init_ui()

        # Start motor thread
        self.motor_thread.start()

    def init_ui(self):
        layout = QVBoxLayout(self)
        # Small screen optimization: reduced spacing/margins
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title (smaller font for compact display)
        title = QLabel("Azimuth Control (0° - 360°)")
        title.setObjectName("title_label")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #3498db;")
        layout.addWidget(title)

        # Current Position
        self.az_display = QLabel("Current Azimuth: 0.0 °")
        self.az_display.setObjectName("value_label")
        self.az_display.setAlignment(Qt.AlignCenter)
        self.az_display.setStyleSheet("font-size: 12px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(self.az_display)

        # Slider Control (Horizontal, optimized size)
        self.az_slider = QSlider(Qt.Horizontal)
        self.az_slider.setRange(0, 360)
        self.az_slider.setValue(0)
        self.az_slider.setTickInterval(30)
        self.az_slider.setTickPosition(QSlider.TicksBothSides)
        self.az_slider.setStyleSheet("QSlider { margin: 5px 0; }")
        self.az_slider.valueChanged.connect(lambda v: self.motor_thread.set_target(float(v)))

        # Manual Buttons (smaller size for 800×480)
        btn_layout = QHBoxLayout()
        self.left_btn = QPushButton("← Left")
        self.right_btn = QPushButton("Right →")
        self.stop_btn = QPushButton("■ Stop")
        # Match altitude button styling
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
        self.left_btn.setStyleSheet(btn_style)
        self.right_btn.setStyleSheet(btn_style)
        self.stop_btn.setStyleSheet(btn_style)

        self.left_btn.clicked.connect(self.move_left)
        self.right_btn.clicked.connect(self.move_right)
        self.stop_btn.clicked.connect(self.stop_motor)

        btn_layout.addWidget(self.left_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.right_btn)

        # Speed Control (compact group box, matches altitude)
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
        control_layout = QVBoxLayout()
        control_layout.addWidget(self.az_slider)
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
            f"Left Pin: {self.az_left_gpio} (Physical Pin {self.az_left_physical})",
            styleSheet="font-size: 11px; color: #666;"
        ))
        gpio_layout.addWidget(QLabel(
            f"Right Pin: {self.az_right_gpio} (Physical Pin {self.az_right_physical})",
            styleSheet="font-size: 11px; color: #666;"
        ))
        layout.addWidget(gpio_frame)

    def move_left(self):
        current = self.motor_thread.current_az
        self.motor_thread.set_target(current - 10.0)  # Move 10° left

    def move_right(self):
        current = self.motor_thread.current_az
        self.motor_thread.set_target(current + 10.0)  # Move 10° right

    def stop_motor(self):
        self.motor_thread.set_target(self.motor_thread.current_az)  # Stop at current position

    def update_azimuth_display(self, value):
        self.az_display.setText(f"Current Azimuth: {value:.1f} °")
        self.az_slider.setValue(int(round(value)))

    def show_error(self, error_msg):
        QMessageBox.critical(self, "Azimuth Error", error_msg)

    def close(self):
        self.motor_thread.stop()
        if self.motor_thread.motor:
            self.motor_thread.motor.close()