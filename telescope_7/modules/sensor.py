# ==============================================
# LSM303DLH Sensor Widget (REAL DATA ONLY | NO BME | NO DUMMY)
# ==============================================
import sys
import time
import math
import smbus2
from threading import Lock
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, 
    QPushButton, QGridLayout, QSizePolicy, QMessageBox
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QFont

# ==============================================
# LSM303DLH Constants (Real Sensor Only)
# ==============================================
# I2C Addresses
ACCEL_ADDR = 0x18
MAG_ADDR = 0x1E

# Accelerometer Registers
ACCEL_CTRL_REG1_A = 0x20
ACCEL_CTRL_REG4_A = 0x23
ACCEL_OUT_X_L_A = 0x28

# Magnetometer Registers
MAG_CRA_REG_M = 0x00
MAG_CRB_REG_M = 0x01
MAG_MR_REG_M = 0x02
MAG_OUT_X_H_M = 0x03

# ==============================================
# LSM303DLH Driver (REAL DATA ONLY)
# ==============================================
class LSM303DLH:
    def __init__(self, i2c_bus=1):
        self.bus = smbus2.SMBus(i2c_bus)
        self.accel_addr = ACCEL_ADDR
        self.mag_addr = MAG_ADDR
        self.lock = Lock()
        self.initialized = False

    def initialize(self):
        """Initialize LSM303DLH (REAL HARDWARE ONLY)"""
        with self.lock:
            try:
                # Initialize Accelerometer (100Hz, normal power)
                self.bus.write_byte_data(self.accel_addr, ACCEL_CTRL_REG1_A, 0x27)  # 100Hz, X/Y/Z enabled
                self.bus.write_byte_data(self.accel_addr, ACCEL_CTRL_REG4_A, 0x00)  # ±2g range
                
                # Initialize Magnetometer (75Hz, normal mode)
                self.bus.write_byte_data(self.mag_addr, MAG_CRA_REG_M, 0x18)  # 75Hz output rate
                self.bus.write_byte_data(self.mag_addr, MAG_CRB_REG_M, 0x20)  # ±1.3g range
                self.bus.write_byte_data(self.mag_addr, MAG_MR_REG_M, 0x00)   # Continuous conversion mode
                
                self.initialized = True
                return True
            except Exception as e:
                raise RuntimeError(f"Failed to initialize LSM303DLH: {str(e)}")

    def read_accelerometer(self):
        """Read real accelerometer data (g)"""
        if not self.initialized:
            raise RuntimeError("LSM303DLH not initialized")
        
        with self.lock:
            try:
                # Read 6 bytes (X/Y/Z low/high)
                data = self.bus.read_i2c_block_data(self.accel_addr, ACCEL_OUT_X_L_A | 0x80, 6)
                
                # Convert to raw values
                x = (data[1] << 8) | data[0]
                y = (data[3] << 8) | data[2]
                z = (data[5] << 8) | data[4]
                
                # Convert to signed 16-bit values
                x = x if x < 32768 else x - 65536
                y = y if y < 32768 else y - 65536
                z = z if z < 32768 else z - 65536
                
                # Convert to g (±2g range: 1 LSB = 0.000061 g)
                x_g = x * 0.000061
                y_g = y * 0.000061
                z_g = z * 0.000061
                
                return (round(x_g, 2), round(y_g, 2), round(z_g, 2))
            except Exception as e:
                raise RuntimeError(f"Failed to read accelerometer: {str(e)}")

    def read_magnetometer_calibrated(self):
        """Read real magnetometer data (mG)"""
        if not self.initialized:
            raise RuntimeError("LSM303DLH not initialized")
        
        with self.lock:
            try:
                # Read 6 bytes (X/Y/Z high/low)
                data = self.bus.read_i2c_block_data(self.mag_addr, MAG_OUT_X_H_M, 6)
                
                # Convert to raw values
                x = (data[0] << 8) | data[1]
                y = (data[2] << 8) | data[3]
                z = (data[4] << 8) | data[5]
                
                # Convert to signed 16-bit values
                x = x if x < 32768 else x - 65536
                y = y if y < 32768 else y - 65536
                z = z if z < 32768 else z - 65536
                
                # Convert to mG (±1.3g range: 1 LSB = 0.061 mG)
                x_mg = x * 0.061
                y_mg = y * 0.061
                z_mg = z * 0.061
                
                return (round(x_mg, 1), round(y_mg, 1), round(z_mg, 1))
            except Exception as e:
                raise RuntimeError(f"Failed to read magnetometer: {str(e)}")

    def close(self):
        """Close I2C bus (safe shutdown)"""
        with self.lock:
            if self.bus:
                try:
                    self.bus.close()
                except:
                    pass
            self.initialized = False

# ==============================================
# Real Sensor Thread (NO DUMMY DATA)
# ==============================================
class SensorThread(QThread):
    data_signal = pyqtSignal(tuple, tuple)  # (accel_data, mag_data)
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, i2c_bus=1):
        super().__init__()
        self.i2c_bus = i2c_bus
        self.running = False
        self.lock = Lock()
        self.sensor = None

    def run(self):
        """Main sensor thread (REAL DATA ONLY)"""
        # Initialize real sensor (no fallback)
        try:
            self.sensor = LSM303DLH(i2c_bus=self.i2c_bus)
            self.sensor.initialize()
            self.status_signal.emit("LSM303DLH initialized - reading real data")
        except Exception as e:
            self.error_signal.emit(f"Sensor initialization failed: {str(e)}")
            self.running = False
            return

        # Read real sensor data (10Hz)
        while self.running:
            try:
                accel_data = self.sensor.read_accelerometer()
                mag_data = self.sensor.read_magnetometer_calibrated()
                self.data_signal.emit(accel_data, mag_data)
                self.status_signal.emit(f"Active - Accel: {accel_data} | Mag: {mag_data}")
                time.sleep(0.1)  # 10Hz update rate (Pi 5 optimized)
            except Exception as e:
                error_msg = f"Real sensor read error: {str(e)}"
                self.error_signal.emit(error_msg)
                self.status_signal.emit(error_msg)
                time.sleep(1)
                # Re-initialize on error (real hardware recovery)
                try:
                    self.sensor.initialize()
                except:
                    self.error_signal.emit("Failed to re-initialize sensor - stopping")
                    self.running = False
                    break

    def start_sensor(self):
        """Start real sensor thread (no dummy)"""
        with self.lock:
            if self.running:
                self.status_signal.emit("Sensor already running (real data only)")
                return
            self.running = True
        if not self.isRunning():
            self.start()

    def stop_sensor(self):
        """Stop real sensor thread"""
        with self.lock:
            self.running = False
        if self.sensor:
            try:
                self.sensor.close()
            except:
                pass
        self.wait(2000)  # Timeout to prevent hanging

# ==============================================
# Sensor Widget (REAL DATA ONLY | NO BME)
# ==============================================
class SensorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.sensor_thread = SensorThread(i2c_bus=1)
        
        # Connect signals (real data only)
        self.sensor_thread.data_signal.connect(self.update_sensor_data)
        self.sensor_thread.status_signal.connect(self.update_status)
        self.sensor_thread.error_signal.connect(self.show_error)
        
        # Initialize UI
        self._setup_ui()
        
        # Default values (no dummy data)
        self.accel_x = 0.0
        self.accel_y = 0.0
        self.accel_z = 0.0
        self.mag_x = 0.0
        self.mag_y = 0.0
        self.mag_z = 0.0

    def _setup_ui(self):
        """Setup UI (REAL LSM303DLH only | NO BME)"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Control Button (activate real sensor)
        control_layout = QHBoxLayout()
        self.activate_btn = QPushButton("Activate Real LSM303DLH Sensor")
        self.activate_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
                color: #ecf0f1;
            }
        """)
        self.activate_btn.clicked.connect(self.toggle_sensor)
        control_layout.addWidget(self.activate_btn)
        main_layout.addLayout(control_layout)

        # Sensor Data Grid (REAL ONLY)
        data_grid = QGridLayout()
        
        # Accelerometer Group (REAL)
        accel_group = QGroupBox("Accelerometer (g) - REAL DATA")
        accel_layout = QGridLayout(accel_group)
        
        self.accel_x_label = QLabel("X: --")
        self.accel_y_label = QLabel("Y: --")
        self.accel_z_label = QLabel("Z: --")
        
        for lbl in [self.accel_x_label, self.accel_y_label, self.accel_z_label]:
            lbl.setFont(QFont("Arial", 12, QFont.Bold))
            lbl.setAlignment(Qt.AlignCenter)
        
        accel_layout.addWidget(QLabel("X Axis:"), 0, 0)
        accel_layout.addWidget(self.accel_x_label, 0, 1)
        accel_layout.addWidget(QLabel("Y Axis:"), 1, 0)
        accel_layout.addWidget(self.accel_y_label, 1, 1)
        accel_layout.addWidget(QLabel("Z Axis:"), 2, 0)
        accel_layout.addWidget(self.accel_z_label, 2, 1)
        
        data_grid.addWidget(accel_group, 0, 0)

        # Magnetometer Group (REAL)
        mag_group = QGroupBox("Magnetometer (mG) - REAL DATA")
        mag_layout = QGridLayout(mag_group)
        
        self.mag_x_label = QLabel("X: --")
        self.mag_y_label = QLabel("Y: --")
        self.mag_z_label = QLabel("Z: --")
        
        for lbl in [self.mag_x_label, self.mag_y_label, self.mag_z_label]:
            lbl.setFont(QFont("Arial", 12, QFont.Bold))
            lbl.setAlignment(Qt.AlignCenter)
        
        mag_layout.addWidget(QLabel("X Axis:"), 0, 0)
        mag_layout.addWidget(self.mag_x_label, 0, 1)
        mag_layout.addWidget(QLabel("Y Axis:"), 1, 0)
        mag_layout.addWidget(self.mag_y_label, 1, 1)
        mag_layout.addWidget(QLabel("Z Axis:"), 2, 0)
        mag_layout.addWidget(self.mag_z_label, 2, 1)
        
        data_grid.addWidget(mag_group, 0, 1)

        main_layout.addLayout(data_grid)

        # Status Label
        self.status_label = QLabel("Status: Sensor disabled (REAL ONLY - no dummy data)")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #666; font-size: 10px; margin-top: 10px;")
        main_layout.addWidget(self.status_label)

    def toggle_sensor(self):
        """Toggle real sensor (no dummy)"""
        if not self.sensor_thread.running:
            self.activate_btn.setText("Deactivate Real LSM303DLH Sensor")
            self.sensor_thread.start_sensor()
        else:
            self.activate_btn.setText("Activate Real LSM303DLH Sensor")
            self.sensor_thread.stop_sensor()
            # Reset labels (no dummy data)
            self.accel_x_label.setText("X: --")
            self.accel_y_label.setText("Y: --")
            self.accel_z_label.setText("Z: --")
            self.mag_x_label.setText("X: --")
            self.mag_y_label.setText("Y: --")
            self.mag_z_label.setText("Z: --")
            self.status_label.setText("Status: Sensor disabled (REAL ONLY - no dummy data)")

    def update_sensor_data(self, accel_data, mag_data):
        """Update real sensor data labels"""
        self.accel_x, self.accel_y, self.accel_z = accel_data
        self.mag_x, self.mag_y, self.mag_z = mag_data
        
        self.accel_x_label.setText(f"X: {self.accel_x:.2f}")
        self.accel_y_label.setText(f"Y: {self.accel_y:.2f}")
        self.accel_z_label.setText(f"Z: {self.accel_z:.2f}")
        
        self.mag_x_label.setText(f"X: {self.mag_x:.1f}")
        self.mag_y_label.setText(f"Y: {self.mag_y:.1f}")
        self.mag_z_label.setText(f"Z: {self.mag_z:.1f}")

    def update_status(self, msg):
        """Update status label (real data only)"""
        self.status_label.setText(f"Status: {msg}")

    def show_error(self, msg):
        """Show critical sensor errors (no dummy fallback)"""
        QMessageBox.critical(self, "REAL SENSOR ERROR", 
                            f"{msg}\n\nNo dummy data available - connect LSM303DLH to I2C Bus 1 and try again.", 
                            QMessageBox.Ok)
        # Stop sensor on critical error
        self.sensor_thread.stop_sensor()
        self.activate_btn.setText("Activate Real LSM303DLH Sensor")
        self.status_label.setText(f"Status: ERROR - {msg[:50]}...")

    def close(self):
        """Cleanup real sensor"""
        if self.sensor_thread.running:
            self.sensor_thread.stop_sensor()
        super().close()

# ==============================================
# Test (Real Sensor Only)
# ==============================================
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("Real LSM303DLH Sensor Test (NO DUMMY DATA)")
    window.setMinimumSize(400, 300)
    
    sensor_widget = SensorWidget()
    window.setCentralWidget(sensor_widget)
    
    window.show()
    sys.exit(app.exec_())