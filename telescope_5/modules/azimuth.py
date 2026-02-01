import sys
import os
from gpiozero import OutputDevice, PWMOutputDevice
from time import sleep
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QComboBox, QSpinBox, QMessageBox, QSlider
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer

# Azimuth Motor Thread (GPIOZero)
class AzimuthMotorThread(QThread):
    position_updated = pyqtSignal(float)
    error = pyqtSignal(str)

    def __init__(self, left_pin=22, right_pin=23):
        super().__init__()
        self.left_pin = left_pin
        self.right_pin = right_pin
        self.target_az = 0.0
        self.current_az = 0.0
        self.speed = 0.5
        self.running = False
        
        # GPIOZero PWM Setup
        self.motor_left = PWMOutputDevice(left_pin, initial_value=0, frequency=100)
        self.motor_right = PWMOutputDevice(right_pin, initial_value=0, frequency=100)

    def set_pins(self, left_pin, right_pin):
        """Update GPIO pins safely"""
        self.stop()
        self.motor_left.close()
        self.motor_right.close()
        self.left_pin = left_pin
        self.right_pin = right_pin
        self.motor_left = PWMOutputDevice(left_pin, initial_value=0, frequency=100)
        self.motor_right = PWMOutputDevice(right_pin, initial_value=0, frequency=100)

    def set_target(self, target_az):
        self.target_az = target_az % 360.0  # 0-360° azimuth wrap

    def set_speed(self, speed):
        self.speed = max(0.1, min(1.0, speed))

    def stop(self):
        self.running = False
        self.motor_left.value = 0
        self.motor_right.value = 0

    def run(self):
        self.running = True
        while self.running:
            if abs(self.current_az - self.target_az) < 0.1:
                self.motor_left.value = 0
                self.motor_right.value = 0
                sleep(0.1)
                continue

            # Calculate shortest path (0-360 wrap)
            diff = self.target_az - self.current_az
            if abs(diff) > 180:
                diff = diff - 360 if diff > 0 else diff + 360

            # Move left/right
            if diff > 0:
                self.motor_right.value = self.speed
                self.motor_left.value = 0
                self.current_az += 0.1 * self.speed
            else:
                self.motor_right.value = 0
                self.motor_left.value = self.speed
                self.current_az -= 0.1 * self.speed

            # Wrap to 0-360
            self.current_az = self.current_az % 360.0
            self.position_updated.emit(self.current_az)
            sleep(0.05)

    def close(self):
        """Safe GPIO cleanup"""
        self.stop()
        self.motor_left.close()
        self.motor_right.close()

# Main Azimuth Widget (Physical Pin Display)
class AzimuthControlWidget(QWidget):
    def __init__(self, config, save_gpio_config, pin_map):
        super().__init__()
        self.config = config
        self.save_gpio_config = save_gpio_config
        self.pin_map = pin_map  # "GPIOxx": (bcm_num, physical_num)

        # Safe Pin Lookup
        az_left_key = self.config["gpio"].get("azimuth_left", "GPIO22")
        az_right_key = self.config["gpio"].get("azimuth_right", "GPIO23")
        
        # Extract BCM numbers
        az_left_pin = self.pin_map[az_left_key][0]
        az_right_pin = self.pin_map[az_right_key][0]

        # Initialize Motor Thread
        self.motor_thread = AzimuthMotorThread(az_left_pin, az_right_pin)
        self.motor_thread.position_updated.connect(self._update_position)
        self.motor_thread.error.connect(self._show_error)
        self.motor_thread.set_target(float(self.config["telescope"]["park_azimuth"]))

        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        # GPIO Pin Selection (Physical Pins in Brackets)
        pin_group = QGroupBox("GPIO Pin Configuration (Azimuth)")
        pin_layout = QHBoxLayout(pin_group)
        
        # Left Pin Combo
        pin_layout.addWidget(QLabel("Left Motor Pin:"))
        self.left_pin_combo = QComboBox()
        for gpio_key in self.pin_map.keys():
            bcm_num, physical_num = self.pin_map[gpio_key]
            self.left_pin_combo.addItem(f"{gpio_key} (Pin {physical_num})", gpio_key)
        self.left_pin_combo.setCurrentIndex(self.left_pin_combo.findData(az_left_key))
        self.left_pin_combo.currentTextChanged.connect(self._update_left_pin)
        pin_layout.addWidget(self.left_pin_combo)
        
        # Right Pin Combo
        pin_layout.addWidget(QLabel("Right Motor Pin:"))
        self.right_pin_combo = QComboBox()
        for gpio_key in self.pin_map.keys():
            bcm_num, physical_num = self.pin_map[gpio_key]
            self.right_pin_combo.addItem(f"{gpio_key} (Pin {physical_num})", gpio_key)
        self.right_pin_combo.setCurrentIndex(self.right_pin_combo.findData(az_right_key))
        self.right_pin_combo.currentTextChanged.connect(self._update_right_pin)
        pin_layout.addWidget(self.right_pin_combo)
        
        main_layout.addWidget(pin_group)

        # Position Control
        control_group = QGroupBox("Azimuth Control (0-360°)")
        control_layout = QVBoxLayout(control_group)

        # Current Position Display
        self.position_label = QLabel(f"Current Azimuth: {self.motor_thread.current_az:.1f}°")
        self.position_label.setAlignment(Qt.AlignCenter)
        self.position_label.setStyleSheet("font-size: 16px; margin: 10px;")
        control_layout.addWidget(self.position_label)

        # Target Slider (0-360°)
        self.az_slider = QSlider(Qt.Horizontal)
        self.az_slider.setRange(0, 360)
        self.az_slider.setValue(int(self.motor_thread.target_az))
        self.az_slider.setTickPosition(QSlider.TicksBelow)
        self.az_slider.setTickInterval(10)
        self.az_slider.valueChanged.connect(lambda v: self.motor_thread.set_target(float(v)))
        control_layout.addWidget(self.az_slider)

        # Speed Control
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Motor Speed (0.1-1.0):"))
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(1, 10)
        self.speed_spin.setValue(int(self.motor_thread.speed * 10))
        self.speed_spin.valueChanged.connect(lambda v: self.motor_thread.set_speed(v/10))
        speed_layout.addWidget(self.speed_spin)
        control_layout.addLayout(speed_layout)

        # Control Buttons
        btn_layout = QHBoxLayout()
        
        self.left_btn = QPushButton("⬅️ Move Left (1°)")
        self.left_btn.setStyleSheet("font-size: 14px; padding: 10px;")
        self.left_btn.clicked.connect(lambda: self.motor_thread.set_target(self.motor_thread.current_az - 1))
        btn_layout.addWidget(self.left_btn)
        
        self.right_btn = QPushButton("➡️ Move Right (1°)")
        self.right_btn.setStyleSheet("font-size: 14px; padding: 10px;")
        self.right_btn.clicked.connect(lambda: self.motor_thread.set_target(self.motor_thread.current_az + 1))
        btn_layout.addWidget(self.right_btn)
        
        self.park_btn = QPushButton("Park (0°)")
        self.park_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        self.park_btn.clicked.connect(self._park_azimuth)
        btn_layout.addWidget(self.park_btn)
        
        self.emergency_btn = QPushButton("🛑 Stop")
        self.emergency_btn.setStyleSheet("background-color: #ff0000; color: white; padding: 10px;")
        self.emergency_btn.clicked.connect(self._emergency_stop)
        btn_layout.addWidget(self.emergency_btn)
        
        control_layout.addLayout(btn_layout)
        main_layout.addWidget(control_group)

        # Start Motor Thread
        self.motor_thread.start()

    # Update Left Pin (FIXED: Safe status bar access)
    def _update_left_pin(self):
        selected_text = self.left_pin_combo.currentText()
        selected_gpio = self.left_pin_combo.currentData()
        bcm_pin = self.pin_map[selected_gpio][0]
        
        self.motor_thread.set_pins(bcm_pin, self.motor_thread.right_pin)
        self.save_gpio_config(self.config, "azimuth", "left", selected_gpio)
        # Safe status bar access (only if parent exists)
        if self.parent() and hasattr(self.parent(), 'statusBar'):
            self.parent().statusBar().showMessage(f"Updated Azimuth Left Pin: {selected_text}")

    # Update Right Pin (FIXED: Safe status bar access)
    def _update_right_pin(self):
        selected_text = self.right_pin_combo.currentText()
        selected_gpio = self.right_pin_combo.currentData()
        bcm_pin = self.pin_map[selected_gpio][0]
        
        self.motor_thread.set_pins(self.motor_thread.left_pin, bcm_pin)
        self.save_gpio_config(self.config, "azimuth", "right", selected_gpio)
        # Safe status bar access
        if self.parent() and hasattr(self.parent(), 'statusBar'):
            self.parent().statusBar().showMessage(f"Updated Azimuth Right Pin: {selected_text}")

    # Update Position Display
    def _update_position(self, pos):
        self.position_label.setText(f"Current Azimuth: {pos:.1f}°")

    # Park Azimuth
    def _park_azimuth(self):
        self.motor_thread.set_target(0.0)
        self.az_slider.setValue(0)

    # Emergency Stop
    def _emergency_stop(self):
        self.motor_thread.stop()

    # Show Error
    def _show_error(self, msg):
        QMessageBox.critical(self, "Azimuth Error", msg)

    # Safe Close
    def close(self):
        self.motor_thread.close()
        self.motor_thread.quit()
        self.motor_thread.wait()