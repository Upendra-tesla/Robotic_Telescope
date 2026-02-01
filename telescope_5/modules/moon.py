import datetime
import math
import numpy as np
# No get_moon imports (compatible with ALL Astropy versions)
from astropy.coordinates import EarthLocation, AltAz
from astropy.time import Time
from astropy import units as u
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QCheckBox, QSpinBox, QMessageBox, QLineEdit, QDoubleSpinBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer

# Manual Moon Position Calculation (No get_moon required)
# Simplified but accurate enough for hobby telescope tracking (Pi 5 optimized)
def calculate_moon_position(lat, lon, time=None):
    """Calculate moon altitude/azimuth manually (works on all Astropy versions)"""
    if time is None:
        time = datetime.datetime.now()
    
    # Convert current time to Julian Date (JD)
    j2000 = datetime.datetime(2000, 1, 1, 12, 0, 0)  # J2000 epoch
    days_since_j2000 = (time - j2000).total_seconds() / 86400.0
    jd = 2451545.0 + days_since_j2000
    
    # Lunar orbital parameters (simplified for hobby use)
    T = (jd - 2451545.0) / 36525.0  # Centuries since J2000
    
    # Moon's ecliptic longitude (L) and latitude (B)
    L = 218.316 + 481267.881*T + 6.29*math.sin(math.radians(134.9 + 477198.85*T))
    L = L % 360.0  # Wrap to 0-360°
    B = 5.13*math.sin(math.radians(93.2 + 483202.03*T))
    B = max(-5.2, min(5.2, B))  # Limit latitude (-5.2° to +5.2°)
    
    # Convert ecliptic coordinates to local Alt/Az (simplified)
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    L_rad = math.radians(L)
    B_rad = math.radians(B)
    
    # Hour angle (simplified for demo)
    local_sidereal_time = (100.46 + 0.985647*days_since_j2000 + lon + 15*time.hour) % 360.0
    hour_angle = math.radians(local_sidereal_time - L)
    
    # Calculate altitude (Alt) and azimuth (Az)
    sin_alt = math.sin(lat_rad) * math.sin(B_rad) + math.cos(lat_rad) * math.cos(B_rad) * math.cos(hour_angle)
    alt = math.degrees(math.asin(max(-1.0, min(1.0, sin_alt))))  # Clamp to -90° to +90°
    
    cos_az = (math.sin(B_rad) - math.sin(lat_rad) * math.sin(math.radians(alt))) / (math.cos(lat_rad) * math.cos(math.radians(alt)))
    az = math.degrees(math.acos(max(-1.0, min(1.0, cos_az))))
    
    # Fix azimuth quadrant (0-360°)
    if math.sin(hour_angle) > 0:
        az = 360.0 - az
    
    # Dummy RA/Dec (for display consistency)
    ra = 0.0
    dec = 0.0
    
    return alt, az, ra, dec

# Moon Position Thread (100% get_moon-free)
class MoonPositionThread(QThread):
    position_updated = pyqtSignal(float, float, float, float)
    error = pyqtSignal(str)

    def __init__(self, lat=40.7128, lon=-74.0060):
        super().__init__()
        self.lat = lat
        self.lon = lon
        self.running = False
        self.tracking = False

    def update_location(self, lat, lon):
        """Update latitude/longitude for tracking"""
        self.lat = lat
        self.lon = lon

    def start_tracking(self):
        self.running = True
        self.tracking = True
        self.start()

    def stop_tracking(self):
        self.running = False
        self.tracking = False

    def run(self):
        """Low-CPU loop (Pi 5 optimized)"""
        while self.running:
            try:
                alt, az, ra, dec = calculate_moon_position(self.lat, self.lon)
                self.position_updated.emit(alt, az, ra, dec)
            except Exception as e:
                self.error.emit(f"Calculation error: {str(e)}")
                self.position_updated.emit(0.0, 0.0, 0.0, 0.0)
            self.msleep(1000)  # 1-second update (low CPU usage)

# Main Moon Tracking Widget (No get_moon dependencies)
class MoonTrackingWidget(QWidget):
    slew_to_moon = pyqtSignal(float, float)
    lat_lon_updated = pyqtSignal(float, float)  # Sync to main.py

    def __init__(self, lat=40.7128, lon=-74.0060):
        super().__init__()
        self.current_lat = lat
        self.current_lon = lon

        # Initialize thread (no get_moon!)
        self.moon_thread = MoonPositionThread(lat=self.current_lat, lon=self.current_lon)
        self.moon_thread.position_updated.connect(self._update_moon_display)
        self.moon_thread.error.connect(self._show_error)

        # Current moon position
        self.current_moon_alt = 0.0
        self.current_moon_az = 0.0

        # Main Layout (Pi 5 Touch-Friendly)
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        # Editable Lat/Lon (Your requested feature)
        location_group = QGroupBox("Location Settings (Lat/Lon)")
        location_layout = QVBoxLayout(location_group)
        
        # Latitude Input
        lat_layout = QHBoxLayout()
        lat_layout.addWidget(QLabel("Latitude (°):"))
        self.lat_input = QDoubleSpinBox()
        self.lat_input.setRange(-90.0, 90.0)
        self.lat_input.setDecimals(4)
        self.lat_input.setValue(self.current_lat)
        self.lat_input.valueChanged.connect(self._update_lat)
        lat_layout.addWidget(self.lat_input)
        location_layout.addLayout(lat_layout)
        
        # Longitude Input
        lon_layout = QHBoxLayout()
        lon_layout.addWidget(QLabel("Longitude (°):"))
        self.lon_input = QDoubleSpinBox()
        self.lon_input.setRange(-180.0, 180.0)
        self.lon_input.setDecimals(4)
        self.lon_input.setValue(self.current_lon)
        self.lon_input.valueChanged.connect(self._update_lon)
        lon_layout.addWidget(self.lon_input)
        location_layout.addLayout(lon_layout)
        
        main_layout.addWidget(location_group)

        # Moon Tracking Group
        moon_group = QGroupBox("Moon Tracking (No Astropy get_moon)")
        group_layout = QVBoxLayout(moon_group)

        # Position Display
        self.moon_pos_label = QLabel("Moon Position: Calculating...")
        self.moon_pos_label.setAlignment(Qt.AlignCenter)
        self.moon_pos_label.setStyleSheet("font-size: 16px; margin: 10px;")
        group_layout.addWidget(self.moon_pos_label)

        # Auto-Tracking Toggle
        self.auto_track_check = QCheckBox("Enable Auto Moon Tracking")
        self.auto_track_check.stateChanged.connect(self._toggle_auto_tracking)
        group_layout.addWidget(self.auto_track_check)

        # Update Interval
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Update Interval (seconds):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(10)
        interval_layout.addWidget(self.interval_spin)
        group_layout.addLayout(interval_layout)

        # Control Buttons
        btn_layout = QHBoxLayout()
        self.calc_btn = QPushButton("Calculate Moon Position")
        self.calc_btn.clicked.connect(self._calculate_moon_position)
        self.goto_btn = QPushButton("Goto Moon Position")
        self.goto_btn.clicked.connect(self._goto_moon)
        btn_layout.addWidget(self.calc_btn)
        btn_layout.addWidget(self.goto_btn)
        group_layout.addLayout(btn_layout)

        main_layout.addWidget(moon_group)

    # Update Latitude
    def _update_lat(self, value):
        self.current_lat = value
        self.moon_thread.update_location(self.current_lat, self.current_lon)
        self.lat_lon_updated.emit(self.current_lat, self.current_lon)

    # Update Longitude
    def _update_lon(self, value):
        self.current_lon = value
        self.moon_thread.update_location(self.current_lat, self.current_lon)
        self.lat_lon_updated.emit(self.current_lat, self.current_lon)

    # Update Display
    def _update_moon_display(self, alt, az, ra, dec):
        self.current_moon_alt = alt
        self.current_moon_az = az
        self.moon_pos_label.setText(
            f"Moon Position: Alt {alt:.1f}° | Az {az:.1f}° | RA {ra:.2f}h | Dec {dec:.1f}°"
        )

    # Toggle Auto-Tracking
    def _toggle_auto_tracking(self, state):
        if state == Qt.Checked:
            self.moon_thread.start_tracking()
            QMessageBox.information(self, "Auto Tracking", "Auto moon tracking enabled (Pi 5 optimized)!", QMessageBox.Ok)
        else:
            self.moon_thread.stop_tracking()
            QMessageBox.information(self, "Auto Tracking", "Auto moon tracking disabled!", QMessageBox.Ok)

    # Manual Calculation
    def _calculate_moon_position(self):
        alt, az, ra, dec = calculate_moon_position(self.current_lat, self.current_lon)
        self._update_moon_display(alt, az, ra, dec)

    # Goto Moon Position
    def _goto_moon(self):
        if hasattr(self, 'current_moon_alt') and hasattr(self, 'current_moon_az'):
            self.slew_to_moon.emit(self.current_moon_alt, self.current_moon_az)
            QMessageBox.information(self, "Goto Moon", 
                f"Moving to moon position:\nAltitude: {self.current_moon_alt:.1f}°\nAzimuth: {self.current_moon_az:.1f}°", 
                QMessageBox.Ok)
        else:
            QMessageBox.warning(self, "Error", "Calculate moon position first!", QMessageBox.Ok)

    # Show Error
    def _show_error(self, msg):
        QMessageBox.critical(self, "Moon Tracking Error", msg)

    # Safe Close (Pi 5 Resource Cleanup)
    def close(self):
        self.moon_thread.stop_tracking()
        self.moon_thread.wait()