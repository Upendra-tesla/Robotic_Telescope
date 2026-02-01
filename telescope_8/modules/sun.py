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
from PyQt5.QtGui import QFont, QPainter, QPen, QBrush, QColor
from . import SETTINGS, get_responsive_stylesheet

def calculate_sun_rise_set(lat, lon, date=None):
    """Calculate sunrise/sunset times using Astropy"""
    if date is None:
        date = datetime.datetime.now().date()
    
    location = EarthLocation(lat=lat*u.deg, lon=lon*u.deg)
    start_time = Time(f"{date} 00:00:00", scale='utc')
    
    sunrise = None
    sunset = None
    prev_alt = None
    
    for t_utc in range(0, 86400, 60):
        current_time = start_time + t_utc*u.second
        sun_coord = get_sun(current_time)
        altaz = sun_coord.transform_to(AltAz(obstime=current_time, location=location))
        current_alt = altaz.alt.value
        
        if prev_alt is not None and prev_alt < 0 and current_alt >= 0 and sunrise is None:
            sunrise = current_time.to_datetime()
        elif prev_alt is not None and prev_alt >= 0 and current_alt < 0 and sunset is None:
            sunset = current_time.to_datetime()
        
        prev_alt = current_alt
    
    if sunrise is None:
        sunrise_str = "N/A"
    else:
        sunrise_local = sunrise.astimezone()
        sunrise_str = sunrise_local.strftime("%H:%M:%S")
    
    if sunset is None:
        sunset_str = "N/A"
    else:
        sunset_local = sunset.astimezone()
        sunset_str = sunset_local.strftime("%H:%M:%S")
    
    return sunrise_str, sunset_str

class SunCalculationThread(QThread):
    sun_data_updated = pyqtSignal(dict)
    status_updated = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.mutex = QMutex()
        self.running = False
        self.tracking = False
        self.latitude = SETTINGS["location"]["latitude"]
        self.longitude = SETTINGS["location"]["longitude"]
        self.current_sun_data = {
            "altitude": 0.0,
            "azimuth": 0.0,
            "sunrise": "",
            "sunset": "",
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
        """Start sun tracking"""
        with QMutexLocker(self.mutex):
            self.tracking = True
            self.current_sun_data["tracking"] = True
        self.status_updated.emit("Sun tracking started")

    def stop_tracking(self):
        """Stop sun tracking"""
        with QMutexLocker(self.mutex):
            self.tracking = False
            self.current_sun_data["tracking"] = False
        self.status_updated.emit("Sun tracking stopped")

    def calculate_sun_position(self):
        """Calculate current sun position using Astropy"""
        try:
            location = EarthLocation(
                lat=self.latitude * u.degree,
                lon=self.longitude * u.degree,
                height=SETTINGS["location"]["altitude"] * u.meter
            )

            current_time = Time(datetime.datetime.now(), scale='utc')
            sun_eq = get_sun(current_time)
            altaz_frame = AltAz(obstime=current_time, location=location)
            sun_altaz = sun_eq.transform_to(altaz_frame)

            sun_altitude = sun_altaz.alt.value
            sun_azimuth = sun_altaz.az.value

            sunrise, sunset = calculate_sun_rise_set(self.latitude, self.longitude)
            visible = sun_altitude > 0

            return {
                "altitude": sun_altitude,
                "azimuth": sun_azimuth,
                "sunrise": sunrise,
                "sunset": sunset,
                "tracking": self.tracking,
                "visible": visible
            }
        except Exception as e:
            self.status_updated.emit(f"Calculation error: {str(e)}")
            return self.current_sun_data

    def run(self):
        self.running = True
        while self.running:
            sun_data = self.calculate_sun_position()
            with QMutexLocker(self.mutex):
                self.current_sun_data = sun_data
            self.sun_data_updated.emit(sun_data)
            QThread.msleep(2000)

    def stop(self):
        self.running = False
        self.tracking = False
        self.wait()

class SunPathWidget(QWidget):
    """Widget to visualize sun path"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 200)
        self.sun_altitude = 0.0
        self.sun_azimuth = 0.0
        self.sun_visible = False

    def update_sun_position(self, altitude, azimuth, visible):
        self.sun_altitude = altitude
        self.sun_azimuth = azimuth
        self.sun_visible = visible
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background
        painter.setBrush(QBrush(QColor(43, 43, 43)))
        painter.drawRect(self.rect())
        
        # Sun path arc
        center_x = self.width() // 2
        center_y = self.height() - 30
        radius = min(center_x - 20, center_y - 30)
        
        # Draw horizon line
        painter.setPen(QPen(QColor(100, 100, 100), 2))
        painter.drawLine(20, center_y, self.width() - 20, center_y)
        
        # Draw cardinal directions
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.setFont(QFont("Arial", 10))
        painter.drawText(center_x - 10, center_y + 20, "S")
        painter.drawText(20, center_y - 10, "E")
        painter.drawText(self.width() - 30, center_y - 10, "W")
        painter.drawText(center_x - 10, center_y - radius - 10, "N")
        
        # Draw sun path (arc from E to W)
        painter.setPen(QPen(QColor(255, 200, 0, 100), 2))
        painter.drawArc(
            center_x - radius,
            center_y - radius,
            2 * radius,
            2 * radius,
            45 * 16,
            270 * 16
        )
        
        # Draw sun position if visible
        if self.sun_visible and 0 <= self.sun_azimuth <= 360 and -90 <= self.sun_altitude <= 90:
            az_rad = math.radians(self.sun_azimuth - 180)
            alt_scaled = (self.sun_altitude + 90) / 180
            
            sun_x = center_x + radius * math.sin(az_rad) * (1 - alt_scaled)
            sun_y = center_y - radius * math.cos(az_rad) * (1 - alt_scaled)
            
            # Draw sun
            if self.sun_altitude > 0:
                painter.setBrush(QBrush(QColor(255, 200, 0)))
                painter.setPen(QPen(QColor(255, 150, 0), 2))
            else:
                painter.setBrush(QBrush(QColor(100, 100, 100)))
                painter.setPen(QPen(QColor(150, 150, 150), 2))
            
            painter.drawEllipse(int(sun_x) - 10, int(sun_y) - 10, 20, 20)
            
            # Draw rays for sun above horizon
            if self.sun_altitude > 0:
                painter.setPen(QPen(QColor(255, 200, 0, 150), 1))
                for i in range(0, 360, 45):
                    rad = math.radians(i)
                    ray_x = int(sun_x + 15 * math.cos(rad))
                    ray_y = int(sun_y + 15 * math.sin(rad))
                    painter.drawLine(int(sun_x), int(sun_y), ray_x, ray_y)
            
            # Draw sun position text
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.setFont(QFont("Arial", 9))
            painter.drawText(
                int(sun_x) + 15, 
                int(sun_y), 
                f"{self.sun_altitude:.1f}°/{self.sun_azimuth:.1f}°"
            )

class SunWidget(QWidget):
    sun_position_updated = pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Apply responsive stylesheet
        self.setStyleSheet(get_responsive_stylesheet())
        
        # Sun Calculation Thread
        self.sun_thread = SunCalculationThread()
        self.sun_thread.sun_data_updated.connect(self.update_sun_data)
        self.sun_thread.status_updated.connect(self.update_status)
        self.sun_thread.start()

        self.init_ui()

    def init_ui(self):
        """Initialize user interface"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Title Group
        title_group = QGroupBox("Sun Tracking")
        title_layout = QVBoxLayout()
        title_label = QLabel("☀️ Sun Position & Tracking")
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
        
        location_layout.addWidget(QLabel("Altitude (m):"), 1, 0)
        self.alt_input = QLineEdit(str(SETTINGS["location"]["altitude"]))
        self.alt_input.setMaximumWidth(100)
        location_layout.addWidget(self.alt_input, 1, 1)
        
        self.update_loc_btn = QPushButton("Update Location")
        self.update_loc_btn.clicked.connect(self.update_location)
        location_layout.addWidget(self.update_loc_btn, 1, 2, 1, 2)
        
        location_group.setLayout(location_layout)
        main_layout.addWidget(location_group)

        # Sun Position Display Group
        position_group = QGroupBox("Current Sun Position")
        position_layout = QGridLayout()
        
        # Altitude
        position_layout.addWidget(QLabel("Altitude:"), 0, 0)
        self.alt_label = QLabel("0.0°")
        self.alt_label.setStyleSheet("color: #ffcc00; font-weight: bold; font-size: 16px;")
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
        self.az_label.setStyleSheet("color: #ffcc00; font-weight: bold; font-size: 16px;")
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

        # Sun Path Visualization
        self.sun_path_widget = SunPathWidget()
        main_layout.addWidget(self.sun_path_widget)

        # Sunrise/Sunset Times Group
        times_group = QGroupBox("Sunrise & Sunset Times")
        times_layout = QGridLayout()
        
        times_layout.addWidget(QLabel("Sunrise:"), 0, 0)
        self.sunrise_label = QLabel("06:00:00")
        self.sunrise_label.setStyleSheet("color: #00a8ff; font-weight: bold; font-size: 14px;")
        times_layout.addWidget(self.sunrise_label, 0, 1)
        
        times_layout.addWidget(QLabel("Sunset:"), 1, 0)
        self.sunset_label = QLabel("18:00:00")
        self.sunset_label.setStyleSheet("color: #ff8800; font-weight: bold; font-size: 14px;")
        times_layout.addWidget(self.sunset_label, 1, 1)
        
        times_group.setLayout(times_layout)
        main_layout.addWidget(times_group)

        # Tracking Controls Group
        control_group = QGroupBox("Tracking Controls")
        control_layout = QHBoxLayout()
        
        self.start_track_btn = QPushButton("▶ Start Tracking")
        self.start_track_btn.clicked.connect(self.sun_thread.start_tracking)
        self.start_track_btn.setStyleSheet("background-color: #444444; color: white;")
        
        self.stop_track_btn = QPushButton("⏸ Stop Tracking")
        self.stop_track_btn.clicked.connect(self.sun_thread.stop_tracking)
        self.stop_track_btn.setEnabled(False)
        self.stop_track_btn.setStyleSheet("background-color: #444444; color: white;")
        
        self.goto_btn = QPushButton("📍 Point to Sun")
        self.goto_btn.clicked.connect(self.point_to_sun)
        self.goto_btn.setStyleSheet("background-color: #ffcc00; color: black;")
        
        control_layout.addWidget(self.start_track_btn)
        control_layout.addWidget(self.stop_track_btn)
        control_layout.addWidget(self.goto_btn)
        control_group.setLayout(control_layout)
        main_layout.addWidget(control_group)

        # Status Group
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout()
        self.status_label = QLabel("Status: Calculating sun position...")
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
            alt = float(self.alt_input.text())
            
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                raise ValueError("Invalid coordinates")
            
            self.sun_thread.set_location(lat, lon)
            SETTINGS["location"]["altitude"] = alt
            self.status_label.setText("Status: Location updated")
            self.status_label.setStyleSheet("color: #00ff00; font-weight: bold;")
        except ValueError as e:
            self.status_label.setText(f"Status: Invalid location - {str(e)}")
            self.status_label.setStyleSheet("color: #ff4444; font-weight: bold;")

    def update_sun_data(self, sun_data):
        """Update sun data display"""
        # Update labels
        self.alt_label.setText(f"{sun_data['altitude']:.1f}°")
        self.az_label.setText(f"{sun_data['azimuth']:.1f}°")
        self.sunrise_label.setText(sun_data['sunrise'])
        self.sunset_label.setText(sun_data['sunset'])
        
        # Update progress bars
        self.alt_progress.setValue(int(sun_data['altitude']))
        self.az_progress.setValue(int(sun_data['azimuth']))
        
        # Update visibility
        if sun_data['visible']:
            self.vis_label.setText("Above Horizon")
            self.vis_label.setStyleSheet("color: #00ff00; font-weight: bold;")
        else:
            self.vis_label.setText("Below Horizon")
            self.vis_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        
        # Update sun path visualization
        self.sun_path_widget.update_sun_position(
            sun_data['altitude'],
            sun_data['azimuth'],
            sun_data['visible']
        )
        
        # Update tracking button states
        if sun_data['tracking']:
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
        if sun_data['tracking'] and sun_data['visible']:
            self.sun_position_updated.emit(
                sun_data['altitude'],
                sun_data['azimuth']
            )

    def point_to_sun(self):
        """Point telescope to current sun position"""
        if hasattr(self.sun_thread, 'current_sun_data'):
            sun_data = self.sun_thread.current_sun_data
            if sun_data['visible']:
                self.sun_position_updated.emit(
                    sun_data['altitude'],
                    sun_data['azimuth']
                )
                self.status_label.setText("Status: Pointing to sun...")
                self.status_label.setStyleSheet("color: #00ff00; font-weight: bold;")
            else:
                self.status_label.setText("Status: Sun is below horizon")
                self.status_label.setStyleSheet("color: #ff4444; font-weight: bold;")

    def update_status(self, status):
        """Update status label"""
        self.status_label.setText(f"Status: {status}")

    def cleanup(self):
        """Cleanup sun thread"""
        self.sun_thread.stop()