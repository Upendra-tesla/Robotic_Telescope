import datetime
import math
from astropy.coordinates import get_sun, EarthLocation, AltAz
from astropy.time import Time
from astropy import units as u
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTextEdit, QMessageBox, QCheckBox
)
from PyQt5.QtCore import QTimer, Qt, pyqtSignal, QThread

# Sun Position Calculation Thread (non-blocking for GUI)
class SunPositionThread(QThread):
    position_updated = pyqtSignal(float, float, float, float)  # alt (°), az (°), ra (h), dec (°)

    def __init__(self, lat=40.7128, lon=-74.0060):
        super().__init__()
        self.lat = lat  # Default: New York (replace with GPS coords)
        self.lon = lon
        self.running = False
        self.tracking = False

    def set_location(self, lat, lon):
        """Update GPS coordinates for sun position calculation"""
        self.lat = lat
        self.lon = lon

    def start_tracking(self):
        """Start continuous sun position updates (automatic tracking)"""
        self.running = True
        self.tracking = True
        self.start()

    def stop_tracking(self):
        """Stop automatic sun tracking"""
        self.running = False
        self.tracking = False

    def calculate_sun_position(self):
        """Calculate current sun position (Alt/Az, RA/Dec) using astropy"""
        # Set up location and time
        location = EarthLocation(lat=self.lat*u.deg, lon=self.lon*u.deg)
        current_time = Time(datetime.datetime.now())
        
        # Calculate sun position
        sun = get_sun(current_time)
        altaz_frame = AltAz(obstime=current_time, location=location)
        sun_altaz = sun.transform_to(altaz_frame)
        
        # Extract values (convert to degrees/hours for readability)
        alt = sun_altaz.alt.deg
        az = sun_altaz.az.deg
        ra = sun.ra.hour  # Right Ascension (hours)
        dec = sun.dec.deg  # Declination (degrees)
        
        return alt, az, ra, dec

    def run(self):
        """Continuous sun position update loop (1Hz for Pi 5)"""
        while self.running:
            alt, az, ra, dec = self.calculate_sun_position()
            self.position_updated.emit(alt, az, ra, dec)
            self.msleep(1000)  # Update every 1 second

# Main Sun Tracking Widget
class SunTrackingWidget(QWidget):  # Critical: Exact class name main.py imports
    # Signal to send sun position to telescope control modules
    slew_to_sun = pyqtSignal(float, float)  # alt (°), az (°)

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self._setup_ui()
        self.setLayout(self.layout)

        # Initialize sun position thread (Raspberry Pi 5 optimized)
        self.sun_thread = SunPositionThread()
        self.sun_thread.position_updated.connect(self._update_sun_display)

        # Default GPS location (replace with real GPS data later)
        self.current_lat = 40.7128
        self.current_lon = -74.0060

    def _setup_ui(self):
        """Create sun tracking UI with safety warnings and controls"""
        # Safety Warning (critical for solar observations)
        safety_group = QGroupBox("⚠️ Solar Safety Warning")
        safety_layout = QVBoxLayout()
        safety_text = QLabel("""
            <font color="red"><b>WARNING:</b></font> Never view the sun directly without a certified solar filter.
            Failure to use proper filtration will cause permanent eye damage.
        """)
        safety_text.setWordWrap(True)
        self.filter_check = QCheckBox("I confirm a solar filter is installed")
        safety_layout.addWidget(safety_text)
        safety_layout.addWidget(self.filter_check)
        safety_group.setLayout(safety_layout)
        self.layout.addWidget(safety_group)

        # Sun Position Display
        display_group = QGroupBox("Current Sun Position")
        display_layout = QVBoxLayout()
        
        self.alt_az_label = QLabel("Altitude: 0.0° | Azimuth: 0.0°")
        self.ra_dec_label = QLabel("RA: 0.0h | Declination: 0.0°")
        display_layout.addWidget(self.alt_az_label)
        display_layout.addWidget(self.ra_dec_label)
        
        display_group.setLayout(display_layout)
        self.layout.addWidget(display_group)

        # Control Buttons
        control_layout = QHBoxLayout()
        
        self.calculate_btn = QPushButton("Calculate Sun Position")
        self.calculate_btn.clicked.connect(self._calculate_single_position)
        
        self.slew_btn = QPushButton("Slew to Sun")
        self.slew_btn.clicked.connect(self._slew_to_sun)
        self.slew_btn.setEnabled(False)  # Disabled until filter is confirmed
        
        self.track_btn = QPushButton("Start Auto Tracking")
        self.track_btn.clicked.connect(self._toggle_tracking)
        
        control_layout.addWidget(self.calculate_btn)
        control_layout.addWidget(self.slew_btn)
        control_layout.addWidget(self.track_btn)
        self.layout.addLayout(control_layout)

        # Filter check box toggle (enable/disable slew button)
        self.filter_check.stateChanged.connect(self._toggle_slew_button)

    def _toggle_slew_button(self, state):
        """Enable slew button only if user confirms solar filter is installed"""
        self.slew_btn.setEnabled(state == Qt.Checked)

    def _calculate_single_position(self):
        """Calculate sun position once (manual refresh)"""
        alt, az, ra, dec = self.sun_thread.calculate_sun_position()
        self._update_sun_display(alt, az, ra, dec)

    def _slew_to_sun(self):
        """One-click slew to sun position (with safety confirmation)"""
        if not self.filter_check.isChecked():
            QMessageBox.critical(self, "Safety Error", "Please confirm a solar filter is installed first!")
            return
        
        # Get current sun position
        alt, az, ra, dec = self.sun_thread.calculate_sun_position()
        
        # Emit signal to telescope control (main.py can connect this to altitude/azimuth modules)
        self.slew_to_sun.emit(alt, az)
        
        QMessageBox.information(self, "Slew to Sun", 
                                f"Telescope slewing to Sun:\nAltitude: {alt:.1f}°\nAzimuth: {az:.1f}°")

    def _toggle_tracking(self):
        """Start/stop automatic sun tracking"""
        if self.sun_thread.tracking:
            self.sun_thread.stop_tracking()
            self.track_btn.setText("Start Auto Tracking")
        else:
            if not self.filter_check.isChecked():
                QMessageBox.critical(self, "Safety Error", "Please confirm a solar filter is installed first!")
                return
            self.sun_thread.start_tracking()
            self.track_btn.setText("Stop Auto Tracking")

    def _update_sun_display(self, alt, az, ra, dec):
        """Update UI with current sun position data"""
        self.alt_az_label.setText(f"Altitude: {alt:.1f}° | Azimuth: {az:.1f}°")
        self.ra_dec_label.setText(f"RA: {ra:.2f}h | Declination: {dec:.1f}°")

    def closeEvent(self, event):
        """Clean up thread on widget close"""
        self.sun_thread.stop_tracking()
        self.sun_thread.wait()
        event.accept()