import requests
import json
from threading import Lock
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QTextEdit, QLabel, QLineEdit, QFrame, QMessageBox,
    QGroupBox
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt

class DeepSeekThread(QThread):
    response_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, api_key, model="deepseek-chat"):
        super().__init__()
        self.running = True
        self.lock = Lock()
        self.api_key = api_key
        self.model = model
        self.prompt_queue = []

    def set_prompt(self, prompt, image_path=None):
        with self.lock:
            self.prompt_queue.append((prompt, image_path))

    def run(self):
        while self.running:
            with self.lock:
                if not self.prompt_queue:
                    self.msleep(100)
                    continue
                prompt, image_path = self.prompt_queue.pop(0)

            try:
                # Base DeepSeek API configuration
                url = "https://api.deepseek.com/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

                # Basic text prompt (image support simplified for small screens)
                messages = [{"role": "user", "content": prompt}]
                
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 500  # Reduced for compact screen output
                }

                # Send API request
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                response.raise_for_status()
                result = response.json()
                
                # Extract AI response
                ai_response = result["choices"][0]["message"]["content"]
                self.response_signal.emit(ai_response)

            except Exception as e:
                self.error_signal.emit(f"AI Error: {str(e)}")

    def stop(self):
        with self.lock:
            self.running = False
        self.wait()

class DeepSeekWidget(QWidget):
    # Fixed: Rename signal to avoid conflict with analyze_image method
    image_analysis_request = pyqtSignal(str)  # Renamed from analyze_image

    def __init__(self, ai_config):
        super().__init__()
        self.api_key = ai_config.get("deepseek_api_key", "")
        self.model = ai_config.get("model", "deepseek-chat")
        # Initialize telescope context storage
        self.telescope_context = {
            "altitude": 0.0,
            "azimuth": 0.0,
            "gps": ""
        }
        
        # AI Thread initialization
        self.ai_thread = DeepSeekThread(self.api_key, self.model)
        self.ai_thread.response_signal.connect(self.update_ai_response)
        self.ai_thread.error_signal.connect(self.show_error)
        
        # UI Setup (optimized for 800×480 displays)
        self.init_ui()
        
        # Start AI thread
        self.ai_thread.start()

    def init_ui(self):
        layout = QVBoxLayout(self)
        # Compact spacing for small screens
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel("AI Assistant (DeepSeek)")
        title.setObjectName("title_label")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #3498db;")
        layout.addWidget(title)

        # API Key Status (compact display)
        api_frame = QFrame()
        api_frame.setStyleSheet("background-color: #f8f9fa; border-radius: 4px; padding: 8px;")
        api_layout = QHBoxLayout(api_frame)
        api_status = "Connected" if self.api_key else "No API Key (Enter Below)"
        api_color = "#2ecc71" if self.api_key else "#e74c3c"
        self.api_status_label = QLabel(f"Status: {api_status}")
        self.api_status_label.setStyleSheet(f"font-size: 11px; color: {api_color};")
        api_layout.addWidget(self.api_status_label)
        layout.addWidget(api_frame)

        # API Key Input (compact)
        key_group = QGroupBox("API Key (Required)")
        key_group.setStyleSheet("font-size: 12px;")
        key_layout = QHBoxLayout(key_group)
        self.api_key_input = QLineEdit()
        self.api_key_input.setStyleSheet("font-size: 11px; padding: 4px;")
        self.api_key_input.setPlaceholderText("Enter DeepSeek API Key")
        self.api_key_input.setText(self.api_key)
        self.api_key_input.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        self.save_key_btn = QPushButton("Save")
        self.save_key_btn.setStyleSheet("""
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
        self.save_key_btn.clicked.connect(self.save_api_key)
        key_layout.addWidget(self.api_key_input)
        key_layout.addWidget(self.save_key_btn)
        layout.addWidget(key_group)

        # Prompt Input (small text area for 480px height)
        prompt_group = QGroupBox("Ask Astronomy Questions")
        prompt_group.setStyleSheet("font-size: 12px;")
        prompt_layout = QVBoxLayout(prompt_group)
        self.prompt_input = QTextEdit()
        self.prompt_input.setStyleSheet("font-size: 11px;")
        self.prompt_input.setMaximumHeight(80)  # Reduced height for small screens
        self.prompt_input.setPlaceholderText("e.g., 'How to focus on the Moon?', 'Explain azimuth tracking'")
        prompt_layout.addWidget(self.prompt_input)
        
        # Send Button
        self.send_btn = QPushButton("Send to AI")
        self.send_btn.setStyleSheet("""
            QPushButton { 
                background-color: #9c27b0; 
                color: white; 
                border: none; 
                border-radius: 4px; 
                padding: 6px 8px; 
                font-size: 12px;
            }
            QPushButton:hover { background-color: #7b1fa2; }
        """)
        self.send_btn.clicked.connect(self.send_prompt)
        prompt_layout.addWidget(self.send_btn)
        layout.addWidget(prompt_group)

        # AI Response (compact output for 800×480)
        response_group = QGroupBox("AI Response")
        response_group.setStyleSheet("font-size: 12px;")
        response_layout = QVBoxLayout(response_group)
        self.response_output = QTextEdit()
        self.response_output.setStyleSheet("font-size: 11px;")
        self.response_output.setMaximumHeight(180)  # Critical for 480px height
        self.response_output.setReadOnly(True)
        response_layout.addWidget(self.response_output)
        layout.addWidget(response_group)

        # Quick Actions (small buttons for astronomy tasks)
        quick_layout = QHBoxLayout()
        self.moon_help_btn = QPushButton("Moon Tracking Help")
        self.sun_help_btn = QPushButton("Sun Safety Tips")
        self.camera_help_btn = QPushButton("Camera Settings")
        # Style for small buttons
        quick_btn_style = """
            QPushButton { 
                background-color: #3498db; 
                color: white; 
                border: none; 
                border-radius: 4px; 
                padding: 4px 6px; 
                font-size: 10px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """
        self.moon_help_btn.setStyleSheet(quick_btn_style)
        self.sun_help_btn.setStyleSheet(quick_btn_style)
        self.camera_help_btn.setStyleSheet(quick_btn_style)
        # Connect quick actions to pre-filled prompts
        self.moon_help_btn.clicked.connect(lambda: self.load_quick_prompt("Explain how to optimize moon tracking for a small telescope (800×480 display)"))
        self.sun_help_btn.clicked.connect(lambda: self.load_quick_prompt("List critical safety tips for solar observation with a telescope"))
        self.camera_help_btn.clicked.connect(lambda: self.load_quick_prompt("Recommend camera settings for lunar photography (640x480 resolution)"))
        quick_layout.addWidget(self.moon_help_btn)
        quick_layout.addWidget(self.sun_help_btn)
        quick_layout.addWidget(self.camera_help_btn)
        layout.addLayout(quick_layout)

    # ======================
    # FIXED: Robust update_context (handles string/dict input + error handling)
    # ======================
    def update_context(self, context):
        """
        Compatibility method for main.py - handles both string and dictionary inputs
        :param context: Can be a string (raw context) or dict with altitude/azimuth/gps keys
        """
        # Default values if input is invalid
        current_alt = 0.0
        current_az = 0.0
        gps_str = ""

        try:
            # Case 1: Context is a dictionary (ideal case)
            if isinstance(context, dict):
                current_alt = context.get("altitude", 0.0)
                current_az = context.get("azimuth", 0.0)
                gps_str = context.get("gps", "")
            
            # Case 2: Context is a string (what main.py is passing)
            elif isinstance(context, str):
                # Clean up string and extract values (basic parsing - adjust if needed)
                # Example string format: "Altitude: 10.5°, Azimuth: 200.0°, GPS: 40.7128° N, -74.0060° W"
                context_clean = context.strip()
                if "Altitude:" in context_clean:
                    # Extract altitude (number after "Altitude:")
                    alt_part = context_clean.split("Altitude:")[1].split("°")[0].strip()
                    current_alt = float(alt_part) if alt_part.replace(".", "").isdigit() else 0.0
                if "Azimuth:" in context_clean:
                    # Extract azimuth (number after "Azimuth:")
                    az_part = context_clean.split("Azimuth:")[1].split("°")[0].strip()
                    current_az = float(az_part) if az_part.replace(".", "").isdigit() else 0.0
                if "GPS:" in context_clean:
                    # Extract GPS string (everything after "GPS:")
                    gps_str = context_clean.split("GPS:")[1].strip()
            
            # Case 3: Unexpected input type (log warning but don't crash)
            else:
                self.show_error(f"Invalid context type: Expected dict/string, got {type(context)}")
                return

            # Pass parsed values to the original context update method
            self.update_telescope_context(current_alt, current_az, gps_str)

        except Exception as e:
            # Catch all errors to prevent crashes
            self.show_error(f"Failed to parse context: {str(e)}")
            # Fallback to default values
            self.update_telescope_context(0.0, 0.0, "")

    # ======================
    # Original Context Update Method (preserved)
    # ======================
    def update_telescope_context(self, current_alt, current_az, gps_str):
        """
        Updates real-time telescope context (altitude, azimuth, GPS) for context-aware AI responses.
        :param current_alt: Current altitude (degrees)
        :param current_az: Current azimuth (degrees)
        :param gps_str: GPS coordinates as a string (e.g., "40.7128° N, -74.0060° W")
        """
        self.telescope_context = {
            "altitude": round(float(current_alt), 1),  # Ensure float to avoid errors
            "azimuth": round(float(current_az), 1),    # Ensure float to avoid errors
            "gps": str(gps_str)                        # Ensure string to avoid errors
        }
        # Update status label with context (debug/transparency)
        self.api_status_label.setText(
            f"Status: Connected | Alt:{self.telescope_context['altitude']}° | Az:{self.telescope_context['azimuth']}°"
        )

    def save_api_key(self):
        self.api_key = self.api_key_input.text().strip()
        self.ai_thread.api_key = self.api_key
        # Update status display
        if self.api_key:
            self.api_status_label.setText("Status: Connected")
            self.api_status_label.setStyleSheet("font-size: 11px; color: #2ecc71;")
            QMessageBox.information(self, "API Key Saved", "DeepSeek API key updated successfully!")
        else:
            self.api_status_label.setText("Status: No API Key")
            self.api_status_label.setStyleSheet("font-size: 11px; color: #e74c3c;")

    def load_quick_prompt(self, prompt):
        self.prompt_input.setText(prompt)

    def send_prompt(self):
        if not self.api_key:
            QMessageBox.warning(self, "Missing API Key", "Please enter your DeepSeek API key first!")
            return
        
        base_prompt = self.prompt_input.toPlainText().strip()
        if not base_prompt:
            QMessageBox.warning(self, "Empty Prompt", "Please enter a question for the AI!")
            return
        
        # Integrate telescope context into the prompt (core feature)
        context = self.telescope_context
        full_prompt = f"""
        Context: 
        - Telescope Altitude: {context['altitude']}°
        - Telescope Azimuth: {context['azimuth']}°
        - GPS Location: {context['gps']}
        - Display Resolution: 800×480
        - Camera Resolution: 640x480

        Question: {base_prompt}
        
        Note: Provide concise, practical answers optimized for a small robotic telescope (Raspberry Pi 5).
        """
        
        # Clear previous response
        self.response_output.setText("AI is thinking...")
        # Send full context-aware prompt to AI thread
        self.ai_thread.set_prompt(full_prompt)

    def update_ai_response(self, response):
        self.response_output.setText(response)

    # Fixed: Rename method to avoid conflict with signal
    def analyze_image_file(self, image_path):
        # Context-aware image analysis prompt
        context = self.telescope_context
        prompt = f"""
        Context:
        - Telescope Altitude: {context['altitude']}°
        - Telescope Azimuth: {context['azimuth']}°
        - GPS Location: {context['gps']}
        - Camera Resolution: 640x480

        Analyze this astronomical image (path: {image_path}): 
        1. Identify the celestial object (Moon/Sun/stars/planets)
        2. Assess image quality (exposure, focus, noise, clarity)
        3. Suggest improvements tailored to the telescope's current position and camera settings
        """
        self.ai_thread.set_prompt(prompt, image_path)
        self.response_output.setText("Analyzing image...")

    def show_error(self, error_msg):
        QMessageBox.critical(self, "AI Error", error_msg)
        self.response_output.setText(f"Error: {error_msg}")

    def close(self):
        self.ai_thread.stop()