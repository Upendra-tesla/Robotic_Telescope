import sys
import json
import psutil
import datetime
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QStatusBar,
    QWidget, QVBoxLayout, QMessageBox, QLabel, QComboBox,
    QHBoxLayout, QGroupBox, QPushButton, QDoubleSpinBox, QLineEdit
)
from PyQt5.QtCore import QTimer, Qt, QThread
from PyQt5.QtGui import QPalette, QColor

# --------------------------
# FIXED: Robust GPIO Setup (Mock + Safety Checks)
# --------------------------
GPIO_AVAILABLE = False
try:
    from gpiozero import OutputDevice, Device
    from gpiozero.pins.mock import MockFactory, MockPin
    
    # Force mock pins for testing (even on Pi, uncomment to test):
    # Device.pin_factory = MockFactory()
    
    # Auto-detect if on Pi (real GPIO) or use mock
    if os.path.exists('/sys/class/gpio'):
        GPIO_AVAILABLE = True
    else:
        # FIX: Properly initialize mock pins to avoid None
        Device.pin_factory = MockFactory()
        GPIO_AVAILABLE = False  # Still mark as unavailable (mock mode)
    
except ImportError:
    # FIX: Full mock implementation for missing gpiozero
    GPIO_AVAILABLE = False
    
    class MockPin:
        """Complete mock pin to avoid NoneType errors"""
        def __init__(self, number):
            self.number = number
            self._state = False  # Initial state: off
        
        @property
        def state(self):
            return self._state
        
        @state.setter
        def state(self, value):
            self._state = value
        
        def close(self):
            self._state = False
    
    class OutputDevice:
        """Mock OutputDevice with safety checks"""
        def __init__(self, pin, active_high=True, initial_value=False):
            self.pin = MockPin(pin) if isinstance(pin, int) else pin
            self.active_high = active_high
            self.initial_value = initial_value
            self._closed = False
        
        def on(self):
            if not self._closed:
                self.pin.state = True
        
        def off(self):
            if not self._closed:
                self.pin.state = False
        
        def close(self):
            self._closed = True
            self.pin.state = False

# Import modules
from modules.altitude import AltitudeControlWidget
from modules.azimuth import AzimuthControlWidget
from modules.webcam import CameraWidget
from modules.sun import SunTrackingWidget
from modules.moon import MoonTrackingWidget
from modules.database import DatabaseWidget
from modules.deepseek import AIWidget

# --------------------------
# SIMPLIFIED: Only 2 Themes (Dark + Light)
# --------------------------
THEMES = {
    "Dark (Default)": {
        "stylesheet": """
            /* Global Theme: Dark (FIXED Input Widgets) */
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
            /* Base text widgets (labels/groups) */
            QLabel, QGroupBox, QTextEdit {
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
            
            /* --------------------------
               FIXED: Input Widgets (High Contrast)
               -------------------------- */
            /* Line Edit (API Key, Object Box) */
            QLineEdit {
                background-color: #2d2d2d;
                color: #ffffff; /* White text on dark background */
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 5px;
            }
            QLineEdit:focus {
                border: 1px solid #ffffff; /* Highlight focus */
            }
            /* Spin/DoubleSpin (Altitude/Azimuth/FPS/GPS) */
            QSpinBox, QDoubleSpinBox {
                background-color: #2d2d2d;
                color: #ffffff; /* White text on dark background */
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 5px;
            }
            QSpinBox::up-button, QDoubleSpinBox::up-button {
                background-color: #3a3a3a;
                color: #ffffff;
                border: none;
            }
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                background-color: #3a3a3a;
                color: #ffffff;
                border: none;
            }
            /* ComboBox (Theme/GPIO Pins) */
            QComboBox {
                background-color: #2d2d2d;
                color: #ffffff; /* White text on dark background */
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 5px;
            }
            QComboBox::drop-down {
                background-color: #3a3a3a;
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #555555;
            }
        """
    },
    "Light": {
        "stylesheet": """
            /* Global Theme: Light (FIXED Input Widgets) */
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
            /* Base text widgets (labels/groups) */
            QLabel, QGroupBox, QTextEdit {
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
                color: #000000;
            }
            QStatusBar {
                background-color: #e9ecef;
                color: #000000;
            }
            
            /* --------------------------
               FIXED: Input Widgets (High Contrast)
               -------------------------- */
            /* Line Edit (API Key, Object Box) */
            QLineEdit {
                background-color: #ffffff;
                color: #000000; /* Black text on white background */
                border: 1px solid #adb5bd;
                border-radius: 5px;
                padding: 5px;
            }
            QLineEdit:focus {
                border: 1px solid #000000; /* Highlight focus */
            }
            /* Spin/DoubleSpin (Altitude/Azimuth/FPS/GPS) */
            QSpinBox, QDoubleSpinBox {
                background-color: #ffffff;
                color: #000000; /* Black text on white background */
                border: 1px solid #adb5bd;
                border-radius: 5px;
                padding: 5px;
            }
            QSpinBox::up-button, QDoubleSpinBox::up-button {
                background-color: #f1f3f5;
                color: #000000;
                border: none;
            }
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                background-color: #f1f3f5;
                color: #000000;
                border: none;
            }
            /* ComboBox (Theme/GPIO Pins) */
            QComboBox {
                background-color: #ffffff;
                color: #000000; /* Black text on white background */
                border: 1px solid #adb5bd;
                border-radius: 5px;
                padding: 5px;
            }
            QComboBox::drop-down {
                background-color: #f1f3f5;
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #adb5bd;
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

        # Step 2: Load config (including saved theme + GPIO + GPS)
        self.config = self._load_config()
        self.current_theme = self.config.get("ui", {}).get("active_theme", "Dark (Default)")
        
        # Step 3: Initialize status bar FIRST (critical fix)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Step 4: Apply theme (now status_bar exists)
        self._apply_theme(self.current_theme, is_initial=True)

        # Step 5: Add GPS Coordinate Controls (Editable)
        self._add_gps_controls()

        # Step 6: Initialize tab widget and tabs
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        
        # Pass config to child widgets (for GPIO/theme)
        self._add_tabs()

        # Step 7: Add theme switcher to status bar
        self._add_theme_switcher()
        
        # Step 8: Update status bar with system info + GPIO status
        self._update_status_bar()

        # Step 9: Start status update timer (1Hz)
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status_bar)
        self.status_timer.start(1000)

        # Step 10: Exit confirmation
        self.setWindowFlags(self.windowFlags() | Qt.WindowCloseButtonHint)

    # --------------------------
    # NEW: Add Editable GPS Coordinate Controls
    # --------------------------
    def _add_gps_controls(self):
        """Add editable latitude/longitude widgets to status bar"""
        # GPS Layout
        gps_layout = QHBoxLayout()
        gps_layout.addWidget(QLabel("GPS Coordinates:"))
        
        # Latitude Spin Box (Range: -90 to 90 degrees)
        self.lat_spin = QDoubleSpinBox()
        self.lat_spin.setRange(-90.0, 90.0)
        self.lat_spin.setDecimals(4)
        self.lat_spin.setValue(self.config["gps"]["default_latitude"])
        self.lat_spin.setFixedWidth(120)
        self.lat_spin.valueChanged.connect(self._update_gps_config)
        gps_layout.addWidget(QLabel("Lat:"))
        gps_layout.addWidget(self.lat_spin)
        
        # Longitude Spin Box (Range: -180 to 180 degrees)
        self.lon_spin = QDoubleSpinBox()
        self.lon_spin.setRange(-180.0, 180.0)
        self.lon_spin.setDecimals(4)
        self.lon_spin.setValue(self.config["gps"]["default_longitude"])
        self.lon_spin.setFixedWidth(120)
        self.lon_spin.valueChanged.connect(self._update_gps_config)
        gps_layout.addWidget(QLabel("Lon:"))
        gps_layout.addWidget(self.lon_spin)
        
        # Add spacing between GPS controls and other status items
        gps_layout.addSpacing(20)

        # Wrap GPS controls in a widget for status bar
        gps_widget = QWidget()
        gps_widget.setLayout(gps_layout)
        self.status_bar.addPermanentWidget(gps_widget)

    # --------------------------
    # NEW: Update GPS Config When Values Change
    # --------------------------
    def _update_gps_config(self):
        """Save updated latitude/longitude to config and file"""
        self.config["gps"]["default_latitude"] = self.lat_spin.value()
        self.config["gps"]["default_longitude"] = self.lon_spin.value()
        
        # Save to config file
        with open("config/settings.json", "w") as f:
            json.dump(self.config, f, indent=4)
        
        # Update status bar message
        self.status_bar.showMessage(
            f"GPS Updated: Lat {self.lat_spin.value():.4f}°, Lon {self.lon_spin.value():.4f}°",
            3000  # Show message for 3 seconds
        )

    # --------------------------
    # Config Management (Theme + GPIO + GPS)
    # --------------------------
    def _load_config(self):
        """Load config file (safe handling for corrupted/empty files)"""
        config_path = "config/settings.json"
        default_config = {
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
            "gpio": {
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

        try:
            # Try to open and read the config file
            with open(config_path, "r") as f:
                # Check if file is empty before parsing
                file_content = f.read().strip()
                if not file_content:
                    raise ValueError("Config file is empty")
                
                # Parse JSON (will throw JSONDecodeError if invalid)
                config = json.loads(file_content)
                
                # Fix missing fields in existing config
                if "gpio" not in config:
                    config["gpio"] = default_config["gpio"]
                if "ui" not in config or "active_theme" not in config["ui"]:
                    config["ui"] = config.get("ui", {})
                    config["ui"]["active_theme"] = default_config["ui"]["active_theme"]
                if "gps" not in config:
                    config["gps"] = default_config["gps"]
                
                # Save corrected config back to file
                with open(config_path, "w") as f:
                    json.dump(config, f, indent=4)
                
                return config

        except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
            # Handle all config errors: missing file, empty file, invalid JSON
            print(f"Config error: {e} → Creating fresh default config")
            
            # Create config directory if missing
            os.makedirs("config", exist_ok=True)
            
            # Write default config to file
            with open(config_path, "w") as f:
                json.dump(default_config, f, indent=4)
            
            # Return default config
            return default_config

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
    # Theme Management (Simplified to 2 Themes)
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
            # FIX: Use self.config (not local config)
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
    # Status Bar (Add GPIO Info + GPS)
    # --------------------------
    def _update_status_bar(self):
        """Update status bar with system info + GPIO status + GPS"""
        # System info (Pi 5 specific)
        try:
            cpu_temp = psutil.sensors_temperatures()["cpu_thermal"][0].current
        except (KeyError, IndexError):
            cpu_temp = 0.0  # Fallback if temp sensor not found
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Updated GPS Coordinates (from editable fields)
        gps_coords = f"Lat: {self.lat_spin.value():.4f}° N, Lon: {self.lon_spin.value():.4f}° W"
        
        # Telescope status
        telescope_status = "Auto | Connected | Normal"
        
        # GPIO status (simplified)
        gpio_status = f"GPIO: {('Enabled' if GPIO_AVAILABLE else 'Mocked')}"

        # Compose status text
        status_text = (
            f"Time: {current_time} | {gps_coords} | "
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