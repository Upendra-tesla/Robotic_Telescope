import ephem
import datetime
from threading import Lock
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QCheckBox, QSpinBox, QGroupBox, QFrame,
    QMessageBox
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer

# Moon tracking thread (optimized for small screen updates)
class MoonTrackingThread(QThread):
    position_signal = pyqtSignal(float, float)
    error_signal = pyqtSignal(str)

    def __init__(self, lat, lon):
        super().__init__()
        self.running = True
        self.lock = Lock()
        self.lat = lat
        self.lon = lon
        self.auto_track = False
        self.update_interval = 5  # Seconds (reduced for small screen)

    def set_location(self, lat, lon):
        with self.lock:
            self.lat = lat
            self.lon = lon

    def set_auto_track(self, enable):
        with self.lock:
            self.auto_track = enable

    def calculate_moon_position(self):
        try:
            # Calculate moon position
            observer = ephem.Observer()
            observer.lat = str(self.lat)
            observer.lon = str(self.lon)
            observer.date = datetime.datetime.now()
            moon = ephem.Moon(observer)
            
            # Convert to degrees
            alt = float(moon.alt) * 180.0 / ephem.pi
            az = float(moon.az) * 180.0 / ephem.pi
            return alt, az
        except Exception as e:
            self.error_signal.emit(f"Moon Calculation Error: {str(e)}")
            return 0.0, 0.0

    def run(self):
        while self.running:
            with self.lock:
                auto_track = self.auto_track
                update_interval = self.update_interval

            if auto_track:
                alt, az = self.calculate_moon_position()
                self.position_signal.emit(alt, az)
            
            # Sleep (shorter interval for small screen responsiveness)
            self.msleep(update_interval * 500)

    def stop(self):
        with self.lock:
            self.running = False
        self.wait()

# Main Moon Widget (800×480 optimized)
class MoonTrackingWidget(QWidget):
    slew_to_moon = pyqtSignal(float, float)
    lat_lon_updated = pyqtSignal(float, float)
    auto_track_check = pyqtSignal(bool)

    def __init__(self, lat, lon):
        super().__init__()
        self.lat = lat
        self.lon = lon

        # Tracking thread
        self.tracking_thread = MoonTrackingThread(lat, lon)
        self.tracking_thread.position_signal.connect(self.update_moon_position)
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

        # Title
        title = QLabel("Lunar Tracking")
        title.setObjectName("title_label")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #3498db;")
        layout.addWidget(title)

        # Current Moon Position (compact display)
        pos_frame = QFrame()
        pos_frame.setStyleSheet("background-color: #f8f9fa; border-radius: 4px; padding: 8px;")
        pos_layout = QVBoxLayout(pos_frame)
        self.alt_label = QLabel(f"Moon Altitude: -- °")
        self.az_label = QLabel(f"Moon Azimuth: -- °")
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
        self.slew_btn = QPushButton("Slew to Moon")
        self.auto_track_btn = QCheckBox("Auto Track Moon")
        # Style buttons (match sun widget)
        self.slew_btn.setStyleSheet("""
            QPushButton { 
                background-color: #3498db; 
                color: white; 
                border: none; 
                border-radius: 4px; 
                padding: 6px 8px; 
                font-size: 12px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        self.auto_track_btn.setStyleSheet("font-size: 11px;")
        # Connect buttons
        self.slew_btn.clicked.connect(self.slew_to_moon_position)
        self.auto_track_btn.stateChanged.connect(self.toggle_auto_track)
        # Add to layout (FIX: use addLayout instead of addWidget for QHBoxLayout)
        btn_layout.addWidget(self.slew_btn)
        btn_layout.addWidget(self.auto_track_btn)
        layout.addLayout(btn_layout)  # <-- FIXED LINE (was addWidget)

        # Moon Phase Info (compact for small screen)
        phase_frame = QFrame()
        phase_frame.setStyleSheet("background-color: #f8f9fa; border-radius: 4px; padding: 8px;")
        phase_layout = QVBoxLayout(phase_frame)
        self.phase_label = QLabel("Moon Phase: Calculating...")
        self.phase_label.setStyleSheet("font-size: 11px; color: #666;")
        phase_layout.addWidget(self.phase_label)
        # Add phase update timer (reduced frequency for small screen)
        self.phase_timer = QTimer()
        self.phase_timer.setInterval(60000)  # Update every minute
        self.phase_timer.timeout.connect(self.update_moon_phase)
        self.phase_timer.start()
        self.update_moon_phase()  # Initial update
        layout.addWidget(phase_frame)

    def update_moon_position(self, alt, az):
        self.alt_label.setText(f"Moon Altitude: {alt:.1f} °")
        self.az_label.setText(f"Moon Azimuth: {az:.1f} °")
        # Emit position for motor control
        self.slew_to_moon.emit(alt, az)

    def update_moon_phase(self):
        try:
            moon = ephem.Moon(datetime.datetime.now())
            phase = moon.phase  # 0 = new, 50 = first quarter, 100 = full
            if phase < 10:
                phase_text = "New Moon"
            elif phase < 40:
                phase_text = "Waxing Crescent"
            elif phase < 60:
                phase_text = "First Quarter"
            elif phase < 90:
                phase_text = "Waxing Gibbous"
            elif phase < 100:
                phase_text = "Full Moon"
            elif phase < 140:
                phase_text = "Waning Gibbous"
            elif phase < 160:
                phase_text = "Last Quarter"
            else:
                phase_text = "Waning Crescent"
            self.phase_label.setText(f"Moon Phase: {phase_text} ({phase:.1f}%)")
        except Exception as e:
            self.phase_label.setText(f"Moon Phase: Error ({str(e)[:30]}...)")

    def slew_to_moon_position(self):
        # Calculate current moon position
        alt, az = self.tracking_thread.calculate_moon_position()
        self.update_moon_position(alt, az)
        QMessageBox.information(self, "Slew to Moon", f"Moving to Moon position:\nAlt: {alt:.1f}° | Az: {az:.1f}°")

    def toggle_auto_track(self, state):
        enable = (state == Qt.Checked)
        self.tracking_thread.set_auto_track(enable)
        self.auto_track_check.emit(enable)
        # Status update
        status = "Enabled" if enable else "Disabled"
        QMessageBox.information(self, "Auto Track", f"Moon auto-tracking {status}")

    def update_location(self):
        self.lat = self.lat_spin.value()
        self.lon = self.lon_spin.value()
        self.tracking_thread.set_location(self.lat, self.lon)
        self.lat_lon_updated.emit(self.lat, self.lon)
        # Update moon phase with new location
        self.update_moon_phase()
        QMessageBox.information(self, "Location Updated", f"New location:\nLat: {self.lat}° | Lon: {self.lon}°")

    def show_error(self, error_msg):
        QMessageBox.critical(self, "Moon Tracking Error", error_msg)

    def close(self):
        self.tracking_thread.stop()
        self.phase_timer.stop()