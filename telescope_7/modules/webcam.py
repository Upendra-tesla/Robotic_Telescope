import cv2
import os
import time
import datetime
import requests
import base64
from threading import Lock, Thread
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QGroupBox, QFrame, QSlider, QMessageBox, QTextEdit
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QImage, QPixmap

# --------------------------
# AI Image Analysis Thread (Non-blocking)
# --------------------------
class DeepSeekAnalysisThread(Thread):
    """Separate thread for DeepSeek API calls (avoids UI freezing)"""
    def __init__(self, image_path, result_callback, error_callback, api_key):
        super().__init__()
        self.image_path = image_path
        self.result_callback = result_callback
        self.error_callback = error_callback
        self.api_key = api_key
        self.daemon = True  # Thread exits when main app closes

    def _encode_image_to_base64(self):
        """Convert image to base64 (required for DeepSeek API)"""
        try:
            with open(self.image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        except Exception as e:
            raise Exception(f"Encode error: {str(e)}")

    def run(self):
        """Execute DeepSeek API call"""
        # Validate API key
        if not self.api_key or self.api_key.strip() == "":
            self.error_callback("❌ DeepSeek API key missing!\nAdd to config/settings.json")
            return

        # Encode image to base64
        try:
            base64_image = self._encode_image_to_base64()
        except Exception as e:
            self.error_callback(f"❌ Image encode failed: {str(e)}")
            return

        # Prepare API request
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Compact prompt (optimized for small screen results)
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": """Analyze this telescope image (CONCISE):
1. Celestial objects visible
2. Image quality (sharpness/exposure)
3. Notable features
4. Quick improvement tips
Keep it short (2-3 sentences max)."""
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ]

        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 300  # Shorter results for small screen
        }

        # Send request to DeepSeek API
        try:
            response = requests.post("https://api.deepseek.com/v1/chat/completions", 
                                    json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            # Extract analysis text
            analysis = result["choices"][0]["message"]["content"].strip()
            self.result_callback(analysis)

        except requests.exceptions.Timeout:
            self.error_callback("❌ API timeout (check internet)")
        except requests.exceptions.ConnectionError:
            self.error_callback("❌ API connection failed (check internet)")
        except requests.exceptions.HTTPError as e:
            self.error_callback(f"❌ API error: {str(e)} (invalid key?)")
        except Exception as e:
            self.error_callback(f"❌ AI failed: {str(e)}")

# --------------------------
# Camera Thread (Pi 5 800×480 Optimized)
# --------------------------
class CameraThread(QThread):
    frame_signal = pyqtSignal(QPixmap)
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    save_signal = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self.running = False
        self.recording = False
        self.lock = Lock()
        
        # Camera config (800×480 optimized)
        self.config = config
        self.resolution = tuple(map(int, config["camera"]["default_resolution"].split("x")))
        self.fps = config["camera"]["default_fps"]
        self.exposure = config["camera"]["exposure"]
        self.image_path = config["camera"]["image_save_path"]
        self.video_path = config["camera"]["video_save_path"]
        
        # Create save directories
        os.makedirs(self.image_path, exist_ok=True)
        os.makedirs(self.video_path, exist_ok=True)
        
        # Camera variables
        self.cap = None
        self.video_writer = None
        self.frame_count = 0
        self.save_frame = False

    def _init_camera(self):
        """Initialize Pi 5 camera (V4L2 backend)"""
        try:
            self.cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
            if not self.cap.isOpened():
                raise Exception("Camera not found (enable with raspi-config)")
            
            # Set camera parameters (astronomy optimized)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            self.cap.set(cv2.CAP_PROP_EXPOSURE, self.exposure)
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)
            self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce latency
            
            # Verify settings
            actual_width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            self.status_signal.emit(f"✅ Cam: {actual_width}x{actual_height} @ {actual_fps} FPS")
            return True
        except Exception as e:
            self.error_signal.emit(f"❌ Cam init error: {str(e)}")
            return False

    def start_camera(self):
        """Start camera (thread-safe)"""
        with self.lock:
            self.running = True
        if not self.isRunning():
            self.start()
        self.status_signal.emit("📹 Camera started")

    def stop_camera(self):
        """Stop camera and release resources"""
        with self.lock:
            self.running = False
            self.recording = False
        if self.cap:
            self.cap.release()
        if self.video_writer:
            self.video_writer.release()
        cv2.destroyAllWindows()
        self.wait()
        self.status_signal.emit("🛑 Camera stopped")

    def toggle_recording(self):
        """Toggle video recording"""
        with self.lock:
            self.recording = not self.recording
        
        if self.recording:
            # Start recording (MP4 format)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            video_filename = f"video_{timestamp}.mp4"
            video_path = os.path.join(self.video_path, video_filename)
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.video_writer = cv2.VideoWriter(
                video_path,
                fourcc,
                self.fps,
                self.resolution
            )
            
            self.status_signal.emit(f"🎥 Recording: {video_filename}")
        else:
            # Stop recording
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
            self.status_signal.emit("⏹️ Recording stopped")

    def capture_image(self):
        """Capture still image (thread-safe)"""
        with self.lock:
            self.save_frame = True
        self.status_signal.emit("📸 Capture requested")

    def set_exposure(self, exposure):
        """Update exposure value"""
        with self.lock:
            self.exposure = exposure
            if self.cap:
                self.cap.set(cv2.CAP_PROP_EXPOSURE, exposure)
        self.status_signal.emit(f"🔆 Exposure: {exposure}")

    def run(self):
        """Main camera loop (low CPU, 800×480 optimized)"""
        if not self._init_camera():
            return
        
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                self.error_signal.emit("❌ Failed to read frame (check camera)")
                break
            
            # Convert BGR → RGB for PyQt (COMPACT size)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            display_frame = cv2.resize(frame_rgb, (320, 240))  # Small preview for 800×480
            
            # Convert to QPixmap
            h, w, ch = display_frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(display_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            
            # Send frame to UI
            self.frame_signal.emit(pixmap)
            
            # Save image if requested
            if self.save_frame:
                self._save_image(frame)
                with self.lock:
                    self.save_frame = False
            
            # Record video if active
            if self.recording and self.video_writer:
                self.video_writer.write(frame)
                self.frame_count += 1
                if self.frame_count % (self.fps * 5) == 0:
                    self.status_signal.emit(f"📼 Frames: {self.frame_count}")
            
            # Pi 5 optimization (minimal sleep)
            time.sleep(0.01)

    def _save_image(self, frame):
        """Save high-quality image to disk"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"image_{timestamp}.jpg"
            filepath = os.path.join(self.image_path, filename)
            
            # Save with 95% JPEG quality
            cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            self.save_signal.emit(filepath)
            self.status_signal.emit(f"✅ Saved: {filename}")
        except Exception as e:
            self.error_signal.emit(f"❌ Save error: {str(e)}")

# --------------------------
# Webcam Widget (800×480 COMPACT DESIGN)
# --------------------------
class WebcamWidget(QWidget):
    # Critical signals (fixed AttributeError)
    analyze_image = pyqtSignal(str)
    status_signal = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.api_key = config["ai"].get("deepseek_api_key", "")
        
        # Initialize camera thread (800×480 optimized)
        self.camera_thread = CameraThread(config)
        self.camera_thread.frame_signal.connect(self.update_frame)
        self.camera_thread.status_signal.connect(self.update_status)
        self.camera_thread.error_signal.connect(self.show_error)
        self.camera_thread.save_signal.connect(self.on_image_saved)

        # Initialize UI (COMPACT for 800×480)
        self.init_ui()

    def init_ui(self):
        # MAIN LAYOUT (MINIMAL padding/spacing)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)  # Tight spacing
        layout.setContentsMargins(8, 8, 8, 8)  # Minimal margins

        # 1. WIDGET TITLE (COMPACT)
        title = QLabel(f"Camera + AI ({self.config['camera']['default_resolution']})")
        title.setStyleSheet("font-size: 10px; font-weight: bold; color: #3498db;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 2. CAMERA FEED (SMALL preview for 800×480)
        feed_frame = QFrame()
        feed_frame.setStyleSheet("background-color: #000; border-radius: 3px; padding: 4px;")
        feed_layout = QVBoxLayout(feed_frame)
        
        self.feed_label = QLabel()
        self.feed_label.setAlignment(Qt.AlignCenter)
        self.feed_label.setFixedSize(320, 240)  # Fixed small size
        self.feed_label.setText("📹 Click Start")
        self.feed_label.setStyleSheet("color: #fff; font-size: 9px;")
        
        feed_layout.addWidget(self.feed_label)
        layout.addWidget(feed_frame, alignment=Qt.AlignCenter)  # Center feed

        # 3. CAMERA CONTROLS (COMPACT group)
        control_group = QGroupBox("Camera Controls")
        control_group.setStyleSheet("font-size: 9px;")
        control_layout = QVBoxLayout(control_group)
        control_layout.setSpacing(5)

        # 3a. POWER BUTTON (COMPACT)
        self.power_btn = QPushButton("Start Camera")
        self.power_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 6px;
                font-size: 9px;
                min-height: 25px;
            }
            QPushButton#running { background-color: #2ecc71; }
        """)
        self.power_btn.clicked.connect(self.toggle_camera)
        control_layout.addWidget(self.power_btn)

        # 3b. CAPTURE/RECORD BUTTONS (SIDE-BY-SIDE, COMPACT)
        capture_layout = QHBoxLayout()
        capture_layout.setSpacing(5)
        
        self.capture_btn = QPushButton("📸 Capture")
        self.record_btn = QPushButton("🎥 Record")
        
        # Button styling (COMPACT)
        btn_style = """
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px;
                font-size: 8px;
                flex: 1;
            }
            QPushButton#recording { background-color: #e74c3c; }
            QPushButton:disabled { background-color: #bdc3c7; }
        """
        self.capture_btn.setStyleSheet(btn_style)
        self.record_btn.setStyleSheet(btn_style)
        
        # Disable by default
        self.capture_btn.setEnabled(False)
        self.record_btn.setEnabled(False)
        
        # Connect buttons
        self.capture_btn.clicked.connect(self.capture_image)
        self.record_btn.clicked.connect(self.toggle_recording)
        
        capture_layout.addWidget(self.capture_btn)
        capture_layout.addWidget(self.record_btn)
        control_layout.addLayout(capture_layout)

        # 3c. EXPOSURE CONTROL (COMPACT)
        exposure_layout = QHBoxLayout()
        exposure_layout.setSpacing(5)
        exposure_layout.addWidget(QLabel("Exposure:", styleSheet="font-size: 8px;"))
        
        self.exposure_slider = QSlider(Qt.Horizontal)
        self.exposure_slider.setRange(0, 1000)
        self.exposure_slider.setValue(self.config["camera"]["exposure"])
        self.exposure_slider.setStyleSheet("height: 15px;")
        self.exposure_slider.setEnabled(False)
        self.exposure_slider.valueChanged.connect(self.set_exposure)
        
        self.exposure_label = QLabel(f"{self.config['camera']['exposure']}")
        self.exposure_label.setStyleSheet("font-size: 8px; width: 30px; text-align: center;")
        
        exposure_layout.addWidget(self.exposure_slider)
        exposure_layout.addWidget(self.exposure_label)
        control_layout.addLayout(exposure_layout)
        
        layout.addWidget(control_group)

        # 4. AI ANALYSIS SECTION (COMPACT for 800×480)
        ai_group = QGroupBox("AI Analysis")
        ai_group.setStyleSheet("font-size: 9px;")
        ai_layout = QVBoxLayout(ai_group)
        ai_layout.setSpacing(5)
        
        # AI Status Label (COMPACT)
        self.ai_status_label = QLabel("Status: Ready")
        self.ai_status_label.setStyleSheet("font-size: 8px; color: #666;")
        ai_layout.addWidget(self.ai_status_label)
        
        # Analysis Results (SMALL height for 800×480)
        self.ai_results_text = QTextEdit()
        self.ai_results_text.setReadOnly(True)
        self.ai_results_text.setStyleSheet("""
            QTextEdit {
                font-size: 8px;
                padding: 4px;
                background-color: #f8f9fa;
                border-radius: 3px;
                height: 120px;  # Compact height
            }
        """)
        self.ai_results_text.setPlaceholderText("AI results will appear here...")
        ai_layout.addWidget(self.ai_results_text)
        
        layout.addWidget(ai_group)

        # 5. STATUS DISPLAY (COMPACT)
        self.status_label = QLabel("Status: Camera off")
        self.status_label.setStyleSheet("font-size: 8px; color: #666;")
        layout.addWidget(self.status_label)

    # --------------------------
    # Core Camera Functions (COMPACT)
    # --------------------------
    def toggle_camera(self):
        """Start/stop camera"""
        if not self.camera_thread.running:
            self.camera_thread.start_camera()
            self.power_btn.setText("Stop Camera")
            self.power_btn.setObjectName("running")
            self.capture_btn.setEnabled(True)
            self.record_btn.setEnabled(True)
            self.exposure_slider.setEnabled(True)
        else:
            self.camera_thread.stop_camera()
            self.power_btn.setText("Start Camera")
            self.power_btn.setObjectName("")
            self.capture_btn.setEnabled(False)
            self.record_btn.setEnabled(False)
            self.exposure_slider.setEnabled(False)
            self.feed_label.setText("📹 Click Start")

    def capture_image(self):
        """Trigger image capture"""
        self.camera_thread.capture_image()
        self.ai_results_text.clear()
        self.ai_status_label.setText("Status: Captured - Analyzing...")

    def toggle_recording(self):
        """Toggle video recording"""
        self.camera_thread.toggle_recording()
        if self.camera_thread.recording:
            self.record_btn.setObjectName("recording")
            self.record_btn.setText("⏹️ Stop Record")
        else:
            self.record_btn.setObjectName("")
            self.record_btn.setText("🎥 Record")

    def set_exposure(self, value):
        """Update exposure"""
        self.camera_thread.set_exposure(value)
        self.exposure_label.setText(f"{value}")

    def update_frame(self, pixmap):
        """Update camera feed (COMPACT)"""
        self.feed_label.setPixmap(pixmap.scaled(self.feed_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    # --------------------------
    # AI Analysis Functions (COMPACT)
    # --------------------------
    def on_image_saved(self, filepath):
        """Callback when image is saved - trigger AI analysis"""
        QMessageBox.information(self, "Saved", f"Image saved:\n{os.path.basename(filepath)}\n\nAnalyzing...", QMessageBox.Ok)
        
        # Emit signal for main.py (fixed AttributeError)
        self.analyze_image.emit(filepath)
        
        # Start AI analysis (COMPACT callbacks)
        def ai_result_handler(analysis):
            """Update UI with AI results"""
            self.ai_results_text.setText(analysis)
            self.ai_status_label.setText("Status: Analysis complete")
            self.status_signal.emit("✅ AI analysis done")

        def ai_error_handler(error):
            """Update UI with AI errors"""
            self.ai_results_text.setText(f"❌ Error:\n{error}")
            self.ai_status_label.setText("Status: Analysis failed")
            self.show_error(error)

        # Launch AI thread
        ai_thread = DeepSeekAnalysisThread(filepath, ai_result_handler, ai_error_handler, self.api_key)
        ai_thread.start()
        self.status_label.setText(f"Status: Analyzing {os.path.basename(filepath)}")

    # --------------------------
    # Utility Functions (COMPACT)
    # --------------------------
    def update_status(self, msg):
        """Update status message (COMPACT)"""
        self.status_label.setText(f"Status: {msg[:40]}")  # Truncate long messages
        self.status_signal.emit(msg)

    def show_error(self, msg):
        """Display error messages (COMPACT dialog)"""
        QMessageBox.critical(self, "Error", msg[:60], QMessageBox.Ok)
        self.update_status(f"Error: {msg[:20]}...")

    def close(self):
        """Cleanup on close"""
        if self.camera_thread.running:
            self.camera_thread.stop_camera()