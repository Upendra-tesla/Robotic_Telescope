import sys
import json
import requests
import subprocess
import threading
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QTextEdit, QLabel, QComboBox, QFrame, QSizePolicy, QCheckBox,
    QMessageBox, QInputDialog, QGroupBox, QGridLayout, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QMutex, QMutexLocker
from PyQt5.QtGui import QFont, QColor, QTextCursor, QPalette
from . import SETTINGS, get_responsive_stylesheet

# DeepSeek API Configuration
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
OLLAMA_DEFAULT_MODEL = SETTINGS["ai"]["ollama_model"]

class DeepSeekThread(QThread):
    response_received = pyqtSignal(str)
    status_update = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.mutex = QMutex()
        self.running = False
        self.pending_prompt = None
        self.mode = SETTINGS["ai"]["mode"]
        self.api_key = SETTINGS["ai"]["deepseek_api_key"]
        self.ollama_model = SETTINGS["ai"]["ollama_model"]
        self.conversation_history = [
            {"role": "system", "content": "You are a helpful assistant for a robotic telescope. "
                                         "Provide concise, actionable responses for astronomy and telescope control. "
                                         "Respond in plain language suitable for amateur astronomers."}
        ]

    def set_mode(self, mode):
        with QMutexLocker(self.mutex):
            self.mode = mode
            SETTINGS["ai"]["mode"] = mode
            self._save_settings()

    def set_api_key(self, api_key):
        with QMutexLocker(self.mutex):
            self.api_key = api_key
            SETTINGS["ai"]["deepseek_api_key"] = api_key
            self._save_settings()

    def set_ollama_model(self, model):
        with QMutexLocker(self.mutex):
            self.ollama_model = model
            SETTINGS["ai"]["ollama_model"] = model
            self._save_settings()

    def send_prompt(self, prompt):
        with QMutexLocker(self.mutex):
            self.pending_prompt = prompt
            self.conversation_history.append({"role": "user", "content": prompt})
        self.status_update.emit(f"Sending request to {self.mode} AI...")

    def clear_history(self):
        with QMutexLocker(self.mutex):
            self.conversation_history = [self.conversation_history[0]]

    def _save_settings(self):
        """Save AI settings to settings.json"""
        try:
            settings_path = Path(__file__).parent.parent / "settings.json"
            with open(settings_path, "w") as f:
                json.dump(SETTINGS, f, indent=2)
        except Exception as e:
            self.error_occurred.emit(f"Failed to save settings: {str(e)}")

    def _call_cloud_api(self, prompt):
        """Call DeepSeek Cloud API"""
        if not self.api_key:
            self.error_occurred.emit("DeepSeek API key is missing!")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "deepseek-chat",
            "messages": self.conversation_history,
            "temperature": 0.7,
            "max_tokens": 500
        }

        try:
            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            answer = result["choices"][0]["message"]["content"]
            self.conversation_history.append({"role": "assistant", "content": answer})
            return answer
        except requests.exceptions.Timeout:
            self.error_occurred.emit("API request timed out")
        except requests.exceptions.ConnectionError:
            self.error_occurred.emit("Network connection error")
        except Exception as e:
            self.error_occurred.emit(f"Cloud API error: {str(e)}")
        return None

    def _call_local_ollama(self, prompt):
        """Call local Ollama instance"""
        try:
            # Check if Ollama is running
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                self.error_occurred.emit("Ollama is not running/installed!")
                return None

            # Send prompt to Ollama
            result = subprocess.run(
                ["ollama", "run", self.ollama_model, prompt],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                answer = result.stdout
                self.conversation_history.append({"role": "assistant", "content": answer})
                return answer
            else:
                self.error_occurred.emit(f"Ollama error: {result.stderr}")
        except subprocess.TimeoutExpired:
            self.error_occurred.emit("Ollama request timed out")
        except FileNotFoundError:
            self.error_occurred.emit("Ollama binary not found")
        except Exception as e:
            self.error_occurred.emit(f"Local AI error: {str(e)}")
        return None

    def run(self):
        self.running = True
        while self.running:
            prompt = None
            with QMutexLocker(self.mutex):
                if self.pending_prompt:
                    prompt = self.pending_prompt
                    self.pending_prompt = None

            if prompt:
                if self.mode == "cloud":
                    answer = self._call_cloud_api(prompt)
                else:
                    answer = self._call_local_ollama(prompt)
                
                if answer:
                    self.response_received.emit(answer)
                self.status_update.emit("Ready")
            
            QThread.msleep(100)

    def stop(self):
        self.running = False
        self.wait()

class DeepSeekWidget(QWidget):
    # Signals for telescope control integration
    point_to_moon = pyqtSignal()
    track_sun = pyqtSignal()
    calibrate_telescope = pyqtSignal()
    status_report = pyqtSignal()
    analyze_image = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Apply responsive stylesheet
        self.setStyleSheet(get_responsive_stylesheet())
        
        # AI Thread Initialization
        self.ai_thread = DeepSeekThread()
        self.ai_thread.response_received.connect(self.append_response)
        self.ai_thread.status_update.connect(self.update_status)
        self.ai_thread.error_occurred.connect(self.show_error)
        self.ai_thread.start()

        self.init_ui()

    def init_ui(self):
        """Initialize user interface"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Title Group
        title_group = QGroupBox("AI Assistant")
        title_layout = QVBoxLayout()
        title_label = QLabel("🤖 DeepSeek AI Assistant")
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(title_label)
        title_group.setLayout(title_layout)
        main_layout.addWidget(title_group)

        # Settings Group
        settings_group = QGroupBox("AI Settings")
        settings_layout = QGridLayout()
        
        # Mode Selection
        settings_layout.addWidget(QLabel("AI Mode:"), 0, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Cloud (DeepSeek)", "Local (Ollama)"])
        self.mode_combo.setCurrentText("Cloud (DeepSeek)" if SETTINGS["ai"]["mode"] == "cloud" else "Local (Ollama)")
        self.mode_combo.currentTextChanged.connect(self.change_mode)
        settings_layout.addWidget(self.mode_combo, 0, 1)
        
        # API Key Input (for cloud mode)
        settings_layout.addWidget(QLabel("API Key:"), 1, 0)
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setText(SETTINGS["ai"]["deepseek_api_key"])
        self.api_key_input.setPlaceholderText("Enter DeepSeek API key")
        self.api_key_input.textChanged.connect(self.update_api_key)
        settings_layout.addWidget(self.api_key_input, 1, 1)
        
        self.save_api_btn = QPushButton("Save Key")
        self.save_api_btn.clicked.connect(self.save_api_key)
        settings_layout.addWidget(self.save_api_btn, 1, 2)
        
        # Model Selection (for local mode)
        settings_layout.addWidget(QLabel("Model:"), 2, 0)
        self.model_combo = QComboBox()
        self.model_combo.addItems(["deepseek-r1:1.5b", "llama2:7b", "mistral:7b", "codellama:7b", "gemma:2b"])
        self.model_combo.setCurrentText(SETTINGS["ai"]["ollama_model"])
        self.model_combo.currentTextChanged.connect(self.update_ollama_model)
        settings_layout.addWidget(self.model_combo, 2, 1)
        
        # Auto-analysis checkbox
        self.auto_analysis_check = QPushButton("🤖 Auto-analysis: OFF")
        self.auto_analysis_check.setCheckable(True)
        self.auto_analysis_check.setChecked(SETTINGS["ai"]["enable_auto_analysis"])
        self.auto_analysis_check.clicked.connect(self.toggle_auto_analysis)
        settings_layout.addWidget(self.auto_analysis_check, 2, 2)
        
        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)

        # Quick Commands Group
        commands_group = QGroupBox("Quick Commands")
        commands_layout = QGridLayout()
        
        quick_commands = [
            ("🌙 Point to Moon", self.point_to_moon.emit, "#ccccff"),
            ("☀️ Track Sun", self.track_sun.emit, "#ffcc00"),
            ("🎯 Calibrate Telescope", self.calibrate_telescope.emit, "#00a8ff"),
            ("📊 Status Report", self.status_report.emit, "#00ff88"),
            ("📸 Analyze Image", self.analyze_image.emit, "#ff8800"),
            ("🌟 Visible Objects", lambda: self.send_quick_command("What objects are visible tonight?"), "#aa00ff"),
            ("🌌 Stargazing Tips", lambda: self.send_quick_command("Give me stargazing tips for tonight"), "#00ffff"),
            ("🔭 Telescope Setup", lambda: self.send_quick_command("How should I set up my telescope?"), "#ff66aa")
        ]
        
        row, col = 0, 0
        for text, callback, color in quick_commands:
            btn = QPushButton(text)
            btn.setStyleSheet(f"background-color: {color}; color: black; font-weight: bold;")
            btn.clicked.connect(lambda checked, c=callback: c())
            btn.setMinimumHeight(40)
            commands_layout.addWidget(btn, row, col)
            col += 1
            if col > 3:
                col = 0
                row += 1
        
        commands_group.setLayout(commands_layout)
        main_layout.addWidget(commands_group)

        # Chat History Group
        chat_group = QGroupBox("Chat History")
        chat_layout = QVBoxLayout()
        
        # Create scroll area for chat history
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(200)
        
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setStyleSheet("""
            QTextEdit {
                background-color: #333333;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 10px;
                font-size: 12px;
            }
        """)
        
        scroll_area.setWidget(self.chat_history)
        chat_layout.addWidget(scroll_area)
        
        chat_group.setLayout(chat_layout)
        main_layout.addWidget(chat_group)

        # Input Area Group
        input_group = QGroupBox("Send Message")
        input_layout = QHBoxLayout()
        
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Type your question or command here...")
        self.prompt_input.returnPressed.connect(self.send_prompt)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_prompt)
        self.send_btn.setStyleSheet("background-color: #00a8ff; color: white; font-weight: bold;")
        
        self.clear_btn = QPushButton("Clear History")
        self.clear_btn.clicked.connect(self.clear_chat_history)
        self.clear_btn.setStyleSheet("background-color: #ff4444; color: white;")
        
        self.voice_btn = QPushButton("🎤 Voice")
        self.voice_btn.clicked.connect(self.voice_input)
        self.voice_btn.setStyleSheet("background-color: #444444; color: white;")
        
        input_layout.addWidget(self.prompt_input, 70)
        input_layout.addWidget(self.send_btn, 10)
        input_layout.addWidget(self.clear_btn, 10)
        input_layout.addWidget(self.voice_btn, 10)
        
        input_group.setLayout(input_layout)
        main_layout.addWidget(input_group)

        # Status Group
        status_group = QGroupBox("Status")
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("Status: Ready")
        self.status_label.setStyleSheet("color: #00ff00; font-weight: bold;")
        status_layout.addWidget(self.status_label, 80)
        
        self.mode_label = QLabel(f"Mode: {SETTINGS['ai']['mode'].upper()}")
        self.mode_label.setStyleSheet("color: #00a8ff; font-weight: bold;")
        status_layout.addWidget(self.mode_label, 20)
        
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)

        main_layout.addStretch()
        self.setLayout(main_layout)
        
        # Update auto-analysis button
        self.update_auto_analysis_button()

    def change_mode(self, mode_text):
        """Change AI mode"""
        mode = "cloud" if "Cloud" in mode_text else "local"
        self.ai_thread.set_mode(mode)
        self.mode_label.setText(f"Mode: {mode.upper()}")
        
        # Update API key field visibility
        if mode == "cloud":
            self.api_key_input.setEnabled(True)
            self.save_api_btn.setEnabled(True)
            self.model_combo.setEnabled(False)
        else:
            self.api_key_input.setEnabled(False)
            self.save_api_btn.setEnabled(False)
            self.model_combo.setEnabled(True)
        
        self.update_status(f"Mode changed to {mode}")

    def update_api_key(self, api_key):
        """Update API key"""
        self.ai_thread.set_api_key(api_key)

    def update_ollama_model(self, model):
        """Update Ollama model"""
        # Remove any description from model name
        model_name = model.split(" ")[0] if " " in model else model
        self.ai_thread.set_ollama_model(model_name)
        self.update_status(f"Model changed to {model_name}")

    def save_api_key(self):
        """Save API key to settings"""
        api_key = self.api_key_input.text().strip()
        if api_key:
            self.ai_thread.set_api_key(api_key)
            QMessageBox.information(self, "Success", "API key saved successfully!")
            self.update_status("API key saved")
        else:
            QMessageBox.warning(self, "Warning", "Please enter an API key")

    def toggle_auto_analysis(self):
        """Toggle auto-analysis feature"""
        SETTINGS["ai"]["enable_auto_analysis"] = self.auto_analysis_check.isChecked()
        self.update_auto_analysis_button()
        
        if SETTINGS["ai"]["enable_auto_analysis"]:
            self.update_status("Auto-analysis enabled")
        else:
            self.update_status("Auto-analysis disabled")

    def update_auto_analysis_button(self):
        """Update auto-analysis button text and style"""
        if SETTINGS["ai"]["enable_auto_analysis"]:
            self.auto_analysis_check.setText("🤖 Auto-analysis: ON")
            self.auto_analysis_check.setStyleSheet("background-color: #00ff00; color: black; font-weight: bold;")
        else:
            self.auto_analysis_check.setText("🤖 Auto-analysis: OFF")
            self.auto_analysis_check.setStyleSheet("background-color: #444444; color: white;")

    def send_quick_command(self, command):
        """Send pre-defined quick commands to AI"""
        self.prompt_input.setText(command)
        self.send_prompt()

    def send_prompt(self):
        """Send user input to AI thread"""
        prompt = self.prompt_input.text().strip()
        if not prompt:
            return
        
        # Add user message to chat history
        self.append_message("You", prompt, "#00a8ff")
        self.prompt_input.clear()
        
        # Send to AI thread
        self.ai_thread.send_prompt(prompt)

    def append_message(self, sender, message, color):
        """Append message to chat history"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        html_message = f"""
        <div style="margin: 5px 0; padding: 8px; border-radius: 10px; background-color: #2b2b2b;">
            <span style="color: {color}; font-weight: bold;">{sender}</span>
            <span style="color: #888888; font-size: 10px; margin-left: 10px;">{timestamp}</span>
            <div style="margin-top: 5px; color: #ffffff;">{message}</div>
        </div>
        """
        
        # Save current scroll position
        scrollbar = self.chat_history.verticalScrollBar()
        at_bottom = scrollbar.value() == scrollbar.maximum()
        
        # Append message
        self.chat_history.append(html_message)
        
        # Scroll to bottom if we were at bottom
        if at_bottom:
            cursor = self.chat_history.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.chat_history.setTextCursor(cursor)

    def append_response(self, response):
        """Append AI response to chat history"""
        self.append_message("AI Assistant", response, "#00ff88")
        self.update_status("Response received")

    def update_status(self, status):
        """Update status label"""
        self.status_label.setText(f"Status: {status}")
        
        # Update status color
        if "error" in status.lower():
            self.status_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        elif "ready" in status.lower() or "received" in status.lower():
            self.status_label.setStyleSheet("color: #00ff00; font-weight: bold;")
        elif "sending" in status.lower():
            self.status_label.setStyleSheet("color: #ffaa00; font-weight: bold;")
        else:
            self.status_label.setStyleSheet("color: #ffffff; font-weight: bold;")

    def show_error(self, error):
        """Show error message"""
        QMessageBox.critical(self, "AI Error", error)
        self.append_message("System", f"Error: {error}", "#ff4444")
        self.update_status(f"Error: {error[:30]}...")

    def clear_chat_history(self):
        """Clear chat history"""
        self.chat_history.clear()
        self.ai_thread.clear_history()
        self.append_message("System", "Chat history cleared", "#ffaa00")
        self.update_status("Chat history cleared")

    def voice_input(self):
        """Simulate voice input (placeholder)"""
        QMessageBox.information(self, "Voice Input", 
                               "Voice input is not implemented in this version.\n"
                               "Future versions may include speech recognition.")

    def cleanup(self):
        """Cleanup AI thread"""
        self.ai_thread.stop()