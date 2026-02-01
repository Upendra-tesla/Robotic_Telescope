import requests
import json
import os
import datetime  # Add missing import
from dotenv import load_dotenv
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QLineEdit, QPushButton, QGroupBox, QComboBox, QMessageBox,
    QCheckBox, QFileDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor

# Load environment variables (API keys)
load_dotenv()

# AI API Thread (thread-safe, NO pigpio)
class DeepSeekThread(QThread):
    response_received = pyqtSignal(str)  # Emits AI response text
    error_occurred = pyqtSignal(str)     # Emits error message
    loading = pyqtSignal(bool)           # Emits loading state (True/False)

    def __init__(self):
        super().__init__()
        self.api_mode = "free"  # "free" or "paid"
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.user_query = ""
        self.context = {}       # Context: telescope position, time, location

    def set_api_mode(self, mode):
        """Switch between free/paid DeepSeek API mode"""
        self.api_mode = mode

    def set_api_key(self, key):
        """Update DeepSeek API key"""
        self.api_key = key
        # Save to .env file (optional)
        with open(".env", "a") as f:
            f.write(f"\nDEEPSEEK_API_KEY={key}")

    def set_context(self, context):
        """Set context for AI (telescope position, time, location)"""
        self.context = context

    def run_query(self, query):
        """Trigger AI query (thread-safe)"""
        self.user_query = query
        self.start()

    def run(self):
        """Execute DeepSeek API call in background (NO pigpio)"""
        self.loading.emit(True)
        try:
            # Validate API key (only for paid mode)
            if not self.api_key and self.api_mode == "paid":
                self.error_occurred.emit("Paid API mode requires a DeepSeek API key (set in .env or UI)")
                self.loading.emit(False)
                return

            # Build API endpoint and headers (compatible with Pi 5)
            url = "https://api.deepseek.com/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}" if self.api_key else ""
            }

            # Build context-aware prompt (telescope position/time)
            context_text = f"""
            CONTEXT:
            - Current Time: {self.context.get('time', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}
            - Telescope Position: Alt={self.context.get('alt', 0.0)}°, Az={self.context.get('az', 0.0)}°
            - GPS Location: {self.context.get('gps', 'Lat: 40.7128° N, Lon: 74.0060° W')}
            - Weather: {self.context.get('weather', 'Clear')}
            
            USER QUESTION: {self.user_query}
            
            INSTRUCTIONS:
            - Answer as an astronomy expert and telescope operation guide
            - Keep responses concise (optimized for Pi 5 screen)
            - Reference the provided context (telescope position/location/time)
            """

            # API request payload (Pi 5 memory-optimized)
            payload = {
                "model": "deepseek-chat" if self.api_mode == "paid" else "deepseek-free",
                "messages": [{"role": "user", "content": context_text}],
                "temperature": 0.7,
                "max_tokens": 500  # Avoid memory issues on Pi 5
            }

            # Make API call (Pi 5 network-optimized timeout)
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=30  # Longer timeout for Pi 5 internet
            )

            # Parse response
            if response.status_code == 200:
                result = response.json()
                ai_response = result["choices"][0]["message"]["content"].strip()
                self.response_received.emit(ai_response)
            else:
                self.error_occurred.emit(f"API Error: {response.status_code} - {response.text}")

        except requests.exceptions.ConnectionError:
            self.error_occurred.emit("Network Error: Could not connect to DeepSeek API (check Pi 5 internet)")
        except Exception as e:
            self.error_occurred.emit(f"Unexpected Error: {str(e)}")
        finally:
            self.loading.emit(False)

# Main AI Widget (FIXED: ai_thread initialized BEFORE _setup_ui)
class AIWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()

        # CRITICAL FIX: Create ai_thread BEFORE _setup_ui()
        self.ai_thread = DeepSeekThread()
        self.ai_thread.response_received.connect(self._add_ai_response)
        self.ai_thread.error_occurred.connect(self._show_error)
        self.ai_thread.loading.connect(self._toggle_loading)

        # Chat history (persisted to file)
        self.chat_history = []
        self.chat_history_path = "data/ai_chat_history.json"
        self._load_chat_history()

        # Current telescope context (mock data - no pigpio)
        self.current_context = {
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "alt": 0.0,
            "az": 0.0,
            "gps": "Lat: 40.7128° N, Lon: 74.0060° W",
            "weather": "Clear"
        }
        self.ai_thread.set_context(self.current_context)

        # Now setup UI (ai_thread exists - no AttributeError)
        self._setup_ui()

        self.setLayout(self.layout)

    def _setup_ui(self):
        """Create AI Assistant UI (touch-friendly, NO pigpio)"""
        # Title
        self.layout.addWidget(QLabel("<h2>DeepSeek AI Assistant</h2>"))

        # API Settings
        api_group = QGroupBox("API Settings")
        api_layout = QHBoxLayout()

        # API Mode (Free/Paid) - connects to existing ai_thread
        api_layout.addWidget(QLabel("API Mode:"))
        self.api_mode_combo = QComboBox()
        self.api_mode_combo.addItems(["free", "paid"])
        self.api_mode_combo.currentTextChanged.connect(self.ai_thread.set_api_mode)
        api_layout.addWidget(self.api_mode_combo)

        # API Key Input
        api_layout.addWidget(QLabel("API Key:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Enter DeepSeek API key (paid mode only)")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        # Load existing API key from .env
        self.api_key_input.setText(os.getenv("DEEPSEEK_API_KEY", ""))
        api_layout.addWidget(self.api_key_input)

        # Save API Key Button
        self.save_key_btn = QPushButton("Save Key")
        self.save_key_btn.clicked.connect(lambda: self.ai_thread.set_api_key(self.api_key_input.text()))
        api_layout.addWidget(self.save_key_btn)

        api_group.setLayout(api_layout)
        self.layout.addWidget(api_group)

        # Chat History Display (read-only)
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("background-color: #2d2d2d; color: #ffffff; font-size: 12px;")
        self.chat_display.setFont(QFont("Arial", 11))  # Pi 5 touch-friendly
        self.layout.addWidget(self.chat_display)

        # Input Area
        input_layout = QHBoxLayout()

        # User Input
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Ask about astronomy/telescope control...")
        self.user_input.returnPressed.connect(self._send_query)  # Enter key to send
        input_layout.addWidget(self.user_input, 4)  # 80% width

        # Send Button
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._send_query)
        self.send_btn.setMinimumSize(80, 40)  # Touch-friendly
        input_layout.addWidget(self.send_btn, 1)  # 20% width

        self.layout.addLayout(input_layout)

        # Optional Features (mock voice input - no hardware)
        feature_layout = QHBoxLayout()

        self.voice_input_btn = QPushButton("Voice Input (Beta)")
        self.voice_input_btn.clicked.connect(lambda: QMessageBox.information(self, "Info", "Voice input requires a microphone on Pi 5"))
        feature_layout.addWidget(self.voice_input_btn)

        self.save_chat_btn = QPushButton("Save Chat History")
        self.save_chat_btn.clicked.connect(self._save_chat_history)
        feature_layout.addWidget(self.save_chat_btn)

        self.clear_chat_btn = QPushButton("Clear Chat")
        self.clear_chat_btn.clicked.connect(self._clear_chat)
        feature_layout.addWidget(self.clear_chat_btn)

        self.layout.addLayout(feature_layout)

        # Status Label
        self.status_label = QLabel("Status: Ready (Free API Mode)")
        self.status_label.setStyleSheet("color: #ffffff;")
        self.layout.addWidget(self.status_label)

    def _send_query(self):
        """Send user query to AI thread (thread-safe, NO pigpio)"""
        query = self.user_input.text().strip()
        if not query:
            QMessageBox.warning(self, "Empty Input", "Please enter a question for the AI assistant")
            return

        # Update context (refresh time/location)
        self.current_context["time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.ai_thread.set_context(self.current_context)

        # Add user message to chat display
        self._add_chat_message("You", query, QColor("#404040"))
        self.user_input.clear()

        # Send query to AI thread
        self.ai_thread.run_query(query)

    def _add_ai_response(self, response):
        """Add AI response to chat display"""
        self._add_chat_message("AI Assistant", response, QColor("#1a1a1a"))
        # Save to chat history
        self.chat_history.append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.datetime.now().isoformat()
        })

    def _add_chat_message(self, sender, message, bg_color):
        """Format and add message to chat display"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_message = f"<font color='#ffffff'><b>{sender} ({timestamp}):</b></font><br>{message}<br><br>"
        
        # Update display (Pi 5 optimized)
        self.chat_display.setTextColor(Qt.white)
        self.chat_display.append(formatted_message)
        # Scroll to bottom
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())

    def _show_error(self, error_msg):
        """Show AI error message to user"""
        self.status_label.setText(f"Status: Error - {error_msg}")
        QMessageBox.critical(self, "AI Error", error_msg)
        # Add error to chat display
        self._add_chat_message("System", f"Error: {error_msg}", QColor("#ff3333"))

    def _toggle_loading(self, is_loading):
        """Toggle loading state (disable send button)"""
        self.send_btn.setEnabled(not is_loading)
        self.user_input.setEnabled(not is_loading)
        if is_loading:
            self.status_label.setText(f"Status: Loading AI response ({self.api_mode_combo.currentText()} mode)...")
        else:
            self.status_label.setText(f"Status: Ready ({self.api_mode_combo.currentText()} mode)")

    def _load_chat_history(self):
        """Load saved chat history (Pi 5 file system)"""
        try:
            if os.path.exists(self.chat_history_path):
                with open(self.chat_history_path, "r") as f:
                    self.chat_history = json.load(f)
                # Populate chat display with history
                for msg in self.chat_history:
                    sender = "You" if msg["role"] == "user" else "AI Assistant"
                    self._add_chat_message(sender, msg["content"], QColor("#404040") if msg["role"] == "user" else QColor("#1a1a1a"))
        except Exception as e:
            self.status_label.setText(f"Status: Could not load chat history - {str(e)}")

    def _save_chat_history(self):
        """Save chat history to JSON (Pi 5 compatible)"""
        try:
            os.makedirs(os.path.dirname(self.chat_history_path), exist_ok=True)
            with open(self.chat_history_path, "w") as f:
                json.dump(self.chat_history, f, indent=2)
            QMessageBox.information(self, "Success", f"Chat history saved to: {self.chat_history_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save chat history: {str(e)}")

    def _clear_chat(self):
        """Clear chat display and history"""
        self.chat_display.clear()
        self.chat_history = []
        self.status_label.setText("Status: Chat history cleared")

    def update_telescope_context(self, alt, az, gps, weather):
        """Update context from main window (mock data - no pigpio)"""
        self.current_context.update({
            "alt": alt,
            "az": az,
            "gps": gps,
            "weather": weather
        })
        self.ai_thread.set_context(self.current_context)

    def closeEvent(self, event):
        """Clean up AI thread (NO pigpio)"""
        self.ai_thread.quit()
        self.ai_thread.wait()
        self._save_chat_history()
        event.accept()