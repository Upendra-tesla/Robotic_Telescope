"""
Sensor Control Module
Optimized for Raspberry Pi 5 (800x480 Touchscreen)
Fixed Signal Signature & Safe I2C Initialization
Supports Mock Data (No Physical Sensor Required)
"""
import sys
import time
import logging
import random
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QGridLayout, QProgressBar, QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QMutex, QMutexLocker
from PyQt5.QtGui import QFont, QColor

# --------------------------
# Fixed Import Logic (Pi 5 Compatible)
# --------------------------
try:
    # Relative import for normal operation
    from . import SETTINGS, get_responsive_stylesheet, save_settings
except ImportError:
    # Fallback import for standalone testing/Thonny compatibility
    import modules
    SETTINGS = modules.SETTINGS
    get_responsive_stylesheet = modules.get_responsive_stylesheet
    save_settings = modules.save_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --------------------------
# Sensor Thread (Fixed Signal Signature)
# --------------------------
class SensorThread(QThread):
    # FIXED: Explicit signal signature (emits dictionary)
    data_update = pyqtSignal(dict)
    status_update = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.mutex = QMutex()  # Thread safety
        self.running = False
        self.sensor_available = False
        
        # Sensor configuration (safe access to SETTINGS)
        self.i2c_address = SETTINGS["gpio"].get("sensor_i2c_address", "0x19")
        self.update_interval = 1.0  # 1 second update rate
        self.base_altitude = SETTINGS["location"].get("altitude", 10.0)
        
        # Try to initialize I2C (safe fallback for Pi 5)
        self._init_i2c()

    def _init_i2c(self):
        """Initialize I2C bus (Pi 5 Compatible - Safe Fallback)"""
        locker = QMutexLocker(self.mutex)
        
        try:
            # Import SMBus2 (I2C library)
            import smbus2
            import re
            
            # Convert hex address to decimal (e.g., "0x19" → 25)
            self.i2c_addr = int(self.i2c_address, 16)
            
            # Initialize I2C bus (bus 1 is default for Pi 5)
            self.bus = smbus2.SMBus(1)
            
            # Test communication with sensor (dummy read)
            # Replace with actual sensor-specific read for your hardware
            self.bus.read_byte(self.i2c_addr)
            
            self.sensor_available = True
            logger.info(f"I2C Sensor initialized (Address: {self.i2c_address}, Bus: 1)")
            self.status_update.emit(f"Sensor Connected: {self.i2c_address}")
            
        except ImportError:
            self.sensor_available = False
            logger.warning("SMBus2 not installed - using mock sensor data")
            self.status_update.emit("SMBus2 Missing - Mock Data Mode")
            
        except FileNotFoundError:
            self.sensor_available = False
            logger.warning("I2C bus not found (enable I2C in raspi-config)")
            self.status_update.emit("I2C Disabled - Mock Data Mode")
            
        except Exception as e:
            self.sensor_available = False
            error_msg = f"Sensor init failed: {str(e)}"
            logger.error(error_msg)
            self.status_update.emit(f"No Sensor - Mock Data Mode ({error_msg[:30]}...)")

    def _read_physical_sensor(self):
        """Read data from physical I2C sensor (replace with your sensor logic)"""
        # NOTE: Replace this with actual read logic for your sensor (e.g., BME280, HTU21D)
        # This is a placeholder for real sensor communication
        try:
            # Dummy read (replace with your sensor's register reads)
            raw_temp = self.bus.read_word_data(self.i2c_addr, 0x00)
            raw_hum = self.bus.read_word_data(self.i2c_addr, 0x02)
            raw_press = self.bus.read_word_data(self.i2c_addr, 0x04)
            raw_heading = self.bus.read_word_data(self.i2c_addr, 0x06)
            
            # Convert raw values to meaningful data (sensor-specific)
            data = {
                "temperature": round((raw_temp / 256.0) - 40.0, 1),
                "humidity": round((raw_hum / 256.0), 1),
                "pressure": round((raw_press / 100.0) + 950.0, 2),
                "compass_heading": round((raw_heading / 100.0) % 360, 1),
                "altitude": round(self.base_altitude + (raw_press % 20) / 2.0, 1)
            }
            return data
            
        except Exception as e:
            logger.error(f"Sensor read error: {e}")
            # Return mock data on read failure
            return self._generate_mock_data()

    def _generate_mock_data(self):
        """Generate realistic mock sensor data (no hardware required)"""
        # Add small random variations for realism
        temp_variation = random.uniform(-0.5, 0.5)
        hum_variation = random.uniform(-0.3, 0.3)
        press_variation = random.uniform(-0.2, 0.2)
        heading_variation = random.uniform(-1.0, 1.0)
        alt_variation = random.uniform(-0.1, 0.1)
        
        data = {
            "temperature": round(22.5 + temp_variation, 1),  # 20-25°C range
            "humidity": round(45.0 + hum_variation, 1),      # 40-50% range
            "pressure": round(1013.25 + press_variation, 2), # Sea level pressure
            "compass_heading": round((time.time() % 360) + heading_variation, 1),
            "altitude": round(self.base_altitude + alt_variation, 1)
        }
        return data

    def run(self):
        """Main sensor reading loop (Thread-Safe)"""
        self.running = True
        logger.info("Sensor thread started (Pi 5 compatible)")
        
        while self.running:
            try:
                locker = QMutexLocker(self.mutex)
                
                # Read data (physical or mock)
                if self.sensor_available:
                    sensor_data = self._read_physical_sensor()
                else:
                    sensor_data = self._generate_mock_data()
                
                # Emit data (matches signal signature: dict)
                self.data_update.emit(sensor_data)
                self.status_update.emit("Data updated successfully")
                
                locker.unlock()
                time.sleep(self.update_interval)  # 1Hz update rate
                
            except Exception as e:
                error_msg = f"Sensor thread error: {str(e)}"
                logger.error(error_msg)
                self.error_signal.emit(error_msg)
                time.sleep(self.update_interval)

    def stop(self):
        """Stop sensor thread (Thread-Safe)"""
        locker = QMutexLocker(self.mutex)
        self.running = False
        logger.info("Sensor thread stopped")
        
        # Cleanup I2C bus
        if hasattr(self, 'bus'):
            try:
                self.bus.close()
            except:
                pass

# --------------------------
# Sensor Widget (800x480 Touchscreen Optimized)
# --------------------------
class SensorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(get_responsive_stylesheet())
        self.sensor_thread = None
        self.current_data = {
            "temperature": 0.0,
            "humidity": 0.0,
            "pressure": 0.0,
            "compass_heading": 0.0,
            "altitude": 0.0
        }
        self.init_ui()
        self.init_thread()

    def init_ui(self):
        """Create Touch-Optimized UI (800x480)"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # Title
        title_label = QLabel("Environmental & Orientation Sensors")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # Sensor Data Grid (Touch-Friendly Sizing)
        data_group = QGroupBox("Sensor Readings")
        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)
        grid_layout.setContentsMargins(10, 10, 10, 10)

        # Temperature
        self.temp_label = QLabel("0.0 °C")
        self.temp_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.temp_label.setAlignment(Qt.AlignCenter)
        self.temp_bar = QProgressBar()
        self.temp_bar.setRange(-10, 50)  # -10°C to 50°C
        self.temp_bar.setValue(0)
        grid_layout.addWidget(QLabel("Temperature:"), 0, 0)
        grid_layout.addWidget(self.temp_label, 0, 1)
        grid_layout.addWidget(self.temp_bar, 0, 2)

        # Humidity
        self.hum_label = QLabel("0.0 %")
        self.hum_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.hum_label.setAlignment(Qt.AlignCenter)
        self.hum_bar = QProgressBar()
        self.hum_bar.setRange(0, 100)  # 0-100% RH
        self.hum_bar.setValue(0)
        grid_layout.addWidget(QLabel("Humidity:"), 1, 0)
        grid_layout.addWidget(self.hum_label, 1, 1)
        grid_layout.addWidget(self.hum_bar, 1, 2)

        # Pressure
        self.press_label = QLabel("0.0 hPa")
        self.press_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.press_label.setAlignment(Qt.AlignCenter)
        self.press_bar = QProgressBar()
        self.press_bar.setRange(900, 1100)  # 900-1100 hPa
        self.press_bar.setValue(1013)
        grid_layout.addWidget(QLabel("Pressure:"), 2, 0)
        grid_layout.addWidget(self.press_label, 2, 1)
        grid_layout.addWidget(self.press_bar, 2, 2)

        # Compass Heading
        self.heading_label = QLabel("0.0 °")
        self.heading_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.heading_label.setAlignment(Qt.AlignCenter)
        self.heading_bar = QProgressBar()
        self.heading_bar.setRange(0, 360)  # 0-360°
        self.heading_bar.setValue(0)
        grid_layout.addWidget(QLabel("Compass:"), 3, 0)
        grid_layout.addWidget(self.heading_label, 3, 1)
        grid_layout.addWidget(self.heading_bar, 3, 2)

        # Altitude
        self.alt_label = QLabel("0.0 m")
        self.alt_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.alt_label.setAlignment(Qt.AlignCenter)
        self.alt_bar = QProgressBar()
        self.alt_bar.setRange(0, 100)  # 0-100 meters
        self.alt_bar.setValue(0)
        grid_layout.addWidget(QLabel("Altitude:"), 4, 0)
        grid_layout.addWidget(self.alt_label, 4, 1)
        grid_layout.addWidget(self.alt_bar, 4, 2)

        data_group.setLayout(grid_layout)
        main_layout.addWidget(data_group)

        # Control Buttons (Touch-Friendly Size)
        btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh Sensor")
        self.refresh_btn.setMinimumHeight(40)
        self.refresh_btn.clicked.connect(self.refresh_sensor)
        btn_layout.addWidget(self.refresh_btn)

        self.calibrate_btn = QPushButton("Calibrate Compass")
        self.calibrate_btn.setMinimumHeight(40)
        self.calibrate_btn.clicked.connect(self.calibrate_compass)
        btn_layout.addWidget(self.calibrate_btn)
        main_layout.addLayout(btn_layout)

        # Status Display
        self.status_label = QLabel("Status: Initializing Sensor...")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("""
            background-color: #333333; 
            padding: 8px; 
            border-radius: 5px;
            font-size: 10px;
        """)
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)

    def init_thread(self):
        """Initialize sensor thread (Safe Startup)"""
        # Stop existing thread if running
        if self.sensor_thread:
            self.sensor_thread.stop()
            self.sensor_thread.wait()

        # Create and start new thread
        self.sensor_thread = SensorThread()
        
        # Connect signals (fixed signature matching)
        self.sensor_thread.data_update.connect(self.update_sensor_data)
        self.sensor_thread.status_update.connect(self.update_status)
        self.sensor_thread.error_signal.connect(self.show_error)
        
        # Start thread
        self.sensor_thread.start()

    def update_sensor_data(self, data):
        """Update UI with new sensor data (Thread-Safe)"""
        # Update current data store
        self.current_data = data

        # Update labels
        self.temp_label.setText(f"{data['temperature']} °C")
        self.hum_label.setText(f"{data['humidity']} %")
        self.press_label.setText(f"{data['pressure']} hPa")
        self.heading_label.setText(f"{data['compass_heading']} °")
        self.alt_label.setText(f"{data['altitude']} m")

        # Update progress bars with color coding
        self.temp_bar.setValue(int(data['temperature']))
        self._set_progress_color(self.temp_bar, data['temperature'], 18, 28)
        
        self.hum_bar.setValue(int(data['humidity']))
        self._set_progress_color(self.hum_bar, data['humidity'], 30, 60)
        
        self.press_bar.setValue(int(data['pressure']))
        self._set_progress_color(self.press_bar, data['pressure'], 1000, 1025)
        
        self.heading_bar.setValue(int(data['compass_heading']))
        self.heading_bar.setStyleSheet("QProgressBar { background-color: #444; color: white; }")
        
        self.alt_bar.setValue(int(data['altitude']))
        self._set_progress_color(self.alt_bar, data['altitude'], 0, 50)

    def _set_progress_color(self, bar, value, low, high):
        """Set progress bar color based on value range (visual feedback)"""
        if value < low:
            bar.setStyleSheet("QProgressBar { background-color: #444; color: white; } QProgressBar::chunk { background-color: #3498db; }")
        elif value > high:
            bar.setStyleSheet("QProgressBar { background-color: #444; color: white; } QProgressBar::chunk { background-color: #e74c3c; }")
        else:
            bar.setStyleSheet("QProgressBar { background-color: #444; color: white; } QProgressBar::chunk { background-color: #2ecc71; }")

    def refresh_sensor(self):
        """Restart sensor thread (refresh connection)"""
        self.update_status("Refreshing sensor connection...")
        self.init_thread()
        self.update_status("Sensor refreshed - using latest data")

    def calibrate_compass(self):
        """Compass calibration placeholder (add your logic)"""
        QMessageBox.information(
            self, 
            "Compass Calibration", 
            "To calibrate:\n1. Rotate sensor 360° slowly\n2. Keep sensor level\n3. Avoid metal objects"
        )
        self.update_status("Compass calibration initiated - follow on-screen instructions")

    def update_status(self, message):
        """Update status label with timestamp"""
        timestamp = time.strftime("%H:%M:%S")
        self.status_label.setText(f"[{timestamp}] Status: {message}")

    def show_error(self, message):
        """Show error message and update status"""
        QMessageBox.critical(self, "Sensor Error", message)
        self.update_status(f"ERROR: {message}")

    def cleanup(self):
        """Cleanup thread on exit"""
        if self.sensor_thread:
            self.sensor_thread.stop()
            self.sensor_thread.wait()
        self.update_status("Sensor thread cleaned up - safe to exit")

    def closeEvent(self, event):
        """Handle widget close event"""
        self.cleanup()
        event.accept()

# --------------------------
# Standalone Test (For Debugging)
# --------------------------
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = SensorWidget()
    window.setWindowTitle("Sensor Control (Pi 5)")
    window.resize(400, 400)  # Half of 800x480 for testing
    window.show()
    sys.exit(app.exec_())