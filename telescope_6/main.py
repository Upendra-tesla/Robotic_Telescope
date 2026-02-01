import sys
import os
import time
import math
import datetime
import json
from threading import Lock
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGridLayout, QLabel,
    QVBoxLayout, QHBoxLayout, QFrame, QMessageBox, QTabWidget,
    QPushButton, QGroupBox, QSpinBox, QDoubleSpinBox, QStatusBar
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer, QPoint
from PyQt5.QtGui import (
    QPainter, QPen, QBrush, QColor, QTransform, QFont, 
    QPolygon
)

# --------------------------
# Global Constants (Pi 5 I2C)
# --------------------------
I2C_BUS = 0  # CHANGED from 1 → Bus 0 (physical pins 27/28)
ACCEL_ADDR = 0x18
MAG_ADDR = 0x1E

# --------------------------
# Fix Module Path
# --------------------------
main_script_dir = os.path.dirname(os.path.abspath(__file__))
module_path = os.path.join(main_script_dir, "modules")

print(f"=== DEBUG: Path Info ===")
print(f"Main script folder: {main_script_dir}")
print(f"Module folder path: {module_path}")
print(f"Module folder exists? {os.path.isdir(module_path)}")
print(f"Files in module folder: {os.listdir(module_path) if os.path.isdir(module_path) else 'NOT FOUND'}")

if os.path.isdir(module_path):
    sys.path.append(module_path)
else:
    print(f"ERROR: Module folder not found at {module_path}")
    sys.exit(1)

# --------------------------
# Import Modules
# --------------------------
try:
    from sensor import LSM303DLH
    from altitude import AltitudeControlWidget
    from azimuth import AzimuthControlWidget
    from database import DatabaseWidget
    from deepseek import DeepSeekWidget
    from moon import MoonTrackingWidget
    from sun import SunTrackingWidget
    from webcam import WebcamWidget
except ImportError as e:
    print(f"ERROR: Failed to import modules - {e}")
    print(f"Make sure all .py files are in {module_path}")
    sys.exit(1)

# ======================
# Magnetic Compass Widget
# ======================
class CompassWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.heading = 0.0
        self.setFixedSize(180, 180)

    def set_heading(self, heading):
        self.heading = heading % 360.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        center = self.rect().center()
        radius = min(center.x(), center.y()) - 10

        # Draw background
        painter.setPen(QPen(QColor("#2c3e50"), 2))
        painter.setBrush(QBrush(QColor("#f8f9fa")))
        painter.drawEllipse(center, radius, radius)

        # Draw cardinal directions
        cardinal_dirs = [
            ("N", 0), ("NE", 45), ("E", 90), ("SE", 135),
            ("S", 180), ("SW", 225), ("W", 270), ("NW", 315)
        ]
        painter.setPen(QPen(QColor("#e74c3c"), 1.5))
        dir_font = QFont()
        dir_font.setPointSize(10)
        painter.setFont(dir_font)
        
        for dir_name, angle in cardinal_dirs:
            rad = math.radians(angle - 90)
            x = int(center.x() + radius * 0.8 * math.cos(rad))
            y = int(center.y() + radius * 0.8 * math.sin(rad))
            text_pos = QPoint(x, y)
            text_rect = painter.boundingRect(0, 0, 20, 20, Qt.AlignCenter, dir_name)
            text_pos.setX(text_pos.x() - text_rect.width() // 2)
            text_pos.setY(text_pos.y() + text_rect.height() // 2)
            painter.drawText(text_pos, dir_name)

        # Draw needle
        painter.save()
        painter.translate(center)
        painter.rotate(-self.heading)
        
        needle_pen = QPen(QColor("#e74c3c"), 2)
        needle_brush = QBrush(QColor("#e74c3c"))
        painter.setPen(needle_pen)
        painter.setBrush(needle_brush)
        
        needle_points = [
            QPoint(0, -radius + 10),
            QPoint(-8, -radius + 30),
            QPoint(8, -radius + 30)
        ]
        painter.drawPolygon(QPolygon(needle_points))
        
        # Needle base
        painter.setBrush(QBrush(QColor("#2c3e50")))
        painter.drawEllipse(0, 0, 10, 10)
        painter.restore()

        # Heading text
        painter.setPen(QPen(QColor("#2c3e50"), 1))
        heading_font = QFont()
        heading_font.setPointSize(9)
        painter.setFont(heading_font)
        
        heading_text = f"{self.heading:.1f}°"
        text_rect = painter.boundingRect(0, 0, 50, 20, Qt.AlignCenter, heading_text)
        x = int(center.x() - text_rect.width() / 2)
        y = int(center.y() + radius + 15)
        painter.drawText(x, y, heading_text)

# ======================
# Helper: Cardinal Direction
# ======================
def degrees_to_cardinal(degrees):
    degrees = degrees % 360.0
    dirs = [
        ("N", 0, 22.5), ("NE", 22.5, 67.5), ("E", 67.5, 112.5), ("SE", 112.5, 157.5),
        ("S", 157.5, 202.5), ("SW", 202.5, 247.5), ("W", 247.5, 292.5), ("NW", 292.5, 337.5),
        ("N", 337.5, 360.0)
    ]
    for name, start, end in dirs:
        if start <= degrees < end:
            return name
    return "N"

# ======================
# Config
# ======================
DEFAULT_CONFIG = {
    "gpio": {
        "alt_up": "GPIO17",
        "alt_down": "GPIO18",
        "azimuth_left": "GPIO22",
        "azimuth_right": "GPIO23"
    },
    "telescope": {
        "park_altitude": 0.0,
        "park_azimuth": 0.0
    },
    "gps": {
        "lat": "40.7128° N",
        "lon": "-74.0060° W"
    },
    "camera": {
        "default_resolution": "640x480",
        "default_fps": 30,
        "exposure": 100,
        "white_balance": "auto",
        "image_save_path": "data/camera/images",
        "video_save_path": "data/camera/videos",
        "ai_temp_path": "data/camera/temp"
    },
    "ai": {
        "deepseek_api_key": "",
        "model": "deepseek-chat",
        "temperature": 0.7
    }
}

PI5_PIN_MAP = {
    "GPIO17": (17, 11),
    "GPIO18": (18, 12),
    "GPIO22": (22, 15),
    "GPIO23": (23, 16),
    "GPIO24": (24, 18),
    "GPIO25": (25, 22),
    "GPIO27": (27, 13)
}

# ======================
# Load/Save Config
# ======================
def load_config():
    config_path = "config/settings.json"
    os.makedirs("config", exist_ok=True)
    config = DEFAULT_CONFIG.copy()
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                loaded_config = json.load(f)
                def merge_config(default, loaded):
                    for key in loaded:
                        if isinstance(loaded[key], dict) and key in default and isinstance(default[key], dict):
                            merge_config(default[key], loaded[key])
                        else:
                            if key == "gpio" and isinstance(loaded[key], dict):
                                print("WARNING: Forcing GPIO pins to locked values")
                                loaded[key] = default["gpio"]
                            default[key] = loaded[key]
                merge_config(config, loaded_config)
        except Exception as e:
            print(f"Failed to load config: {e}")
            print("Falling back to DEFAULT_CONFIG")
    return config

def save_config(config):
    config_path = "config/settings.json"
    os.makedirs("config", exist_ok=True)
    try:
        config["gpio"] = DEFAULT_CONFIG["gpio"]
        with open(config_path, "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Failed to save config: {e}")

# ======================
# Sensor Thread (With Error Handling)
# ======================
class SensorThread(QThread):
    data_signal = pyqtSignal(tuple, tuple)
    error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = True
        self.lock = Lock()
        self.sensor = None
        self._initialize_sensor()

    def _initialize_sensor(self):
        """Safe sensor initialization"""
        try:
            self.sensor = LSM303DLH(i2c_bus=I2C_BUS, accel_addr=ACCEL_ADDR, mag_addr=MAG_ADDR)
            self.sensor.initialize()
        except RuntimeError as e:
            self.error_signal.emit(f"Sensor Initialization Failed:\n{str(e)}")
            print(f"Sensor Init Error: {e}")

    def run(self):
        # If sensor failed to initialize, run with dummy data
        if not self.sensor:
            self.error_signal.emit("Using dummy sensor data (no hardware detected)")
            while self.running:
                # Dummy data to keep GUI functional
                accel_data = (0.0, 0.0, 1.0)
                mag_data = (0.0, 0.0, 0.0)
                self.data_signal.emit(accel_data, mag_data)
                time.sleep(1)
            return

        # Normal operation with sensor
        while self.running:
            try:
                accel_data = self.sensor.read_accelerometer()
                mag_data = self.sensor.read_magnetometer_calibrated()
                self.data_signal.emit(accel_data, mag_data)
                time.sleep(0.5)  # Faster updates
            except Exception as e:
                error_msg = f"Sensor Read Error: {str(e)}"
                self.error_signal.emit(error_msg)
                print(error_msg)
                time.sleep(1)

    def stop(self):
        with self.lock:
            self.running = False
        if self.sensor:
            self.sensor.close()
        self.wait()

# ======================
# Main Application
# ======================
class TelescopeControllerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Robotic Telescope Controller (Pi 5)")
        self.setGeometry(100, 100, 800, 480)
        self.setStyleSheet("""
            QMainWindow { background-color: #f0f0f0; }
            QLabel { font-size: 12px; }
            QLabel#value_label { font-size: 14px; font-weight: bold; color: #2c3e50; }
            QLabel#title_label { font-size: 16px; font-weight: bold; color: #3498db; }
            QLabel#compass_dir_label { font-size: 16px; font-weight: bold; color: #e74c3c; }
            QFrame, QGroupBox { background-color: white; border-radius: 6px; padding: 10px; }
            QPushButton { 
                background-color: #3498db; 
                color: white; 
                border: none; 
                border-radius: 4px; 
                padding: 6px 10px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton#ai_btn { background-color: #9c27b0; }
            QPushButton#ai_btn:hover { background-color: #7b1fa2; }
            QTabWidget::pane { border: 1px solid #ddd; border-radius: 6px; }
            QTabBar::tab { padding: 8px 15px; font-size: 12px; }
            QSlider { margin: 8px 0; }
            QSpinBox, QDoubleSpinBox { font-size: 12px; padding: 4px; }
        """)

        # Load config
        self.config = load_config()
        
        # Create AI temp path
        ai_temp_path = self.config["camera"].get("ai_temp_path", "data/camera/temp")
        os.makedirs(ai_temp_path, exist_ok=True)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.setStyleSheet("font-size: 11px;")
        self.status_bar.showMessage("Ready | Alt:17/18 | Az:22/23 | Pi 5 I2C Bus 1 | 800×480 Display")

        # Parse GPS
        lat_numeric = float(self.config["gps"]["lat"].split("°")[0].strip('-'))
        lon_numeric = float(self.config["gps"]["lon"].split("°")[0].strip('-'))
        if "W" in self.config["gps"]["lon"]:
            lon_numeric = -lon_numeric

        # Initialize modules
        self.altitude_widget = AltitudeControlWidget(
            config=self.config,
            save_gpio_config=self.save_gpio_config,
            pin_map=PI5_PIN_MAP
        )
        self.azimuth_widget = AzimuthControlWidget(
            config=self.config,
            save_gpio_config=self.save_gpio_config,
            pin_map=PI5_PIN_MAP
        )
        self.database_widget = DatabaseWidget()
        self.deepseek_widget = DeepSeekWidget(self.config["ai"])
        self.moon_widget = MoonTrackingWidget(lat=lat_numeric, lon=lon_numeric)
        self.moon_widget.slew_to_moon.connect(self._slew_to_moon_position)
        self.moon_widget.lat_lon_updated.connect(self._update_gps_and_ai_context)
        self.moon_widget.auto_track_check.connect(self._on_moon_tracking_toggled)

        self.sun_widget = SunTrackingWidget(lat=lat_numeric, lon=lon_numeric)
        self.sun_widget.slew_to_sun.connect(self._slew_to_sun_position)
        self.sun_widget.lat_lon_updated.connect(self._update_gps_and_ai_context)
        self.sun_widget.auto_track_check.connect(self._on_sun_tracking_toggled)

        self.webcam_widget = WebcamWidget(self.config)
        self.webcam_widget.analyze_image.connect(self._analyze_image_with_ai)

        # Sensor thread
        self.sensor_thread = SensorThread()
        self.sensor_thread.data_signal.connect(self.update_sensor_data)
        self.sensor_thread.error_signal.connect(self.show_sensor_error)
        self.sensor_thread.start()

        # Tab widget
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # Add tabs
        self.sensor_tab = self.create_sensor_tab()
        self.tab_widget.addTab(self.sensor_tab, "1. Sensors")
        self.tab_widget.addTab(self.create_motion_tab(), "2. Motors")
        self.tab_widget.addTab(self.moon_widget, "3. Moon")
        self.tab_widget.addTab(self.sun_widget, "4. Sun")
        self.tab_widget.addTab(self.webcam_widget, "5. Camera")
        self.tab_widget.addTab(self.deepseek_widget, "6. AI")
        self.tab_widget.addTab(self.database_widget, "7. Logs")

        # Initialize AI context
        self.update_ai_context()

    # Auto-record handlers
    def _on_moon_tracking_toggled(self, enabled):
        self._handle_tracking_auto_record(enabled, "Moon")

    def _on_sun_tracking_toggled(self, enabled):
        self._handle_tracking_auto_record(enabled, "Sun")

    def _handle_tracking_auto_record(self, enabled, target):
        if enabled:
            if not self.webcam_widget.camera_thread.running:
                self.webcam_widget.toggle_camera()
                self.status_bar.showMessage(f"Camera started for {target} tracking")
            
            if not self.webcam_widget.camera_thread.recording:
                self.webcam_widget.toggle_recording()
                self.status_bar.showMessage(f"Auto-record: {target} (Alt:17/18, Az:22/23)")
                
                self.database_widget.db_thread.set_operation(
                    "log",
                    (0.0, 0.0, target, "auto_record_start", f"Auto-recording started for {target} tracking")
                )
        else:
            if self.webcam_widget.camera_thread.recording:
                self.webcam_widget.toggle_recording()
                self.status_bar.showMessage(f"Auto-record stopped: {target}")
                
                self.database_widget.db_thread.set_operation(
                    "log",
                    (0.0, 0.0, target, "auto_record_stop", f"Auto-recording stopped for {target} tracking")
                )

    # AI Image Analysis
    def _analyze_image_with_ai(self, image_path):
        if not self.config["ai"]["deepseek_api_key"]:
            QMessageBox.critical(self, "AI Error", "Add DeepSeek API key to config/settings.json!", QMessageBox.Ok)
            return

        prompt = f"""
        Analyze this astronomical image (800×480 display, GPIO 17/18/22/23):
        1. Identify celestial object (Moon/Sun/stars)
        2. Assess image quality (exposure/focus/noise)
        3. Suggest improvements
        
        Context: Tracking {self._get_active_tracking_target()} at {self.config['gps']['lat']}, {self.config['gps']['lon']}
        """

        self.status_bar.showMessage("Analyzing image with AI...")
        
        class AIAnalysisThread(QThread):
            result_ready = pyqtSignal(str)
            
            def __init__(self, deepseek_widget, prompt, image_path):
                super().__init__()
                self.deepseek_widget = deepseek_widget
                self.prompt = prompt
                self.image_path = image_path

            def run(self):
                try:
                    self.deepseek_widget.analyze_image(image_path)
                    self.result_ready.emit("Image analysis sent to AI tab - check results there!")
                except Exception as e:
                    self.result_ready.emit(f"AI Error: {str(e)}")

        self.ai_thread = AIAnalysisThread(self.deepseek_widget, prompt, image_path)
        self.ai_thread.result_ready.connect(self._show_ai_analysis_result)
        self.ai_thread.start()

    def _show_ai_analysis_result(self, result):
        self.status_bar.showMessage("AI analysis complete")
        QMessageBox.information(
            self,
            "AI Analysis",
            result,
            QMessageBox.Ok
        )
        self.database_widget.db_thread.set_operation(
            "log",
            (0.0, 0.0, "AI", "image_analysis", f"AI analyzed image: {result[:80]}...")
        )

    def _get_active_tracking_target(self):
        if self.moon_widget.auto_track_btn.isChecked():
            return "Moon"
        elif self.sun_widget.auto_track_btn.isChecked():
            return "Sun"
        else:
            return "unknown object"

    # Core methods
    def _slew_to_moon_position(self, target_alt, target_az):
        self.altitude_widget.motor_thread.set_target(max(0.0, min(90.0, target_alt)))
        self.altitude_widget.alt_slider.setValue(int(target_alt))
        self.azimuth_widget.motor_thread.set_target(target_az)
        self.azimuth_widget.az_slider.setValue(int(target_az))
        
        self.database_widget.db_thread.set_operation(
            "log",
            (target_alt, target_az, "Moon", "goto_moon", f"Slewed to moon: Alt {target_alt:.1f}°, Az {target_az:.1f}°")
        )
        
        self.status_bar.showMessage(f"Slewing to Moon: Alt {target_alt:.1f}° | Az {target_az:.1f}°")
        self.update_ai_context()

    def _slew_to_sun_position(self, target_alt, target_az):
        if not self.sun_widget.filter_check.isChecked():
            QMessageBox.critical(self, "SOLAR SAFETY", "Confirm solar filter first!", QMessageBox.Ok)
            return

        self.altitude_widget.motor_thread.set_target(max(0.0, min(90.0, target_alt)))
        self.altitude_widget.alt_slider.setValue(int(target_alt))
        self.azimuth_widget.motor_thread.set_target(target_az)
        self.azimuth_widget.az_slider.setValue(int(target_az))
        
        self.database_widget.db_thread.set_operation(
            "log",
            (target_alt, target_az, "Sun", "goto_sun", f"Slewed to sun (safe): Alt {target_alt:.1f}°, Az {target_az:.1f}°")
        )
        
        self.status_bar.showMessage(f"Slewing to Sun (SAFE): Alt {target_alt:.1f}° | Az {target_az:.1f}°")
        self.update_ai_context()

    def _update_gps_and_ai_context(self, new_lat, new_lon):
        lat_dir = "N" if new_lat >= 0 else "S"
        lon_dir = "E" if new_lon >= 0 else "W"
        self.config["gps"]["lat"] = f"{abs(new_lat):.4f}° {lat_dir}"
        self.config["gps"]["lon"] = f"{abs(new_lon):.4f}° {lon_dir}"
        
        self.update_ai_context()
        self.status_bar.showMessage(f"GPS Updated: {self.config['gps']['lat']}, {self.config['gps']['lon']}")

    def update_ai_context(self):
        current_alt = self.altitude_widget.motor_thread.current_alt
        current_az = self.azimuth_widget.motor_thread.current_az
        gps_str = f"{self.config['gps']['lat']}, {self.config['gps']['lon']}"
        pass

    def save_gpio_config(self, config, axis, direction, gpio_key):
        QMessageBox.warning(self, "GPIO Locked", f"GPIO pins are locked to:\nAlt: 17 (up)/18 (down)\nAz: 22 (left)/23 (right)", QMessageBox.Ok)
        return

    # Sensor tab
    def create_sensor_tab(self):
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(15, 15, 15, 15)

        title_label = QLabel("LSM303DLH Orientation Data + Magnetic Compass (Pi 5)")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setObjectName("title_label")
        main_layout.addWidget(title_label)

        # Main grid
        main_grid = QGridLayout()

        # Left column: Data
        readout_frame = QFrame()
        readout_layout = QGridLayout(readout_frame)
        readout_layout.setSpacing(10)

        # Accelerometer
        accel_title = QLabel("Accelerometer (g) | Altitude")
        accel_title.setObjectName("title_label")
        readout_layout.addWidget(accel_title, 0, 0, 1, 2)

        self.accel_x_label = QLabel("X: --")
        self.accel_y_label = QLabel("Y: --")
        self.accel_z_label = QLabel("Z: --")
        self.accel_x_label.setObjectName("value_label")
        self.accel_y_label.setObjectName("value_label")
        self.accel_z_label.setObjectName("value_label")
        readout_layout.addWidget(self.accel_x_label, 1, 0)
        readout_layout.addWidget(self.accel_y_label, 1, 1)
        readout_layout.addWidget(self.accel_z_label, 2, 0, 1, 2)

        # Magnetometer
        mag_title = QLabel("Magnetometer (mG) | Azimuth (Calibrated)")
        mag_title.setObjectName("title_label")
        readout_layout.addWidget(mag_title, 3, 0, 1, 2)

        self.mag_x_label = QLabel("X: --")
        self.mag_y_label = QLabel("Y: --")
        self.mag_z_label = QLabel("Z: --")
        self.mag_x_label.setObjectName("value_label")
        self.mag_y_label.setObjectName("value_label")
        self.mag_z_label.setObjectName("value_label")
        readout_layout.addWidget(self.mag_x_label, 4, 0)
        readout_layout.addWidget(self.mag_y_label, 4, 1)
        readout_layout.addWidget(self.mag_z_label, 5, 0, 1, 2)

        # Azimuth + Cardinal
        self.sensor_az_label = QLabel("Current Azimuth (Sensor): -- °")
        self.sensor_az_label.setObjectName("value_label")
        readout_layout.addWidget(self.sensor_az_label, 6, 0, 1, 2)

        self.cardinal_dir_label = QLabel("Cardinal Direction: --")
        self.cardinal_dir_label.setObjectName("compass_dir_label")
        self.cardinal_dir_label.setAlignment(Qt.AlignCenter)
        readout_layout.addWidget(self.cardinal_dir_label, 7, 0, 1, 2)

        # Calibration buttons
        calibrate_alt_btn = QPushButton("Calibrate Alt")
        calibrate_alt_btn.clicked.connect(self.calibrate_altitude_with_sensor)
        readout_layout.addWidget(calibrate_alt_btn, 8, 0)

        calibrate_az_btn = QPushButton("Calibrate Az")
        calibrate_az_btn.clicked.connect(self.calibrate_azimuth_with_sensor)
        readout_layout.addWidget(calibrate_az_btn, 8, 1)

        # Add to grid
        main_grid.addWidget(readout_frame, 0, 0)

        # Right column: Compass
        compass_frame = QFrame()
        compass_layout = QVBoxLayout(compass_frame)
        compass_layout.setAlignment(Qt.AlignCenter)
        
        self.compass_widget = CompassWidget()
        compass_layout.addWidget(self.compass_widget, alignment=Qt.AlignCenter)
        
        main_grid.addWidget(compass_frame, 0, 1)

        # Add grid to main layout
        main_layout.addLayout(main_grid)
        return tab

    # Motion tab
    def create_motion_tab(self):
        tab = QWidget()
        main_layout = QHBoxLayout(tab)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.addWidget(self.altitude_widget)
        main_layout.addWidget(self.azimuth_widget)
        return tab

    # Update sensor data
    def update_sensor_data(self, accel_data, mag_data):
        # Update labels
        self.accel_x_label.setText(f"X: {accel_data[0]:.2f}")
        self.accel_y_label.setText(f"Y: {accel_data[1]:.2f}")
        self.accel_z_label.setText(f"Z: {accel_data[2]:.2f}")
        self.mag_x_label.setText(f"X: {mag_data[0]:.1f}")
        self.mag_y_label.setText(f"Y: {mag_data[1]:.1f}")
        self.mag_z_label.setText(f"Z: {mag_data[2]:.1f}")

        # Store latest data
        self.latest_accel_data = accel_data
        self.latest_mag_data = mag_data

        # Calculate altitude/azimuth
        current_alt = self.calculate_altitude_from_accel(accel_data)
        current_az = self.calculate_azimuth_from_mag(mag_data)
        
        # Update UI
        self.sensor_az_label.setText(f"Current Azimuth (Sensor): {current_az:.1f} °")
        self.cardinal_dir_label.setText(f"Cardinal Direction: {degrees_to_cardinal(current_az)}")
        self.compass_widget.set_heading(current_az)

        self.status_bar.showMessage(f"Sensor: Alt {current_alt:.1f}° | Az {current_az:.1f}° ({degrees_to_cardinal(current_az)}) | Pi 5 I2C Bus 1")

        self.update_ai_context()

    # Calculate altitude
    def calculate_altitude_from_accel(self, accel_data):
        x, y, z = accel_data
        try:
            total_accel = math.sqrt(x**2 + y**2 + z**2)
            tilt_rad = math.acos(z / total_accel)
            tilt_deg = math.degrees(tilt_rad)
            return max(0.0, min(90.0, tilt_deg))
        except:
            return 0.0

    # Calculate azimuth
    def calculate_azimuth_from_mag(self, mag_data):
        x, y, z = mag_data
        try:
            heading_rad = math.atan2(y, x)
            heading_deg = math.degrees(heading_rad)
            heading_deg = heading_deg % 360.0
            return heading_deg
        except:
            return 0.0

    # Calibrate altitude
    def calibrate_altitude_with_sensor(self):
        if hasattr(self, 'latest_accel_data'):
            sensor_alt = self.calculate_altitude_from_accel(self.latest_accel_data)
            self.altitude_widget.motor_thread.set_target(sensor_alt)
            self.altitude_widget.alt_slider.setValue(int(sensor_alt))
            QMessageBox.information(self, "Alt Calibrated", f"Altitude set to {sensor_alt:.1f}°")
        else:
            QMessageBox.warning(self, "Calibration Error", "No accelerometer data available!")

    # Calibrate azimuth
    def calibrate_azimuth_with_sensor(self):
        if hasattr(self, 'latest_mag_data'):
            sensor_az = self.calculate_azimuth_from_mag(self.latest_mag_data)
            self.azimuth_widget.motor_thread.set_target(sensor_az)
            self.azimuth_widget.az_slider.setValue(int(sensor_az))
            QMessageBox.information(self, "Az Calibrated", f"Azimuth set to {sensor_az:.1f}°")
        else:
            QMessageBox.warning(self, "Calibration Error", "No magnetometer data available!")

    # Show sensor error
    def show_sensor_error(self, error_msg):
        QMessageBox.critical(self, "Sensor Error", error_msg)
        self.status_bar.showMessage(f"Sensor Error: {error_msg[:50]}... | Pi 5 I2C Bus 1")

    # Track sun/moon/webcam/AI
    def track_sun(self):
        self.tab_widget.setCurrentWidget(self.sun_widget)
        if not self.sun_widget.filter_check.isChecked():
            QMessageBox.critical(self, "SOLAR SAFETY", "Confirm solar filter first!")
            return
        self.sun_widget.auto_track_btn.setChecked(True)
        QMessageBox.information(self, "Sun Tracking", "Auto sun tracking enabled (SAFE)")

    def track_moon(self):
        self.tab_widget.setCurrentWidget(self.moon_widget)
        self.moon_widget.auto_track_btn.setChecked(True)
        QMessageBox.information(self, "Moon Tracking", "Auto moon tracking enabled")

    def start_webcam(self):
        self.tab_widget.setCurrentWidget(self.webcam_widget)
        if not self.webcam_widget.camera_thread.running:
            self.webcam_widget.toggle_camera()
        QMessageBox.information(self, "Camera Started", "Preview ready for AI analysis")

    def deepseek_query(self):
        self.tab_widget.setCurrentWidget(self.deepseek_widget)
        QMessageBox.information(self, "AI Assistant", "Use AI tab for astronomy queries")

    # Close event
    def closeEvent(self, event):
        # Cleanup threads
        self.sensor_thread.stop()
        self.altitude_widget.close()
        self.azimuth_widget.close()
        self.database_widget.closeEvent(event)
        self.deepseek_widget.close()
        self.moon_widget.close()
        self.sun_widget.close()
        self.webcam_widget.close()

        # Save config
        save_config(self.config)

        event.accept()

# ======================
# Run Application
# ======================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TelescopeControllerGUI()
    window.show()
    sys.exit(app.exec_())