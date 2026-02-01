"""
Azimuth Motor Control Module
Optimized for Raspberry Pi 5 (800x480 Touchscreen)
No Pigpio Dependency - Pure GPIOZero (Pi 5 Compatible)
"""
import sys
import time
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSlider, QProgressBar, QGroupBox, QGridLayout, QComboBox,
    QLineEdit, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QMutex, QMutexLocker
from PyQt5.QtGui import QFont

# --------------------------
# Fixed Import Logic (Pi 5 Compatible)
# --------------------------
try:
    # Relative import for normal operation
    from . import SETTINGS, get_responsive_stylesheet, get_pin_display_name, save_settings
except ImportError:
    # Fallback import for standalone testing/Thonny compatibility
    import modules
    SETTINGS = modules.SETTINGS
    get_responsive_stylesheet = modules.get_responsive_stylesheet
    get_pin_display_name = modules.get_pin_display_name
    save_settings = modules.save_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --------------------------
# Azimuth Control Thread (Thread-Safe)
# --------------------------
class AzimuthThread(QThread):
    # Signals for UI updates
    status_update = pyqtSignal(str)
    position_update = pyqtSignal(int)
    error_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.mutex = QMutex()  # Thread safety
        self.running = False
        self.target_position = 0
        self.current_position = 0
        self.speed = SETTINGS["telescope"]["default_speed"]
        
        # GPIO Motor Configuration (Pi 5 Compatible - No Pigpio)
        self.motor = None
        self.pwm = None
        self.azimuth_pins = SETTINGS["gpio"]["azimuth_pins"]
        
        # GPIOZero Import (Safe)
        try:
            from gpiozero import Motor as GPIOMotor, PWMOutputDevice
            self.GPIOMotor = GPIOMotor
            self.PWMOutputDevice = PWMOutputDevice
            self.gpio_available = True
            logger.info("GPIOZero available - using real GPIO (Pi 5 compatible)")
        except ImportError:
            self.gpio_available = False
            logger.warning("GPIOZero not available - using mock motor (test mode)")
    
    def init_motor(self, pins=None):
        """Initialize azimuth motor (Pi 5 Compatible - No Pigpio)"""
        locker = QMutexLocker(self.mutex)
        
        # Update pins if provided
        if pins:
            self.azimuth_pins = pins
            SETTINGS["gpio"]["azimuth_pins"] = pins
            save_settings()
        
        try:
            if self.gpio_available:
                # Clean up existing motor/pwm
                if self.motor:
                    self.motor.stop()
                if self.pwm:
                    self.pwm.stop()
                
                # Use GPIOZero's DEFAULT pin factory (100% Pi 5 Compatible)
                self.motor = self.GPIOMotor(
                    forward=self.azimuth_pins["in1"],
                    backward=self.azimuth_pins["in2"]
                )
                self.pwm = self.PWMOutputDevice(
                    pin=self.azimuth_pins["ena"],
                    frequency=SETTINGS["gpio"]["pwm_frequency"]
                )
                self.pwm.value = self.speed / 100  # Convert % to 0-1 range
                
                logger.info(f"Azimuth motor initialized (Pi 5) - Pins: IN1={self.azimuth_pins['in1']}, IN2={self.azimuth_pins['in2']}, ENA={self.azimuth_pins['ena']}")
                self.status_update.emit(f"Motor Ready (Pins: {self.azimuth_pins['in1']}/{self.azimuth_pins['in2']}/{self.azimuth_pins['ena']})")
            else:
                self.status_update.emit("Using Mock Motor (Test Mode)")
                
        except Exception as e:
            error_msg = f"Motor Init Error: {str(e)} (Safe Mode Enabled)"
            logger.error(error_msg)
            self.status_update.emit(error_msg)
            # Safe mode - set motor to None (no crashes)
            self.motor = None
            self.pwm = None

    def set_azimuth(self, target):
        """Set target azimuth (0-360 degrees)"""
        locker = QMutexLocker(self.mutex)
        # Validate target range
        self.target_position = max(0, min(360, int(target)))
        self.status_update.emit(f"Target: {self.target_position}°")

    def set_speed(self, speed):
        """Set motor speed (10-100%)"""
        locker = QMutexLocker(self.mutex)
        self.speed = max(10, min(100, int(speed)))
        if self.pwm:
            self.pwm.value = self.speed / 100
        self.status_update.emit(f"Speed: {self.speed}%")

    def stop_motors(self):
        """Emergency stop motor"""
        locker = QMutexLocker(self.mutex)
        if self.motor:
            self.motor.stop()
        self.status_update.emit("Motor Stopped")

    def run(self):
        """Main thread loop (position control)"""
        self.running = True
        logger.info("Azimuth thread started")
        
        while self.running:
            try:
                locker = QMutexLocker(self.mutex)
                
                # Only move if motor is available and target != current
                if self.motor and self.current_position != self.target_position:
                    # Calculate direction (shortest path)
                    diff = self.target_position - self.current_position
                    if abs(diff) > 180:
                        # Wrap around (shorter path)
                        if diff > 0:
                            diff -= 360
                        else:
                            diff += 360
                    
                    if diff > 0:
                        # Move RIGHT (Clockwise)
                        self.motor.forward()
                        self.current_position += 0.2  # Simulated position increment
                        self.status_update.emit(f"Moving RIGHT - {self.current_position:.1f}°")
                    else:
                        # Move LEFT (Counter-Clockwise)
                        self.motor.backward()
                        self.current_position -= 0.2  # Simulated position increment
                        self.status_update.emit(f"Moving LEFT - {self.current_position:.1f}°")
                    
                    # Wrap position (0-360)
                    if self.current_position > 360:
                        self.current_position = 0
                    elif self.current_position < 0:
                        self.current_position = 360
                    
                    # Update UI with current position
                    self.position_update.emit(int(self.current_position))
                    
                    # Stop if target reached
                    if abs(self.current_position - self.target_position) < 0.2:
                        self.motor.stop()
                        self.current_position = self.target_position
                        self.position_update.emit(int(self.current_position))
                        self.status_update.emit(f"Reached Target: {self.target_position}°")
                
                locker.unlock()
                time.sleep(0.05)  # 50ms loop (smooth control)
                
            except Exception as e:
                error_msg = f"Thread Error: {str(e)}"
                logger.error(error_msg)
                self.error_signal.emit(error_msg)
                self.stop_motors()
                time.sleep(0.1)

    def stop(self):
        """Stop thread and motor"""
        locker = QMutexLocker(self.mutex)
        self.running = False
        self.stop_motors()
        logger.info("Azimuth thread stopped")

# --------------------------
# Azimuth Control Widget (800x480 Touchscreen Optimized)
# --------------------------
class AzimuthControlWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(get_responsive_stylesheet())
        self.azimuth_thread = None
        self.init_ui()
        self.init_thread()

    def init_ui(self):
        """Create UI (800x480 Touch-Friendly)"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # Title
        title_label = QLabel("Azimuth Control (0-360°)")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # GPIO Pin Configuration Group
        pin_group = QGroupBox("GPIO Pin Configuration")
        pin_layout = QGridLayout()
        pin_layout.setSpacing(6)

        # IN1 Pin Selection
        pin_layout.addWidget(QLabel("IN1 Pin:"), 0, 0)
        self.in1_combo = QComboBox()
        self.in1_combo.addItems([f"GPIO{i}" for i in range(2, 28)])
        self.in1_combo.setCurrentText(f"GPIO{SETTINGS['gpio']['azimuth_pins']['in1']}")
        pin_layout.addWidget(self.in1_combo, 0, 1)

        # IN2 Pin Selection
        pin_layout.addWidget(QLabel("IN2 Pin:"), 1, 0)
        self.in2_combo = QComboBox()
        self.in2_combo.addItems([f"GPIO{i}" for i in range(2, 28)])
        self.in2_combo.setCurrentText(f"GPIO{SETTINGS['gpio']['azimuth_pins']['in2']}")
        pin_layout.addWidget(self.in2_combo, 1, 1)

        # ENA Pin Selection
        pin_layout.addWidget(QLabel("ENA Pin:"), 2, 0)
        self.ena_combo = QComboBox()
        self.ena_combo.addItems([f"GPIO{i}" for i in range(2, 28)])
        self.ena_combo.setCurrentText(f"GPIO{SETTINGS['gpio']['azimuth_pins']['ena']}")
        pin_layout.addWidget(self.ena_combo, 2, 1)

        # Apply Pins Button
        self.apply_pins_btn = QPushButton("Apply Pins")
        self.apply_pins_btn.clicked.connect(self.apply_pins)
        pin_layout.addWidget(self.apply_pins_btn, 3, 0, 1, 2)

        pin_group.setLayout(pin_layout)
        main_layout.addWidget(pin_group)

        # Position Control Group
        control_group = QGroupBox("Position Control")
        control_layout = QVBoxLayout()
        control_layout.setSpacing(6)

        # Position Slider (0-360)
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 360)
        self.position_slider.setValue(0)
        self.position_slider.setTickInterval(30)
        self.position_slider.setTickPosition(QSlider.TicksBelow)
        self.position_slider.valueChanged.connect(self.on_slider_change)
        control_layout.addWidget(QLabel("Target Position (°):"))
        control_layout.addWidget(self.position_slider)

        # Position Display
        self.position_bar = QProgressBar()
        self.position_bar.setRange(0, 360)
        self.position_bar.setValue(0)
        self.position_bar.setFormat("Current: %v°")
        control_layout.addWidget(self.position_bar)

        # Speed Control
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Speed:"))
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(10, 100)
        self.speed_slider.setValue(SETTINGS["telescope"]["default_speed"])
        self.speed_slider.valueChanged.connect(self.on_speed_change)
        speed_layout.addWidget(self.speed_slider)
        self.speed_label = QLabel(f"{SETTINGS['telescope']['default_speed']}%")
        speed_layout.addWidget(self.speed_label)
        control_layout.addLayout(speed_layout)

        # Manual Control Buttons (Touch-Friendly Size)
        btn_layout = QHBoxLayout()
        self.left_btn = QPushButton("← LEFT")
        self.left_btn.setMinimumHeight(40)
        self.left_btn.clicked.connect(self.move_left)
        btn_layout.addWidget(self.left_btn)

        self.stop_btn = QPushButton("STOP")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setStyleSheet("background-color: #ff4444; color: white;")
        self.stop_btn.clicked.connect(self.stop_motor)
        btn_layout.addWidget(self.stop_btn)

        self.right_btn = QPushButton("RIGHT →")
        self.right_btn.setMinimumHeight(40)
        self.right_btn.clicked.connect(self.move_right)
        btn_layout.addWidget(self.right_btn)

        control_layout.addLayout(btn_layout)
        control_group.setLayout(control_layout)
        main_layout.addWidget(control_group)

        # Status Display
        self.status_label = QLabel("Status: Initializing...")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("background-color: #333333; padding: 5px; border-radius: 3px;")
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)

    def init_thread(self):
        """Initialize control thread"""
        self.azimuth_thread = AzimuthThread()
        # Connect signals to UI
        self.azimuth_thread.status_update.connect(self.update_status)
        self.azimuth_thread.position_update.connect(self.update_position)
        self.azimuth_thread.error_signal.connect(self.show_error)
        # Initialize motor with current pins
        self.apply_pins()
        # Start thread
        self.azimuth_thread.start()

    def apply_pins(self):
        """Apply selected GPIO pins"""
        try:
            # Get selected pins (convert "GPIO17" → 17)
            in1_pin = int(self.in1_combo.currentText().replace("GPIO", ""))
            in2_pin = int(self.in2_combo.currentText().replace("GPIO", ""))
            ena_pin = int(self.ena_combo.currentText().replace("GPIO", ""))
            
            # Update settings
            SETTINGS["gpio"]["azimuth_pins"] = {
                "in1": in1_pin,
                "in2": in2_pin,
                "ena": ena_pin
            }
            save_settings()
            
            # Re-initialize motor with new pins
            self.azimuth_thread.init_motor(SETTINGS["gpio"]["azimuth_pins"])
            self.update_status(f"Pins Updated: IN1={in1_pin}, IN2={in2_pin}, ENA={ena_pin}")
            
        except Exception as e:
            error_msg = f"Failed to apply pins: {str(e)}"
            self.show_error(error_msg)
            logger.error(error_msg)

    def on_slider_change(self, value):
        """Handle target position slider change"""
        self.azimuth_thread.set_azimuth(value)
        self.update_status(f"Target Set: {value}°")

    def on_speed_change(self, value):
        """Handle speed slider change"""
        self.azimuth_thread.set_speed(value)
        self.speed_label.setText(f"{value}%")

    def move_left(self):
        """Manual LEFT button"""
        current = self.position_slider.value()
        new_target = max(0, current - 10)
        self.position_slider.setValue(new_target)
        self.azimuth_thread.set_azimuth(new_target)

    def move_right(self):
        """Manual RIGHT button"""
        current = self.position_slider.value()
        new_target = min(360, current + 10)
        self.position_slider.setValue(new_target)
        self.azimuth_thread.set_azimuth(new_target)

    def stop_motor(self):
        """Emergency stop button"""
        self.azimuth_thread.stop_motors()
        self.update_status("Emergency Stop Triggered")

    def update_position(self, value):
        """Update position display"""
        self.position_bar.setValue(value)

    def update_status(self, message):
        """Update status label"""
        self.status_label.setText(f"Status: {message}")

    def show_error(self, message):
        """Show error message box"""
        QMessageBox.critical(self, "Azimuth Control Error", message)
        self.update_status(f"ERROR: {message}")

    def cleanup(self):
        """Cleanup thread and motor"""
        if self.azimuth_thread:
            self.azimuth_thread.stop()
            self.azimuth_thread.wait()  # Wait for thread to finish
        self.update_status("Cleanup Complete - Motor Stopped")

    def closeEvent(self, event):
        """Handle widget close"""
        self.cleanup()
        event.accept()

# --------------------------
# Standalone Test (For Debugging)
# --------------------------
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = AzimuthControlWidget()
    window.setWindowTitle("Azimuth Control (Pi 5)")
    window.resize(400, 400)  # Half of 800x480 for testing
    window.show()
    sys.exit(app.exec_())