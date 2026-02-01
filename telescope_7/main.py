# ==============================================
# Robotic Telescope Controller - Pi 5 (800×480)
# ==============================================
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
    QPushButton, QGroupBox, QSpinBox, QDoubleSpinBox, QStatusBar,
    QSizePolicy, QScrollArea
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont

# ==============================================
# Constants & Configuration (Pi 5 800×480 Optimized)
# ==============================================
I2C_BUS = 1
ACCEL_ADDR = 0x18  # LSM303DLH Accelerometer
MAG_ADDR = 0x1E    # LSM303DLH Magnetometer

# Default Configuration (TIGHTLY OPTIMIZED FOR 800×480)
DEFAULT_CONFIG = {
    "gpio": {
        "alt_up": "GPIO17",
        "alt_down": "GPIO18",
        "azimuth_left": "GPIO27",
        "azimuth_right": "GPIO23"
    },
    "telescope": {
        "park_altitude": 0.0,
        "park_azimuth": 0.0,
        "max_speed": 1.0,
        "latitude": 40.7128,
        "longitude": -74.006
    },
    "gps": {
        "lat": "40.7128° N",
        "lon": "-74.0060° W"
    },
    "camera": {
        "default_resolution": "640x480",
        "default_fps": 20,
        "exposure": 500,
        "image_save_path": "data/images",
        "video_save_path": "data/videos",
        "ai_temp_path": "data/camera/temp"
    },
    "ai": {
        "deepseek_api_key": "",
        "model": "deepseek-chat",
        "temperature": 0.7,
        "max_tokens": 500
    },
    "ui": {
        "min_window_width": 800,
        "min_window_height": 480,
        "font_scale": 0.8,       # Tighter font scaling for 800×480
        "spacing_scale": 0.5     # Reduced spacing (critical for small screen)
    }
}

# Pi 5 Pin Mapping (GPIO27 for Azimuth Left)
PI5_PIN_MAP = {
    "GPIO17": (17, 11),
    "GPIO18": (18, 12),
    "GPIO23": (23, 16),
    "GPIO27": (27, 13),
    "GPIO24": (24, 18),
    "GPIO25": (25, 22),
    "GPIO22": (22, 15)
}

# ==============================================
# Helper Functions (800×480 Optimized)
# ==============================================
def fix_module_path():
    """Fix module import path (validate real sensor modules)"""
    main_script_dir = os.path.dirname(os.path.abspath(__file__))
    module_path = os.path.join(main_script_dir, "modules")

    print(f"=== DEBUG: Path Information ===")
    print(f"Main script directory: {main_script_dir}")
    print(f"Module directory path: {module_path}")
    print(f"Module directory exists? {os.path.isdir(module_path)}")
    
    if os.path.isdir(module_path):
        sys.path.append(module_path)
        required_modules = [
            "altitude.py", "azimuth.py", "webcam.py", "sensor.py", 
            "moon.py", "sun.py", "database.py", "deepseek.py"
        ]
        missing = [m for m in required_modules if not os.path.exists(os.path.join(module_path, m))]
        if missing:
            print(f"ERROR: Missing required modules: {missing}")
            return False
        print(f"Valid modules found: {os.listdir(module_path)}")
        return True
    else:
        print(f"ERROR: Module directory not found at {module_path}")
        return False

def load_config():
    """Load configuration (preserve GPIO27 + DeepSeek key)"""
    config_path = "config/settings.json"
    os.makedirs("config", exist_ok=True)
    config = DEFAULT_CONFIG.copy()
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                loaded_config = json.load(f)
                
            # Recursive merge (preserve nested dicts)
            def merge_config(default, loaded):
                for key in loaded:
                    if isinstance(loaded[key], dict) and key in default and isinstance(default[key], dict):
                        merge_config(default[key], loaded[key])
                    else:
                        if key == "gpio":
                            loaded[key] = {
                                "alt_up": "GPIO17",
                                "alt_down": "GPIO18",
                                "azimuth_left": loaded[key].get("azimuth_left", "GPIO27"),
                                "azimuth_right": "GPIO23"
                            }
                        elif key == "ai":
                            default[key]["deepseek_api_key"] = loaded[key].get("deepseek_api_key", "")
                        default[key] = loaded[key]
            merge_config(config, loaded_config)
            
        except json.JSONDecodeError as e:
            print(f"Config parse error (invalid JSON): {e} | Falling back to defaults")
        except Exception as e:
            print(f"Config load error: {e} | Falling back to defaults")
    return config

def save_config(config):
    """Save configuration (lock GPIO27 + DeepSeek key)"""
    config_path = "config/settings.json"
    os.makedirs("config", exist_ok=True)
    try:
        config["gpio"] = {
            "alt_up": "GPIO17",
            "alt_down": "GPIO18",
            "azimuth_left": config["gpio"].get("azimuth_left", "GPIO27"),
            "azimuth_right": "GPIO23"
        }
        config["ai"] = {
            "deepseek_api_key": config["ai"].get("deepseek_api_key", ""),
            "model": config["ai"].get("model", "deepseek-chat"),
            "temperature": config["ai"].get("temperature", 0.7),
            "max_tokens": config["ai"].get("max_tokens", 500)
        }
        with open(config_path, "w") as f:
            json.dump(config, f, indent=4)
        print(f"Config saved to {config_path} (GPIO27 + DeepSeek key preserved)")
    except Exception as e:
        print(f"Config save error: {e}")

def degrees_to_cardinal(degrees):
    """Convert azimuth degrees to cardinal direction"""
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

def check_i2c_bus(bus_number):
    """Check I2C bus existence/permissions (Pi 5 specific)"""
    bus_path = f"/dev/i2c-{bus_number}"
    exists = os.path.exists(bus_path)
    if exists:
        readable = os.access(bus_path, os.R_OK)
        writable = os.access(bus_path, os.W_OK)
        if not (readable and writable):
            print(f"WARNING: I2C Bus {bus_number} exists but no read/write permissions (run with sudo?)")
            return False
    return exists

def get_scaled_font_size(base_size, scale_factor=1.0):
    """Calculate responsive font size for Pi 5 800×480 display"""
    return max(7, int(base_size * scale_factor * DEFAULT_CONFIG["ui"]["font_scale"]))

# ==============================================
# Main Application Class (800×480 Optimized)
# ==============================================
class TelescopeControllerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        # Core Pi 5 Setup (800×480 EXACT FIT)
        self.setWindowTitle("Telescope Controller (Pi 5 | 800×480)")
        self.setFixedSize(  # Fixed size to match Pi 5 display (no resizing issues)
            DEFAULT_CONFIG["ui"]["min_window_width"],
            DEFAULT_CONFIG["ui"]["min_window_height"]
        )
        self.setStyleSheet(self._get_800x480_stylesheet())

        # Load Configuration
        self.config = load_config()
        
        # Create required directories
        for dir_path in [
            self.config["camera"]["image_save_path"],
            self.config["camera"]["video_save_path"],
            self.config["camera"]["ai_temp_path"]
        ]:
            os.makedirs(dir_path, exist_ok=True)

        # Status Bar (COMPACT for 800×480)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.setStyleSheet("font-size: 9px; padding: 2px;")
        self.status_bar.showMessage(f"Ready | Sensor: OFF | Camera: OFF | I2C Bus {I2C_BUS}")

        # Parse GPS Coordinates
        try:
            lat_str = self.config["gps"]["lat"].split("°")[0].strip()
            lon_str = self.config["gps"]["lon"].split("°")[0].strip()
            self.lat_numeric = float(lat_str.replace('-', ''))
            self.lon_numeric = float(lon_str.replace('-', ''))
            
            if "S" in self.config["gps"]["lat"]:
                self.lat_numeric = -self.lat_numeric
            if "W" in self.config["gps"]["lon"]:
                self.lon_numeric = -self.lon_numeric
        except (ValueError, IndexError) as e:
            print(f"GPS Parse Error: {e} | Using defaults")
            self.lat_numeric = 40.7128
            self.lon_numeric = -74.0060
            self.config["gps"]["lat"] = "40.7128° N"
            self.config["gps"]["lon"] = "-74.0060° W"

        # Import Modules (Real Sensor Only)
        try:
            # Core controls
            from altitude import AltitudeControlWidget
            from azimuth import AzimuthControlWidget
            
            # Real sensor widget (NO BME, NO DUMMY DATA)
            from sensor import SensorWidget
            
            # Camera/AI (800×480 optimized)
            from webcam import WebcamWidget
            
            # Celestial Tracking
            from moon import MoonTrackingWidget
            from sun import SunTrackingWidget
            
            # AI/Logging
            from deepseek import DeepSeekWidget
            from database import DatabaseWidget

            # Initialize Widgets (COMPACT sizing)
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

            # Critical: Real sensor widget (no dummy fallback)
            self.sensor_widget = SensorWidget()
            self.sensor_widget.setMinimumSize(750, 300)  # Fit 800×480
            self.sensor_widget.sensor_thread.status_signal.connect(self._update_sensor_status)
            self.sensor_widget.sensor_thread.error_signal.connect(self._show_sensor_error)

            # Initialize Webcam Widget (800×480 optimized)
            self.webcam_widget = WebcamWidget(self.config)
            self.webcam_widget.analyze_image.connect(self._on_image_analyzed)
            self.webcam_widget.status_signal.connect(self._update_status_bar)
            self.camera_active = False

            # Celestial Tracking (COMPACT)
            self.moon_widget = MoonTrackingWidget(lat=self.lat_numeric, lon=self.lon_numeric)
            self.moon_widget.setMinimumSize(750, 350)
            self.moon_widget.slew_to_moon.connect(self._slew_to_moon_position)
            self.moon_widget.lat_lon_updated.connect(self._update_gps_and_ai_context)
            self.moon_widget.auto_track_check.connect(self._on_moon_tracking_toggled)

            self.sun_widget = SunTrackingWidget(lat=self.lat_numeric, lon=self.lon_numeric)
            self.sun_widget.setMinimumSize(750, 350)
            self.sun_widget.slew_to_sun.connect(self._slew_to_sun_position)
            self.sun_widget.lat_lon_updated.connect(self._update_gps_and_ai_context)
            self.sun_widget.auto_track_check.connect(self._on_sun_tracking_toggled)

            # AI/Logging (COMPACT)
            self.deepseek_widget = DeepSeekWidget(self.config["ai"])
            self.deepseek_widget.setMinimumSize(750, 350)
            self.database_widget = DatabaseWidget()
            self.database_widget.setMinimumSize(750, 350)

        except ImportError as e:
            QMessageBox.critical(self, "Module Error", 
                                f"Failed to load modules:\n{str(e)}\n\n"
                                "Check:\n1. 'modules' folder exists\n2. All .py files are present\n3. Dependencies installed (pip3 install smbus2 opencv-python pyqt5 requests)")
            sys.exit(1)

        # Create Main Tab Widget (800×480 OPTIMIZED)
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        self.tab_widget.setStyleSheet("""
            QTabBar::tab {
                padding: 4px 8px;  # Reduced tab padding
                font-size: 9px;
                margin: 0px;
            }
            QTabBar::tab:selected {
                background-color: #3498db;
                color: white;
            }
            QTabWidget::pane {
                border: 1px solid #ddd;
                padding: 5px;  # Minimal padding
            }
        """)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self.tab_widget)

        # Add Tabs (SHORTENED LABELS for small tab bar)
        self.tab_widget.addTab(self.create_sensor_tab(), "1. Sensors")
        self.tab_widget.addTab(self.create_motion_tab(), "2. Motors")
        self.tab_widget.addTab(self.moon_widget, "3. Moon")
        self.tab_widget.addTab(self.sun_widget, "4. Sun")
        self.tab_widget.addTab(self.webcam_widget, "5. Camera+AI")
        self.tab_widget.addTab(self.deepseek_widget, "6. AI Chat")
        self.tab_widget.addTab(self.database_widget, "7. Logs")

        # Initialize AI Context
        self.update_ai_context()

    # ==============================================
    # UI Helpers (800×480 OPTIMIZED)
    # ==============================================
    def _get_800x480_stylesheet(self):
        """MINIMAL, FUNCTIONAL stylesheet for 800×480"""
        return f"""
            QMainWindow {{ background-color: #f5f5f5; }}
            QLabel {{ font-size: {get_scaled_font_size(9)}px; }}
            QLabel#value_label {{ 
                font-size: {get_scaled_font_size(10)}px; 
                font-weight: bold; 
                color: #2c3e50;
            }}
            QLabel#title_label {{ 
                font-size: {get_scaled_font_size(11)}px; 
                font-weight: bold; 
                color: #3498db;
                margin-bottom: 4px;  # Reduced margin
            }}
            QFrame, QGroupBox {{ 
                background-color: white; 
                border-radius: 3px; 
                padding: 5px;  # Minimal padding
                border: 1px solid #ddd;
                margin-bottom: 5px;  # Reduced margin
            }}
            QPushButton {{ 
                background-color: #3498db; 
                color: white; 
                border: none; 
                border-radius: 3px; 
                padding: 4px 8px;  # Smaller buttons
                font-size: {get_scaled_font_size(9)}px;
                min-height: 25px;  # Compact buttons
            }}
            QPushButton:hover {{ background-color: #2980b9; }}
            QPushButton#ai_btn {{ background-color: #9c27b0; }}
            QPushButton#sensor_btn {{ 
                background-color: #e74c3c;
                padding: 6px 12px;
                font-size: {get_scaled_font_size(10)}px;
            }}
            QSpinBox, QDoubleSpinBox {{ 
                font-size: {get_scaled_font_size(9)}px; 
                padding: 2px;
                min-width: 60px;  # Smaller spin boxes
                border-radius: 2px;
                border: 1px solid #ddd;
            }}
            QStatusBar {{
                font-size: 9px;
                padding: 2px;
                background-color: #f8f9fa;
                border-top: 1px solid #ddd;
            }}
            QScrollArea {{ border: none; }}
            QTextEdit {{ font-size: {get_scaled_font_size(9)}px; padding: 4px; }}
        """

    def create_sensor_tab(self):
        """Sensor tab (COMPACT for 800×480)"""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        main_layout.setSpacing(int(8 * DEFAULT_CONFIG["ui"]["spacing_scale"]))  # Tight spacing
        main_layout.setContentsMargins(8, 8, 8, 8)  # Minimal margins

        # Title (shortened for small screen)
        title_label = QLabel("LSM303DLH Sensor (REAL DATA ONLY)")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setObjectName("title_label")
        main_layout.addWidget(title_label)

        # Real Sensor Widget (fits 800×480)
        self.sensor_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(self.sensor_widget)

        # Critical Warning Label (COMPACT)
        warning_label = QLabel("⚠️ NO DUMMY DATA - LSM303DLH required!")
        warning_label.setAlignment(Qt.AlignCenter)
        warning_label.setStyleSheet("font-size: 8px; color: #e74c3c; font-weight: bold;")
        main_layout.addWidget(warning_label)

        # Status Label (COMPACT)
        self.sensor_status_label = QLabel("Status: Click 'Activate Sensors'")
        self.sensor_status_label.setAlignment(Qt.AlignCenter)
        self.sensor_status_label.setStyleSheet("font-size: 8px; color: #666;")
        main_layout.addWidget(self.sensor_status_label)

        return tab

    def create_motion_tab(self):
        """Motion tab (50/50 split, 800×480 FIT)"""
        tab = QWidget()
        main_layout = QHBoxLayout(tab)
        main_layout.setSpacing(int(8 * DEFAULT_CONFIG["ui"]["spacing_scale"]))
        main_layout.setContentsMargins(8, 8, 8, 8)
        
        # Exact 50/50 split (no overflow)
        main_layout.setStretch(0, 1)
        main_layout.setStretch(1, 1)
        
        # Compact sizing for motor widgets
        self.altitude_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.azimuth_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        main_layout.addWidget(self.altitude_widget)
        main_layout.addWidget(self.azimuth_widget)
        return tab

    # ==============================================
    # Core Functionality (Unchanged Logic, Compact UI)
    # ==============================================
    def _update_status_bar(self, message):
        """Update status bar (COMPACT message)"""
        try:
            active_tab = self.tab_widget.tabText(self.tab_widget.currentIndex())
            full_msg = f"{message[:40]} | {active_tab}"  # Truncate long messages
        except:
            full_msg = message[:50]
        self.status_bar.showMessage(full_msg)

    def _on_tab_changed(self, index):
        """Update status bar on tab change"""
        tab_name = self.tab_widget.tabText(index)
        sensor_state = "ON" if self.sensor_widget.sensor_thread.running else "OFF"
        camera_state = "ON" if self.webcam_widget.camera_thread.running else "OFF"
        self._update_status_bar(f"Sensor: {sensor_state} | Camera: {camera_state} | AI: Ready")

    def _update_sensor_status(self, msg):
        """Update sensor status (COMPACT)"""
        self.sensor_status_label.setText(f"Status: {msg[:30]}")  # Truncate
        sensor_state = "ON" if self.sensor_widget.sensor_thread.running else "OFF"
        self._update_status_bar(f"Sensor: {sensor_state} | Camera: {'ON' if self.webcam_widget.camera_thread.running else 'OFF'}")

    def _show_sensor_error(self, msg):
        """Show critical sensor errors (COMPACT dialog)"""
        QMessageBox.critical(self, "SENSOR ERROR", 
                            f"{msg[:60]}\n\nConnect LSM303DLH to I2C Bus 1.", 
                            QMessageBox.Ok)
        self._update_status_bar(f"Sensor: ERROR | Camera: {'ON' if self.webcam_widget.camera_thread.running else 'OFF'}")

    def _on_image_analyzed(self, filepath):
        """Handler for analyze_image signal"""
        self.database_widget.db_thread.set_operation(
            "log",
            (0.0, 0.0, "AI", "image_analysis_start", f"Analyzing: {os.path.basename(filepath)}")
        )
        self._update_status_bar(f"AI: Analyzing {os.path.basename(filepath)[:20]}")

    def _handle_tracking_auto_record(self, enabled, target):
        """Auto-recording for celestial tracking"""
        if enabled:
            if not self.webcam_widget.camera_thread.running:
                self.webcam_widget.toggle_camera()
                self.camera_active = True
                self._update_status_bar(f"Camera ON for {target} tracking")
            
            if not self.webcam_widget.camera_thread.recording:
                self.webcam_widget.toggle_recording()
                self._update_status_bar(f"Recording: {target}")
                
                self.database_widget.db_thread.set_operation(
                    "log",
                    (0.0, 0.0, target, "auto_record_start", f"Auto-record: {target}")
                )
        else:
            if self.webcam_widget.camera_thread.recording:
                self.webcam_widget.toggle_recording()
                self._update_status_bar(f"Recording stopped: {target}")
                
                self.database_widget.db_thread.set_operation(
                    "log",
                    (0.0, 0.0, target, "auto_record_stop", f"Auto-record stop: {target}")
                )

    def _on_moon_tracking_toggled(self, enabled):
        self._handle_tracking_auto_record(enabled, "Moon")

    def _on_sun_tracking_toggled(self, enabled):
        self._handle_tracking_auto_record(enabled, "Sun (Filter)")

    def _slew_to_moon_position(self, target_alt, target_az):
        """Slew to moon (safe bounds)"""
        safe_alt = max(0.0, min(90.0, target_alt))
        safe_az = target_az % 360.0
        
        self.altitude_widget.motor_thread.set_target(safe_alt)
        self.altitude_widget.alt_slider.setValue(int(safe_alt))
        self.azimuth_widget.motor_thread.set_target(safe_az)
        self.azimuth_widget.az_slider.setValue(int(safe_az))
        
        self.database_widget.db_thread.set_operation(
            "log",
            (safe_alt, safe_az, "Moon", "goto_moon", f"Moon: Alt {safe_alt:.1f}°, Az {safe_az:.1f}°")
        )
        
        self._update_status_bar(f"Slewing to Moon: {safe_alt:.1f}°/{safe_az:.1f}°")
        self.update_ai_context()

    def _slew_to_sun_position(self, target_alt, target_az):
        """Slew to sun (safety critical)"""
        if not self.sun_widget.filter_check.isChecked():
            QMessageBox.critical(self, "SOLAR WARNING", 
                                "SOLAR FILTER REQUIRED!\nAborting sun slew.", 
                                QMessageBox.Ok)
            return

        safe_alt = max(0.0, min(90.0, target_alt))
        safe_az = target_az % 360.0
        
        self.altitude_widget.motor_thread.set_target(safe_alt)
        self.altitude_widget.alt_slider.setValue(int(safe_alt))
        self.azimuth_widget.motor_thread.set_target(safe_az)
        self.azimuth_widget.az_slider.setValue(int(safe_az))
        
        self.database_widget.db_thread.set_operation(
            "log",
            (safe_alt, safe_az, "Sun", "goto_sun", f"Sun: Alt {safe_alt:.1f}°, Az {safe_az:.1f}°")
        )
        
        self._update_status_bar(f"Slewing to Sun: {safe_alt:.1f}°/{safe_az:.1f}°")
        self.update_ai_context()

    def _update_gps_and_ai_context(self, new_lat, new_lon):
        """Update GPS and AI context"""
        lat_dir = "N" if new_lat >= 0 else "S"
        lon_dir = "E" if new_lon >= 0 else "W"
        self.config["gps"]["lat"] = f"{abs(new_lat):.4f}° {lat_dir}"
        self.config["gps"]["lon"] = f"{abs(new_lon):.4f}° {lon_dir}"
        self.lat_numeric = new_lat
        self.lon_numeric = new_lon
        
        self.update_ai_context()
        self._update_status_bar(f"GPS: {self.config['gps']['lat'][:10]}, {self.config['gps']['lon'][:10]}")

    def update_ai_context(self):
        """Update AI context (COMPACT)"""
        try:
            current_alt = self.altitude_widget.motor_thread.current_alt
            current_az = self.azimuth_widget.motor_thread.current_az
            gps_str = f"{self.config['gps']['lat'][:10]}, {self.config['gps']['lon'][:10]}"
            camera_state = f"Cam: {'ON' if self.webcam_widget.camera_thread.running else 'OFF'}"
            sensor_state = f"Sensor: {'ON' if self.sensor_widget.sensor_thread.running else 'OFF'}"
        except:
            current_alt = 0.0
            current_az = 0.0
            gps_str = f"{self.config['gps']['lat'][:10]}, {self.config['gps']['lon'][:10]}"
            camera_state = "Cam: Unknown"
            sensor_state = "Sensor: Unknown"

        # Compact AI context (fits small screen)
        context = f"""
        Pi 5 Telescope (800×480):
        - Position: Alt {current_alt:.1f}°, Az {current_az:.1f}°
        - Location: {gps_str}
        - {camera_state}, {sensor_state}
        - GPIO: Alt(17/18), Az(27/23)
        - Cam: {self.config['camera']['default_resolution']}, Exp {self.config['camera']['exposure']}
        """
        self.deepseek_widget.update_context(context)

    def save_gpio_config(self, config, axis, direction, gpio_key):
        """GPIO config save handler (COMPACT dialog)"""
        QMessageBox.information(self, "GPIO Config (Pi 5)", 
                                "Pi 5 GPIO Pins (Locked):\n"
                                "- Alt Up: 17 | Alt Down: 18\n"
                                "- Az Left: 27 | Az Right: 23", 
                                QMessageBox.Ok)
        save_config(self.config)

    def closeEvent(self, event):
        """Cleanup (safe shutdown)"""
        # Stop real sensor widget
        if self.sensor_widget.sensor_thread.running:
            self.sensor_widget.close()
        
        # Stop camera
        if self.webcam_widget.camera_thread.running:
            self.webcam_widget.close()
        
        # Stop motors
        try:
            self.altitude_widget.close()
            self.azimuth_widget.close()
        except:
            pass
        
        # Stop AI/database
        try:
            self.database_widget.closeEvent(event)
            self.deepseek_widget.close()
        except:
            pass
        
        # Save config
        save_config(self.config)
        
        self._update_status_bar("Shutting down safely...")
        time.sleep(0.5)
        event.accept()

# ==============================================
# Application Entry Point (800×480 Optimized)
# ==============================================
if __name__ == "__main__":
    # Pi 5 High DPI Scaling (critical for small screen)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    
    # Fix module path first
    if not fix_module_path():
        QMessageBox.critical(None, "Module Error", 
                            "Missing modules! Ensure 'modules' folder has:\n"
                            "- altitude.py, azimuth.py, sensor.py, webcam.py\n"
                            "- moon.py, sun.py, database.py, deepseek.py")
        sys.exit(1)

    # Debug Real Sensor Hardware Status
    print(f"\n=== RASPBERRY PI 5 DIAGNOSTICS (800×480) ===")
    print(f"I2C Bus {I2C_BUS} Available: {check_i2c_bus(I2C_BUS)}")
    print(f"GPIO 27 Mapped: {PI5_PIN_MAP['GPIO27']}")
    print(f"Display: {DEFAULT_CONFIG['ui']['min_window_width']}×{DEFAULT_CONFIG['ui']['min_window_height']}")
    print(f"DeepSeek API Key: {'Configured' if load_config()['ai']['deepseek_api_key'] else 'Missing'}")
    print(f"⚠️ REAL SENSOR MODE - LSM303DLH required!\n")

    # Initialize App (800×480 optimized)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Consistent style across Pi 5

    # Create & Show Main Window (fixed 800×480)
    window = TelescopeControllerGUI()
    window.show()
    
    # Run App
    sys.exit(app.exec_())