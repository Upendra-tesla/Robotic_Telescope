import cv2
import numpy as np
import os
import datetime  # Add missing import
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QComboBox, QSpinBox, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QImage, QPixmap

# Camera Thread (thread-safe for Pi 5 - NO pigpio, NO Picamera2)
class CameraThread(QThread):
    frame_ready = pyqtSignal(np.ndarray)  # Emits OpenCV frame
    error_occurred = pyqtSignal(str)      # Emits error message

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.running = False
        self.recording = False
        self.cap = None
        self.out = None
        self.save_path = config["camera"]["video_save_path"]

        # Create save directories (Pi 5 compatible)
        os.makedirs(self.save_path, exist_ok=True)
        os.makedirs(config["camera"]["image_save_path"], exist_ok=True)

    def start_camera(self):
        """Start camera stream (works with USB webcam/Pi Camera)"""
        self.running = True
        self.start()

    def stop_camera(self):
        """Stop camera stream and clean up"""
        self.running = False
        self.recording = False
        if self.out:
            self.out.release()
        if self.cap:
            self.cap.release()
        self.wait()

    def toggle_recording(self):
        """Start/stop video recording (no pigpio/Picamera2)"""
        if not self.running:
            self.error_occurred.emit("Start camera first before recording!")
            return

        self.recording = not self.recording
        if self.recording:
            # Use OpenCV (no encode streams - fixes h264 error)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.save_path}/telescope_video_{timestamp}.mp4"
            
            # Pi 5-compatible codec
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            width = int(self.config["camera"]["default_resolution"].split("x")[0])
            height = int(self.config["camera"]["default_resolution"].split("x")[1])
            fps = self.config["camera"]["default_fps"]
            
            self.out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
            self.error_occurred.emit(f"Recording started: {filename}")
        else:
            if self.out:
                self.out.release()
                self.out = None
            self.error_occurred.emit("Recording stopped")

    def capture_image(self):
        """Capture still image (no pigpio)"""
        if not self.running:
            self.error_occurred.emit("Start camera first before capturing!")
            return

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.config['camera']['image_save_path']}/telescope_image_{timestamp}.jpg"
        
        ret, frame = self.cap.read()
        if ret:
            cv2.imwrite(filename, frame)
            self.error_occurred.emit(f"Image saved: {filename}")
        else:
            self.error_occurred.emit("Failed to capture image (no frame)")

    def run(self):
        """Camera capture loop (no pigpio/Picamera2)"""
        try:
            # Use OpenCV (universal - no Picamera2 encode errors)
            self.cap = cv2.VideoCapture(0)  # 0 = default camera
            
            # Set resolution/FPS from config
            width = int(self.config["camera"]["default_resolution"].split("x")[0])
            height = int(self.config["camera"]["default_resolution"].split("x")[1])
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_FPS, self.config["camera"]["default_fps"])

            if not self.cap.isOpened():
                self.error_occurred.emit("Could not open camera (check hardware)")
                self.running = False
                return

            while self.running:
                ret, frame = self.cap.read()
                if ret:
                    self.frame_ready.emit(frame)
                    if self.recording and self.out:
                        self.out.write(frame)
                else:
                    self.error_occurred.emit("Lost camera connection")
                    break

        except Exception as e:
            self.error_occurred.emit(f"Camera error: {str(e)}")
        finally:
            # Cleanup
            if self.cap:
                self.cap.release()
            if self.out:
                self.out.release()

# Main Camera Widget (FIXED: camera_thread initialized BEFORE _setup_ui)
class CameraWidget(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.layout = QVBoxLayout()

        # CRITICAL FIX: Initialize camera_thread BEFORE _setup_ui()
        self.camera_thread = CameraThread(config)
        self.camera_thread.frame_ready.connect(self._update_frame)
        self.camera_thread.error_occurred.connect(self._show_status)

        # Now setup UI (buttons connect to existing camera_thread)
        self._setup_ui()

        # Camera preview label (added after _setup_ui for order)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #000000;")
        self.layout.addWidget(self.preview_label)

        self.setLayout(self.layout)

    def _setup_ui(self):
        """Create camera control UI (touch-friendly, no pigpio)"""
        # Title
        self.layout.addWidget(QLabel("<h2>Camera Control</h2>"))

        # Camera Settings
        settings_group = QGroupBox("Camera Settings")
        settings_layout = QHBoxLayout()

        # Resolution
        settings_layout.addWidget(QLabel("Resolution:"))
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["640x480", "1280x720", "1920x1080"])
        self.resolution_combo.setCurrentText(self.config["camera"]["default_resolution"])
        settings_layout.addWidget(self.resolution_combo)

        # FPS
        settings_layout.addWidget(QLabel("FPS:"))
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(10, 60)
        self.fps_spin.setValue(self.config["camera"]["default_fps"])
        settings_layout.addWidget(self.fps_spin)

        settings_group.setLayout(settings_layout)
        self.layout.addWidget(settings_group)

        # Control Buttons
        control_layout = QHBoxLayout()

        # Start/Stop Camera
        self.start_btn = QPushButton("Start Camera")
        self.start_btn.clicked.connect(self._toggle_camera)
        control_layout.addWidget(self.start_btn)

        # Capture Image (now connects to existing camera_thread)
        self.capture_btn = QPushButton("Capture Image")
        self.capture_btn.clicked.connect(self.camera_thread.capture_image)
        self.capture_btn.setEnabled(False)
        control_layout.addWidget(self.capture_btn)

        # Record Video
        self.record_btn = QPushButton("Start Recording")
        self.record_btn.clicked.connect(self._toggle_recording)
        self.record_btn.setEnabled(False)
        control_layout.addWidget(self.record_btn)

        self.layout.addLayout(control_layout)

        # Status Label
        self.status_label = QLabel("Status: Camera stopped")
        self.status_label.setStyleSheet("color: #ffffff;")
        self.layout.addWidget(self.status_label)

    def _toggle_camera(self):
        """Start/stop camera stream (no pigpio)"""
        if not self.camera_thread.running:
            # Update config
            self.config["camera"]["default_resolution"] = self.resolution_combo.currentText()
            self.config["camera"]["default_fps"] = self.fps_spin.value()
            
            # Start camera
            self.camera_thread.start_camera()
            self.start_btn.setText("Stop Camera")
            self.capture_btn.setEnabled(True)
            self.record_btn.setEnabled(True)
            self.status_label.setText("Status: Camera running")
        else:
            # Stop camera
            self.camera_thread.stop_camera()
            self.start_btn.setText("Start Camera")
            self.capture_btn.setEnabled(False)
            self.record_btn.setEnabled(False)
            self.record_btn.setText("Start Recording")
            self.status_label.setText("Status: Camera stopped")
            self.preview_label.clear()

    def _toggle_recording(self):
        """Start/stop video recording (no pigpio)"""
        self.camera_thread.toggle_recording()
        if self.camera_thread.recording:
            self.record_btn.setText("Stop Recording")
            self.status_label.setText("Status: Recording video...")
        else:
            self.record_btn.setText("Start Recording")
            self.status_label.setText("Status: Camera running (not recording)")

    def _update_frame(self, frame):
        """Convert OpenCV frame to PyQt5 pixmap (Pi 5 optimized)"""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        
        qt_frame = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_frame).scaled(
            self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.preview_label.setPixmap(pixmap)

    def _show_status(self, message):
        """Update status label (no pigpio errors)"""
        self.status_label.setText(f"Status: {message}")
        if "error" in message.lower():
            QMessageBox.critical(self, "Camera Error", message)

    def closeEvent(self, event):
        """Clean up camera thread (no pigpio)"""
        self.camera_thread.stop_camera()
        event.accept()