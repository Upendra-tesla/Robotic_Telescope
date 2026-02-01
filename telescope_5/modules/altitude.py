import sys
import os
from gpiozero import OutputDevice, PWMOutputDevice
from time import sleep
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QComboBox, QSpinBox, QMessageBox, QSlider
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer

# Motor Control Thread (GPIOZero + Pi 5 Safe)
class AltitudeMotorThread(QThread):
    position_updated = pyqtSignal(float)
    error = pyqtSignal(str)

    def __init__(self, up_pin=17, down_pin=18):
        super().__init__()
        self.up_pin = up_pin
        self.down_pin = down_pin
        self.target_alt = 0.0
        self.current_alt = 0.0
        self.speed = 0.5
        self.running = False
        
        # GPIOZero PWM Setup (smooth movement)
        self.motor_up = PWMOutputDevice(up_pin, initial_value=0, frequency=100)
        self.motor_down = PWMOutputDevice(down_pin, initial_value=0, frequency=100)

    def set_pins(self, up_pin, down_pin):
        """Update GPIO pins (safe reinitialization)"""
        self.stop()
        self.motor_up.close()
        self.motor_down.close()
        self.up_pin = up_pin
        self.down_pin = down_pin
        self.motor_up = PWMOutputDevice(up_pin, initial_value=0, frequency=100)
        self.motor_down = PWMOutputDevice(down_pin, initial_value=0, frequency=100)

    def set_target(self, target_alt):
        self.target_alt = max(0.0, min(90.0, target_alt))  # 0-90° altitude limit

    def set_speed(self, speed):
        self.speed = max(0.1, min(1.0, speed))  # 0.1-1.0 speed limit

    def stop(self):
        self.running = False
        self.motor_up.value = 0
        self.motor_down.value = 0

    def run(self):
        self.running = True
        while self.running:
            if abs(self.current_alt - self.target_alt) < 0.1:
                self.motor_up.value = 0
                self.motor_down.value = 0
                sleep(0.1)
                continue

            # Move to target
            if self.current_alt < self.target_alt:
                self.motor_up.value = self.speed
                self.motor_down.value = 0
                self.current_alt += 0.1 * self.speed
            else:
                self.motor_up.value = 0
                self.motor_down.value = self.speed
                self.current_alt -= 0.1 * self.speed

            self.position_updated.emit(self.current_alt)
            sleep(0.05)  # Pi 5 CPU optimization

    def close(self):
        """Safe GPIO cleanup (critical for Pi 5)"""
        self.stop()
        self.motor_up.close()
        self.motor_down.close()

# Main Altitude Widget (Physical Pin Display)
class AltitudeControlWidget(QWidget):
    def __init__(self, config, save_gpio_config, pin_map):
        super().__init__()
        self.config = config
        self.save_gpio_config = save_gpio_config
        self.pin_map = pin_map  # Format: "GPIOxx": (bcm_num, physical_num)

        # Safe GPIO Pin Lookup
        alt_up_key = self.config["gpio"].get("alt_up", "GPIO17")
        alt_down_key = self.config["gpio"].get("alt_down", "GPIO18")
        
        # Extract BCM numbers (ignore physical for GPIOZero)
        alt_up_pin = self.pin_map[alt_up_key][0]  # BCM number
        alt_down_pin = self.pin_map[alt_down_key][0]  # BCM number

        # Initialize Motor Thread
        self.motor_thread = AltitudeMotorThread(alt_up_pin, alt_down_pin)
        self.motor_thread.position_updated.connect(self._update_position)
        self.motor_thread.error.connect(self._show_error)
        self.motor_thread.set_target(float(self.config["telescope"]["park_altitude"]))

        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        # GPIO Pin Selection (With Physical Pin Numbers)
        pin_group = QGroupBox("GPIO Pin Configuration (Altitude)")
        pin_layout = QHBoxLayout(pin_group)
        
        # Up Pin Combo (GPIOxx (Pin X))
        pin_layout.addWidget(QLabel("Up Motor Pin:"))
        self.up_pin_combo = QComboBox()
        # Populate with BCM + physical pin labels
        for gpio_key in self.pin_map.keys():
            bcm_num, physical_num = self.pin_map[gpio_key]
            self.up_pin_combo.addItem(f"{gpio_key} (Pin {physical_num})", gpio_key)
        # Set current selection (match GPIO key)
        self.up_pin_combo.setCurrentIndex(self.up_pin_combo.findData(alt_up_key))
        self.up_pin_combo.currentTextChanged.connect(self._update_up_pin)
        pin_layout.addWidget(self.up_pin_combo)
        
        # Down Pin Combo (GPIOxx (Pin X))
        pin_layout.addWidget(QLabel("Down Motor Pin:"))
        self.down_pin_combo = QComboBox()
        for gpio_key in self.pin_map.keys():
            bcm_num, physical_num = self.pin_map[gpio_key]
            self.down_pin_combo.addItem(f"{gpio_key} (Pin {physical_num})", gpio_key)
        self.down_pin_combo.setCurrentIndex(self.down_pin_combo.findData(alt_down_key))
        self.down_pin_combo.currentTextChanged.connect(self._update_down_pin)
        pin_layout.addWidget(self.down_pin_combo)
        
        main_layout.addWidget(pin_group)

        # Position Control
        control_group = QGroupBox("Altitude Control (0-90°)")
        control_layout = QVBoxLayout(control_group)

        # Current Position Display
        self.position_label = QLabel(f"Current Altitude: {self.motor_thread.current_alt:.1f}°")
        self.position_label.setAlignment(Qt.AlignCenter)
        self.position_label.setStyleSheet("font-size: 16px; margin: 10px;")
        control_layout.addWidget(self.position_label)

        # Target Slider
        self.alt_slider = QSlider(Qt.Horizontal)
        self.alt_slider.setRange(0, 90)
        self.alt_slider.setValue(int(self.motor_thread.target_alt))
        self.alt_slider.setTickPosition(QSlider.TicksBelow)
        self.alt_slider.setTickInterval(5)
        self.alt_slider.valueChanged.connect(lambda v: self.motor_thread.set_target(float(v)))
        control_layout.addWidget(self.alt_slider)

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
        
        self.up_btn = QPushButton("⬆️ Move Up (1°)")
        self.up_btn.setStyleSheet("font-size: 14px; padding: 10px;")
        self.up_btn.clicked.connect(lambda: self.motor_thread.set_target(self.motor_thread.current_alt + 1))
        btn_layout.addWidget(self.up_btn)
        
        self.down_btn = QPushButton("⬇️ Move Down (1°)")
        self.down_btn.setStyleSheet("font-size: 14px; padding: 10px;")
        self.down_btn.clicked.connect(lambda: self.motor_thread.set_target(self.motor_thread.current_alt - 1))
        btn_layout.addWidget(self.down_btn)
        
        self.park_btn = QPushButton("Park (0°)")
        self.park_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        self.park_btn.clicked.connect(self._park_altitude)
        btn_layout.addWidget(self.park_btn)
        
        self.emergency_btn = QPushButton("🛑 Stop")
        self.emergency_btn.setStyleSheet("background-color: #ff0000; color: white; padding: 10px;")
        self.emergency_btn.clicked.connect(self._emergency_stop)
        btn_layout.addWidget(self.emergency_btn)
        
        control_layout.addLayout(btn_layout)
        main_layout.addWidget(control_group)

        # Start Motor Thread
        self.motor_thread.start()

    # Update Up Pin (Save config with GPIO key, not display text)
   # In _update_up_pin (line 203)
    def _update_up_pin(self):
        selected_text = self.up_pin_combo.currentText()
        selected_gpio = self.up_pin_combo.currentData()  # Get "GPIOxx" (not display text)
        bcm_pin = self.pin_map[selected_gpio][0]
        
        # Update motor pins
        self.motor_thread.set_pins(bcm_pin, self.motor_thread.down_pin)
        # Save to config
        self.save_gpio_config(self.config, "altitude", "up", selected_gpio)
        # FIX: Safe status bar access
        if self.parent() and hasattr(self.parent(), 'statusBar'):
            self.parent().statusBar().showMessage(f"Updated Altitude Up Pin: {selected_text}")

    # In _update_down_pin (line 214)
    def _update_down_pin(self):
        selected_text = self.down_pin_combo.currentText()
        selected_gpio = self.down_pin_combo.currentData()
        bcm_pin = self.pin_map[selected_gpio][0]
        
        self.motor_thread.set_pins(self.motor_thread.up_pin, bcm_pin)
        self.save_gpio_config(self.config, "altitude", "down", selected_gpio)
        # FIX: Safe status bar access
        if self.parent() and hasattr(self.parent(), 'statusBar'):
            self.parent().statusBar().showMessage(f"Updated Altitude Down Pin: {selected_text}")
       
    # Update Position Display
    def _update_position(self, pos):
        self.position_label.setText(f"Current Altitude: {pos:.1f}°")

    # Park Altitude
    def _park_altitude(self):
        self.motor_thread.set_target(0.0)
        self.alt_slider.setValue(0)

    # Emergency Stop
    def _emergency_stop(self):
        self.motor_thread.stop()

    # Show Error
    def _show_error(self, msg):
        QMessageBox.critical(self, "Altitude Error", msg)

    # Safe Close (GPIO Cleanup)
    def close(self):
        self.motor_thread.close()
        self.motor_thread.quit()
        self.motor_thread.wait()