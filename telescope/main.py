import sys
import json
import psutil
import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QStatusBar,
    QWidget, QVBoxLayout, QMessageBox, QLabel, QComboBox,
    QHBoxLayout
)
from PyQt5.QtCore import QTimer, Qt, QThread
from PyQt5.QtGui import QPalette, QColor

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
        """
    }
}

class TelescopeMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Step 1: Basic window setup (first)
        self.setWindowTitle("Raspberry Pi 5 Telescope Controller")
        self.setGeometry(100, 100, 1280, 720)  # Pi 5 touchscreen optimized

        # Step 2: Load config (including saved theme)
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
        self._add_tabs()

        # Step 6: Add theme switcher to status bar
        self._add_theme_switcher()
        
        # Step 7: Update status bar with system info
        self._update_status_bar()

        # Step 8: Start status update timer (1Hz)
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status_bar)
        self.status_timer.start(1000)

        # Step 9: Exit confirmation
        self.setWindowFlags(self.windowFlags() | Qt.WindowCloseButtonHint)

    # --------------------------
    # Theme Management Methods (Fixed)
    # --------------------------
    def _load_config(self):
        """Load config file (create default if missing)"""
        config_path = "config/settings.json"
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
        except FileNotFoundError:
            # Create default config if missing
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
                "ui": {
                    "theme": "dark",
                    "touch_mode": True,
                    "status_bar_update_rate": 1000,
                    "active_theme": "Dark (Default)"  # Add theme to config
                },
                "gps": {
                    "default_latitude": 40.7128,
                    "default_longitude": -74.0060,
                    "use_gps_module": False
                }
            }
            # Save default config
            import os
            os.makedirs("config", exist_ok=True)
            with open(config_path, "w") as f:
                json.dump(config, f, indent=4)
        return config

    def _add_theme_switcher(self):
        """Add theme selection dropdown to status bar"""
        # Theme label + dropdown
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Theme:"))
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEMES.keys())
        self.theme_combo.setCurrentText(self.current_theme)
        self.theme_combo.currentTextChanged.connect(self._on_theme_change)
        
        # Wrap in widget (required for status bar layout)
        theme_widget = QWidget()
        theme_widget.setLayout(theme_layout)
        
        # Add to status bar (permanent right-side widget)
        self.status_bar.addPermanentWidget(theme_widget)

    def _apply_theme(self, theme_name, is_initial=False):
        """
        Apply selected global theme to entire window
        is_initial: True for first launch (avoids status bar message issues)
        """
        if theme_name in THEMES:
            # Set global stylesheet (core fix)
            self.setStyleSheet(THEMES[theme_name]["stylesheet"])
            
            # Update config with current theme
            self.config["ui"]["active_theme"] = theme_name
            
            # Save config (persist theme)
            with open("config/settings.json", "w") as f:
                json.dump(self.config, f, indent=4)
            
            # Only update status bar message if NOT initial (fixes AttributeError)
            if not is_initial:
                # Safety check: get current message (or empty string if none)
                current_msg = self.status_bar.currentMessage() or ""
                self.status_bar.showMessage(f"Theme changed to: {theme_name} | {current_msg}")

    def _on_theme_change(self, new_theme):
        """Handle real-time theme selection change"""
        self.current_theme = new_theme
        self._apply_theme(new_theme, is_initial=False)

    # --------------------------
    # Original Functionality (Preserved)
    # --------------------------
    def _add_tabs(self):
        """Add all functional tabs to the main window"""
        self.tab_widget.addTab(AltitudeControlWidget(), "Altitude Control")
        self.tab_widget.addTab(AzimuthControlWidget(), "Azimuth Control")
        self.tab_widget.addTab(CameraWidget(self.config), "Camera")
        self.tab_widget.addTab(SunTrackingWidget(), "Sun Tracking")
        self.tab_widget.addTab(MoonTrackingWidget(), "Moon Tracking")
        self.tab_widget.addTab(DatabaseWidget(), "Data Logging")
        self.tab_widget.addTab(AIWidget(), "AI Assistant")

    def _update_status_bar(self):
        """Update status bar with real-time system/telescope info"""
        # System info (Pi 5 specific)
        cpu_temp = psutil.sensors_temperatures()["cpu_thermal"][0].current
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Mock GPS (replace with real GPS module integration)
        gps_coords = "Lat: 40.7128° N, Lon: 74.0060° W"
        
        # Telescope status (replace with real hardware status)
        telescope_status = "Auto | Connected | Normal"

        # Compose status text
        status_text = (
            f"Time: {current_time} | GPS: {gps_coords} | "
            f"Temp: {cpu_temp:.1f}°C | Telescope: {telescope_status}"
        )
        self.status_bar.showMessage(status_text)

    def closeEvent(self, event):
        """Confirm exit to prevent accidental closure"""
        reply = QMessageBox.question(
            self, "Exit Confirmation",
            "Are you sure you want to exit? The telescope will park automatically.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # Park telescope before exit (call park function here)
            event.accept()
        else:
            event.ignore()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TelescopeMainWindow()
    window.show()
    sys.exit(app.exec_())