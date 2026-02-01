import ephem
import datetime
from threading import Lock
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QCheckBox, QSpinBox, QGroupBox, QFrame,
    QMessageBox
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer

# Solar tracking thread (optimized for small screen updates)
class SunTrackingThread(QThread):
    position_signal = pyqtSignal(float, float)
    error_signal = pyqtSignal(str)

    def __init__(self, lat, lon):
        super().__init__()
        self.running = True
        self.lock = Lock()
        self.lat = lat
        self.lon = lon
        self.auto_track = False
        self.update_interval = 5  # Seconds (reduced for small screen responsiveness)

    def set_location(self, lat, lon):
        with self.lock:
            self.lat = lat
            self.lon = lon

    def set_auto_track(self, enable):
        with self.lock:
            self.auto_track = enable

    def calculate_sun_position(self):
        try:
            # Calculate sun position
            observer = ephem.Observer()
            observer.lat = str(self.lat)
            observer.lon = str(self.lon)
            observer.date = datetime.datetime.now()
            sun = ephem.Sun(observer)
            
            # Convert to degrees
            alt = float(sun.alt) * 180.0 / ephem.pi
            az = float(sun.az) * 180.0 / ephem.pi
            return max(0.0, alt), az  # Ensure altitude ≥0 (sun above horizon)
        except Exception as e:
            self.error_signal.emit(f"Sun Calculation Error: {str(e)}")
            return 0.0, 0.0

    def run(self):
        while self.running:
            with self.lock:
                auto_track = self.auto_track
                update_interval = self.update_interval

            if auto_track:
                alt, az = self.calculate_sun_position()
                self.position_signal.emit(alt, az)
            
            # Sleep (shorter interval for small screen responsiveness)
            self.msleep(update_interval * 500)  # 0.5x speed for snappier UI

    def stop(self):
        with self.lock:
            self.running = False
        self.wait()

# Main Sun Widget (800×480 optimized)
class SunTrackingWidget(QWidget):
    slew_to_sun = pyqtSignal(float, float)
    lat_lon_updated = pyqtSignal(float, float)
    auto_track_check = pyqtSignal(bool)

    def __init__(self, lat, lon):
        super().__init__()
        self.lat = lat
        self.lon = lon
        self.filter_engaged = False  # Critical safety check

        # Tracking thread
        self.tracking_thread = SunTrackingThread(lat, lon)
        self.tracking_thread.position_signal.connect(self.update_sun_position)
        self.tracking_thread.error_signal.connect(self.show_error)
        
        # UI Setup (compact for 800×480)
        self.init_ui()
        
        # Start tracking thread
        self.tracking_thread.start()

    def init_ui(self):
        layout = QVBoxLayout(self)
        # Small screen spacing
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title (safety warning for sun tracking)
        title = QLabel("Solar Tracking (SAFETY CRITICAL)")
        title.setObjectName("title_label")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #e74c3c;")
        layout.addWidget(title)

        # Safety Warning Frame (prominent for small screen)
        safety_frame = QFrame()
        safety_frame.setStyleSheet("background-color: #ffebee; border-radius: 4px; padding: 8px; border: 1px solid #e74c3c;")
        safety_layout = QVBoxLayout(safety_frame)
        safety_label = QLabel("⚠️ NEVER view the Sun without a certified solar filter! ⚠️")
        safety_label.setStyleSheet("font-size: 11px; color: #e74c3c; font-weight: bold; text-align: center;")
        safety_layout.addWidget(safety_label)
        # Filter Checkbox (MANDATORY for sun tracking)
        self.filter_check = QCheckBox("I confirm a solar filter is installed (REQUIRED)")
        self.filter_check.setStyleSheet("font-size: 11px; color: #e74c3c;")
        self.filter_check.stateChanged.connect(self.toggle_filter)
        safety_layout.addWidget(self.filter_check)
        layout.addWidget(safety_frame)

        # Current Sun Position (compact display)
        pos_frame = QFrame()
        pos_frame.setStyleSheet("background-color: #f8f9fa; border-radius: 4px; padding: 8px;")
        pos_layout = QVBoxLayout(pos_frame)
        self.alt_label = QLabel(f"Sun Altitude: -- °")
        self.az_label = QLabel(f"Sun Azimuth: -- °")
        self.alt_label.setStyleSheet("font-size: 11px; color: #2c3e50; font-weight: bold;")
        self.az_label.setStyleSheet("font-size: 11px; color: #2c3e50; font-weight: bold;")
        pos_layout.addWidget(self.alt_label)
        pos_layout.addWidget(self.az_label)
        layout.addWidget(pos_frame)

        # Location Settings (compact for small screen)
        loc_group = QGroupBox("Location (Lat/Lon)")
        loc_group.setStyleSheet("font-size: 12px;")
        loc_layout = QHBoxLayout(loc_group)
        # Latitude
        lat_layout = QHBoxLayout()
        lat_layout.addWidget(QLabel("Lat:", styleSheet="font-size: 11px;"))
        self.lat_spin = QSpinBox()
        self.lat_spin.setRange(-90, 90)
        self.lat_spin.setValue(int(self.lat))
        self.lat_spin.setStyleSheet("font-size: 11px; padding: 2px;")
        lat_layout.addWidget(self.lat_spin)
        # Longitude
        lon_layout = QHBoxLayout()
        lon_layout.addWidget(QLabel("Lon:", styleSheet="font-size: 11px;"))
        self.lon_spin = QSpinBox()
        self.lon_spin.setRange(-180, 180)
        self.lon_spin.setValue(int(self.lon))
        self.lon_spin.setStyleSheet("font-size: 11px; padding: 2px;")
        lon_layout.addWidget(self.lon_spin)
        # Save Button
        self.save_loc_btn = QPushButton("Save")
        self.save_loc_btn.setStyleSheet("""
            QPushButton { 
                background-color: #3498db; 
                color: white; 
                border: none; 
                border-radius: 4px; 
                padding: 4px 8px; 
                font-size: 11px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        self.save_loc_btn.clicked.connect(self.update_location)
        # Add to layout
        loc_layout.addLayout(lat_layout)
        loc_layout.addLayout(lon_layout)
        loc_layout.addWidget(self.save_loc_btn)
        layout.addWidget(loc_group)

        # Control Buttons (smaller for 800×480)
        btn_layout = QHBoxLayout()
        self.slew_btn = QPushButton("Slew to Sun")
        self.auto_track_btn = QCheckBox("Auto Track Sun")
        # Style buttons
        self.slew_btn.setStyleSheet("""
            QPushButton { 
                background-color: #3498db; 
                color: white; 
                border: none; 
                border-radius: 4px; 
                padding: 6px 8px; 
                font-size: 12px;
            }
            QPushButton:disabled { background-color: #bdc3c7; }
            QPushButton:hover:enabled { background-color: #2980b9; }
        """)
        self.auto_track_btn.setStyleSheet("font-size: 11px;")
        # Connect buttons
        self.slew_btn.clicked.connect(self.slew_to_sun_position)
        self.auto_track_btn.stateChanged.connect(self.toggle_auto_track)
        # Disable buttons by default (filter required)
        self.slew_btn.setEnabled(False)
        self.auto_track_btn.setEnabled(False)
        # Add to layout (FIX: use addLayout instead of addWidget)
        btn_layout.addWidget(self.slew_btn)
        btn_layout.addWidget(self.auto_track_btn)
        layout.addLayout(btn_layout)  # <-- FIXED LINE (was addWidget)

    def toggle_filter(self, state):
        # Enable/disable sun controls only if filter is confirmed
        self.filter_engaged = (state == Qt.Checked)
        self.slew_btn.setEnabled(self.filter_engaged)
        self.auto_track_btn.setEnabled(self.filter_engaged)
        # Safety warning if filter is unchecked
        if not self.filter_engaged and self.auto_track_btn.isChecked():
            self.auto_track_btn.setChecked(False)
            QMessageBox.warning(self, "Solar Safety", "Auto tracking disabled - solar filter required!")

    def update_sun_position(self, alt, az):
        self.alt_label.setText(f"Sun Altitude: {alt:.1f} °")
        self.az_label.setText(f"Sun Azimuth: {az:.1f} °")
        # Emit position for motor control
        self.slew_to_sun.emit(alt, az)

    def slew_to_sun_position(self):
        if not self.filter_engaged:
            QMessageBox.critical(self, "Solar Safety", "Solar filter confirmation required!")
            return
        # Calculate current sun position
        alt, az = self.tracking_thread.calculate_sun_position()
        self.update_sun_position(alt, az)
        QMessageBox.information(self, "Slew to Sun", f"Moving to Sun position:\nAlt: {alt:.1f}° | Az: {az:.1f}°")

    def toggle_auto_track(self, state):
        enable = (state == Qt.Checked)
        self.tracking_thread.set_auto_track(enable)
        self.auto_track_check.emit(enable)
        # Status update
        status = "Enabled" if enable else "Disabled"
        QMessageBox.information(self, "Auto Track", f"Sun auto-tracking {status} (filter confirmed)")

    def update_location(self):
        self.lat = self.lat_spin.value()
        self.lon = self.lon_spin.value()
        self.tracking_thread.set_location(self.lat, self.lon)
        self.lat_lon_updated.emit(self.lat, self.lon)
        QMessageBox.information(self, "Location Updated", f"New location:\nLat: {self.lat}° | Lon: {self.lon}°")

    def show_error(self, error_msg):
        QMessageBox.critical(self, "Sun Tracking Error", error_msg)

    def close(self):
        self.tracking_thread.stop()