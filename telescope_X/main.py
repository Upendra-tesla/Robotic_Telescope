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
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer

# --------------------------
# Critical: Fix Module Path (With Debug Logs)
# --------------------------
# Get the FULL path to the folder containing main.py
main_script_dir = os.path.dirname(os.path.abspath(__file__))
# Get the FULL path to the "module" subfolder
module_path = os.path.join(main_script_dir, "modules")

# Print debug info (to confirm path is correct)
print(f"=== DEBUG: Path Info ===")
print(f"Main script folder: {main_script_dir}")
print(f"Module folder path: {module_path}")
print(f"Module folder exists? {os.path.isdir(module_path)}")
print(f"Files in module folder: {os.listdir(module_path) if os.path.isdir(module_path) else 'NOT FOUND'}")

# Add module folder to Python's search path (only if it exists!)
if os.path.isdir(module_path):
    sys.path.append(module_path)
else:
    print(f"ERROR: Module folder not found at {module_path}")
    sys.exit(1)

# --------------------------
# Import Modules (Now Safe)
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
# Full Config (LOCKED GPIO Pins for Alt/Az)
# ======================
DEFAULT_CONFIG = {
    "gpio": {
        "alt_up": "GPIO17",       # LOCKED: Physical pin 11 (alt up)
        "alt_down": "GPIO18",     # LOCKED: Physical pin 12 (alt down)
        "azimuth_left": "GPIO22", # LOCKED: Physical pin 15 (az left)
        "azimuth_right": "GPIO23" # LOCKED: Physical pin 16 (az right)
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
        "ai_temp_path": "data/camera/temp"  # For AI analysis frames
    },
    "ai": {
        "deepseek_api_key": "",  # Add your API key here
        "model": "deepseek-chat",
        "temperature": 0.7
    }
}

# PI5_PIN_MAP (Confirmed Pin Mappings)
PI5_PIN_MAP = {
    "GPIO17": (17, 11),  # GPIO17 = Physical pin 11 (alt up)
    "GPIO18": (18, 12),  # GPIO18 = Physical pin 12 (alt down)
    "GPIO22": (22, 15),  # GPIO22 = Physical pin 15 (az left)
    "GPIO23": (23, 16),  # GPIO23 = Physical pin 16 (az right)
    "GPIO24": (24, 18),
    "GPIO25": (25, 22),
    "GPIO27": (27, 13)
}

# ======================
# Load/Save Config (FIXED: Preserves all DEFAULT_CONFIG keys)
# ======================
def load_config():
    config_path = "config/settings.json"
    os.makedirs("config", exist_ok=True)
    
    # Start with a FULL copy of DEFAULT_CONFIG (critical fix!)
    config = DEFAULT_CONFIG.copy()
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                loaded_config = json.load(f)
                # Recursively merge loaded config into DEFAULT_CONFIG (preserves missing keys)
                def merge_config(default, loaded):
                    for key in loaded:
                        if isinstance(loaded[key], dict) and key in default and isinstance(default[key], dict):
                            merge_config(default[key], loaded[key])
                        else:
                            # FORCE GPIO pins to locked values (prevent invalid changes)
                            if key == "gpio" and isinstance(loaded[key], dict):
                                print("WARNING: Forcing GPIO pins to locked values (Alt:17/18, Az:22/23)")
                                loaded[key] = default["gpio"]  # Override with locked GPIO pins
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
        # FORCE GPIO pins to locked values before saving
        config["gpio"] = DEFAULT_CONFIG["gpio"]
        with open(config_path, "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Failed to save config: {e}")

# ======================
# Sensor Thread (Unchanged)
# ======================
class SensorThread(QThread):
    data_signal = pyqtSignal(tuple, tuple)
    error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = True
        self.lock = Lock()
        self.sensor = LSM303DLH(i2c_bus=I2C_BUS, accel_addr=ACCEL_ADDR, mag_addr=MAG_ADDR)

    def run(self):
        try:
            self.sensor.initialize()
        except RuntimeError as e:
            self.error_signal.emit(str(e))
            return

        while self.running:
            try:
                accel_data = self.sensor.read_accelerometer()
                mag_data = self.sensor.read_magnetometer()
                self.data_signal.emit(accel_data, mag_data)
                time.sleep(1)
            except RuntimeError as e:
                self.error_signal.emit(str(e))
                time.sleep(1)

    def stop(self):
        with self.lock:
            self.running = False
        self.sensor.close()
        self.wait()

# ======================
# Main Application Class (RESIZED to 800×480 + Locked GPIO)
# ======================
class TelescopeControllerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Robotic Telescope Controller (Pi 5)")
        # RESIZE FIX: Set window to 800×480 (small screen friendly)
        self.setGeometry(100, 100, 800, 480)
        # UI Tweaks for small screen (smaller fonts/spacing)
        self.setStyleSheet("""
            QMainWindow { background-color: #f0f0f0; }
            QLabel { font-size: 12px; }  /* Smaller font for 800×480 */
            QLabel#value_label { font-size: 14px; font-weight: bold; color: #2c3e50; }
            QLabel#title_label { font-size: 16px; font-weight: bold; color: #3498db; }
            QFrame, QGroupBox { background-color: white; border-radius: 6px; padding: 10px; } /* Smaller padding */
            QPushButton { 
                background-color: #3498db; 
                color: white; 
                border: none; 
                border-radius: 4px; 
                padding: 6px 10px;  /* Smaller buttons */
                font-size: 12px;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton#ai_btn { background-color: #9c27b0; }
            QPushButton#ai_btn:hover { background-color: #7b1fa2; }
            QTabWidget::pane { border: 1px solid #ddd; border-radius: 6px; }
            QTabBar::tab { padding: 8px 15px; font-size: 12px; } /* Smaller tabs */
            QSlider { margin: 8px 0; }
            QSpinBox, QDoubleSpinBox { font-size: 12px; padding: 4px; }
        """)

        # Load config (GPIO pins locked to 17/18/22/23)
        self.config = load_config()
        
        # Fallback for ai_temp_path (extra safety)
        ai_temp_path = self.config["camera"].get("ai_temp_path", "data/camera/temp")
        os.makedirs(ai_temp_path, exist_ok=True)

        # Status Bar (smaller font)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.setStyleSheet("font-size: 11px;")
        self.status_bar.showMessage("Ready | Alt:17/18 | Az:22/23 | 800×480 Display")

        # Parse GPS
        lat_numeric = float(self.config["gps"]["lat"].split("°")[0].strip('-'))
        lon_numeric = float(self.config["gps"]["lon"].split("°")[0].strip('-'))
        if "W" in self.config["gps"]["lon"]:
            lon_numeric = -lon_numeric

        # ======================
        # Initialize Modules (Locked GPIO Pins)
        # ======================
        # Motion Controllers (uses locked GPIO 17/18 for Alt, 22/23 for Az)
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

        # Database
        self.database_widget = DatabaseWidget()

        # AI Widget
        self.deepseek_widget = DeepSeekWidget(self.config["ai"])

        # Moon Tracking
        self.moon_widget = MoonTrackingWidget(lat=lat_numeric, lon=lon_numeric)
        self.moon_widget.slew_to_moon.connect(self._slew_to_moon_position)
        self.moon_widget.lat_lon_updated.connect(self._update_gps_and_ai_context)
        self.moon_widget.auto_track_check.connect(self._on_moon_tracking_toggled)  # FIXED: removed .stateChanged

        # Sun Tracking
        self.sun_widget = SunTrackingWidget(lat=lat_numeric, lon=lon_numeric)
        self.sun_widget.slew_to_sun.connect(self._slew_to_sun_position)
        self.sun_widget.lat_lon_updated.connect(self._update_gps_and_ai_context)
        self.sun_widget.auto_track_check.connect(self._on_sun_tracking_toggled)  # FIXED: removed .stateChanged

        # Webcam Widget
        self.webcam_widget = WebcamWidget(self.config)
        self.webcam_widget.analyze_image.connect(self._analyze_image_with_ai)

        # Sensor Thread
        self.sensor_thread = SensorThread()
        self.sensor_thread.data_signal.connect(self.update_sensor_data)
        self.sensor_thread.error_signal.connect(self.show_sensor_error)
        self.sensor_thread.start()

        # ======================
        # Tab Widget Setup (Small Screen Optimized)
        # ======================
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # Add Tabs (simplified labels for small screen)
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

    # ======================
    # Auto-Record Handlers (FIXED: Webcam Method Calls)
    # ======================
    def _on_moon_tracking_toggled(self, enabled):
        self._handle_tracking_auto_record(enabled, "Moon")

    def _on_sun_tracking_toggled(self, enabled):
        self._handle_tracking_auto_record(enabled, "Sun")

    def _handle_tracking_auto_record(self, enabled, target):
        if enabled:
            if not self.webcam_widget.camera_thread.running:
                self.webcam_widget.toggle_camera()  # FIXED: removed underscore
                self.status_bar.showMessage(f"Camera started for {target} tracking")
            
            if not self.webcam_widget.camera_thread.recording:
                self.webcam_widget.toggle_recording()  # FIXED: removed underscore
                self.status_bar.showMessage(f"Auto-record: {target} (Alt:17/18, Az:22/23)")
                
                self.database_widget.db_thread.set_operation(
                    "log",
                    (0.0, 0.0, target, "auto_record_start", f"Auto-recording started for {target} tracking")
                )
        else:
            if self.webcam_widget.camera_thread.recording:
                self.webcam_widget.toggle_recording()  # FIXED: removed underscore
                self.status_bar.showMessage(f"Auto-record stopped: {target}")
                
                self.database_widget.db_thread.set_operation(
                    "log",
                    (0.0, 0.0, target, "auto_record_stop", f"Auto-recording stopped for {target} tracking")
                )

    # ======================
    # AI Image Analysis Handler (Unchanged)
    # ======================
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
                    # FIXED: Call correct analyze_image method (no extra prompt arg)
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

    # ======================
    # Core Methods (Unchanged)
    # ======================
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
        # FIXED: DeepSeek widget doesn't have update_telescope_context - remove or implement
        # self.deepseek_widget.update_telescope_context(current_alt, current_az, gps_str)
        pass

    def save_gpio_config(self, config, axis, direction, gpio_key):
        # BLOCK GPIO changes (locked to 17/18/22/23)
        QMessageBox.warning(self, "GPIO Locked", f"GPIO pins are locked to:\nAlt: 17 (up)/18 (down)\nAz: 22 (left)/23 (right)", QMessageBox.Ok)
        return

    def create_sensor_tab(self):
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        main_layout.setSpacing(12)  # Smaller spacing
        main_layout.setContentsMargins(15, 15, 15, 15)

        title_label = QLabel("LSM303DLH Orientation Data")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setObjectName("title_label")
        main_layout.addWidget(title_label)

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
        mag_title = QLabel("Magnetometer (mG) | Azimuth")
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

        # Calibration Buttons (smaller)
        calibrate_alt_btn = QPushButton("Calibrate Alt")
        calibrate_alt_btn.clicked.connect(self.calibrate_altitude_with_sensor)
        readout_layout.addWidget(calibrate_alt_btn, 6, 0)

        calibrate_az_btn = QPushButton("Calibrate Az")
        calibrate_az_btn.clicked.connect(self.calibrate_azimuth_with_sensor)
        readout_layout.addWidget(calibrate_az_btn, 6, 1)

        # Current Sensor Azimuth
        self.sensor_az_label = QLabel("Current Azimuth (Sensor): -- °")
        self.sensor_az_label.setObjectName("value_label")
        readout_layout.addWidget(self.sensor_az_label, 7, 0, 1, 2)

        main_layout.addWidget(readout_frame)
        return tab

    def create_motion_tab(self):
        tab = QWidget()
        main_layout = QHBoxLayout(tab)
        main_layout.setSpacing(10)  # Smaller spacing
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.addWidget(self.altitude_widget)
        main_layout.addWidget(self.azimuth_widget)
        return tab

    def update_sensor_data(self, accel_data, mag_data):
        self.accel_x_label.setText(f"X: {accel_data[0]:.2f}")
        self.accel_y_label.setText(f"Y: {accel_data[1]:.2f}")
        self.accel_z_label.setText(f"Z: {accel_data[2]:.2f}")
        self.mag_x_label.setText(f"X: {mag_data[0]:.1f}")
        self.mag_y_label.setText(f"Y: {mag_data[1]:.1f}")
        self.mag_z_label.setText(f"Z: {mag_data[2]:.1f}")

        self.latest_accel_data = accel_data
        self.latest_mag_data = mag_data

        current_alt = self.calculate_altitude_from_accel(accel_data)
        current_az = self.calculate_azimuth_from_mag(mag_data)
        self.sensor_az_label.setText(f"Current Azimuth (Sensor): {current_az:.1f} °")
        self.status_bar.showMessage(f"Sensor: Alt {current_alt:.1f}° | Az {current_az:.1f}° | Ready")

        self.update_ai_context()

    def calculate_altitude_from_accel(self, accel_data):
        x, y, z = accel_data
        try:
            total_accel = math.sqrt(x**2 + y**2 + z**2)
            tilt_rad = math.acos(z / total_accel)
            tilt_deg = math.degrees(tilt_rad)
            return max(0.0, min(90.0, tilt_deg))
        except:
            return 0.0

    def calculate_azimuth_from_mag(self, mag_data):
        x, y, z = mag_data
        try:
            heading_rad = math.atan2(y, x)
            heading_deg = math.degrees(heading_rad)
            heading_deg = heading_deg % 360.0
            return heading_deg
        except:
            return 0.0

    def calibrate_altitude_with_sensor(self):
        sensor_alt = self.calculate_altitude_from_accel(self.latest_accel_data)
        self.altitude_widget.motor_thread.set_target(sensor_alt)
        self.altitude_widget.alt_slider.setValue(int(sensor_alt))
        QMessageBox.information(self, "Alt Calibrated", f"Altitude set to {sensor_alt:.1f}°")

    def calibrate_azimuth_with_sensor(self):
        sensor_az = self.calculate_azimuth_from_mag(self.latest_mag_data)
        self.azimuth_widget.motor_thread.set_target(sensor_az)
        self.azimuth_widget.az_slider.setValue(int(sensor_az))
        QMessageBox.information(self, "Az Calibrated", f"Azimuth set to {sensor_az:.1f}°")

    def show_sensor_error(self, error_msg):
        QMessageBox.critical(self, "Sensor Error", error_msg)

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
            self.webcam_widget.toggle_camera()  # FIXED: removed underscore
        QMessageBox.information(self, "Camera Started", "Preview ready for AI analysis")

    def deepseek_query(self):
        self.tab_widget.setCurrentWidget(self.deepseek_widget)
        QMessageBox.information(self, "AI Assistant", "Use AI tab for astronomy queries")

    def closeEvent(self, event):
        # Cleanup all threads
        self.sensor_thread.stop()
        self.altitude_widget.close()
        self.azimuth_widget.close()
        self.database_widget.closeEvent(event)
        self.deepseek_widget.close()
        self.moon_widget.close()
        self.sun_widget.close()
        self.webcam_widget.close()

        # Save config (GPIO pins locked)
        save_config(self.config)

        event.accept()

# ======================
# Run Application
# ======================
if __name__ == "__main__":
    I2C_BUS = 0
    ACCEL_ADDR = 0x18
    MAG_ADDR = 0x1E
    
    app = QApplication(sys.argv)
    window = TelescopeControllerGUI()
    window.show()
    sys.exit(app.exec_())