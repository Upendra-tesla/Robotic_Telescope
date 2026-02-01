import datetime
import math
from astropy.coordinates import get_body, EarthLocation, AltAz
from astropy.time import Time
from astropy import units as u
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QMessageBox, QCheckBox, QFrame
)
from PyQt5.QtCore import QTimer, Qt, pyqtSignal, QThread
from PyQt5.QtGui import QPainter, QPen, QBrush

# Moon Position & Phase Calculation Thread (non-blocking for GUI)
class MoonPositionThread(QThread):
    position_updated = pyqtSignal(float, float, float, float, float, str)  
    # alt (°), az (°), ra (h), dec (°), illumination (%), phase_name

    def __init__(self, lat=40.7128, lon=-74.0060):
        super().__init__()
        self.lat = lat  # Default: New York (replace with GPS coords)
        self.lon = lon
        self.running = False
        self.tracking = False

    def set_location(self, lat, lon):
        """Update GPS coordinates for moon position calculation"""
        self.lat = lat
        self.lon = lon

    def start_tracking(self):
        """Start continuous moon position/phase updates (1Hz for Pi 5)"""
        self.running = True
        self.tracking = True
        self.start()

    def stop_tracking(self):
        """Stop automatic moon tracking"""
        self.running = False
        self.tracking = False

    def calculate_moon_phase(self, illumination):
        """Determine moon phase name from illumination percentage"""
        if illumination >= 98:
            return "Full Moon"
        elif illumination >= 50:
            return "Waning Gibbous"
        elif illumination >= 2:
            return "Waning Crescent"
        elif illumination <= 0:
            return "New Moon"
        elif illumination <= 50:
            return "Waxing Crescent"
        else:
            return "Waxing Gibbous"

    def calculate_moon_position(self):
        """Calculate moon position (Alt/Az, RA/Dec) and illumination using astropy (fixed import)"""
        # Set up location and time (Pi 5 system time)
        location = EarthLocation(lat=self.lat*u.deg, lon=self.lon*u.deg)
        current_time = Time(datetime.datetime.now())
        
        # Correct way to get moon position (replaces get_moon)
        moon = get_body('moon', current_time, location=location)
        altaz_frame = AltAz(obstime=current_time, location=location)
        moon_altaz = moon.transform_to(altaz_frame)
        
        # Extract core values
        alt = moon_altaz.alt.deg
        az = moon_altaz.az.deg
        ra = moon.ra.hour
        dec = moon.dec.deg
        
        # Calculate moon illumination (0-100%) - simplified but accurate for Pi 5
        sun = get_body('sun', current_time, location=location)
        # Calculate elongation (angle between sun and moon)
        elongation = math.acos(
            math.sin(moon.dec.rad) * math.sin(sun.dec.rad) +
            math.cos(moon.dec.rad) * math.cos(sun.dec.rad) * math.cos(moon.ra.rad - sun.ra.rad)
        )
        # Calculate phase angle and illumination
        phase_angle = math.atan2(
            sun.distance.au * math.sin(elongation),
            moon.distance.au - sun.distance.au * math.cos(elongation)
        )
        illumination = (1 + math.cos(phase_angle)) / 2 * 100
        
        # Get phase name
        phase_name = self.calculate_moon_phase(illumination)
        
        return alt, az, ra, dec, illumination, phase_name

    def run(self):
        """Continuous update loop (optimized for Pi 5's CPU)"""
        while self.running:
            alt, az, ra, dec, illumination, phase = self.calculate_moon_position()
            self.position_updated.emit(alt, az, ra, dec, illumination, phase)
            self.msleep(1000)  # Update every 1 second (low CPU usage)

# Moon Phase Visual Widget (for UI feedback)
class MoonPhaseWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(150, 150)
        self.illumination = 50.0
        self.phase_name = "First Quarter"

    def set_phase(self, illumination, phase_name):
        self.illumination = illumination
        self.phase_name = phase_name
        self.update()  # Redraw phase graphic

    def paintEvent(self, event):
        """Draw a simple visual representation of the moon phase"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw background
        center = self.rect().center()
        radius = min(center.x(), center.y()) - 10
        painter.setBrush(QBrush(Qt.black))
        painter.drawEllipse(center, radius, radius)
        
        # Draw moon (illuminated portion)
        painter.setBrush(QBrush(Qt.white))
        pen = QPen(Qt.white, 1)
        painter.setPen(pen)
        
        # Calculate illuminated width based on phase
        if self.phase_name in ["Full Moon", "New Moon"]:
            # Full or new moon (circle)
            painter.drawEllipse(center, radius-5, radius-5)
        elif "Waning" in self.phase_name:
            # Waning (right side illuminated)
            illuminated_width = int((self.illumination / 100) * (radius * 2))
            rect = self.rect().adjusted(
                center.x() - radius + (radius*2 - illuminated_width),
                center.y() - radius + 5,
                center.x() + radius - 5,
                center.y() + radius - 5
            )
            painter.drawChord(rect, 90*16, 180*16)
        else:
            # Waxing (left side illuminated)
            illuminated_width = int((self.illumination / 100) * (radius * 2))
            rect = self.rect().adjusted(
                center.x() - radius + 5,
                center.y() - radius + 5,
                center.x() + radius - (radius*2 - illuminated_width),
                center.y() + radius - 5
            )
            painter.drawChord(rect, 270*16, 180*16)
        
        # Draw phase name text
        painter.setPen(QPen(Qt.white, 1))
        painter.drawText(10, 20, f"{self.phase_name}")
        painter.drawText(10, 40, f"Illumination: {self.illumination:.1f}%")

# Main Moon Tracking Widget
class MoonTrackingWidget(QWidget):  # Critical: Exact class name for main.py import
    # Signal to send moon position to telescope control modules
    slew_to_moon = pyqtSignal(float, float)  # alt (°), az (°)

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self._setup_ui()
        self.setLayout(self.layout)

        # Initialize moon position thread (Pi 5 optimized)
        self.moon_thread = MoonPositionThread()
        self.moon_thread.position_updated.connect(self._update_moon_display)

        # Default GPS location (replace with real GPS data later)
        self.current_lat = 40.7128
        self.current_lon = -74.0060

    def _setup_ui(self):
        """Create moon tracking UI with phase display and controls"""
        # Title & Info
        info_group = QGroupBox("Moon Tracking")
        info_layout = QVBoxLayout()
        info_text = QLabel("Moon tracking with real-time phase and illumination data (Pi 5 optimized)")
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)
        info_group.setLayout(info_layout)
        self.layout.addWidget(info_group)

        # Moon Position + Phase Display
        display_layout = QHBoxLayout()
        
        # Phase visual widget
        self.phase_widget = MoonPhaseWidget()
        display_layout.addWidget(self.phase_widget)
        
        # Text position display
        text_display = QVBoxLayout()
        self.alt_az_label = QLabel("Altitude: 0.0° | Azimuth: 0.0°")
        self.ra_dec_label = QLabel("RA: 0.0h | Declination: 0.0°")
        text_display.addWidget(self.alt_az_label)
        text_display.addWidget(self.ra_dec_label)
        display_layout.addLayout(text_display)

        self.layout.addLayout(display_layout)

        # Control Buttons
        control_layout = QHBoxLayout()
        
        self.calculate_btn = QPushButton("Calculate Moon Position")
        self.calculate_btn.clicked.connect(self._calculate_single_position)
        
        self.slew_btn = QPushButton("Slew to Moon")
        self.slew_btn.clicked.connect(self._slew_to_moon)
        
        self.track_btn = QPushButton("Start Auto Tracking")
        self.track_btn.clicked.connect(self._toggle_tracking)
        
        control_layout.addWidget(self.calculate_btn)
        control_layout.addWidget(self.slew_btn)
        control_layout.addWidget(self.track_btn)
        self.layout.addLayout(control_layout)

    def _calculate_single_position(self):
        """Calculate moon position once (manual refresh)"""
        alt, az, ra, dec, illumination, phase = self.moon_thread.calculate_moon_position()
        self._update_moon_display(alt, az, ra, dec, illumination, phase)

    def _slew_to_moon(self):
        """One-click slew to moon position"""
        # Get current moon position
        alt, az, ra, dec, illumination, phase = self.moon_thread.calculate_moon_position()
        
        # Emit signal to telescope control (connect to altitude/azimuth modules in main.py)
        self.slew_to_moon.emit(alt, az)
        
        QMessageBox.information(self, "Slew to Moon", 
                                f"Telescope slewing to Moon:\nAltitude: {alt:.1f}°\nAzimuth: {az:.1f}°\nPhase: {phase}")

    def _toggle_tracking(self):
        """Start/stop automatic moon tracking"""
        if self.moon_thread.tracking:
            self.moon_thread.stop_tracking()
            self.track_btn.setText("Start Auto Tracking")
        else:
            self.moon_thread.start_tracking()
            self.track_btn.setText("Stop Auto Tracking")

    def _update_moon_display(self, alt, az, ra, dec, illumination, phase):
        """Update UI with moon position/phase data"""
        # Update text labels
        self.alt_az_label.setText(f"Altitude: {alt:.1f}° | Azimuth: {az:.1f}°")
        self.ra_dec_label.setText(f"RA: {ra:.2f}h | Declination: {dec:.1f}°")
        
        # Update phase widget
        self.phase_widget.set_phase(illumination, phase)

    def closeEvent(self, event):
        """Clean up thread on widget close (Pi 5 resource management)"""
        self.moon_thread.stop_tracking()
        self.moon_thread.wait()
        event.accept()