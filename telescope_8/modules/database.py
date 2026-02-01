"""
Database & Logging Module
Optimized for Raspberry Pi 5 (800x480 Touchscreen)
Safe SETTINGS Access (No KeyErrors)
"""
import sys
import time
import logging
import sqlite3
import csv
import os
from pathlib import Path
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QTableWidget, QTableWidgetItem, QComboBox,
    QCheckBox, QFileDialog, QProgressBar, QMessageBox,
    QGridLayout, QSpinBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QMutex, QMutexLocker
from PyQt5.QtGui import QFont, QColor

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
# Logging Thread (Safe Settings Access)
# --------------------------
class LoggingThread(QThread):
    log_update = pyqtSignal(list)
    status_update = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    progress_update = pyqtSignal(int)
    
    def __init__(self):
        super().__init__()
        self.mutex = QMutex()
        self.running = False
        self.log_data = []
        
        # Safe SETTINGS access (fallback values for missing keys)
        self.save_interval = SETTINGS["database"].get("save_interval", 30)  # 30s default
        self.log_limit = SETTINGS["database"].get("log_limit", 1000)
        self.auto_save = SETTINGS["database"].get("auto_save", True)
        self.db_filename = SETTINGS["database"].get("db_filename", "telescope_logs.db")
        self.table_name = SETTINGS["database"].get("table_name", "telescope_data")
        
        # Database setup
        self.db_path = Path(__file__).parent.parent / "database" / self.db_filename
        self.db_path.parent.mkdir(exist_ok=True)  # Create database dir if missing
        self.conn = None
        self.cursor = None
        
        # Initialize database
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database (safe setup)"""
        try:
            # Create/connect to database
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self.cursor = self.conn.cursor()
            
            # Create table if not exists
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                altitude REAL,
                azimuth REAL,
                temperature REAL,
                humidity REAL,
                pressure REAL,
                camera_status TEXT,
                motor_status TEXT,
                notes TEXT
            )
            """
            self.cursor.execute(create_table_sql)
            self.conn.commit()
            
            logger.info(f"Database initialized: {self.db_path}")
            self.status_update.emit(f"Database ready: {self.db_filename}")
            
        except Exception as e:
            error_msg = f"Database init failed: {str(e)}"
            logger.error(error_msg)
            self.error_signal.emit(error_msg)
            # Fallback to in-memory logging
            self.conn = None
            self.cursor = None

    def log_data_point(self, data):
        """Log a single data point (thread-safe)"""
        locker = QMutexLocker(self.mutex)
        
        # Add timestamp if missing
        if "timestamp" not in data:
            data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Add to in-memory log
        self.log_data.append(data)
        
        # Trim log to limit
        if len(self.log_data) > self.log_limit:
            self.log_data = self.log_data[-self.log_limit:]
        
        # Emit update for UI
        self.log_update.emit([list(data.values())])
        
        # Auto-save if enabled
        if self.auto_save and len(self.log_data) % 10 == 0:  # Save every 10 entries
            self._save_to_database()

    def _save_to_database(self):
        """Save in-memory logs to database (safe)"""
        if not self.conn or not self.cursor:
            self.status_update.emit("Database not available - logging to memory only")
            return
        
        try:
            locker = QMutexLocker(self.mutex)
            if not self.log_data:
                return
            
            # Prepare insert statement
            insert_sql = f"""
            INSERT INTO {self.table_name} (
                timestamp, altitude, azimuth, temperature, humidity,
                pressure, camera_status, motor_status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            # Insert batch of records
            batch_size = 50
            batch = self.log_data[-batch_size:]  # Take last 50 entries
            values = [
                (
                    entry.get("timestamp", ""),
                    entry.get("altitude", 0.0),
                    entry.get("azimuth", 0.0),
                    entry.get("temperature", 0.0),
                    entry.get("humidity", 0.0),
                    entry.get("pressure", 0.0),
                    entry.get("camera_status", ""),
                    entry.get("motor_status", ""),
                    entry.get("notes", "")
                ) for entry in batch
            ]
            
            self.cursor.executemany(insert_sql, values)
            self.conn.commit()
            
            self.status_update.emit(f"Saved {len(batch)} records to database")
            self.progress_update.emit(min(100, int(len(self.log_data)/self.log_limit * 100)))
            
        except Exception as e:
            error_msg = f"Database save error: {str(e)}"
            logger.error(error_msg)
            self.error_signal.emit(error_msg)

    def export_logs(self, export_format="csv", filepath=None):
        """Export logs to file (CSV/JSON)"""
        if not filepath:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = Path(__file__).parent.parent / "exports" / f"telescope_logs_{timestamp}.{export_format}"
            filepath.parent.mkdir(exist_ok=True)
        
        try:
            locker = QMutexLocker(self.mutex)
            
            if export_format.lower() == "csv":
                # Export to CSV
                with open(filepath, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=self.log_data[0].keys())
                    writer.writeheader()
                    writer.writerows(self.log_data)
            elif export_format.lower() == "json":
                # Export to JSON
                import json
                with open(filepath, "w") as f:
                    json.dump(self.log_data, f, indent=2)
            else:
                raise Exception(f"Unsupported format: {export_format}")
            
            self.status_update.emit(f"Logs exported to: {filepath}")
            logger.info(f"Logs exported to {filepath}")
            return True
            
        except Exception as e:
            error_msg = f"Export error: {str(e)}"
            logger.error(error_msg)
            self.error_signal.emit(error_msg)
            return False

    def clear_logs(self):
        """Clear in-memory logs (safe)"""
        locker = QMutexLocker(self.mutex)
        self.log_data = []
        self.log_update.emit([])  # Signal UI to clear
        self.progress_update.emit(0)
        self.status_update.emit("In-memory logs cleared")

    def run(self):
        """Main logging thread loop"""
        self.running = True
        logger.info("Logging thread started (Pi 5 compatible)")
        
        last_save = time.time()
        while self.running:
            try:
                # Auto-save on interval
                if self.auto_save and (time.time() - last_save) >= self.save_interval:
                    self._save_to_database()
                    last_save = time.time()
                
                time.sleep(1.0)  # Check every second
                
            except Exception as e:
                error_msg = f"Logging thread error: {str(e)}"
                logger.error(error_msg)
                self.error_signal.emit(error_msg)
                time.sleep(1.0)

    def stop(self):
        """Stop thread and clean up"""
        locker = QMutexLocker(self.mutex)
        self.running = False
        
        # Final save before exit
        if self.auto_save:
            self._save_to_database()
        
        # Close database connection
        if self.conn:
            try:
                self.conn.close()
            except:
                pass
        
        logger.info("Logging thread stopped")

# --------------------------
# Database Widget (800x480 Touchscreen Optimized)
# --------------------------
class DatabaseWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(get_responsive_stylesheet())
        self.logging_thread = None
        self.log_headers = [
            "Timestamp", "Altitude (°)", "Azimuth (°)", 
            "Temp (°C)", "Humidity (%)", "Pressure (hPa)",
            "Camera Status", "Motor Status", "Notes"
        ]
        self.init_ui()
        self.init_logging_thread()

    def init_ui(self):
        """Create Touch-Optimized UI (800x480)"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # Title
        title_label = QLabel("Data Logging & Database")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # Database Settings Group
        settings_group = QGroupBox("Logging Settings")
        settings_layout = QGridLayout()
        settings_layout.setSpacing(6)

        # Auto-Save Toggle
        self.auto_save_check = QCheckBox("Auto-Save to Database")
        self.auto_save_check.setChecked(SETTINGS["database"].get("auto_save", True))
        self.auto_save_check.stateChanged.connect(self.update_auto_save)
        settings_layout.addWidget(self.auto_save_check, 0, 0, 1, 2)

        # Save Interval
        settings_layout.addWidget(QLabel("Save Interval (sec):"), 1, 0)
        self.save_interval_spin = QSpinBox()
        self.save_interval_spin.setRange(5, 300)
        self.save_interval_spin.setValue(SETTINGS["database"].get("save_interval", 30))
        self.save_interval_spin.valueChanged.connect(self.update_save_interval)
        settings_layout.addWidget(self.save_interval_spin, 1, 1)

        # Log Limit
        settings_layout.addWidget(QLabel("Log Limit:"), 2, 0)
        self.log_limit_spin = QSpinBox()
        self.log_limit_spin.setRange(100, 5000)
        self.log_limit_spin.setValue(SETTINGS["database"].get("log_limit", 1000))
        self.log_limit_spin.valueChanged.connect(self.update_log_limit)
        settings_layout.addWidget(self.log_limit_spin, 2, 1)

        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)

        # Log Table (Touch-Friendly)
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(len(self.log_headers))
        self.log_table.setHorizontalHeaderLabels(self.log_headers)
        self.log_table.horizontalHeader().setStretchLastSection(True)
        # Resize columns for small screen
        self.log_table.setColumnWidth(0, 120)  # Timestamp
        self.log_table.setColumnWidth(1, 60)   # Altitude
        self.log_table.setColumnWidth(2, 60)   # Azimuth
        self.log_table.setColumnWidth(3, 60)   # Temp
        self.log_table.setColumnWidth(4, 60)   # Humidity
        self.log_table.setColumnWidth(5, 70)   # Pressure
        self.log_table.setColumnWidth(6, 80)   # Camera
        self.log_table.setColumnWidth(7, 80)   # Motor
        self.log_table.setColumnWidth(8, 80)   # Notes
        main_layout.addWidget(self.log_table)

        # Log Progress
        self.log_progress = QProgressBar()
        self.log_progress.setRange(0, 100)
        self.log_progress.setValue(0)
        self.log_progress.setFormat("Log Usage: %p%")
        main_layout.addWidget(self.log_progress)

        # Control Buttons (Touch-Friendly Size)
        btn_layout = QHBoxLayout()
        
        self.export_btn = QPushButton("Export Logs")
        self.export_btn.setMinimumHeight(40)
        self.export_btn.clicked.connect(self.export_logs)
        btn_layout.addWidget(self.export_btn)

        self.clear_btn = QPushButton("Clear Logs")
        self.clear_btn.setMinimumHeight(40)
        self.clear_btn.clicked.connect(self.clear_logs)
        btn_layout.addWidget(self.clear_btn)

        self.save_btn = QPushButton("Save Now")
        self.save_btn.setMinimumHeight(40)
        self.save_btn.clicked.connect(self.save_now)
        btn_layout.addWidget(self.save_btn)

        main_layout.addLayout(btn_layout)

        # Status Display
        self.status_label = QLabel("Status: Initializing Logging...")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("background-color: #333333; padding: 5px; border-radius: 3px;")
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)

    def init_logging_thread(self):
        """Initialize logging thread (safe startup)"""
        # Stop existing thread
        if self.logging_thread:
            self.logging_thread.stop()
            self.logging_thread.wait()
        
        # Start new thread
        self.logging_thread = LoggingThread()
        
        # Connect signals
        self.logging_thread.log_update.connect(self.update_log_table)
        self.logging_thread.status_update.connect(self.update_status)
        self.logging_thread.error_signal.connect(self.show_error)
        self.logging_thread.progress_update.connect(self.log_progress.setValue)
        
        # Start thread
        self.logging_thread.start()
        
        # Apply initial settings
        self.update_auto_save()
        self.update_save_interval()
        self.update_log_limit()

    def update_log_table(self, new_rows):
        """Update log table with new data (thread-safe)"""
        # Clear table if empty list is received
        if not new_rows:
            self.log_table.setRowCount(0)
            return
        
        # Add new rows
        current_rows = self.log_table.rowCount()
        for row_data in new_rows:
            self.log_table.insertRow(current_rows)
            for col, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignCenter)
                self.log_table.setItem(current_rows, col, item)
            current_rows += 1
        
        # Scroll to bottom
        if current_rows > 0:
            self.log_table.scrollToBottom()

    def update_auto_save(self):
        """Update auto-save setting"""
        SETTINGS["database"]["auto_save"] = self.auto_save_check.isChecked()
        if self.logging_thread:
            self.logging_thread.auto_save = self.auto_save_check.isChecked()
        save_settings()
        self.update_status(f"Auto-save: {'Enabled' if self.auto_save_check.isChecked() else 'Disabled'}")

    def update_save_interval(self):
        """Update save interval setting"""
        SETTINGS["database"]["save_interval"] = self.save_interval_spin.value()
        if self.logging_thread:
            self.logging_thread.save_interval = self.save_interval_spin.value()
        save_settings()
        self.update_status(f"Save interval set to {self.save_interval_spin.value()} seconds")

    def update_log_limit(self):
        """Update log limit setting"""
        SETTINGS["database"]["log_limit"] = self.log_limit_spin.value()
        if self.logging_thread:
            self.logging_thread.log_limit = self.log_limit_spin.value()
        save_settings()
        self.update_status(f"Log limit set to {self.log_limit_spin.value()} entries")

    def export_logs(self):
        """Export logs to file"""
        # Show file dialog
        export_format = SETTINGS["database"].get("export_format", "csv")
        filters = f"{export_format.upper()} Files (*.{export_format});;All Files (*.*)"
        filepath, _ = QFileDialog.getSaveFileName(
            self, 
            "Export Logs", 
            f"telescope_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{export_format}",
            filters
        )
        
        if filepath:
            success = self.logging_thread.export_logs(export_format, filepath)
            if success:
                QMessageBox.information(self, "Export Success", f"Logs exported to:\n{filepath}")

    def clear_logs(self):
        """Clear logs (with confirmation)"""
        reply = QMessageBox.question(
            self, 
            "Clear Logs", 
            "Are you sure you want to clear all in-memory logs?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.logging_thread.clear_logs()
            self.update_status("Logs cleared successfully")

    def save_now(self):
        """Force save to database"""
        self.logging_thread._save_to_database()
        self.update_status("Forced save to database completed")

    def update_status(self, message):
        """Update status label with timestamp"""
        timestamp = time.strftime("%H:%M:%S")
        self.status_label.setText(f"[{timestamp}] Status: {message}")

    def show_error(self, message):
        """Show error message"""
        QMessageBox.critical(self, "Database Error", message)
        self.update_status(f"ERROR: {message}")

    def log_custom_data(self, data):
        """Log custom data point (call from other modules)"""
        if self.logging_thread:
            self.logging_thread.log_data_point(data)

    def cleanup(self):
        """Cleanup thread on exit"""
        if self.logging_thread:
            self.logging_thread.stop()
            self.logging_thread.wait()
        self.update_status("Logging thread cleaned up - safe to exit")

    def closeEvent(self, event):
        """Handle widget close"""
        self.cleanup()
        event.accept()

# --------------------------
# Standalone Test (For Debugging)
# --------------------------
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = DatabaseWidget()
    window.setWindowTitle("Database Control (Pi 5)")
    window.resize(800, 480)  # Full touchscreen size
    window.show()
    
    # Test logging a data point
    test_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "altitude": 45.0,
        "azimuth": 180.0,
        "temperature": 22.5,
        "humidity": 48.2,
        "pressure": 1013.25,
        "camera_status": "Idle",
        "motor_status": "Stopped",
        "notes": "Test entry"
    }
    window.log_custom_data(test_data)
    
    sys.exit(app.exec_())