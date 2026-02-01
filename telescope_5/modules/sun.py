import datetime
import math
import numpy as np
# No fragile get_sun imports (compatible with ALL Astropy versions)
from astropy.coordinates import EarthLocation, AltAz
from astropy.time import Time
from astropy import units as u
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QCheckBox, QSpinBox, QMessageBox, QLineEdit, QDoubleSpinBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer

# Manual Sun Position Calculation (No get_sun required - Pi 5 optimized)
def calculate_sun_position(lat, lon, time=None):
    """Calculate sun altitude/azimuth manually (works on all Astropy versions)"""
    if time is None:
        time = datetime.datetime.now()
    
    # Convert to Julian Date (J2000 epoch)
    j2000 = datetime.datetime(2000, 1, 1, 12, 0, 0)
    days_since_j2000 = (time - j2000).total_seconds() / 86400.0
    
    # Solar orbital parameters (simplified for hobby use)
    T = days_since_j2000 / 36525.0
    L = 280.466 + 36000.7698*T  # Mean longitude
    L = L % 360.0
    g = 357.529 + 35999.050*T  # Mean anomaly
    g = math.radians(g % 360.0)
    
    # True longitude (corrected for eccentricity)
    lambda_sun = L + 1.915*math.sin(g) + 0.020*math.sin(2*g)
    lambda_sun = math.radians(lambda_sun % 360.0)
    
    # Declination (Dec)
    dec = math.degrees(math.asin(math.sin(lambda_sun) * math.sin(math.radians(23.44))))  # Obliquity of ecliptic
    
    # Local Sidereal Time (LST)
    lst = (100.46 + 0.985647*days_since_j2000 + lon + 15*time.hour) % 360.0
    
    # Hour Angle (HA)
    ha = lst - math.degrees(lambda_sun)
    ha = math.radians(ha % 360.0)
    
    # Altitude (Alt)
    lat_rad = math.radians(lat)
    sin_alt = math.sin(lat_rad) * math.sin(math.radians(dec)) + math.cos(lat_rad) * math.cos(math.radians(dec)) * math.cos(ha)
    alt = math.degrees(math.asin(max(-1.0, min(1.0, sin_alt))))  # Clamp to -90° to +90°
    
    # Azimuth (Az)
    cos_az = (math.sin(math.radians(dec)) - math.sin(lat_rad) * math.sin(math.radians(alt))) / (math.cos(lat_rad) * math.cos(math.radians(alt)))
    az = math.degrees(math.acos(max(-1.0, min(1.0, cos_az))))
    
    # Fix azimuth quadrant (0-360°)
    if math.sin(ha) > 0:
        az = 360.0 - az
    
    # Dummy RA/Dec (for display consistency)
    ra = 0.0
    dec_deg = dec
    
    return alt, az, ra, dec_deg

# Sun Position Thread (Lat/Lon Support + No Import Errors)
class SunPositionThread(QThread):
    position_updated = pyqtSignal(float, float, float, float)
    error = pyqtSignal(str)

    def __init__(self, lat=40.7128, lon=-74.0060):
        super().__init__()
        self.lat = lat  # Accept lat parameter (fixes TypeError)
        self.lon = lon  # Accept lon parameter (fixes TypeError)
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
        """Low-CPU loop (Pi 5 optimized - 1-second updates)"""
        while self.running:
            try:
                alt, az, ra, dec = calculate_sun_position(self.lat, self.lon)
                self.position_updated.emit(alt, az, ra, dec)
            except Exception as e:
                self.error.emit(f"Calculation error: {str(e)}")
                self.position_updated.emit(0.0, 0.0, 0.0, 0.0)
            self.msleep(1000)  # Reduce Pi 5 CPU usage

# Main Sun Tracking Widget (Lat/Lon Support + Fixes TypeError)
class SunTrackingWidget(QWidget):
    slew_to_sun = pyqtSignal(float, float)
    lat_lon_updated = pyqtSignal(float, float)  # Sync to main.py

    def __init__(self, lat=40.7128, lon=-74.0060):  # Add lat/lon parameters (FIX!)
        super().__init__()
        self.current_lat = lat  # Store lat
        self.current_lon = lon  # Store lon

        # Initialize thread with lat/lon (fixes main.py argument error)
        self.sun_thread = SunPositionThread(lat=self.current_lat, lon=self.current_lon)
        self.sun_thread.position_updated.connect(self._update_sun_display)
        self.sun_thread.error.connect(self._show_error)

        # Current sun position
        self.current_sun_alt = 0.0
        self.current_sun_az = 0.0

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

        # Critical Solar Safety Warning (Pi 5 UI)
        safety_group = QGroupBox("⚠️ SOLAR SAFETY WARNING (CRITICAL!)")
        safety_layout = QVBoxLayout()
        safety_text = QLabel("""
            <font color="red"><b>WARNING:</b></font> Never view the sun directly without a certified solar filter.
            Failure to use proper filtration will cause PERMANENT EYE DAMAGE or BLINDNESS.
        """)
        safety_text.setWordWrap(True)
        self.filter_check = QCheckBox("I confirm a solar filter is installed (I accept risk)")
        safety_layout.addWidget(safety_text)
        safety_layout.addWidget(self.filter_check)
        safety_group.setLayout(safety_layout)
        main_layout.addWidget(safety_group)

        # Sun Tracking Group
        sun_group = QGroupBox("Sun Tracking (Pi 5 Optimized)")
        group_layout = QVBoxLayout(sun_group)

        # Position Display
        self.sun_pos_label = QLabel("Sun Position: Calculating...")
        self.sun_pos_label.setAlignment(Qt.AlignCenter)
        self.sun_pos_label.setStyleSheet("font-size: 16px; margin: 10px;")
        group_layout.addWidget(self.sun_pos_label)

        # Auto-Tracking Toggle (With Safety Check)
        self.auto_track_check = QCheckBox("Enable Auto Sun Tracking")
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
        self.calc_btn = QPushButton("Calculate Sun Position")
        self.calc_btn.clicked.connect(self._calculate_sun_position)
        self.goto_btn = QPushButton("Goto Sun Position")
        self.goto_btn.clicked.connect(self._goto_sun)
        btn_layout.addWidget(self.calc_btn)
        btn_layout.addWidget(self.goto_btn)
        group_layout.addLayout(btn_layout)

        main_layout.addWidget(sun_group)

    # Update Latitude (Sync to main.py)
    def _update_lat(self, value):
        self.current_lat = value
        self.sun_thread.update_location(self.current_lat, self.current_lon)
        self.lat_lon_updated.emit(self.current_lat, self.current_lon)

    # Update Longitude (Sync to main.py)
    def _update_lon(self, value):
        self.current_lon = value
        self.sun_thread.update_location(self.current_lat, self.current_lon)
        self.lat_lon_updated.emit(self.current_lat, self.current_lon)

    # Update Sun Display
    def _update_sun_display(self, alt, az, ra, dec):
        self.current_sun_alt = alt
        self.current_sun_az = az
        self.sun_pos_label.setText(
            f"Sun Position: Alt {alt:.1f}° | Az {az:.1f}° | RA {ra:.2f}h | Dec {dec:.1f}°"
        )

    # Toggle Auto-Tracking (With Safety Lock)
    def _toggle_auto_tracking(self, state):
        if state == Qt.Checked:
            if not self.filter_check.isChecked():
                QMessageBox.critical(self, "SAFETY ERROR", "Confirm solar filter is installed first!", QMessageBox.Ok)
                self.auto_track_check.setChecked(False)
                return
            self.sun_thread.start_tracking()
            QMessageBox.information(self, "Auto Tracking", "Auto sun tracking enabled (Pi 5 optimized)!", QMessageBox.Ok)
        else:
            self.sun_thread.stop_tracking()
            QMessageBox.information(self, "Auto Tracking", "Auto sun tracking disabled!", QMessageBox.Ok)

    # Manual Sun Position Calculation
    def _calculate_sun_position(self):
        alt, az, ra, dec = calculate_sun_position(self.current_lat, self.current_lon)
        self._update_sun_display(alt, az, ra, dec)

    # Goto Sun Position
    def _goto_sun(self):
        if not self.filter_check.isChecked():
            QMessageBox.critical(self, "SAFETY ERROR", "Confirm solar filter is installed first!", QMessageBox.Ok)
            return
        if hasattr(self, 'current_sun_alt') and hasattr(self, 'current_sun_az'):
            self.slew_to_sun.emit(self.current_sun_alt, self.current_sun_az)
            QMessageBox.information(self, "Goto Sun", 
                f"Moving to sun position:\nAltitude: {self.current_sun_alt:.1f}°\nAzimuth: {self.current_sun_az:.1f}°", 
                QMessageBox.Ok)
        else:
            QMessageBox.warning(self, "Error", "Calculate sun position first!", QMessageBox.Ok)

    # Show Error
    def _show_error(self, msg):
        QMessageBox.critical(self, "Sun Tracking Error", msg)

    # Safe Close (Pi 5 Resource Cleanup)
    def close(self):
        self.sun_thread.stop_tracking()
        self.sun_thread.wait()