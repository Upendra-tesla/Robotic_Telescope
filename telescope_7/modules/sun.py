import ephem
import datetime
from threading import Lock
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QCheckBox, QDoubleSpinBox, QGroupBox, QFrame,
    QMessageBox, QSizePolicy
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer

# Solar tracking thread (Pi 5 / 800×480 Optimized)
class SunTrackingThread(QThread):
    position_signal = pyqtSignal(float, float)
    error_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    sunrise_sunset_signal = pyqtSignal(str, str)

    def __init__(self, lat, lon):
        super().__init__()
        self.running = True
        self.lock = Lock()
        self.lat = float(lat)
        self.lon = float(lon)
        self.auto_track = False
        self.update_interval = 2  # 2s update (Pi 5 responsive)

    def set_location(self, lat, lon):
        """Thread-safe location update (decimal precision)"""
        with self.lock:
            self.lat = float(lat)
            self.lon = float(lon)
        self.status_signal.emit(f"📍 Location: {lat:.2f}° N, {lon:.2f}° E")
        self.calculate_sunrise_sunset()  # Update sunrise/sunset with new location

    def set_auto_track(self, enable):
        """Thread-safe auto-track toggle (safety-locked)"""
        with self.lock:
            self.auto_track = enable
        status = "ENABLED" if enable else "DISABLED"
        self.status_signal.emit(f"🔄 Auto-track: {status} (filter required!)")

    def calculate_sun_position(self):
        """Pi 5 optimized sun position calculation (safety critical)"""
        try:
            observer = ephem.Observer()
            observer.lat = str(self.lat)
            observer.lon = str(self.lon)
            observer.date = ephem.now()  # Faster than datetime (ephem native)
            observer.pressure = 0  # Disable refraction (faster calculation)
            sun = ephem.Sun(observer)
            
            # Convert radians to degrees
            alt = float(sun.alt) * 180.0 / ephem.pi
            az = float(sun.az) * 180.0 / ephem.pi
            return alt, az
        except Exception as e:
            self.error_signal.emit(f"Calc Error: {str(e)[:25]}...")
            return 0.0, 0.0

    def calculate_sunrise_sunset(self):
        """Calculate sunrise/sunset times (Pi 5 optimized)"""
        try:
            observer = ephem.Observer()
            observer.lat = str(self.lat)
            observer.lon = str(self.lon)
            observer.date = ephem.now()
            
            # Calculate sunrise/sunset
            sunrise = ephem.localtime(observer.next_rising(ephem.Sun()))
            sunset = ephem.localtime(observer.next_setting(ephem.Sun()))
            
            # Format times (ultra-compact for 800×480)
            sunrise_str = sunrise.strftime("%H:%M")
            sunset_str = sunset.strftime("%H:%M")
            
            self.sunrise_sunset_signal.emit(sunrise_str, sunset_str)
            self.status_signal.emit(f"🌅 {sunrise_str} | 🌇 {sunset_str}")
        except Exception as e:
            self.error_signal.emit(f"Sunrise Error: {str(e)[:25]}...")

    def run(self):
        """Main tracking loop (low CPU for Pi 5)"""
        while self.running:
            with self.lock:
                auto_track = self.auto_track
                update_interval = self.update_interval

            if auto_track:
                alt, az = self.calculate_sun_position()
                self.position_signal.emit(alt, az)
            
            # Reduced sleep for responsiveness (800×480)
            self.msleep(update_interval * 500)

    def stop(self):
        """Graceful thread shutdown"""
        with self.lock:
            self.running = False
        self.wait()

# Main Sun Widget (800×480 Ultra-Compact + Lat/Lon Same Row)
class SunTrackingWidget(QWidget):
    slew_to_sun = pyqtSignal(float, float)
    lat_lon_updated = pyqtSignal(float, float)
    auto_track_check = pyqtSignal(bool)

    def __init__(self, lat, lon):
        super().__init__()
        self.lat = float(lat)
        self.lon = float(lon)

        # Safety critical: Solar filter check
        self.filter_checked = False

        # Tracking thread (Pi 5 optimized)
        self.tracking_thread = SunTrackingThread(lat, lon)
        self.tracking_thread.position_signal.connect(self.update_sun_position)
        self.tracking_thread.error_signal.connect(self.show_error)
        self.tracking_thread.status_signal.connect(self.update_status)
        self.tracking_thread.sunrise_sunset_signal.connect(self.update_sunrise_sunset)
        
        # Start tracking thread
        self.tracking_thread.start()

        # UI Setup (800×480 Ultra-Compact + Lat/Lon Same Row)
        self.init_ui()

        # Initial sunrise/sunset update
        self.tracking_thread.calculate_sunrise_sunset()

    def init_ui(self):
        layout = QVBoxLayout(self)
        # ULTRA-COMPACT spacing/margins (critical for 800×480)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        # 1. Title (Safety Critical + Compact)
        title = QLabel("Solar Tracking (Filter REQUIRED!)")
        title.setStyleSheet("font-size: 12px; font-weight: bold; color: #e74c3c;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 2. Solar Filter Warning (Safety Critical + Compact)
        filter_frame = QFrame()
        filter_frame.setStyleSheet("background-color: #ffebee; border-radius: 3px; padding: 4px; border: 1px solid #e74c3c;")
        filter_layout = QVBoxLayout(filter_frame)
        filter_layout.setContentsMargins(2, 2, 2, 2)
        
        self.filter_check = QCheckBox("✅ Solar filter installed (SAFETY)")
        self.filter_check.setStyleSheet("font-size: 10px; color: #e74c3c; font-weight: bold;")
        self.filter_check.stateChanged.connect(self.toggle_filter)
        filter_layout.addWidget(self.filter_check)
        layout.addWidget(filter_frame)

        # 3. Current Sun Position (Ultra-Compact Display)
        pos_frame = QFrame()
        pos_frame.setStyleSheet("background-color: #f8f9fa; border-radius: 3px; padding: 4px;")
        pos_layout = QHBoxLayout(pos_frame)  # HBox for horizontal compact layout
        pos_layout.setContentsMargins(2, 2, 2, 2)
        pos_layout.setSpacing(8)
        
        self.alt_label = QLabel(f"Alt: -- °")
        self.az_label = QLabel(f"Az: -- °")
        self.alt_label.setStyleSheet("font-size: 10px; color: #2c3e50; font-weight: bold;")
        self.az_label.setStyleSheet("font-size: 10px; color: #2c3e50; font-weight: bold;")
        
        pos_layout.addWidget(self.alt_label)
        pos_layout.addStretch(1)
        pos_layout.addWidget(self.az_label)
        layout.addWidget(pos_frame)

        # 4. Sunrise/Sunset Info (800×480 Ultra-Compact)
        sunrise_frame = QFrame()
        sunrise_frame.setStyleSheet("background-color: #f8f9fa; border-radius: 3px; padding: 4px;")
        sunrise_layout = QHBoxLayout(sunrise_frame)  # HBox for compactness
        sunrise_layout.setContentsMargins(2, 2, 2, 2)
        sunrise_layout.setSpacing(8)
        
        self.sunrise_label = QLabel("Sunrise: --:--")
        self.sunset_label = QLabel("Sunset: --:--")
        self.sunrise_label.setStyleSheet("font-size: 9px; color: #666;")
        self.sunset_label.setStyleSheet("font-size: 9px; color: #666;")
        
        sunrise_layout.addWidget(self.sunrise_label)
        sunrise_layout.addStretch(1)
        sunrise_layout.addWidget(self.sunset_label)
        layout.addWidget(sunrise_frame)

        # 5. Location Settings (SAME ROW + Ultra-Compact)
        loc_group = QGroupBox("Location (Lat/Lon)")
        loc_group.setStyleSheet("font-size: 10px;")
        loc_layout = QHBoxLayout(loc_group)  # SAME ROW (HBox)
        loc_layout.setContentsMargins(3, 3, 3, 3)
        loc_layout.setSpacing(2)  # MINIMAL spacing between elements
        
        # Latitude (Label + Spin Box - Ultra-Compact)
        lat_row = QHBoxLayout()
        lat_row.setSpacing(1)  # No gap between label/spin
        lat_row.addWidget(QLabel("Lat:", styleSheet="font-size: 8px;"))
        self.lat_spin = QDoubleSpinBox()
        self.lat_spin.setRange(-90.0, 90.0)
        self.lat_spin.setDecimals(4)
        self.lat_spin.setValue(self.lat)
        self.lat_spin.setStyleSheet("font-size: 8px; padding: 1px;")
        self.lat_spin.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.lat_spin.setFixedWidth(90)  # TINY width (fits 4 decimals)
        lat_row.addWidget(self.lat_spin)
        loc_layout.addLayout(lat_row)
        
        # Longitude (Label + Spin Box - Ultra-Compact)
        lon_row = QHBoxLayout()
        lon_row.setSpacing(1)  # No gap between label/spin
        lon_row.addWidget(QLabel("Lon:", styleSheet="font-size: 8px;"))
        self.lon_spin = QDoubleSpinBox()
        self.lon_spin.setRange(-180.0, 180.0)
        self.lon_spin.setDecimals(4)
        self.lon_spin.setValue(self.lon)
        self.lon_spin.setStyleSheet("font-size: 8px; padding: 1px;")
        self.lon_spin.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.lon_spin.setFixedWidth(90)  # TINY width (fits 4 decimals)
        lon_row.addWidget(self.lon_spin)
        loc_layout.addLayout(lon_row)
        
        # Save Button (Ultra-Compact + Aligned Right)
        self.save_loc_btn = QPushButton("Save")
        self.save_loc_btn.setStyleSheet("""
            QPushButton { 
                background-color: #3498db; 
                color: white; 
                border: none; 
                border-radius: 3px; 
                padding: 2px 5px; 
                font-size: 8px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        self.save_loc_btn.setFixedWidth(60)  # Micro width
        self.save_loc_btn.clicked.connect(self.update_location)
        loc_layout.addStretch(1)  # Push button to right
        loc_layout.addWidget(self.save_loc_btn)
        
        layout.addWidget(loc_group)

        # 6. Control Buttons (800×480 Ultra-Compact + Safety Lock)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(5)
        
        self.slew_btn = QPushButton("Slew to Sun")
        self.auto_track_btn = QCheckBox("Auto Track")
        
        # Slew Button Style (Ultra-Compact)
        self.slew_btn.setStyleSheet("""
            QPushButton { 
                background-color: #3498db; 
                color: white; 
                border: none; 
                border-radius: 3px; 
                padding: 3px 5px; 
                font-size: 9px;
                flex: 1;
            }
            QPushButton:disabled { background-color: #bdc3c7; }
            QPushButton:hover:enabled { background-color: #2980b9; }
        """)
        
        # Auto Track Checkbox Style (Compact)
        self.auto_track_btn.setStyleSheet("font-size: 9px; margin-left: 5px;")
        
        # Disable buttons by default (safety lock)
        self.slew_btn.setEnabled(False)
        self.auto_track_btn.setEnabled(False)
        
        # Connect buttons
        self.slew_btn.clicked.connect(self.slew_to_sun_position)
        self.auto_track_btn.stateChanged.connect(self.toggle_auto_track)
        
        # Add to layout
        btn_layout.addWidget(self.slew_btn)
        btn_layout.addWidget(self.auto_track_btn)
        layout.addLayout(btn_layout)

    def toggle_filter(self, state):
        """Safety: Enable/disable controls based on filter check"""
        self.filter_checked = (state == Qt.Checked)
        self.slew_btn.setEnabled(self.filter_checked)
        self.auto_track_btn.setEnabled(self.filter_checked)
        
        if self.filter_checked:
            self.update_status("⚠️ Filter confirmed - controls enabled")
        else:
            self.update_status("❌ Filter NOT confirmed - controls disabled")
            # Disable auto-track if filter is unchecked
            if self.auto_track_btn.isChecked():
                self.auto_track_btn.setChecked(False)
                self.tracking_thread.set_auto_track(False)

    def update_status(self, status_msg):
        """Update status messages (compact for small screen)"""
        pass  # Can connect to main status bar if needed

    def update_sun_position(self, alt, az):
        """Update sun position display (compact format)"""
        self.alt_label.setText(f"Alt: {alt:.1f} °")
        self.az_label.setText(f"Az: {az:.1f} °")
        # Emit position for motor control
        self.slew_to_sun.emit(alt, az)

    def update_sunrise_sunset(self, sunrise_str, sunset_str):
        """Update sunrise/sunset display (compact format)"""
        self.sunrise_label.setText(f"Sunrise: {sunrise_str}")
        self.sunset_label.setText(f"Sunset: {sunset_str}")

    def slew_to_sun_position(self):
        """Slew telescope to current sun position (safety critical)"""
        if not self.filter_checked:
            QMessageBox.critical(self, "SAFETY WARNING", 
                                "Solar filter required!\nDamage risk!", 
                                QMessageBox.Ok)
            return

        alt, az = self.tracking_thread.calculate_sun_position()
        self.update_sun_position(alt, az)
        # Compact message box (short text for small screen)
        QMessageBox.information(self, "Slew to Sun", 
                               f"Move to Sun:\nAlt: {alt:.1f}° | Az: {az:.1f}°")

    def toggle_auto_track(self, state):
        """Toggle auto-tracking on/off (safety-locked)"""
        enable = (state == Qt.Checked)
        if enable and not self.filter_checked:
            QMessageBox.critical(self, "SAFETY ERROR", "Solar filter required!")
            self.auto_track_btn.setChecked(False)
            return
        
        self.tracking_thread.set_auto_track(enable)
        self.auto_track_check.emit(enable)
        # Compact status update
        status = "On" if enable else "Off"
        QMessageBox.information(self, "Auto Track", f"Sun tracking {status}")

    def update_location(self):
        """Update location coordinates (compact feedback)"""
        self.lat = self.lat_spin.value()
        self.lon = self.lon_spin.value()
        self.tracking_thread.set_location(self.lat, self.lon)
        self.lat_lon_updated.emit(self.lat, self.lon)
        # Update sunrise/sunset with new location
        self.tracking_thread.calculate_sunrise_sunset()
        # Compact message box
        QMessageBox.information(self, "Location Updated", 
                               f"Lat: {self.lat:.4f}°\nLon: {self.lon:.4f}°")

    def show_error(self, error_msg):
        """Show compact error messages"""
        QMessageBox.critical(self, "Error", error_msg[:50], QMessageBox.Ok)

    def close(self):
        """Cleanup on widget close"""
        self.tracking_thread.stop()