"""
Webcam Control Module
Optimized for Raspberry Pi 5 (800x480 Touchscreen)
Graceful Handling of Missing Settings/Camera
FIXED: QGridLayout Import Error
"""
import sys
import time
import cv2
import logging
import os
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QComboBox, QSlider, QCheckBox, QFileDialog,
    QProgressBar, QMessageBox, QGridLayout  # FIX: Added QGridLayout to imports
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QMutex, QMutexLocker
from PyQt5.QtGui import QImage, QPixmap, QFont

# Fixed Import Logic
try:
    from . import SETTINGS, get_responsive_stylesheet, save_settings
except ImportError:
    import modules
    SETTINGS = modules.SETTINGS
    get_responsive_stylesheet = modules.get_responsive_stylesheet
    save_settings = modules.save_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --------------------------
# Camera Thread (Safe Initialization)
# --------------------------
class CameraThread(QThread):
    frame_update = pyqtSignal(QImage)
    status_update = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    recording_progress = pyqtSignal(int)
    
    def __init__(self, camera_id, resolution="640x480"):
        super().__init__()
        self.mutex = QMutex()
        self.running = False
        self.recording = False
        self.camera_id = camera_id
        self.cap = None
        
        # Parse resolution (safe fallback)
        try:
            self.width, self.height = map(int, resolution.split('x'))
        except:
            self.width, self.height = 640, 480  # Default fallback
        
        # Camera settings (safe access to SETTINGS)
        self.framerate = SETTINGS["camera"].get("framerate", 30)
        self.recording_format = SETTINGS["camera"].get("recording_format", "mp4")
        self.video_duration = SETTINGS["camera"].get("video_duration", 300)  # Safe fallback
        self.recording_quality = SETTINGS["camera"].get("recording_quality", 80)
        self.flip_horizontal = SETTINGS["camera"].get("flip_horizontal", False)
        self.flip_vertical = SETTINGS["camera"].get("flip_vertical", False)
        
        # Recording variables
        self.out = None
        self.recording_start_time = 0
        self.recording_filepath = ""
        
        # Create recordings directory
        self.recording_dir = Path(__file__).parent.parent / "recordings"
        self.recording_dir.mkdir(exist_ok=True)

    def init_camera(self):
        """Initialize camera (safe fallback)"""
        locker = QMutexLocker(self.mutex)
        
        try:
            # Release existing capture
            if self.cap:
                self.cap.release()
            
            # Initialize camera (try multiple IDs if needed)
            self.cap = cv2.VideoCapture(self.camera_id)
            if not self.cap.isOpened():
                # Fallback to camera 0 if selected ID fails
                self.cap = cv2.VideoCapture(0)
                if not self.cap.isOpened():
                    raise Exception("No camera detected")
            
            # Set camera properties (safe)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_FPS, self.framerate)
            
            logger.info(f"Camera initialized (ID: {self.camera_id}, Res: {self.width}x{self.height})")
            self.status_update.emit(f"Camera ready: {self.width}x{self.height}")
            
        except Exception as e:
            error_msg = f"Camera init failed: {str(e)}"
            logger.error(error_msg)
            self.error_signal.emit(error_msg)
            self.cap = None

    def start_recording(self):
        """Start video recording (safe)"""
        locker = QMutexLocker(self.mutex)
        
        if not self.cap or not self.cap.isOpened():
            self.error_signal.emit("Cannot record - camera not initialized")
            return
        
        if self.recording:
            self.stop_recording()
        
        # Create filename
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.recording_filepath = str(self.recording_dir / f"recording_{timestamp}.{self.recording_format}")
        
        # Video writer setup
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # MP4 default
        if self.recording_format.lower() == "avi":
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
        
        self.out = cv2.VideoWriter(
            self.recording_filepath,
            fourcc,
            self.framerate,
            (self.width, self.height)
        )
        
        if not self.out.isOpened():
            self.error_signal.emit("Failed to create video file")
            self.out = None
            return
        
        self.recording = True
        self.recording_start_time = time.time()
        logger.info(f"Recording started: {self.recording_filepath}")
        self.status_update.emit(f"Recording: {os.path.basename(self.recording_filepath)}")

    def stop_recording(self):
        """Stop video recording"""
        locker = QMutexLocker(self.mutex)
        
        if self.recording and self.out:
            self.out.release()
            self.out = None
            self.recording = False
            logger.info(f"Recording stopped: {self.recording_filepath}")
            self.status_update.emit(f"Recording saved: {os.path.basename(self.recording_filepath)}")

    def capture_image(self):
        """Capture single image"""
        locker = QMutexLocker(self.mutex)
        
        if not self.cap or not self.cap.isOpened():
            self.error_signal.emit("Cannot capture - camera not initialized")
            return
        
        # Create snapshots directory
        snapshot_dir = Path(__file__).parent.parent / "snapshots"
        snapshot_dir.mkdir(exist_ok=True)
        
        # Capture frame
        ret, frame = self.cap.read()
        if ret:
            # Apply flips
            if self.flip_horizontal:
                frame = cv2.flip(frame, 1)
            if self.flip_vertical:
                frame = cv2.flip(frame, 0)
            
            # Save image
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filepath = str(snapshot_dir / f"snapshot_{timestamp}.jpg")
            cv2.imwrite(filepath, frame)
            logger.info(f"Image captured: {filepath}")
            self.status_update.emit(f"Saved: {os.path.basename(filepath)}")
        else:
            self.error_signal.emit("Failed to capture image")

    def run(self):
        """Main camera loop"""
        self.running = True
        self.init_camera()
        
        while self.running:
            try:
                if self.cap and self.cap.isOpened():
                    # Read frame
                    ret, frame = self.cap.read()
                    if ret:
                        # Apply flips
                        if self.flip_horizontal:
                            frame = cv2.flip(frame, 1)
                        if self.flip_vertical:
                            frame = cv2.flip(frame, 0)
                        
                        # Convert to QImage (for UI)
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        h, w, ch = rgb_frame.shape
                        bytes_per_line = ch * w
                        qt_frame = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
                        self.frame_update.emit(qt_frame.scaled(self.width, self.height, Qt.KeepAspectRatio))
                        
                        # Handle recording
                        if self.recording and self.out:
                            self.out.write(frame)
                            
                            # Update progress
                            elapsed = time.time() - self.recording_start_time
                            progress = int((elapsed / self.video_duration) * 100)
                            self.recording_progress.emit(min(progress, 100))
                            
                            # Auto-stop after duration
                            if elapsed >= self.video_duration:
                                self.stop_recording()
                    else:
                        self.error_signal.emit("Failed to read frame")
                        time.sleep(0.1)
                else:
                    # Mock frame if no camera
                    mock_frame = QImage(self.width, self.height, QImage.Format_RGB888)
                    mock_frame.fill(Qt.gray)
                    self.frame_update.emit(mock_frame)
                    self.status_update.emit("No camera detected (mock mode)")
                    time.sleep(1.0)
                
                time.sleep(1/self.framerate)  # Match framerate
                
            except Exception as e:
                error_msg = f"Camera thread error: {str(e)}"
                logger.error(error_msg)
                self.error_signal.emit(error_msg)
                time.sleep(0.5)

    def stop(self):
        """Stop thread and clean up"""
        locker = QMutexLocker(self.mutex)
        self.running = False
        self.stop_recording()
        if self.cap:
            self.cap.release()
        logger.info("Camera thread stopped")

# --------------------------
# Webcam Widget (800x480 Optimized)
# --------------------------
class WebcamWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(get_responsive_stylesheet())
        self.camera_thread = None
        self.default_resolution = SETTINGS["camera"].get("default_resolution", "640x480")
        self.init_ui()
        self.init_camera()

    def init_ui(self):
        """Create UI (800x480 Touch-Friendly)"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # Title
        title_label = QLabel("Camera Control")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # Camera Selection Group
        cam_group = QGroupBox("Camera Settings")
        cam_layout = QGridLayout()
        cam_layout.setSpacing(6)

        # Camera ID
        cam_layout.addWidget(QLabel("Camera ID:"), 0, 0)
        self.cam_id_combo = QComboBox()
        self.cam_id_combo.addItems(["0", "1", "2"])
        self.cam_id_combo.setCurrentText(str(SETTINGS["camera"].get("default_camera", 0)))
        cam_layout.addWidget(self.cam_id_combo, 0, 1)

        # Resolution
        cam_layout.addWidget(QLabel("Resolution:"), 1, 0)
        self.res_combo = QComboBox()
        self.res_combo.addItems(["320x240", "640x480", "800x480", "1280x720"])
        self.res_combo.setCurrentText(self.default_resolution)
        cam_layout.addWidget(self.res_combo, 1, 1)

        # Apply Settings
        self.apply_cam_btn = QPushButton("Apply Settings")
        self.apply_cam_btn.clicked.connect(self.apply_camera_settings)
        cam_layout.addWidget(self.apply_cam_btn, 2, 0, 1, 2)

        # Flip Options
        self.flip_h_check = QCheckBox("Flip Horizontal")
        self.flip_h_check.setChecked(SETTINGS["camera"].get("flip_horizontal", False))
        self.flip_h_check.stateChanged.connect(self.toggle_flip)
        cam_layout.addWidget(self.flip_h_check, 3, 0)

        self.flip_v_check = QCheckBox("Flip Vertical")
        self.flip_v_check.setChecked(SETTINGS["camera"].get("flip_vertical", False))
        self.flip_v_check.stateChanged.connect(self.toggle_flip)
        cam_layout.addWidget(self.flip_v_check, 3, 1)

        cam_group.setLayout(cam_layout)
        main_layout.addWidget(cam_group)

        # Camera Preview
        self.preview_label = QLabel()
        self.preview_label.setMinimumSize(320, 240)
        self.preview_label.setStyleSheet("border: 1px solid #555555;")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setText("Camera Preview")
        main_layout.addWidget(self.preview_label)

        # Recording Controls
        rec_group = QGroupBox("Recording Controls")
        rec_layout = QVBoxLayout()
        rec_layout.setSpacing(6)

        # Record Buttons
        btn_layout = QHBoxLayout()
        self.record_btn = QPushButton("Start Recording")
        self.record_btn.setMinimumHeight(40)
        self.record_btn.setStyleSheet("background-color: #ff4444; color: white;")
        self.record_btn.clicked.connect(self.toggle_recording)
        btn_layout.addWidget(self.record_btn)

        self.capture_btn = QPushButton("Capture Image")
        self.capture_btn.setMinimumHeight(40)
        self.capture_btn.clicked.connect(self.capture_image)
        btn_layout.addWidget(self.capture_btn)
        rec_layout.addLayout(btn_layout)

        # Recording Progress
        self.rec_progress = QProgressBar()
        self.rec_progress.setRange(0, 100)
        self.rec_progress.setValue(0)
        rec_layout.addWidget(self.rec_progress)

        # Auto-Record
        self.auto_rec_check = QCheckBox("Auto-Record on Start")
        self.auto_rec_check.setChecked(SETTINGS["camera"].get("auto_record", False))
        self.auto_rec_check.stateChanged.connect(self.update_auto_record)
        rec_layout.addWidget(self.auto_rec_check)

        rec_group.setLayout(rec_layout)
        main_layout.addWidget(rec_group)

        # Status
        self.status_label = QLabel("Status: Initializing...")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("background-color: #333333; padding: 5px; border-radius: 3px;")
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)

    def init_camera(self):
        """Initialize camera thread"""
        # Stop existing thread
        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread.wait()
        
        # Start new thread
        cam_id = int(self.cam_id_combo.currentText())
        resolution = self.res_combo.currentText()
        
        self.camera_thread = CameraThread(cam_id, resolution)
        # Connect signals
        self.camera_thread.frame_update.connect(self.update_preview)
        self.camera_thread.status_update.connect(self.update_status)
        self.camera_thread.error_signal.connect(self.show_error)
        self.camera_thread.recording_progress.connect(self.update_recording_progress)
        
        # Start thread
        self.camera_thread.start()
        
        # Auto-record if enabled
        if self.auto_rec_check.isChecked():
            self.toggle_recording()

    def apply_camera_settings(self):
        """Apply camera settings"""
        # Update SETTINGS
        SETTINGS["camera"]["default_camera"] = int(self.cam_id_combo.currentText())
        SETTINGS["camera"]["default_resolution"] = self.res_combo.currentText()
        save_settings()
        
        # Restart camera
        self.init_camera()
        self.update_status(f"Settings applied: Camera {self.cam_id_combo.currentText()}, {self.res_combo.currentText()}")

    def toggle_flip(self):
        """Toggle camera flip settings"""
        SETTINGS["camera"]["flip_horizontal"] = self.flip_h_check.isChecked()
        SETTINGS["camera"]["flip_vertical"] = self.flip_v_check.isChecked()
        save_settings()
        self.update_status(f"Flip: H={self.flip_h_check.isChecked()}, V={self.flip_v_check.isChecked()}")

    def update_auto_record(self):
        """Update auto-record setting"""
        SETTINGS["camera"]["auto_record"] = self.auto_rec_check.isChecked()
        save_settings()

    def toggle_recording(self):
        """Start/stop recording"""
        if self.camera_thread.recording:
            self.camera_thread.stop_recording()
            self.record_btn.setText("Start Recording")
            self.record_btn.setStyleSheet("background-color: #ff4444; color: white;")
            self.rec_progress.setValue(0)
        else:
            self.camera_thread.start_recording()
            self.record_btn.setText("Stop Recording")
            self.record_btn.setStyleSheet("background-color: #44ff44; color: black;")

    def capture_image(self):
        """Capture image"""
        self.camera_thread.capture_image()

    def update_preview(self, frame):
        """Update camera preview"""
        self.preview_label.setPixmap(QPixmap.fromImage(frame))

    def update_recording_progress(self, value):
        """Update recording progress bar"""
        self.rec_progress.setValue(value)

    def update_status(self, message):
        """Update status label"""
        self.status_label.setText(f"Status: {message}")

    def show_error(self, message):
        """Show error message"""
        QMessageBox.critical(self, "Camera Error", message)
        self.update_status(f"ERROR: {message}")

    def cleanup(self):
        """Cleanup camera thread"""
        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread.wait()
        self.update_status("Camera cleaned up")

    def closeEvent(self, event):
        """Handle widget close"""
        self.cleanup()
        event.accept()