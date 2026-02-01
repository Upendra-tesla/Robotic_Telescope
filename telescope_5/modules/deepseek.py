import requests
import json
import os
import datetime
from dotenv import load_dotenv

# Fixed import block (all required widgets included)
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QLineEdit, QPushButton, QMessageBox, QComboBox, QGroupBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor

# Load environment variables (Pi 5 compatible)
load_dotenv()

# AI API Thread (Pi 5 Thread-Safe)
class DeepSeekThread(QThread):
    response_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    loading = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.api_mode = "free"
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.user_query = ""
        self.context = {}  # Telescope context (alt/az/gps)

    def set_api_mode(self, mode):
        self.api_mode = mode

    def set_api_key(self, key):
        self.api_key = key
        # Save key to .env file (Pi 5 compatible)
        with open(".env", "a") as f:
            f.write(f"\nDEEPSEEK_API_KEY={key}")

    def set_context(self, context):
        self.context = context

    def run_query(self, query):
        self.user_query = query
        self.start()

    def run(self):
        """DeepSeek API Call (Pi 5 Optimized)"""
        self.loading.emit(True)
        try:
            # Validate API key for paid mode
            if self.api_mode == "paid" and not self.api_key:
                self.error_occurred.emit("Paid API mode requires a DeepSeek API key!")
                self.loading.emit(False)
                return

            # API endpoint and headers
            url = "https://api.deepseek.com/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}" if self.api_mode == "paid" else ""
            }

            # Build context-aware prompt
            context_text = f"""
            CONTEXT (Telescope on Raspberry Pi 5):
            - Current Time: {self.context.get('time', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}
            - Telescope Position: Alt={self.context.get('alt', 0.0)}°, Az={self.context.get('az', 0.0)}°
            - GPS Location: {self.context.get('gps', 'Lat: 40.7128° N, Lon: 74.0060° W')}
            
            USER QUESTION: {self.user_query}
            
            INSTRUCTIONS:
            - Answer as an astronomy expert (Pi 5 optimized for concise responses)
            - Reference the telescope context if relevant
            - Keep answers short (适合small Pi 5 screen)
            """

            # Payload (Pi 5 memory optimized)
            payload = {
                "model": "deepseek-chat" if self.api_mode == "paid" else "deepseek-free",
                "messages": [{"role": "user", "content": context_text}],
                "temperature": 0.7,
                "max_tokens": 500
            }

            # Make API call (Pi 5 network timeout optimized)
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=30  # Longer timeout for Pi 5 slow internet
            )

            if response.status_code == 200:
                result = response.json()
                ai_response = result["choices"][0]["message"]["content"].strip()
                self.response_received.emit(ai_response)
            else:
                self.error_occurred.emit(f"API Error: {response.status_code} - {response.text}")

        except requests.exceptions.ConnectionError:
            self.error_occurred.emit("Network Error: Check Pi 5 internet connection!")
        except Exception as e:
            self.error_occurred.emit(f"Unexpected Error: {str(e)}")
        finally:
            self.loading.emit(False)

# Fixed DeepSeekWidget (all imports resolved)
class DeepSeekWidget(QWidget):
    def __init__(self):
        super().__init__()
        # Initialize AI thread
        self.ai_thread = DeepSeekThread()
        self.ai_thread.response_received.connect(self._show_response)
        self.ai_thread.error_occurred.connect(self._show_error)
        self.ai_thread.loading.connect(self._toggle_loading)

        # Chat history (Pi 5 persistent storage)
        self.chat_history = []
        self.chat_history_path = "data/ai_chat_history.json"
        os.makedirs("data", exist_ok=True)
        self._load_chat_history()

        # Telescope context
        self.current_context = {
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "alt": 0.0,
            "az": 0.0,
            "gps": "Lat: 40.7128° N, Lon: 74.0060° W"
        }
        self.ai_thread.set_context(self.current_context)

        # Preserve original UI structure
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        # AI Assistant Group (now QGroupBox is defined!)
        ai_group = QGroupBox("DeepSeek AI Assistant")
        group_layout = QVBoxLayout(ai_group)

        # API Settings (Original UI + Fixed Imports)
        api_layout = QHBoxLayout()
        api_layout.addWidget(QLabel("API Mode:"))
        self.api_mode_combo = QComboBox()
        self.api_mode_combo.addItems(["free", "paid"])
        self.api_mode_combo.currentTextChanged.connect(self.ai_thread.set_api_mode)
        api_layout.addWidget(self.api_mode_combo)
        
        api_layout.addWidget(QLabel("DeepSeek API Key:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("Enter API key (paid mode only)")
        self.api_key_input.setText(os.getenv("DEEPSEEK_API_KEY", ""))
        api_layout.addWidget(self.api_key_input)
        
        self.save_key_btn = QPushButton("Save Key")
        self.save_key_btn.clicked.connect(lambda: self.ai_thread.set_api_key(self.api_key_input.text()))
        api_layout.addWidget(self.save_key_btn)
        group_layout.addLayout(api_layout)

        # Prompt Input (Original UI)
        prompt_layout = QVBoxLayout()
        prompt_layout.addWidget(QLabel("Enter your astronomical query:"))
        self.prompt_input = QTextEdit()
        self.prompt_input.setFixedHeight(100)
        self.prompt_input.setPlaceholderText("e.g., Best time to observe Jupiter tonight?")
        prompt_layout.addWidget(self.prompt_input)
        group_layout.addLayout(prompt_layout)

        # Submit Button (Original UI)
        self.submit_btn = QPushButton("Submit Query to DeepSeek")
        self.submit_btn.clicked.connect(self._submit_query)
        group_layout.addWidget(self.submit_btn)

        # Response Display (Original UI)
        response_layout = QVBoxLayout()
        response_layout.addWidget(QLabel("DeepSeek AI Response:"))
        self.response_text = QTextEdit()
        self.response_text.setReadOnly(True)
        self.response_text.setFixedHeight(200)
        response_layout.addWidget(self.response_text)
        group_layout.addLayout(response_layout)

        # Chat Management Buttons (Original UI)
        chat_layout = QHBoxLayout()
        self.save_chat_btn = QPushButton("Save Chat History")
        self.save_chat_btn.clicked.connect(self._save_chat_history)
        self.clear_chat_btn = QPushButton("Clear Chat")
        self.clear_chat_btn.clicked.connect(self._clear_chat)
        chat_layout.addWidget(self.save_chat_btn)
        chat_layout.addWidget(self.clear_chat_btn)
        group_layout.addLayout(chat_layout)

        main_layout.addWidget(ai_group)

    def _submit_query(self):
        """Submit query to AI (Original Logic)"""
        api_key = self.api_key_input.text().strip()
        prompt = self.prompt_input.toPlainText().strip()

        if self.api_mode_combo.currentText() == "paid" and not api_key:
            QMessageBox.warning(self, "Error", "Enter API key for paid mode!")
            return
        if not prompt:
            QMessageBox.warning(self, "Error", "Enter a query!")
            return

        # Update context
        self.current_context["time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.ai_thread.set_context(self.current_context)

        # Run query
        self.response_text.clear()
        self.response_text.append("Processing query (Pi 5 optimized)...")
        self.ai_thread.run_query(prompt)

        # Save to chat history
        self.chat_history.append({
            "role": "user",
            "content": prompt,
            "timestamp": datetime.datetime.now().isoformat()
        })

    def _show_response(self, response):
        """Display AI response"""
        self.response_text.clear()
        self.response_text.append(response)
        
        # Save to chat history
        self.chat_history.append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.datetime.now().isoformat()
        })

    def _show_error(self, error_msg):
        """Display error message"""
        self.response_text.clear()
        self.response_text.append(f"Error: {error_msg}")
        QMessageBox.critical(self, "AI Error", error_msg)

    def _toggle_loading(self, is_loading):
        """Toggle loading state"""
        self.submit_btn.setEnabled(not is_loading)
        self.prompt_input.setEnabled(not is_loading)

    def _load_chat_history(self):
        """Load chat history (Pi 5 compatible)"""
        try:
            if os.path.exists(self.chat_history_path):
                with open(self.chat_history_path, "r") as f:
                    self.chat_history = json.load(f)
        except Exception as e:
            print(f"Pi 5 Chat History Load Error: {e}")

    def _save_chat_history(self):
        """Save chat history"""
        try:
            with open(self.chat_history_path, "w") as f:
                json.dump(self.chat_history, f, indent=2)
            QMessageBox.information(self, "Success", "Chat history saved to Pi 5 storage!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save chat: {e}")

    def _clear_chat(self):
        """Clear chat history"""
        self.response_text.clear()
        self.chat_history = []
        QMessageBox.information(self, "Info", "Chat history cleared!")

    def update_telescope_context(self, alt, az, gps):
        """Update telescope context for AI"""
        self.current_context.update({
            "alt": alt,
            "az": az,
            "gps": gps
        })
        self.ai_thread.set_context(self.current_context)

    def closeEvent(self, event):
        """Pi 5 Resource Cleanup"""
        self.ai_thread.quit()
        self.ai_thread.wait()
        self._save_chat_history()
        event.accept()