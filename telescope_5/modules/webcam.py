import cv2
import numpy as np
import json
import os
import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QComboBox, QSpinBox, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor

# Camera Thread (Pi 5 Optimized)
class CameraThread(QThread):
    frame_ready = pyqtSignal(np.ndarray)
    histogram_ready = pyqtSignal(np.ndarray, np.ndarray, np.ndarray)
    error_occurred = pyqtSignal(str)
    status_updated = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.running = False
        self.recording = False
        self.cap = None
        self.out = None
        
        # Save paths
        self.image_path = config["camera"]["image_save_path"]
        self.video_path = config["camera"]["video_save_path"]
        os.makedirs(self.image_path, exist_ok=True)
        os.makedirs(self.video_path, exist_ok=True)

    def start_camera(self):
        """Start camera with config settings"""
        if not self.running:
            self.running = True
            self.start()
            self.status_updated.emit("Camera started")

    def stop_camera(self):
        """Stop camera and cleanup"""
        self.running = False
        self.recording = False
        if self.out:
            self.out.release()
            self.out = None
        if self.cap:
            self.cap.release()
            self.cap = None
        self.status_updated.emit("Camera stopped")

    def toggle_recording(self):
        """Start/stop video recording"""
        if not self.running:
            self.error_occurred.emit("Start camera first!")
            return

        self.recording = not self.recording
        if self.recording:
            # Get config settings
            res = self.config["camera"]["default_resolution"]
            width = int(res.split("x")[0])
            height = int(res.split("x")[1])
            fps = self.config["camera"]["default_fps"]
            
            # Create video writer
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.video_path}/vid_{timestamp}.mp4"
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
            
            self.status_updated.emit(f"Recording started: {filename}")
        else:
            if self.out:
                self.out.release()
                self.out = None
            self.status_updated.emit("Recording stopped")

    def capture_image(self):
        """Capture still image"""
        if not self.running or not self.cap:
            self.error_occurred.emit("Start camera first!")
            return

        ret, frame = self.cap.read()
        if ret:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.image_path}/img_{timestamp}.jpg"
            cv2.imwrite(filename, frame)
            self.status_updated.emit(f"Image saved: {filename}")
        else:
            self.error_occurred.emit("Failed to capture image")

    def calculate_histogram(self, frame):
        """Calculate RGB histogram (optimized for Pi 5)"""
        chans = cv2.split(frame)
        hist_data = []
        for chan in chans:
            hist = cv2.calcHist([chan], [0], None, [64], [0, 256])
            hist_data.append(hist)
        return hist_data[0], hist_data[1], hist_data[2]

    def run(self):
        """Camera main loop"""
        try:
            # Initialize camera
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                self.error_occurred.emit("Failed to open camera")
                self.running = False
                return

            # Apply config settings
            res = self.config["camera"]["default_resolution"]
            width = int(res.split("x")[0])
            height = int(res.split("x")[1])
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_FPS, self.config["camera"]["default_fps"])

            frame_count = 0
            while self.running:
                ret, frame = self.cap.read()
                if ret:
                    # Emit frame for preview
                    self.frame_ready.emit(frame)
                    
                    # Write to video if recording
                    if self.recording and self.out:
                        self.out.write(frame)
                    
                    # Calculate histogram every 3 frames (CPU optimization)
                    if frame_count % 3 == 0:
                        r_hist, g_hist, b_hist = self.calculate_histogram(frame)
                        self.histogram_ready.emit(r_hist, g_hist, b_hist)
                    
                    frame_count += 1
                else:
                    self.error_occurred.emit("Lost camera connection")
                    break
                
                self.msleep(33)  # ~30fps

        except Exception as e:
            self.error_occurred.emit(f"Camera error: {str(e)}")
        finally:
            self.stop_camera()

# RGB Histogram Widget
class HistogramWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(300, 150)
        self.r_hist = np.zeros((64, 1))
        self.g_hist = np.zeros((64, 1))
        self.b_hist = np.zeros((64, 1))

    def update_histogram(self, r_hist, g_hist, b_hist):
        self.r_hist = r_hist
        self.g_hist = g_hist
        self.b_hist = b_hist
        self.update()

    def paintEvent(self, event):
        """Draw RGB histogram"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Dark background
        painter.fillRect(self.rect(), QColor("#2d2d2d"))
        
        # Get dimensions
        w = self.width()
        h = self.height()
        bin_width = w // 64
        max_height = h - 20

        # Normalize histograms
        max_val = max(np.max(self.r_hist), np.max(self.g_hist), np.max(self.b_hist))
        if max_val == 0:
            max_val = 1

        # Draw Red channel
        painter.setPen(QPen(QColor("#ff0000"), bin_width))
        for i in range(64):
            val = int((self.r_hist[i][0] / max_val) * max_height)
            y = h - val - 10
            painter.drawPoint(i * bin_width + bin_width//2, y)

        # Draw Green channel
        painter.setPen(QPen(QColor("#00ff00"), bin_width))
        for i in range(64):
            val = int((self.g_hist[i][0] / max_val) * max_height)
            y = h - val - 10
            painter.drawPoint(i * bin_width + bin_width//2, y)

        # Draw Blue channel
        painter.setPen(QPen(QColor("#0000ff"), bin_width))
        for i in range(64):
            val = int((self.b_hist[i][0] / max_val) * max_height)
            y = h - val - 10
            painter.drawPoint(i * bin_width + bin_width//2, y)

        # Draw labels
        painter.setPen(QPen(QColor("#ffffff")))
        painter.drawText(10, 15, "RGB Histogram (R: Red, G: Green, B: Blue)")

# Main Webcam Widget
class WebcamWidget(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config

        # Initialize camera thread
        self.camera_thread = CameraThread(config)
        self.camera_thread.frame_ready.connect(self._update_frame)
        self.camera_thread.histogram_ready.connect(self._update_histogram)
        self.camera_thread.error_occurred.connect(self._show_error)
        self.camera_thread.status_updated.connect(self._update_status)

        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        # Camera Settings Group
        settings_group = QGroupBox("Camera Settings")
        settings_layout = QVBoxLayout(settings_group)

        # Resolution
        res_layout = QHBoxLayout()
        res_layout.addWidget(QLabel("Resolution:"))
        self.res_combo = QComboBox()
        self.res_combo.addItems(["640x480", "1280x720", "1920x1080"])
        self.res_combo.setCurrentText(config["camera"]["default_resolution"])
        self.res_combo.currentTextChanged.connect(self._update_resolution)
        res_layout.addWidget(self.res_combo)
        settings_layout.addLayout(res_layout)

        # FPS
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("FPS:"))
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(config["camera"]["default_fps"])
        self.fps_spin.valueChanged.connect(self._update_fps)
        fps_layout.addWidget(self.fps_spin)
        settings_layout.addLayout(fps_layout)

        # Exposure
        exp_layout = QHBoxLayout()
        exp_layout.addWidget(QLabel("Exposure:"))
        self.exp_spin = QSpinBox()
        self.exp_spin.setRange(1, 1000)
        self.exp_spin.setValue(config["camera"]["exposure"])
        self.exp_spin.valueChanged.connect(self._update_exposure)
        exp_layout.addWidget(self.exp_spin)
        settings_layout.addLayout(exp_layout)

        # White Balance
        wb_layout = QHBoxLayout()
        wb_layout.addWidget(QLabel("White Balance:"))
        self.wb_combo = QComboBox()
        self.wb_combo.addItems(["auto", "incandescent", "fluorescent", "daylight", "cloudy"])
        self.wb_combo.setCurrentText(config["camera"]["white_balance"])
        self.wb_combo.currentTextChanged.connect(self._update_white_balance)
        wb_layout.addWidget(self.wb_combo)
        settings_layout.addLayout(wb_layout)

        main_layout.addWidget(settings_group)

        # Camera Control Buttons
        btn_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("▶️ Start Camera")
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        self.start_btn.clicked.connect(self._toggle_camera)
        btn_layout.addWidget(self.start_btn)
        
        self.capture_btn = QPushButton("📷 Capture Image")
        self.capture_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 10px;")
        self.capture_btn.clicked.connect(self.camera_thread.capture_image)
        self.capture_btn.setEnabled(False)
        btn_layout.addWidget(self.capture_btn)
        
        self.record_btn = QPushButton("📹 Start Recording")
        self.record_btn.setStyleSheet("background-color: #ff9800; color: white; padding: 10px;")
        self.record_btn.clicked.connect(self._toggle_recording)
        self.record_btn.setEnabled(False)
        btn_layout.addWidget(self.record_btn)
        
        main_layout.addLayout(btn_layout)

        # Preview + Histogram
        preview_layout = QHBoxLayout()
        
        # Camera Preview
        self.preview_label = QLabel("Camera Preview (Stopped)")
        self.preview_label.setFixedSize(640, 480)
        self.preview_label.setStyleSheet("border: 1px solid #404040; background-color: #000000;")
        self.preview_label.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(self.preview_label)
        
        # RGB Histogram
        self.histogram_widget = HistogramWidget()
        preview_layout.addWidget(self.histogram_widget)
        
        preview_layout.setAlignment(Qt.AlignCenter)
        main_layout.addLayout(preview_layout)

        # Status Bar
        self.status_label = QLabel("Status: Camera stopped")
        self.status_label.setStyleSheet("color: #ffffff; margin-top: 10px;")
        main_layout.addWidget(self.status_label)

    # Toggle Camera Start/Stop
    def _toggle_camera(self):
        if not self.camera_thread.running:
            self.camera_thread.start_camera()
            self.start_btn.setText("⏹️ Stop Camera")
            self.capture_btn.setEnabled(True)
            self.record_btn.setEnabled(True)
        else:
            self.camera_thread.stop_camera()
            self.start_btn.setText("▶️ Start Camera")
            self.capture_btn.setEnabled(False)
            self.record_btn.setEnabled(False)
            self.record_btn.setText("📹 Start Recording")
            self.preview_label.setText("Camera Preview (Stopped)")

    # Toggle Recording
    def _toggle_recording(self):
        self.camera_thread.toggle_recording()
        if self.camera_thread.recording:
            self.record_btn.setText("⏹️ Stop Recording")
        else:
            self.record_btn.setText("📹 Start Recording")

    # Update Preview Frame
    def _update_frame(self, frame):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        
        qt_frame = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_frame).scaled(
            self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.preview_label.setPixmap(pixmap)

    # Update Histogram
    def _update_histogram(self, r_hist, g_hist, b_hist):
        self.histogram_widget.update_histogram(r_hist, g_hist, b_hist)

    # Update Status
    def _update_status(self, msg):
        self.status_label.setText(f"Status: {msg}")

    # Show Error
    def _show_error(self, msg):
        self.status_label.setText(f"Error: {msg}")
        QMessageBox.critical(self, "Camera Error", msg)

    # Update Config Settings
    def _update_resolution(self, res):
        self.config["camera"]["default_resolution"] = res
        self._save_config()

    def _update_fps(self, fps):
        self.config["camera"]["default_fps"] = fps
        self._save_config()

    def _update_exposure(self, exp):
        self.config["camera"]["exposure"] = exp
        self._save_config()

    def _update_white_balance(self, wb):
        self.config["camera"]["white_balance"] = wb
        self._save_config()

    # Save Config
    def _save_config(self):
        os.makedirs("config", exist_ok=True)
        with open("config/settings.json", "w") as f:
            json.dump(self.config, f, indent=4)

    # Safe Close
    def close(self):
        self.camera_thread.stop_camera()
        self.camera_thread.quit()
        self.camera_thread.wait()