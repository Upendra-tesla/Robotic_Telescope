import sys
import math
import datetime
import astropy.units as u
from astropy.coordinates import EarthLocation, SkyCoord, AltAz, get_sun
from astropy.time import Time
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QFrame, QSizePolicy, QProgressBar, QGroupBox,
    QGridLayout, QComboBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QMutex, QMutexLocker
from PyQt5.QtGui import QFont, QPainter, QPen, QBrush, QColor, QPixmap
from . import SETTINGS, get_responsive_stylesheet

# Universal get_moon import
try:
    from astropy.coordinates import get_moon
except ImportError:
    try:
        from astropy.coordinates.moon import get_moon
    except ImportError:
        def get_moon(time, location=None):
            from astropy.coordinates import solar_system_ephemeris, EarthLocation as EL
            from astropy.coordinates import get_body
            with solar_system_ephemeris.set('builtin'):
                return get_body('moon', time, location or EL(0*u.deg, 0*u.deg))

# Moon phase emojis and descriptions
MOON_PHASES = [
    ("New Moon", "🌑", 0.0),
    ("Waxing Crescent", "🌒", 0.125),
    ("First Quarter", "🌓", 0.25),
    ("Waxing Gibbous", "🌔", 0.375),
    ("Full Moon", "🌕", 0.5),
    ("Waning Gibbous", "🌖", 0.625),
    ("Last Quarter", "🌗", 0.75),
    ("Waning Crescent", "🌘", 0.875)
]

class MoonCalculationThread(QThread):
    moon_data_updated = pyqtSignal(dict)
    status_updated = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.mutex = QMutex()
        self.running = False
        self.tracking = False
        self.latitude = SETTINGS["location"]["latitude"]
        self.longitude = SETTINGS["location"]["longitude"]
        self.current_moon_data = {
            "altitude": 0.0,
            "azimuth": 0.0,
            "phase": 0.0,
            "illumination": 0.0,
            "phase_name": "New Moon",
            "phase_emoji": "🌑",
            "tracking": False,
            "visible": False
        }

    def set_location(self, latitude, longitude):
        """Update location coordinates"""
        with QMutexLocker(self.mutex):
            self.latitude = float(latitude) if latitude else SETTINGS["location"]["latitude"]
            self.longitude = float(longitude) if longitude else SETTINGS["location"]["longitude"]
            SETTINGS["location"]["latitude"] = self.latitude
            SETTINGS["location"]["longitude"] = self.longitude

    def start_tracking(self):
        """Start moon tracking"""
        with QMutexLocker(self.mutex):
            self.tracking = True
            self.current_moon_data["tracking"] = True
        self.status_updated.emit("Moon tracking started")

    def stop_tracking(self):
        """Stop moon tracking"""
        with QMutexLocker(self.mutex):
            self.tracking = False
            self.current_moon_data["tracking"] = False
        self.status_updated.emit("Moon tracking stopped")

    def calculate_moon_position(self):
        """Calculate current moon position/phase using Astropy"""
        try:
            location = EarthLocation(
                lat=self.latitude * u.degree,
                lon=self.longitude * u.degree,
                height=SETTINGS["location"]["altitude"] * u.meter
            )

            current_time = Time(datetime.datetime.now(), scale='utc')
            moon_eq = get_moon(current_time, location=location)
            altaz_frame = AltAz(obstime=current_time, location=location)
            moon_altaz = moon_eq.transform_to(altaz_frame)

            moon_altitude = moon_altaz.alt.value
            moon_azimuth = moon_altaz.az.value

            # Calculate moon phase & illumination
            sun_eq = get_sun(current_time)
            phase_angle = moon_eq.separation(sun_eq).value
            phase_angle_rad = math.radians(phase_angle)
            illumination = (1 + math.cos(phase_angle_rad)) / 2 * 100

            # Calculate phase (0-1: 0 = new, 0.5 = full, 1 = new)
            if phase_angle <= 180:
                phase = phase_angle / 360
            else:
                phase = (360 - phase_angle) / 360 + 0.5

            # Get phase name/emoji
            phase_name, phase_emoji, _ = self.get_moon_phase(phase)
            visible = moon_altitude > 0

            return {
                "altitude": moon_altitude,
                "azimuth": moon_azimuth,
                "phase": phase,
                "illumination": illumination,
                "phase_name": phase_name,
                "phase_emoji": phase_emoji,
                "tracking": self.tracking,
                "visible": visible
            }
        except Exception as e:
            self.status_updated.emit(f"Calculation error: {str(e)}")
            return self.current_moon_data

    def get_moon_phase(self, phase):
        """Get moon phase name and emoji from phase value (0-1)"""
        phase = phase % 1.0
        closest = min(MOON_PHASES, key=lambda x: abs(x[2] - phase))
        return closest

    def run(self):
        self.running = True
        while self.running:
            moon_data = self.calculate_moon_position()
            with QMutexLocker(self.mutex):
                self.current_moon_data = moon_data
            self.moon_data_updated.emit(moon_data)
            QThread.msleep(2000)

    def stop(self):
        self.running = False
        self.tracking = False
        self.wait()

class MoonPhaseWidget(QWidget):
    """Widget to visualize moon phase"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self.phase = 0.0
        self.illumination = 0.0
        self.phase_emoji = "🌑"
        self.phase_name = "New Moon"

    def update_moon_phase(self, phase, illumination, emoji, name):
        self.phase = phase
        self.illumination = illumination
        self.phase_emoji = emoji
        self.phase_name = name
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background
        painter.setBrush(QBrush(QColor(43, 43, 43)))
        painter.drawRect(self.rect())
        
        # Moon circle
        center_x = self.width() // 2
        center_y = self.height() // 2
        radius = min(center_x, center_y) - 30
        
        # Draw dark circle (unilluminated part)
        painter.setBrush(QBrush(QColor(60, 60, 60)))
        painter.setPen(QPen(QColor(100, 100, 100), 2))
        painter.drawEllipse(center_x - radius, center_y - radius, 2 * radius, 2 * radius)
        
        # Illuminated portion
        phase = self.phase % 1.0
        illuminated_width = int(radius * 2 * (self.illumination / 100.0))
        
        # Draw illuminated part
        if phase < 0.5:
            # Waxing (right side illuminated)
            painter.setBrush(QBrush(QColor(220, 220, 220)))
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawEllipse(
                center_x - radius + (radius * 2 - illuminated_width),
                center_y - radius,
                illuminated_width,
                2 * radius
            )
        else:
            # Waning (left side illuminated)
            painter.setBrush(QBrush(QColor(220, 220, 220)))
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawEllipse(
                center_x - radius,
                center_y - radius,
                illuminated_width,
                2 * radius
            )
        
        # Draw phase emoji and text
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.setFont(QFont("Arial", 24))
        painter.drawText(center_x - 15, center_y + radius + 30, self.phase_emoji)
        
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        text_width = painter.fontMetrics().width(self.phase_name)
        painter.drawText(center_x - text_width // 2, center_y + radius + 50, self.phase_name)
        
        painter.setFont(QFont("Arial", 9))
        illum_text = f"Illumination: {self.illumination:.1f}%"
        text_width = painter.fontMetrics().width(illum_text)
        painter.drawText(center_x - text_width // 2, center_y + radius + 65, illum_text)

class MoonWidget(QWidget):
    moon_position_updated = pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Apply responsive stylesheet
        self.setStyleSheet(get_responsive_stylesheet())
        
        # Moon Calculation Thread
        self.moon_thread = MoonCalculationThread()
        self.moon_thread.moon_data_updated.connect(self.update_moon_data)
        self.moon_thread.status_updated.connect(self.update_status)
        self.moon_thread.start()

        self.init_ui()

    def init_ui(self):
        """Initialize user interface"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Title Group
        title_group = QGroupBox("Moon Tracking")
        title_layout = QVBoxLayout()
        title_label = QLabel("🌙 Moon Position & Phase")
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(title_label)
        title_group.setLayout(title_layout)
        main_layout.addWidget(title_group)

        # Location Input Group
        location_group = QGroupBox("Location Settings")
        location_layout = QGridLayout()
        
        location_layout.addWidget(QLabel("Latitude:"), 0, 0)
        self.lat_input = QLineEdit(str(SETTINGS["location"]["latitude"]))
        self.lat_input.setMaximumWidth(100)
        location_layout.addWidget(self.lat_input, 0, 1)
        
        location_layout.addWidget(QLabel("Longitude:"), 0, 2)
        self.lon_input = QLineEdit(str(SETTINGS["location"]["longitude"]))
        self.lon_input.setMaximumWidth(100)
        location_layout.addWidget(self.lon_input, 0, 3)
        
        self.update_loc_btn = QPushButton("Update Location")
        self.update_loc_btn.clicked.connect(self.update_location)
        location_layout.addWidget(self.update_loc_btn, 0, 4)
        
        location_group.setLayout(location_layout)
        main_layout.addWidget(location_group)

        # Moon Position Display Group
        position_group = QGroupBox("Current Moon Position")
        position_layout = QGridLayout()
        
        # Altitude
        position_layout.addWidget(QLabel("Altitude:"), 0, 0)
        self.alt_label = QLabel("0.0°")
        self.alt_label.setStyleSheet("color: #ccccff; font-weight: bold; font-size: 16px;")
        position_layout.addWidget(self.alt_label, 0, 1)
        
        self.alt_progress = QProgressBar()
        self.alt_progress.setRange(-90, 90)
        self.alt_progress.setValue(0)
        self.alt_progress.setTextVisible(True)
        self.alt_progress.setFormat("%v°")
        position_layout.addWidget(self.alt_progress, 0, 2)
        
        # Azimuth
        position_layout.addWidget(QLabel("Azimuth:"), 1, 0)
        self.az_label = QLabel("0.0°")
        self.az_label.setStyleSheet("color: #ccccff; font-weight: bold; font-size: 16px;")
        position_layout.addWidget(self.az_label, 1, 1)
        
        self.az_progress = QProgressBar()
        self.az_progress.setRange(0, 360)
        self.az_progress.setValue(0)
        self.az_progress.setTextVisible(True)
        self.az_progress.setFormat("%v°")
        position_layout.addWidget(self.az_progress, 1, 2)
        
        # Visibility
        position_layout.addWidget(QLabel("Visibility:"), 2, 0)
        self.vis_label = QLabel("Below Horizon")
        self.vis_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        position_layout.addWidget(self.vis_label, 2, 1)
        
        position_group.setLayout(position_layout)
        main_layout.addWidget(position_group)

        # Moon Phase Visualization
        phase_group = QGroupBox("Moon Phase")
        phase_layout = QHBoxLayout()
        
        self.moon_phase_widget = MoonPhaseWidget()
        phase_layout.addWidget(self.moon_phase_widget)
        
        # Phase info
        info_layout = QVBoxLayout()
        
        self.phase_label = QLabel("New Moon 🌑")
        self.phase_label.setStyleSheet("color: #ccccff; font-weight: bold; font-size: 14px;")
        info_layout.addWidget(self.phase_label)
        
        self.illum_progress = QProgressBar()
        self.illum_progress.setRange(0, 100)
        self.illum_progress.setValue(0)
        self.illum_progress.setTextVisible(True)
        self.illum_progress.setFormat("%p% Illuminated")
        self.illum_progress.setStyleSheet("""
            QProgressBar {
                background-color: #333333;
                border: 1px solid #555555;
                border-radius: 5px;
            }
            QProgressBar::chunk {
                background-color: #ccccff;
            }
        """)
        info_layout.addWidget(self.illum_progress)
        
        info_layout.addStretch()
        phase_layout.addLayout(info_layout)
        
        phase_group.setLayout(phase_layout)
        main_layout.addWidget(phase_group)

        # Tracking Controls Group
        control_group = QGroupBox("Tracking Controls")
        control_layout = QHBoxLayout()
        
        self.start_track_btn = QPushButton("▶ Start Tracking")
        self.start_track_btn.clicked.connect(self.moon_thread.start_tracking)
        self.start_track_btn.setStyleSheet("background-color: #444444; color: white;")
        
        self.stop_track_btn = QPushButton("⏸ Stop Tracking")
        self.stop_track_btn.clicked.connect(self.moon_thread.stop_tracking)
        self.stop_track_btn.setEnabled(False)
        self.stop_track_btn.setStyleSheet("background-color: #444444; color: white;")
        
        self.goto_btn = QPushButton("📍 Point to Moon")
        self.goto_btn.clicked.connect(self.point_to_moon)
        self.goto_btn.setStyleSheet("background-color: #ccccff; color: black;")
        
        control_layout.addWidget(self.start_track_btn)
        control_layout.addWidget(self.stop_track_btn)
        control_layout.addWidget(self.goto_btn)
        control_group.setLayout(control_layout)
        main_layout.addWidget(control_group)

        # Status Group
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout()
        self.status_label = QLabel("Status: Calculating moon position...")
        self.status_label.setStyleSheet("color: #ffaa00; font-weight: bold;")
        status_layout.addWidget(self.status_label)
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)

        main_layout.addStretch()
        self.setLayout(main_layout)

    def update_location(self):
        """Update location coordinates"""
        try:
            lat = float(self.lat_input.text())
            lon = float(self.lon_input.text())
            
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                raise ValueError("Invalid coordinates")
            
            self.moon_thread.set_location(lat, lon)
            self.status_label.setText("Status: Location updated")
            self.status_label.setStyleSheet("color: #00ff00; font-weight: bold;")
        except ValueError as e:
            self.status_label.setText(f"Status: Invalid location - {str(e)}")
            self.status_label.setStyleSheet("color: #ff4444; font-weight: bold;")

    def update_moon_data(self, moon_data):
        """Update moon data display"""
        self.alt_label.setText(f"{moon_data['altitude']:.1f}°")
        self.az_label.setText(f"{moon_data['azimuth']:.1f}°")
        self.phase_label.setText(f"{moon_data['phase_name']} {moon_data['phase_emoji']}")
        
        self.alt_progress.setValue(int(moon_data['altitude']))
        self.az_progress.setValue(int(moon_data['azimuth']))
        self.illum_progress.setValue(int(moon_data['illumination']))
        
        # Update visibility
        if moon_data['visible']:
            self.vis_label.setText("Above Horizon")
            self.vis_label.setStyleSheet("color: #00ff00; font-weight: bold;")
        else:
            self.vis_label.setText("Below Horizon")
            self.vis_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        
        self.moon_phase_widget.update_moon_phase(
            moon_data['phase'],
            moon_data['illumination'],
            moon_data['phase_emoji'],
            moon_data['phase_name']
        )
        
        # Update tracking button states
        if moon_data['tracking']:
            self.start_track_btn.setEnabled(False)
            self.stop_track_btn.setEnabled(True)
            self.start_track_btn.setStyleSheet("background-color: #555555; color: #888888;")
            self.stop_track_btn.setStyleSheet("background-color: #ff4444; color: white;")
        else:
            self.start_track_btn.setEnabled(True)
            self.stop_track_btn.setEnabled(False)
            self.start_track_btn.setStyleSheet("background-color: #00a8ff; color: white;")
            self.stop_track_btn.setStyleSheet("background-color: #555555; color: #888888;")
        
        # Emit position for telescope control if tracking
        if moon_data['tracking'] and moon_data['visible']:
            self.moon_position_updated.emit(
                moon_data['altitude'],
                moon_data['azimuth']
            )

    def point_to_moon(self):
        """Point telescope to current moon position"""
        if hasattr(self.moon_thread, 'current_moon_data'):
            moon_data = self.moon_thread.current_moon_data
            if moon_data['visible']:
                self.moon_position_updated.emit(
                    moon_data['altitude'],
                    moon_data['azimuth']
                )
                self.status_label.setText("Status: Pointing to moon...")
                self.status_label.setStyleSheet("color: #00ff00; font-weight: bold;")
            else:
                self.status_label.setText("Status: Moon is below horizon")
                self.status_label.setStyleSheet("color: #ff4444; font-weight: bold;")

    def update_status(self, status):
        """Update status label"""
        self.status_label.setText(f"Status: {status}")

    def cleanup(self):
        """Cleanup moon thread"""
        self.moon_thread.stop()