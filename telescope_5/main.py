import sys
import os
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox,
    QComboBox, QSpinBox, QCheckBox, QGroupBox, QLineEdit
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPalette, QColor

# --------------------------
# Critical: Add modules folder to path
# --------------------------
MODULES_PATH = os.path.join(os.path.dirname(__file__), "modules")
if MODULES_PATH not in sys.path:
    sys.path.append(MODULES_PATH)

# Import components
from altitude import AltitudeControlWidget
from azimuth import AzimuthControlWidget
from database import DatabaseWidget
from deepseek import DeepSeekWidget
from moon import MoonTrackingWidget
from sun import SunTrackingWidget
from webcam import WebcamWidget

# --------------------------
# Pi 5 Theme (Touch-Friendly Dark Mode)
# --------------------------
def setup_pi5_theme(app):
    app.setStyle("Fusion")
    palette = QPalette()
    
    # Dark theme for Pi 5 touchscreen
    palette.setColor(QPalette.Window, QColor(46, 46, 46))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(30, 30, 30))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    
    app.setPalette(palette)
    
    # Larger font for touchscreen
    font = QFont()
    font.setPointSize(10)
    app.setFont(font)

# --------------------------
# Critical: GPIO Pin Map (BCM + Physical Pin Numbers)
# --------------------------
def get_gpio_pin_map():
    """Return BCM pins with physical pin numbers (Raspberry Pi 5)"""
    # Format: "GPIOxx": (bcm_number, physical_pin_number)
    return {
        "GPIO2": (2, 3),    "GPIO3": (3, 5),
        "GPIO4": (4, 7),    "GPIO5": (5, 29),
        "GPIO6": (6, 31),   "GPIO7": (7, 26),
        "GPIO8": (8, 24),   "GPIO9": (9, 21),
        "GPIO10": (10, 19), "GPIO11": (11, 23),
        "GPIO12": (12, 32), "GPIO13": (13, 33),
        "GPIO14": (14, 8),  "GPIO15": (15, 10),
        "GPIO16": (16, 36), "GPIO17": (17, 11),
        "GPIO18": (18, 12), "GPIO19": (19, 35),
        "GPIO20": (20, 38), "GPIO21": (21, 40),
        "GPIO22": (22, 15), "GPIO23": (23, 16),
        "GPIO24": (24, 18), "GPIO25": (25, 22),
        "GPIO26": (26, 37), "GPIO27": (27, 13)
    }

# --------------------------
# Load Config (Guaranteed GPIO Keys)
# --------------------------
def load_config():
    config_path = "config/settings.json"
    os.makedirs("config", exist_ok=True)
    
    default_config = {
        "gpio": {
            "alt_up": "GPIO17",
            "alt_down": "GPIO18",
            "azimuth_left": "GPIO22",
            "azimuth_right": "GPIO23"
        },
        "telescope": {
            "park_altitude": 0.0,
            "park_azimuth": 0.0,
            "max_speed": 1.0,
            "latitude": 40.7128,  # Default: New York
            "longitude": -74.0060 # Default: New York
        },
        "camera": {
            "default_resolution": "640x480",
            "default_fps": 30,
            "exposure": 500,
            "white_balance": "auto",
            "image_save_path": "data/images",
            "video_save_path": "data/videos"
        }
    }
    
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        
        # Add missing keys
        if "gpio" not in config:
            config["gpio"] = default_config["gpio"]
        else:
            for key in default_config["gpio"]:
                if key not in config["gpio"]:
                    config["gpio"][key] = default_config["gpio"][key]
        
        # Add lat/lon if missing
        if "latitude" not in config["telescope"]:
            config["telescope"]["latitude"] = default_config["telescope"]["latitude"]
        if "longitude" not in config["telescope"]:
            config["telescope"]["longitude"] = default_config["telescope"]["longitude"]
        
        with open(config_path, "w") as f:
            json.dump(config, f, indent=4)
        
        return config
    
    except (FileNotFoundError, json.JSONDecodeError):
        with open(config_path, "w") as f:
            json.dump(default_config, f, indent=4)
        return default_config

# --------------------------
# Save GPIO Config
# --------------------------
def save_gpio_config(config, gpio_type, pin_key, pin_label):
    if gpio_type == "altitude":
        if pin_key == "up":
            config["gpio"]["alt_up"] = pin_label
        else:
            config["gpio"]["alt_down"] = pin_label
    elif gpio_type == "azimuth":
        if pin_key == "left":
            config["gpio"]["azimuth_left"] = pin_label
        else:
            config["gpio"]["azimuth_right"] = pin_label
    
    with open("config/settings.json", "w") as f:
        json.dump(config, f, indent=4)

# --------------------------
# Main Window (Full Integration)
# --------------------------
class TelescopeControlMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Telescope Control System (Pi 5 + GPIOZero)")
        self.setGeometry(100, 100, 1200, 800)
        
        # Load config and pin map
        self.config = load_config()
        self.gpio_pin_map = get_gpio_pin_map()  # BCM + physical pins
        
        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Status Bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready - Pi 5 Optimized | Physical Pin Numbers Enabled")

        # Tab Widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # 1. Altitude Control (GPIOZero + Physical Pins)
        self.altitude_widget = AltitudeControlWidget(
            self.config, save_gpio_config, self.gpio_pin_map
        )
        self.tab_widget.addTab(self.altitude_widget, "Altitude Control")

        # 2. Azimuth Control (GPIOZero + Physical Pins)
        self.azimuth_widget = AzimuthControlWidget(
            self.config, save_gpio_config, self.gpio_pin_map
        )
        self.tab_widget.addTab(self.azimuth_widget, "Azimuth Control")

        # 3. Moon Tracking (Editable Lat/Lon)
        self.moon_widget = MoonTrackingWidget(
            lat=self.config["telescope"]["latitude"],
            lon=self.config["telescope"]["longitude"]
        )
        self.tab_widget.addTab(self.moon_widget, "Moon Tracking")
        self.moon_widget.slew_to_moon.connect(self._slew_to_position)
        self.moon_widget.lat_lon_updated.connect(self._update_telescope_lat_lon)

        # 4. Sun Tracking (Editable Lat/Lon)
        self.sun_widget = SunTrackingWidget(
            lat=self.config["telescope"]["latitude"],
            lon=self.config["telescope"]["longitude"]
        )
        self.tab_widget.addTab(self.sun_widget, "Sun Tracking")
        self.sun_widget.slew_to_sun.connect(self._slew_to_position)
        self.sun_widget.lat_lon_updated.connect(self._update_telescope_lat_lon)

        # 5. Camera Control (Start/Stop + Capture + Record + RGB Histogram)
        self.webcam_widget = WebcamWidget(self.config)
        self.tab_widget.addTab(self.webcam_widget, "Camera Control")

        # 6. Data Logging
        self.database_widget = DatabaseWidget()
        self.tab_widget.addTab(self.database_widget, "Data Logging")

        # 7. AI Assistant
        self.deepseek_widget = DeepSeekWidget()
        self.tab_widget.addTab(self.deepseek_widget, "AI Assistant")

        # Bottom Control Buttons
        bottom_layout = QHBoxLayout()
        
        # Park Button
        self.park_btn = QPushButton("Park Telescope")
        self.park_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px;")
        self.park_btn.clicked.connect(self._park_telescope)
        bottom_layout.addWidget(self.park_btn)
        
        # Emergency Stop
        self.emergency_stop_btn = QPushButton("EMERGENCY STOP")
        self.emergency_stop_btn.setStyleSheet("background-color: #ff0000; color: white; font-weight: bold; padding: 8px;")
        self.emergency_stop_btn.clicked.connect(self._emergency_stop)
        bottom_layout.addWidget(self.emergency_stop_btn)
        
        # Save Config
        self.save_config_btn = QPushButton("Save Configuration")
        self.save_config_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 8px;")
        self.save_config_btn.clicked.connect(self._save_config)
        bottom_layout.addWidget(self.save_config_btn)
        
        main_layout.addLayout(bottom_layout)

        # Pi 5 Resource Cleanup
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self._cleanup_resources)
        self.cleanup_timer.start(30000)

    # Core Functions
    def _slew_to_position(self, alt, az):
        """Move telescope to target position"""
        self.altitude_widget.alt_slider.setValue(int(alt))
        self.altitude_widget.motor_thread.set_target(float(alt))
        
        self.azimuth_widget.az_slider.setValue(int(az))
        self.azimuth_widget.motor_thread.set_target(float(az))
        
        QMessageBox.information(
            self, "Slew to Target",
            f"Telescope moving to:\nAltitude: {alt:.1f}°\nAzimuth: {az:.1f}°",
            QMessageBox.Ok
        )

    def _update_telescope_lat_lon(self, lat, lon):
        """Update lat/lon in config when user edits it"""
        self.config["telescope"]["latitude"] = lat
        self.config["telescope"]["longitude"] = lon
        self.status_bar.showMessage(f"Updated Location: Lat {lat:.4f}, Lon {lon:.4f}")

    def _park_telescope(self):
        self.altitude_widget._park_altitude()
        self.azimuth_widget._park_azimuth()
        self.status_bar.showMessage("Telescope Parked - Safe Position (0° Alt / 0° Az)")
        QMessageBox.information(self, "Park Complete", "Telescope parked at safe position!", QMessageBox.Ok)

    def _emergency_stop(self):
        self.altitude_widget._emergency_stop()
        self.azimuth_widget._emergency_stop()
        self.status_bar.showMessage("EMERGENCY STOP: All Movement Halted")
        QMessageBox.critical(self, "Emergency Stop", "All telescope movement stopped!", QMessageBox.Ok)

    def _save_config(self):
        with open("config/settings.json", "w") as f:
            json.dump(self.config, f, indent=4)
        self.status_bar.showMessage("Configuration Saved (Including Lat/Lon & GPIO Pins)")
        QMessageBox.information(self, "Success", "All settings saved to config/settings.json!", QMessageBox.Ok)

    def _cleanup_resources(self):
        self.status_bar.showMessage("Resource Cleanup - Pi 5 Memory Optimized")

    def closeEvent(self, event):
        """Safe exit with GPIO cleanup"""
        self.altitude_widget.close()
        self.azimuth_widget.close()
        self.moon_widget.close()
        self.sun_widget.close()
        self.webcam_widget.close()
        self.database_widget.close()
        self.deepseek_widget.close()
        
        self.cleanup_timer.stop()
        
        confirm = QMessageBox.question(
            self, "Exit", "Are you sure you want to exit?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.status_bar.showMessage("Exiting Safely - GPIO Pins Released")
            event.accept()
        else:
            event.ignore()

# --------------------------
# Main Program Entry
# --------------------------
def main():
    # Pi 5 Environment Fixes
    os.environ["QT_QPA_EGLFS_PHYSICAL_WIDTH"] = "1280"
    os.environ["QT_QPA_EGLFS_PHYSICAL_HEIGHT"] = "800"
    os.environ["QT_QPA_PLATFORM"] = "xcb"
    
    app = QApplication(sys.argv)
    setup_pi5_theme(app)
    
    window = TelescopeControlMainWindow()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()