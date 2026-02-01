import time
from threading import Lock
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QSlider, QGroupBox, QSpinBox, QFrame, QMessageBox
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from gpiozero import Motor  # No pigpio import (Pi 5 native)

# Locked GPIO/Physical Pin Mapping for Azimuth (NON-CHANGEABLE)
# FIXED: Updated to GPIO27 (left) / GPIO23 (right) per main.py requirements
# Pi 5 Optimized - Fixed pins for stability
LOCKED_AZ_PINS = {
    "left": {"gpio": "GPIO27", "physical": 13, "numeric": 27},  # Corrected from GPIO22!
    "right": {"gpio": "GPIO23", "physical": 16, "numeric": 23}
}

class AzimuthMotorThread(QThread):
    """Thread-safe azimuth motor control (Pi 5 optimized)"""
    position_signal = pyqtSignal(float)
    error_signal = pyqtSignal(str)

    def __init__(self, az_left_pin, az_right_pin):
        super().__init__()
        self.running = True
        self.lock = Lock()
        self.current_az = 0.0
        self.target_az = 0.0
        self.speed = 1.0  # Degrees per second (0.1-5.0 range)

        # Initialize motor with Pi 5 native pin factory (no pigpio!)
        self.az_left_pin = az_left_pin
        self.az_right_pin = az_right_pin
        try:
            self.motor = Motor(forward=az_right_pin, backward=az_left_pin)
            self.motor.stop()  # Ensure motor starts in stopped state
        except Exception as e:
            self.error_signal.emit(f"Azimuth Motor Error: {str(e)}")
            self.motor = None

    def set_target(self, target):
        """Set target azimuth (wrapped 0-360°)"""
        with self.lock:
            self.target_az = target % 360.0  # Wrap to 0-360°

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
                current = self.current_az
                target = self.target_az

            # Calculate shortest path (0-360° wrap)
            diff = target - current
            if abs(diff) > 180:
                diff = diff - 360 if diff > 0 else diff + 360

            if abs(diff) < 0.1:  # Stop if within 0.1° of target
                self.motor.stop()
                time.sleep(0.1)
                continue

            # Move motor (normalized speed 0-1 for gpiozero)
            try:
                speed_normalized = self.speed / 5.0  # Convert 1-5 → 0.2-1.0
                if diff > 0:
                    self.motor.forward(speed_normalized)
                    self.current_az = (self.current_az + self.speed * 0.1) % 360.0
                else:
                    self.motor.backward(speed_normalized)
                    self.current_az = (self.current_az - self.speed * 0.1) % 360.0

                self.position_signal.emit(self.current_az)
                time.sleep(0.1)  # Pi 5 optimized sleep (reduces CPU usage)
            except Exception as e:
                self.error_signal.emit(f"Azimuth Movement Error: {str(e)}")
                self.motor.stop()
                time.sleep(1)  # Pause before retrying

    def stop(self):
        """Safe motor stop (thread-safe)"""
        with self.lock:
            self.running = False
        if self.motor:
            self.motor.stop()
        self.wait()

class AzimuthControlWidget(QWidget):
    """Compact azimuth control widget (800×480 optimized)"""
    def __init__(self, config, save_gpio_config, pin_map):
        super().__init__()
        self.config = config
        self.save_gpio_config = save_gpio_config
        self.pin_map = pin_map

        # FORCE Locked GPIO Pins (ignore config - Pi 5 stability)
        # Corrected to GPIO27 (left) / GPIO23 (right)
        self.az_left_gpio = LOCKED_AZ_PINS["left"]["gpio"]
        self.az_right_gpio = LOCKED_AZ_PINS["right"]["gpio"]
        self.az_left_physical = LOCKED_AZ_PINS["left"]["physical"]
        self.az_right_physical = LOCKED_AZ_PINS["right"]["physical"]
        self.az_left_pin = LOCKED_AZ_PINS["left"]["numeric"]
        self.az_right_pin = LOCKED_AZ_PINS["right"]["numeric"]

        # Validate locked pins (redundant but safe)
        if self.az_left_gpio not in pin_map:
            QMessageBox.warning(self, "GPIO Locked", 
                               f"Azimuth Left pin forced to {self.az_left_gpio} (Physical Pin {self.az_left_physical})")
        if self.az_right_gpio not in pin_map:
            QMessageBox.warning(self, "GPIO Locked", 
                               f"Azimuth Right pin forced to {self.az_right_gpio} (Physical Pin {self.az_right_physical})")

        # Initialize motor thread
        self.motor_thread = AzimuthMotorThread(self.az_left_pin, self.az_right_pin)
        self.motor_thread.position_signal.connect(self.update_azimuth_display)
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
        title = QLabel("Azimuth (0°-360°)")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 12px; font-weight: bold; color: #3498db;")
        layout.addWidget(title)

        # 2. Current Position (compact display)
        self.az_display = QLabel("Current: 0.0 °")
        self.az_display.setAlignment(Qt.AlignCenter)
        self.az_display.setStyleSheet("font-size: 10px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(self.az_display)

        # 3. Control Layout (slider + buttons - compact)
        control_layout = QVBoxLayout()
        control_layout.setSpacing(5)

        # Horizontal Slider (compact size)
        self.az_slider = QSlider(Qt.Horizontal)
        self.az_slider.setRange(0, 360)
        self.az_slider.setValue(0)
        self.az_slider.setTickInterval(30)  # Fewer ticks = less clutter
        self.az_slider.setTickPosition(QSlider.TicksBothSides)
        self.az_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 8px;
                background: #ddd;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                width: 16px;
                height: 12px;
                background: #3498db;
                border-radius: 8px;
                margin: -4px 0;
            }
        """)
        self.az_slider.valueChanged.connect(lambda v: self.motor_thread.set_target(float(v)))
        control_layout.addWidget(self.az_slider)

        # Manual Buttons (compact size)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)
        
        # Button style (matches altitude widget - consistent look)
        btn_style = """
            QPushButton { 
                background-color: #3498db; 
                color: white; 
                border: none; 
                border-radius: 3px; 
                padding: 4px 6px; 
                font-size: 10px;
                min-height: 25px;
                flex: 1;
            }
            QPushButton:hover { background-color: #2980b9; }
        """
        
        self.left_btn = QPushButton("← Left")
        self.right_btn = QPushButton("Right →")
        self.stop_btn = QPushButton("■ Stop")
        
        self.left_btn.setStyleSheet(btn_style)
        self.right_btn.setStyleSheet(btn_style)
        self.stop_btn.setStyleSheet(btn_style)

        self.left_btn.clicked.connect(self.move_left)
        self.right_btn.clicked.connect(self.move_right)
        self.stop_btn.clicked.connect(self.stop_motor)

        btn_layout.addWidget(self.left_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.right_btn)
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
            f"Left: {self.az_left_gpio} (Pin {self.az_left_physical})",
            styleSheet="font-size: 9px; color: #666;"
        ))
        gpio_layout.addWidget(QLabel(
            f"Right: {self.az_right_gpio} (Pin {self.az_right_physical})",
            styleSheet="font-size: 9px; color: #666;"
        ))
        layout.addWidget(gpio_frame)

    def move_left(self):
        """Move 10° left (compact step size)"""
        current = self.motor_thread.current_az
        self.motor_thread.set_target(current - 10.0)

    def move_right(self):
        """Move 10° right (compact step size)"""
        current = self.motor_thread.current_az
        self.motor_thread.set_target(current + 10.0)

    def stop_motor(self):
        """Stop at current position"""
        self.motor_thread.set_target(self.motor_thread.current_az)

    def update_azimuth_display(self, value):
        """Update position display (compact format)"""
        self.az_display.setText(f"Current: {value:.1f} °")
        self.az_slider.setValue(int(round(value)))

    def show_error(self, error_msg):
        """Show compact error dialog"""
        QMessageBox.critical(self, "Azimuth Error", error_msg[:60], QMessageBox.Ok)

    def close(self):
        """Safe cleanup on close"""
        self.motor_thread.stop()
        if self.motor_thread.motor:
            self.motor_thread.motor.close()