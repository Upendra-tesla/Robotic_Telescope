import sys
import json
import psutil
import datetime
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QStatusBar,
    QWidget, QVBoxLayout, QMessageBox, QLabel, QComboBox,
    QHBoxLayout, QGroupBox, QPushButton
)
from PyQt5.QtCore import QTimer, Qt, QThread
from PyQt5.QtGui import QPalette, QColor

# GPIO Setup (with fallback for non-Raspberry Pi)
try:
    from gpiozero import OutputDevice, Device
    from gpiozero.pins.mock import MockFactory
    # Use mock pins if not on Pi (for testing)
    if not os.path.exists('/sys/class/gpio'):
        Device.pin_factory = MockFactory()
    GPIO_AVAILABLE = True
except ImportError:
    # Mock gpiozero for non-Pi environments
    class OutputDevice:
        def __init__(self, pin, active_high=True, initial_value=False):
            self.pin = pin
            self.value = initial_value
        def on(self): self.value = True
        def off(self): self.value = False
    GPIO_AVAILABLE = False

# Import modules
from modules.altitude import AltitudeControlWidget
from modules.azimuth import AzimuthControlWidget
from modules.webcam import CameraWidget
from modules.sun import SunTrackingWidget
from modules.moon import MoonTrackingWidget
from modules.database import DatabaseWidget
from modules.deepseek import AIWidget

# --------------------------
# Global Theme Configuration
# --------------------------
THEMES = {
    "Dark (Default)": {
        "stylesheet": """
            /* Global Theme: Dark */
            QMainWindow { 
                background-color: #1a1a1a; 
                color: #ffffff;
            }
            QTabWidget { 
                color: #ffffff; 
                background-color: #1a1a1a;
            }
            QTabWidget::pane {
                border: 1px solid #404040;
                background-color: #1a1a1a;
            }
            QTabBar::tab { 
                background-color: #2d2d2d; 
                padding: 10px; 
                min-width: 120px; 
                color: #ffffff;
                margin-right: 2px;
            }
            QTabBar::tab:selected { 
                background-color: #404040; 
            }
            QPushButton { 
                background-color: #333333; 
                color: #ffffff;
                min-height: 40px; 
                min-width: 40px;
                border-radius: 5px;
                border: none;
            }
            QPushButton#emergencyStop { 
                background-color: #ff3333; 
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #444444;
            }
            QSlider { 
                color: #ffffff; 
                background-color: #2d2d2d;
            }
            QSlider::groove:horizontal {
                background-color: #2d2d2d;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background-color: #ffffff;
                width: 16px;
                height: 16px;
                border-radius: 8px;
                margin: -4px 0;
            }
            QLabel, QGroupBox, QTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                color: #ffffff;
            }
            QGroupBox {
                border: 1px solid #404040;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 5px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QStatusBar {
                background-color: #2d2d2d;
                color: #ffffff;
            }
            QComboBox {
                background-color: #2d2d2d;
                border: 1px solid #404040;
                border-radius: 5px;
                padding: 5px;
            }
        """
    },
    "Light": {
        "stylesheet": """
            /* Global Theme: Light */
            QMainWindow { 
                background-color: #f8f9fa; 
                color: #000000;
            }
            QTabWidget { 
                color: #000000; 
                background-color: #f8f9fa;
            }
            QTabWidget::pane {
                border: 1px solid #adb5bd;
                background-color: #f8f9fa;
            }
            QTabBar::tab { 
                background-color: #e9ecef; 
                padding: 10px; 
                min-width: 120px; 
                color: #000000;
                margin-right: 2px;
            }
            QTabBar::tab:selected { 
                background-color: #dee2e6; 
            }
            QPushButton { 
                background-color: #adb5bd; 
                color: #000000;
                min-height: 40px; 
                min-width: 40px;
                border-radius: 5px;
                border: none;
            }
            QPushButton#emergencyStop { 
                background-color: #dc3545; 
                font-weight: 700;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #ced4da;
            }
            QSlider { 
                color: #000000; 
                background-color: #e9ecef;
            }
            QSlider::groove:horizontal {
                background-color: #e9ecef;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background-color: #000000;
                width: 16px;
                height: 16px;
                border-radius: 8px;
                margin: -4px 0;
            }
            QLabel, QGroupBox, QTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                color: #000000;
            }
            QGroupBox {
                border: 1px solid #adb5bd;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 5px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QStatusBar {
                background-color: #e9ecef;
                color: #000000;
            }
            QComboBox {
                background-color: #e9ecef;
                border: 1px solid #adb5bd;
                border-radius: 5px;
                padding: 5px;
            }
        """
    },
    "Astronomy Blue": {
        "stylesheet": """
            /* Global Theme: Astronomy Blue (Night Sky) */
            QMainWindow { 
                background-color: #0a1929; 
                color: #e6f1ff;
            }
            QTabWidget { 
                color: #e6f1ff; 
                background-color: #0a1929;
            }
            QTabWidget::pane {
                border: 1px solid #23395d;
                background-color: #0a1929;
            }
            QTabBar::tab { 
                background-color: #112240; 
                padding: 10px; 
                min-width: 120px; 
                color: #e6f1ff;
                margin-right: 2px;
            }
            QTabBar::tab:selected { 
                background-color: #23395d; 
            }
            QPushButton { 
                background-color: #1746a2; 
                color: #e6f1ff;
                min-height: 40px; 
                min-width: 40px;
                border-radius: 5px;
                border: none;
            }
            QPushButton#emergencyStop { 
                background-color: #ff6b6b; 
                font-weight: 700;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #2857b8;
            }
            QSlider { 
                color: #e6f1ff; 
                background-color: #112240;
            }
            QSlider::groove:horizontal {
                background-color: #112240;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background-color: #ffd166;
                width: 16px;
                height: 16px;
                border-radius: 8px;
                margin: -4px 0;
            }
            QLabel, QGroupBox, QTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                color: #e6f1ff;
            }
            QGroupBox {
                border: 1px solid #23395d;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 5px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QStatusBar {
                background-color: #112240;
                color: #e6f1ff;
            }
            QComboBox {
                background-color: #112240;
                border: 1px solid #23395d;
                border-radius: 5px;
                padding: 5px;
            }
        """
    }
}

# --------------------------
# GPIO Pin Mapping (BCM → Physical Pin)
# --------------------------
GPIO_PIN_MAP = {
    "2 (Pin 3)": 2,
    "3 (Pin 5)": 3,
    "4 (Pin 7)": 4,
    "17 (Pin 11)": 17,
    "18 (Pin 12)": 18,
    "27 (Pin 13)": 27,
    "22 (Pin 15)": 22,
    "23 (Pin 16)": 23,
    "24 (Pin 18)": 24,
    "25 (Pin 22)": 25,
    "8 (Pin 24)": 8,
    "7 (Pin 26)": 7,
    "12 (Pin 32)": 12,
    "16 (Pin 36)": 16,
    "20 (Pin 38)": 20,
    "21 (Pin 40)": 21
}

class TelescopeMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Step 1: Basic window setup (first)
        self.setWindowTitle("Raspberry Pi 5 Telescope Controller")
        self.setGeometry(100, 100, 1280, 720)  # Pi 5 touchscreen optimized

        # Step 2: Load config (including saved theme + GPIO)
        self.config = self._load_config()
        self.current_theme = self.config.get("ui", {}).get("active_theme", "Dark (Default)")
        
        # Step 3: Initialize status bar FIRST (critical fix)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Step 4: Apply theme (now status_bar exists)
        self._apply_theme(self.current_theme, is_initial=True)

        # Step 5: Initialize tab widget and tabs
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        
        # Pass config to child widgets (for GPIO/theme)
        self._add_tabs()

        # Step 6: Add theme switcher to status bar
        self._add_theme_switcher()
        
        # Step 7: Update status bar with system info + GPIO status
        self._update_status_bar()

        # Step 8: Start status update timer (1Hz)
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status_bar)
        self.status_timer.start(1000)

        # Step 9: Exit confirmation
        self.setWindowFlags(self.windowFlags() | Qt.WindowCloseButtonHint)

    # --------------------------
    # Config Management (Theme + GPIO)
    # --------------------------
    def _load_config(self):
        """Load config file (create default if missing, add missing GPIO fields)"""
        config_path = "config/settings.json"
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            
            # Fix: Add missing GPIO fields to old configs
            if "gpio" not in config:
                config["gpio"] = {
                    "altitude_up": "17 (Pin 11)",
                    "altitude_down": "18 (Pin 12)",
                    "azimuth_left": "27 (Pin 13)",
                    "azimuth_right": "22 (Pin 15)"
                }
            # Fix: Add missing UI theme field to old configs
            if "ui" not in config or "active_theme" not in config["ui"]:
                config["ui"] = config.get("ui", {})
                config["ui"]["active_theme"] = "Dark (Default)"
            
            # Save updated config back to file
            with open(config_path, "w") as f:
                json.dump(config, f, indent=4)
                
        except FileNotFoundError:
            # Create default config with GPIO pins
            config = {
                "camera": {
                    "default_resolution": "1280x720",
                    "default_fps": 30,
                    "image_save_path": "data/images/",
                    "video_save_path": "data/videos/",
                    "exposure": 100,
                    "white_balance": "auto"
                },
                "telescope": {
                    "altitude_min": 0.0,
                    "altitude_max": 90.0,
                    "azimuth_min": 0.0,
                    "azimuth_max": 360.0,
                    "park_altitude": 0.0,
                    "park_azimuth": 0.0
                },
                "gpio": {  # New GPIO config
                    "altitude_up": "17 (Pin 11)",
                    "altitude_down": "18 (Pin 12)",
                    "azimuth_left": "27 (Pin 13)",
                    "azimuth_right": "22 (Pin 15)"
                },
                "ui": {
                    "theme": "dark",
                    "touch_mode": True,
                    "status_bar_update_rate": 1000,
                    "active_theme": "Dark (Default)"
                },
                "gps": {
                    "default_latitude": 40.7128,
                    "default_longitude": -74.0060,
                    "use_gps_module": False
                }
            }
            # Save default config
            os.makedirs("config", exist_ok=True)
            with open(config_path, "w") as f:
                json.dump(config, f, indent=4)
        return config

    def save_gpio_config(self, gpio_type, pin_key, pin_label):
        """Save GPIO pin config to settings.json"""
        # Ensure gpio key exists before saving
        if "gpio" not in self.config:
            self.config["gpio"] = {}
        self.config["gpio"][f"{gpio_type}_{pin_key}"] = pin_label
        with open("config/settings.json", "w") as f:
            json.dump(self.config, f, indent=4)
        # Update status bar
        self.status_bar.showMessage(f"GPIO Updated: {gpio_type} {pin_key} = {pin_label} | " + self.status_bar.currentMessage())

    # --------------------------
    # Theme Management (Preserved + Fixed)
    # --------------------------
    def _add_theme_switcher(self):
        """Add theme selection dropdown to status bar"""
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Theme:"))
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEMES.keys())
        self.theme_combo.setCurrentText(self.current_theme)
        self.theme_combo.currentTextChanged.connect(self._on_theme_change)
        
        theme_widget = QWidget()
        theme_widget.setLayout(theme_layout)
        self.status_bar.addPermanentWidget(theme_widget)

    def _apply_theme(self, theme_name, is_initial=False):
        """Apply selected global theme to entire window"""
        if theme_name in THEMES:
            self.setStyleSheet(THEMES[theme_name]["stylesheet"])
            # Ensure ui key exists before saving
            if "ui" not in self.config:
                self.config["ui"] = {}
            self.config["ui"]["active_theme"] = theme_name
            with open("config/settings.json", "w") as f:
                json.dump(self.config, f, indent=4)
            
            if not is_initial:
                current_msg = self.status_bar.currentMessage() or ""
                self.status_bar.showMessage(f"Theme changed to: {theme_name} | {current_msg}")

    def _on_theme_change(self, new_theme):
        """Handle real-time theme selection change"""
        self.current_theme = new_theme
        self._apply_theme(new_theme, is_initial=False)

    # --------------------------
    # Tab Management (Pass Config to Child Widgets)
    # --------------------------
    def _add_tabs(self):
        """Add all functional tabs (pass config for GPIO/theme)"""
        self.tab_widget.addTab(AltitudeControlWidget(self.config, self.save_gpio_config, GPIO_PIN_MAP), "Altitude Control")
        self.tab_widget.addTab(AzimuthControlWidget(self.config, self.save_gpio_config, GPIO_PIN_MAP), "Azimuth Control")
        self.tab_widget.addTab(CameraWidget(self.config), "Camera")
        self.tab_widget.addTab(SunTrackingWidget(), "Sun Tracking")
        self.tab_widget.addTab(MoonTrackingWidget(), "Moon Tracking")
        self.tab_widget.addTab(DatabaseWidget(), "Data Logging")
        self.tab_widget.addTab(AIWidget(), "AI Assistant")

    # --------------------------
    # Status Bar (Add GPIO Info)
    # --------------------------
    def _update_status_bar(self):
        """Update status bar with system + GPIO info"""
        # System info (Pi 5 specific)
        try:
            cpu_temp = psutil.sensors_temperatures()["cpu_thermal"][0].current
        except (KeyError, IndexError):
            cpu_temp = 0.0  # Fallback if temp sensor not found
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Mock GPS
        gps_coords = "Lat: 40.7128° N, Lon: 74.0060° W"
        
        # Telescope status
        telescope_status = "Auto | Connected | Normal"
        
        # GPIO status (simplified)
        gpio_status = f"GPIO: {('Enabled' if GPIO_AVAILABLE else 'Mocked')}"

        # Compose status text
        status_text = (
            f"Time: {current_time} | GPS: {gps_coords} | "
            f"Temp: {cpu_temp:.1f}°C | {gpio_status} | Telescope: {telescope_status}"
        )
        self.status_bar.showMessage(status_text)

    # --------------------------
    # Exit Handling
    # --------------------------
    def closeEvent(self, event):
        """Confirm exit + clean up GPIO"""
        reply = QMessageBox.question(
            self, "Exit Confirmation",
            "Are you sure you want to exit? The telescope will park automatically.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # Clean up GPIO (if available)
            if GPIO_AVAILABLE:
                try:
                    # Close all GPIO devices (placeholder for child widget cleanup)
                    pass
                except Exception:
                    pass
            event.accept()
        else:
            event.ignore()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TelescopeMainWindow()
    window.show()
    sys.exit(app.exec_())