import cv2
import time
import os
import datetime  # FIXED: Moved to top (avoids runtime import issues)
from threading import Lock
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QGroupBox, QSpinBox, QFrame, QMessageBox,
    QCheckBox
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap

# Camera thread (optimized for 640x480 resolution)
class CameraThread(QThread):
    frame_signal = pyqtSignal(QImage)
    error_signal = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self.running = False
        self.recording = False
        self.lock = Lock()
        # Camera config (optimized for small screen)
        self.resolution = (640, 480)  # Match 800×480 window
        self.fps = config["camera"].get("default_fps", 30)
        self.exposure = config["camera"].get("exposure", 100)
        # Recording setup
        self.video_writer = None
        self.save_path = config["camera"]["video_save_path"]
        self.image_path = config["camera"]["image_save_path"]
        # AI temp path (for analysis frames)
        self.ai_temp_path = config["camera"].get("ai_temp_path", "data/camera/temp")
        # Create save directories (including AI temp path)
        os.makedirs(self.save_path, exist_ok=True)
        os.makedirs(self.image_path, exist_ok=True)
        os.makedirs(self.ai_temp_path, exist_ok=True)
        # Store last frame/path for AI analysis
        self.last_frame = None
        self.last_frame_path = None

    def start_camera(self):
        with self.lock:
            self.running = True
        self.start()

    def stop_camera(self):
        with self.lock:
            self.running = False
        # Stop recording if active
        self.stop_recording()
        self.wait()

    def start_recording(self):
        with self.lock:
            if not self.running:
                self.error_signal.emit("Start camera first before recording!")
                return
            self.recording = True
            # Create video writer (optimized for small screen)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.save_path}/telescope_{timestamp}.avi"
            fourcc = cv2.VideoWriter_fourcc(*"XVID")
            self.video_writer = cv2.VideoWriter(filename, fourcc, self.fps, self.resolution)

    def stop_recording(self):
        with self.lock:
            self.recording = False
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None

    def capture_image(self):
        with self.lock:
            if not self.running or self.last_frame is None:
                self.error_signal.emit("Start camera first before capturing!")
                return None
        # Save current frame as image
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.image_path}/telescope_{timestamp}.jpg"
        # Save frame to disk (thread-safe)
        cv2.imwrite(filename, self.last_frame)
        self.last_frame_path = filename  # For AI analysis
        return filename

    def set_exposure(self, exposure):
        with self.lock:
            self.exposure = exposure
            # Update camera exposure if running (immediate effect)
            if self.running:
                self.cap.set(cv2.CAP_PROP_EXPOSURE, exposure)

    def set_fps(self, fps):
        with self.lock:
            self.fps = fps
            # Update camera FPS if running (immediate effect)
            if self.running:
                self.cap.set(cv2.CAP_PROP_FPS, fps)

    def run(self):
        # Initialize camera (use default camera, 640x480)
        self.cap = cv2.VideoCapture(0)  # FIXED: Store cap as instance variable for runtime adjustments
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        self.cap.set(cv2.CAP_PROP_EXPOSURE, self.exposure)

        if not self.cap.isOpened():
            self.error_signal.emit("Failed to open camera!")
            return

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                self.error_signal.emit("Failed to read camera frame!")
                break

            # Flip frame (mirror for usability)
            frame = cv2.flip(frame, 1)

            # Record if enabled
            with self.lock:
                recording = self.recording
            if recording and self.video_writer:
                self.video_writer.write(frame)

            # Convert frame to QImage (for Qt display)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            qt_frame = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            # Resize to fit 800×480 window (critical!)
            qt_frame = qt_frame.scaled(640, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.frame_signal.emit(qt_frame)

            # Save last frame for capture/AI (thread-safe)
            with self.lock:
                self.last_frame = frame.copy()

            # Control frame rate (prevents high CPU usage)
            time.sleep(1/self.fps)

        # Cleanup
        self.cap.release()
        if self.video_writer:
            self.video_writer.release()

# Main Webcam Widget (800×480 optimized)
class WebcamWidget(QWidget):
    analyze_image = pyqtSignal(str)  # For AI integration

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.camera_active = False
        self.recording_active = False

        # Camera thread
        self.camera_thread = CameraThread(config)
        self.camera_thread.frame_signal.connect(self.update_preview)
        self.camera_thread.error_signal.connect(self.show_error)
        
        # UI Setup (compact for 800×480)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        # Small screen spacing
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel("Camera Control (640×480)")
        title.setObjectName("title_label")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #3498db;")
        layout.addWidget(title)

        # Camera Preview (critical for 480px height)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("border: 1px solid #ddd; background-color: #000;")
        # Set fixed size for 800×480 window
        self.preview_label.setFixedSize(640, 320)  # Reduced height to fit
        layout.addWidget(self.preview_label)

        # Camera Controls (compact)
        control_group = QGroupBox("Camera Settings")
        control_group.setStyleSheet("font-size: 12px;")
        control_layout = QHBoxLayout(control_group)
        # Exposure
        exp_layout = QHBoxLayout()
        exp_layout.addWidget(QLabel("Exposure:", styleSheet="font-size: 11px;"))
        self.exp_spin = QSpinBox()
        self.exp_spin.setRange(0, 200)
        self.exp_spin.setValue(self.config["camera"]["exposure"])
        self.exp_spin.setStyleSheet("font-size: 11px; padding: 2px;")
        self.exp_spin.valueChanged.connect(self.update_exposure)
        exp_layout.addWidget(self.exp_spin)
        # FPS
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("FPS:", styleSheet="font-size: 11px;"))
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(10, 30)
        self.fps_spin.setValue(self.config["camera"]["default_fps"])
        self.fps_spin.setStyleSheet("font-size: 11px; padding: 2px;")
        self.fps_spin.valueChanged.connect(self.update_fps)
        fps_layout.addWidget(self.fps_spin)
        # Add to layout
        control_layout.addLayout(exp_layout)
        control_layout.addLayout(fps_layout)
        layout.addWidget(control_group)

        # Action Buttons (smaller for 800×480)
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Camera")
        self.record_btn = QPushButton("Start Recording")
        self.capture_btn = QPushButton("Capture Image")
        self.analyze_btn = QPushButton("Analyze Image (AI)")
        # Style buttons (match motor/ tracking widgets)
        btn_style = """
            QPushButton { 
                background-color: #3498db; 
                color: white; 
                border: none; 
                border-radius: 4px; 
                padding: 6px 8px; 
                font-size: 11px;
            }
            QPushButton:disabled { background-color: #bdc3c7; }
            QPushButton:hover:enabled { background-color: #2980b9; }
        """
        # AI button special style
        ai_btn_style = """
            QPushButton { 
                background-color: #9c27b0; 
                color: white; 
                border: none; 
                border-radius: 4px; 
                padding: 6px 8px; 
                font-size: 11px;
            }
            QPushButton:disabled { background-color: #bdc3c7; }
            QPushButton:hover:enabled { background-color: #7b1fa2; }
        """
        self.start_btn.setStyleSheet(btn_style)
        self.record_btn.setStyleSheet(btn_style)
        self.capture_btn.setStyleSheet(btn_style)
        self.analyze_btn.setStyleSheet(ai_btn_style)
        # Disable non-camera buttons by default
        self.record_btn.setEnabled(False)
        self.capture_btn.setEnabled(False)
        self.analyze_btn.setEnabled(False)
        # Connect buttons
        self.start_btn.clicked.connect(self.toggle_camera)
        self.record_btn.clicked.connect(self.toggle_recording)
        self.capture_btn.clicked.connect(self.capture_image)
        self.analyze_btn.clicked.connect(self.analyze_current_image)
        # Add to layout
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.record_btn)
        btn_layout.addWidget(self.capture_btn)
        btn_layout.addWidget(self.analyze_btn)

        # ======================
        # FIXED: Wrap btn_layout in a QWidget (layouts can't be added directly to addWidget())
        # ======================
        btn_widget = QWidget()  # Create empty widget to host the button layout
        btn_widget.setLayout(btn_layout)
        layout.addWidget(btn_widget)  # Add the widget (not the layout) to the parent layout

        # Status Frame (compact)
        status_frame = QFrame()
        status_frame.setStyleSheet("background-color: #f8f9fa; border-radius: 4px; padding: 8px;")
        status_layout = QVBoxLayout(status_frame)
        self.status_label = QLabel("Status: Camera Off")
        self.status_label.setStyleSheet("font-size: 11px; color: #666;")
        status_layout.addWidget(self.status_label)
        layout.addWidget(status_frame)

        # Auto-record checkbox (for tracking integration)
        auto_layout = QHBoxLayout()
        self.auto_record_check = QCheckBox("Auto-record when tracking")
        self.auto_record_check.setStyleSheet("font-size: 11px;")
        auto_layout.addWidget(self.auto_record_check)
        layout.addLayout(auto_layout)

    def update_preview(self, frame):
        # Update preview with scaled frame (fits 800×480)
        self.preview_label.setPixmap(QPixmap.fromImage(frame))

    def toggle_camera(self):
        if not self.camera_active:
            # Start camera
            self.camera_thread.start_camera()
            self.camera_active = True
            self.start_btn.setText("Stop Camera")
            self.record_btn.setEnabled(True)
            self.capture_btn.setEnabled(True)
            self.analyze_btn.setEnabled(True)
            self.status_label.setText("Status: Camera Active (640×480)")
        else:
            # Stop camera
            self.camera_thread.stop_camera()
            self.camera_active = False
            self.start_btn.setText("Start Camera")
            self.record_btn.setEnabled(False)
            self.capture_btn.setEnabled(False)
            self.analyze_btn.setEnabled(False)
            # Stop recording if active
            if self.recording_active:
                self.toggle_recording()
            self.status_label.setText("Status: Camera Off")
            # Clear preview
            self.preview_label.clear()

    def toggle_recording(self):
        if not self.recording_active:
            # Start recording
            self.camera_thread.start_recording()
            self.recording_active = True
            self.record_btn.setText("Stop Recording")
            self.status_label.setText(f"Status: Recording (FPS: {self.fps_spin.value()})")
        else:
            # Stop recording
            self.camera_thread.stop_recording()
            self.recording_active = False
            self.record_btn.setText("Start Recording")
            self.status_label.setText("Status: Camera Active (Recording Stopped)")

    def capture_image(self):
        # Capture current frame
        filename = self.camera_thread.capture_image()
        if filename:  # Only show message if capture succeeded
            QMessageBox.information(self, "Image Captured", f"Image saved to:\n{filename}")
            # Pass to AI for analysis
            self.analyze_image.emit(filename)

    def analyze_current_image(self):
        # Capture and analyze in one step
        filename = self.camera_thread.capture_image()
        if filename:  # Only proceed if capture succeeded
            self.analyze_image.emit(filename)
            QMessageBox.information(self, "AI Analysis", "Sending image to AI for analysis...\nCheck AI tab for results!")

    def update_exposure(self, value):
        self.camera_thread.set_exposure(value)
        self.status_label.setText(f"Status: Exposure set to {value} | FPS: {self.fps_spin.value()}")

    def update_fps(self, value):
        self.camera_thread.set_fps(value)
        self.status_label.setText(f"Status: FPS set to {value} | Exposure: {self.exp_spin.value()}")

    def show_error(self, error_msg):
        QMessageBox.critical(self, "Camera Error", error_msg)
        # Reset UI on error
        if self.camera_active:
            self.toggle_camera()

    def close(self):
        # Cleanup camera thread
        if self.camera_active:
            self.camera_thread.stop_camera()