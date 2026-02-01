import sys
import datetime
import json
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget,
    QVBoxLayout, QHBoxLayout, QStatusBar, QMessageBox,
    QToolBar, QAction, QMenu, QMenuBar, QSplitter,
    QLabel, QPushButton, QFrame
)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon, QKeySequence

# Import custom modules
from modules.altitude import AltitudeControlWidget
from modules.azimuth import AzimuthControlWidget
from modules.sensor import SensorWidget
from modules.webcam import WebcamWidget
from modules.database import DatabaseWidget
from modules.sun import SunWidget
from modules.moon import MoonWidget
from modules.deepseek import DeepSeekWidget
from modules import SETTINGS, cleanup_gpio, get_responsive_stylesheet, get_pin_display_name

class TelescopeMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Window Configuration - FIXED 800x480 for Raspberry Pi touchscreen
        self.setWindowTitle("Robotic Telescope Control System - Raspberry Pi")
        self.setFixedSize(800, 480)  # Fixed size per requirement
        
        # Apply stylesheet optimized for 800x480
        self.setStyleSheet(get_responsive_stylesheet())
        
        # Set application icon
        self.setWindowIcon(QIcon.fromTheme("camera"))
        
        # Initialize UI
        self.init_ui()
        
        # Setup update timers
        self.setup_timers()
        
        # Log startup
        self.status_bar.showMessage("System initialized successfully", 5000)

    def init_ui(self):
        """Initialize the user interface (optimized for 800x480)"""
        # Central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(3, 3, 3, 3)
        self.main_layout.setSpacing(3)

        # Create menu bar (compact version)
        self.create_menu_bar()

        # Create compact toolbar
        self.create_toolbar()

        # Create tab widget (optimized for small screen)
        self.tab_widget = QTabWidget()
        self.tab_widget.setFont(QFont("Arial", 8))
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #444444;
                background-color: #2b2b2b;
            }
            QTabBar::tab {
                background-color: #333333;
                color: #cccccc;
                padding: 4px 8px;
                margin-right: 1px;
                min-width: 50px;
                min-height: 18px;
                font-size: 8px;
            }
            QTabBar::tab:selected {
                background-color: #2b2b2b;
                color: #ffffff;
                border-bottom: 2px solid #00a8ff;
            }
            QTabBar::tab:hover {
                background-color: #3a3a3a;
            }
        """)
        
        self.main_layout.addWidget(self.tab_widget, stretch=1)

        # Create tabs in specified order (compact layout)
        self.create_tabs()

        # Create status bar (compact)
        self.create_status_bar()

        # Create bottom control panel (compact)
        self.create_control_panel()

    def create_menu_bar(self):
        """Create compact application menu bar"""
        menubar = self.menuBar()
        menubar.setMaximumHeight(25)
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_settings)
        file_menu.addAction(save_action)
        
        load_action = QAction("Load", self)
        load_action.setShortcut("Ctrl+L")
        load_action.triggered.connect(self.load_settings)
        file_menu.addAction(load_action)
        
        file_menu.addSeparator()
        
        export_action = QAction("Export", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self.export_data)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Tools menu
        tools_menu = menubar.addMenu("Tools")
        
        calibrate_action = QAction("Calibrate", self)
        calibrate_action.triggered.connect(self.calibrate_all)
        tools_menu.addAction(calibrate_action)
        
        emergency_action = QAction("Emergency Stop", self)
        emergency_action.setShortcut("Ctrl+Shift+E")
        emergency_action.triggered.connect(self.emergency_stop)
        tools_menu.addAction(emergency_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_toolbar(self):
        """Create compact toolbar with quick actions"""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setMaximumHeight(30)
        self.addToolBar(toolbar)
        
        # Emergency stop button (compact)
        emergency_btn = QPushButton("🛑 STOP")
        emergency_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff4444;
                color: white;
                font-weight: bold;
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 8px;
                min-height: 20px;
            }
        """)
        emergency_btn.clicked.connect(self.emergency_stop)
        toolbar.addWidget(emergency_btn)
        
        toolbar.addSeparator()
        
        # Save button
        save_btn = QPushButton("💾 Save")
        save_btn.setToolTip("Save settings")
        save_btn.setStyleSheet("font-size: 8px; min-height: 20px;")
        save_btn.clicked.connect(self.save_settings)
        toolbar.addWidget(save_btn)
        
        # Status indicator
        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet("color: #00ff00; font-size: 16px; padding: 2px;")
        self.status_indicator.setToolTip("System Status: Online")
        toolbar.addWidget(self.status_indicator)

    def create_tabs(self):
        """Create all application tabs (compact layout)"""
        tab_order = SETTINGS["ui"]["tab_order"]
        
        for tab_name in tab_order:
            if tab_name == "control":
                self.create_control_tab()
            elif tab_name == "sensors":
                self.create_sensor_tab()
            elif tab_name == "camera":
                self.create_camera_tab()
            elif tab_name == "sun":
                self.create_sun_tab()
            elif tab_name == "moon":
                self.create_moon_tab()
            elif tab_name == "database":
                self.create_database_tab()
            elif tab_name == "ai":
                self.create_ai_tab()

    def create_control_tab(self):
        """Create control tab with altitude and azimuth (compact)"""
        control_tab = QWidget()
        control_layout = QHBoxLayout(control_tab)
        control_layout.setSpacing(3)
        control_layout.setContentsMargins(3, 3, 3, 3)
        
        # Altitude Control (compact)
        self.altitude_widget = AltitudeControlWidget()
        control_layout.addWidget(self.altitude_widget, 50)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #555555;")
        control_layout.addWidget(separator)
        
        # Azimuth Control (compact)
        self.azimuth_widget = AzimuthControlWidget()
        control_layout.addWidget(self.azimuth_widget, 50)
        
        self.tab_widget.addTab(control_tab, "🏗️ Control")

    def create_sensor_tab(self):
        """Create sensor tab (compact)"""
        self.sensor_widget = SensorWidget()
        self.tab_widget.addTab(self.sensor_widget, "📡 Sensors")

    def create_camera_tab(self):
        """Create camera tab (compact)"""
        self.camera_widget = WebcamWidget()
        self.tab_widget.addTab(self.camera_widget, "📷 Camera")

    def create_sun_tab(self):
        """Create sun tracking tab (compact)"""
        self.sun_widget = SunWidget()
        self.tab_widget.addTab(self.sun_widget, "☀️ Sun")

    def create_moon_tab(self):
        """Create moon tracking tab (compact)"""
        self.moon_widget = MoonWidget()
        self.tab_widget.addTab(self.moon_widget, "🌙 Moon")

    def create_database_tab(self):
        """Create database tab (compact)"""
        self.database_widget = DatabaseWidget()
        self.tab_widget.addTab(self.database_widget, "💾 Database")

    def create_ai_tab(self):
        """Create AI assistant tab (compact)"""
        self.ai_widget = DeepSeekWidget()
        self.tab_widget.addTab(self.ai_widget, "🤖 AI")

    def create_status_bar(self):
        """Create compact status bar"""
        self.status_bar = QStatusBar()
        self.status_bar.setMaximumHeight(20)
        self.setStatusBar(self.status_bar)
        
        # Add compact status widgets
        self.gpio_status = QLabel("GPIO: ✓")
        self.gpio_status.setStyleSheet("color: #00ff00; padding: 1px 5px; font-size: 8px;")
        self.status_bar.addPermanentWidget(self.gpio_status)
        
        self.camera_status = QLabel("Camera: ✗")
        self.camera_status.setStyleSheet("color: #ff4444; padding: 1px 5px; font-size: 8px;")
        self.status_bar.addPermanentWidget(self.camera_status)
        
        self.ai_status = QLabel(f"AI: {SETTINGS['ai']['mode'].upper()}")
        self.ai_status.setStyleSheet("color: #00a8ff; padding: 1px 5px; font-size: 8px;")
        self.status_bar.addPermanentWidget(self.ai_status)
        
        self.position_status = QLabel("Pos: 0.0°/0.0°")
        self.position_status.setStyleSheet("color: #ffaa00; padding: 1px 5px; font-size: 8px;")
        self.status_bar.addPermanentWidget(self.position_status)
        
        # Initial status message
        self.status_bar.showMessage("System ready", 5000)

    def create_control_panel(self):
        """Create compact bottom control panel"""
        control_panel = QFrame()
        control_panel.setMaximumHeight(35)
        control_panel.setStyleSheet("""
            QFrame {
                background-color: #333333;
                border-top: 1px solid #444444;
                padding: 2px;
            }
        """)
        
        panel_layout = QHBoxLayout(control_panel)
        panel_layout.setSpacing(2)
        
        # Compact quick actions
        quick_actions = [
            ("🌙 Moon", self.point_to_moon),
            ("☀️ Sun", self.track_sun),
            ("🎯 Calibrate", self.calibrate_all),
            ("📸 Capture", self.capture_image),
            ("📊 Log", self.toggle_logging)
        ]
        
        for text, callback in quick_actions:
            btn = QPushButton(text)
            btn.setMaximumHeight(28)
            btn.setStyleSheet("font-size: 8px; padding: 2px 4px;")
            btn.clicked.connect(callback)
            panel_layout.addWidget(btn)
        
        self.main_layout.addWidget(control_panel)

    def setup_timers(self):
        """Setup update timers"""
        # Position update timer
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self.update_position_status)
        self.position_timer.start(1000)  # Update every second
        
        # System status timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_system_status)
        self.status_timer.start(5000)  # Update every 5 seconds
        
        # Auto-save timer
        self.autosave_timer = QTimer()
        self.autosave_timer.timeout.connect(self.auto_save)
        self.autosave_timer.start(30000)  # Auto-save every 30 seconds

    def update_position_status(self):
        """Update position status in status bar"""
        try:
            alt = self.altitude_widget.altitude_thread.current_altitude
            az = self.azimuth_widget.azimuth_thread.current_azimuth
            self.position_status.setText(f"Pos: {alt:.1f}/{az:.1f}°")
        except:
            pass

    def update_system_status(self):
        """Update system status indicators"""
        # Update camera status
        if hasattr(self.camera_widget, 'camera_thread') and self.camera_widget.camera_thread.running:
            self.camera_status.setText("Cam: ✓")
            self.camera_status.setStyleSheet("color: #00ff00; padding: 1px 5px; font-size: 8px;")
        else:
            self.camera_status.setText("Cam: ✗")
            self.camera_status.setStyleSheet("color: #ff4444; padding: 1px 5px; font-size: 8px;")
        
        # Update AI status
        mode = SETTINGS["ai"]["mode"]
        if mode == "cloud":
            self.ai_status.setText("AI: Cloud")
            self.ai_status.setStyleSheet("color: #00a8ff; padding: 1px 5px; font-size: 8px;")
        else:
            self.ai_status.setText("AI: Local")
            self.ai_status.setStyleSheet("color: #00ff00; padding: 1px 5px; font-size: 8px;")
        
               # Update GPIO status
        try:
            import gpiozero
            self.gpio_status.setText("GPIO: ✓")
            self.gpio_status.setStyleSheet("color: #00ff00; padding: 1px 5px; font-size: 8px;")
        except:
            self.gpio_status.setText("GPIO: ✗")
            self.gpio_status.setStyleSheet("color: #ff4444; padding: 1px 5px; font-size: 8px;")

    def save_settings(self):
        """Save current settings to file"""
        try:
            settings_path = Path(__file__).parent / "settings.json"
            with open(settings_path, "w") as f:
                json.dump(SETTINGS, f, indent=2)
            self.status_bar.showMessage("Settings saved", 3000)
            self.status_indicator.setStyleSheet("color: #00ff00; font-size: 16px; padding: 2px;")
        except Exception as e:
            self.status_bar.showMessage(f"Save failed: {str(e)}", 5000)
            self.status_indicator.setStyleSheet("color: #ff4444; font-size: 16px; padding: 2px;")

    def load_settings(self):
        """Load settings from file"""
        try:
            from modules import load_settings
            global SETTINGS
            SETTINGS = load_settings()
            self.status_bar.showMessage("Settings loaded", 3000)
        except Exception as e:
            self.status_bar.showMessage(f"Load failed: {str(e)}", 5000)

    def auto_save(self):
        """Auto-save settings and data"""
        if SETTINGS["database"]["auto_save"]:
            self.save_settings()
            self.status_bar.showMessage("Auto-saved", 2000)

    def export_data(self):
        """Export data from database"""
        if hasattr(self.database_widget, 'logging_thread'):
            self.database_widget.logging_thread.export_log("csv")
            self.status_bar.showMessage("Data exported", 3000)

    def toggle_fullscreen(self):
        """Toggle fullscreen mode (optimized for touchscreen)"""
        if self.isFullScreen():
            self.showNormal()
            self.setFixedSize(800, 480)
        else:
            self.showFullScreen()

    def change_theme(self, theme):
        """Change application theme"""
        SETTINGS["ui"]["theme"] = theme
        self.setStyleSheet(get_responsive_stylesheet())
        self.status_bar.showMessage(f"Theme: {theme}", 3000)

    def calibrate_all(self):
        """Calibrate all sensors and motors"""
        # Reset altitude/azimuth to zero
        if hasattr(self.altitude_widget, 'altitude_thread'):
            self.altitude_widget.altitude_thread.set_altitude(0)
        
        if hasattr(self.azimuth_widget, 'azimuth_thread'):
            self.azimuth_widget.azimuth_thread.set_azimuth(0)
        
        # Calibrate compass sensor
        if hasattr(self.sensor_widget, 'sensor_thread'):
            self.sensor_widget.sensor_thread.calibrate()
        
        self.status_bar.showMessage("Calibration started", 3000)

    def emergency_stop(self):
        """Emergency stop all operations"""
        reply = QMessageBox.critical(
            self, "Emergency Stop",
            "Stop all operations?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Stop all motors
            if hasattr(self.altitude_widget, 'altitude_thread'):
                self.altitude_widget.altitude_thread.stop_motors()
            
            if hasattr(self.azimuth_widget, 'azimuth_thread'):
                self.azimuth_widget.azimuth_thread.stop_motors()
            
            # Stop camera recording
            if hasattr(self.camera_widget, 'camera_thread'):
                self.camera_widget.camera_thread.stop_recording()
            
            # Update status indicators
            self.status_indicator.setStyleSheet("color: #ff4444; font-size: 16px; padding: 2px;")
            self.status_bar.showMessage("EMERGENCY STOPPED", 5000)

    def point_to_moon(self):
        """Point telescope to moon"""
        self.tab_widget.setCurrentIndex(self.tab_widget.indexOf(self.moon_widget))
        if hasattr(self.moon_widget, 'point_to_moon'):
            self.moon_widget.point_to_moon()

    def track_sun(self):
        """Start tracking sun"""
        self.tab_widget.setCurrentIndex(self.tab_widget.indexOf(self.sun_widget))
        if hasattr(self.sun_widget, 'sun_thread'):
            self.sun_widget.sun_thread.start_tracking()

    def capture_image(self):
        """Capture image from camera"""
        if hasattr(self.camera_widget, 'capture_image'):
            self.camera_widget.capture_image()

    def toggle_logging(self):
        """Toggle data logging"""
        if hasattr(self.database_widget, 'logging_thread'):
            if self.database_widget.logging_thread.logging:
                self.database_widget.logging_thread.stop_logging()
                self.status_bar.showMessage("Logging stopped", 3000)
            else:
                self.database_widget.logging_thread.start_logging()
                self.status_bar.showMessage("Logging started", 3000)

    def open_settings(self):
        """Open settings dialog (compact version)"""
        QMessageBox.information(
            self, "Settings",
            f"Location: {SETTINGS['location']['latitude']:.4f}, {SETTINGS['location']['longitude']:.4f}\n"
            f"AI Mode: {SETTINGS['ai']['mode']}\n"
            f"Log Limit: {SETTINGS['database']['log_limit']}"
        )

    def show_about(self):
        """Show about dialog (compact)"""
        QMessageBox.about(
            self, "About",
            "Robotic Telescope Control\nv2.0.0\nRaspberry Pi 5 Optimized\n800x480 Touchscreen Ready"
        )

    def show_documentation(self):
        """Show documentation shortcut"""
        QMessageBox.information(
            self, "Help",
            "Shortcuts:\nCtrl+S: Save\nCtrl+Q: Exit\nF11: Fullscreen\nCtrl+Shift+E: Emergency Stop"
        )

    def cleanup_resources(self):
        """Cleanup all resources before exit"""
        self.status_bar.showMessage("Cleaning up...")
        
        # Stop timers
        self.position_timer.stop()
        self.status_timer.stop()
        self.autosave_timer.stop()
        
        # Cleanup all widgets
        widgets = [
            self.altitude_widget,
            self.azimuth_widget,
            self.sensor_widget,
            self.camera_widget,
            self.database_widget,
            self.sun_widget,
            self.moon_widget,
            self.ai_widget
        ]
        
        for widget in widgets:
            if hasattr(widget, 'cleanup'):
                widget.cleanup()
        
        # Cleanup GPIO pins
        cleanup_gpio()
        
        self.status_bar.showMessage("Ready to exit", 2000)

    def closeEvent(self, event):
        """Handle application exit confirmation"""
        reply = QMessageBox.question(
            self,
            "Exit",
            "Exit application?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.cleanup_resources()
            event.accept()
        else:
            event.ignore()

def main():
    """Main application entry point (optimized for Raspberry Pi 5)"""
    # Enable high DPI scaling for small screens
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # Create application instance
    app = QApplication(sys.argv)
    app.setApplicationName("TelescopeControl")
    app.setApplicationVersion("2.0.0")
    app.setStyle("Fusion")
    
    # Set dark palette optimized for 800x480 displays
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(43, 43, 43))
    palette.setColor(QPalette.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.Base, QColor(33, 33, 33))
    palette.setColor(QPalette.AlternateBase, QColor(43, 43, 43))
    palette.setColor(QPalette.Text, QColor(255, 255, 255))
    palette.setColor(QPalette.Button, QColor(43, 43, 43))
    palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
    palette.setColor(QPalette.Highlight, QColor(0, 168, 255))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)
    
    # Create and show main window (fixed 800x480 size)
    window = TelescopeMainWindow()
    window.show()
    
    # Run application
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()