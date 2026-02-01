import time
import sqlite3
from threading import Lock
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QFrame, QMessageBox
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer

class DatabaseThread(QThread):
    log_added = pyqtSignal(list)
    error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = True
        self.lock = Lock()
        self.db_conn = None
        self.db_cursor = None
        self.operation_queue = []

        # Initialize database
        try:
            self.db_conn = sqlite3.connect('telescope_logs.db', check_same_thread=False)
            self.db_cursor = self.db_conn.cursor()
            # Create table if not exists
            self.db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS telescope_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    altitude REAL,
                    azimuth REAL,
                    target TEXT,
                    action TEXT,
                    details TEXT
                )
            ''')
            self.db_conn.commit()
        except Exception as e:
            self.error_signal.emit(f"Database Error: {str(e)}")

    def set_operation(self, action, data):
        with self.lock:
            self.operation_queue.append((action, data))

    def run(self):
        if not self.db_conn:
            return

        while self.running:
            with self.lock:
                if not self.operation_queue:
                    time.sleep(0.1)
                    continue
                op, data = self.operation_queue.pop(0)

            try:
                if op == "log":
                    # Data format: (altitude, azimuth, target, action, details)
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    alt, az, target, action, details = data
                    self.db_cursor.execute('''
                        INSERT INTO telescope_logs 
                        (timestamp, altitude, azimuth, target, action, details)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (timestamp, alt, az, target, action, details))
                    self.db_conn.commit()
                    # Emit log for UI update
                    self.log_added.emit([timestamp, alt, az, target, action, details])
            except Exception as e:
                self.error_signal.emit(f"Log Error: {str(e)}")
                time.sleep(1)

    def stop(self):
        with self.lock:
            self.running = False
        if self.db_conn:
            self.db_conn.close()
        self.wait()

class DatabaseWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.db_thread = DatabaseThread()
        self.db_thread.log_added.connect(self.add_log_entry)
        self.db_thread.error_signal.connect(self.show_error)
        
        # UI Setup (800×480 optimized)
        self.init_ui()
        
        # Start database thread
        self.db_thread.start()

    def init_ui(self):
        layout = QVBoxLayout(self)
        # Small screen optimization
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel("Telescope Activity Logs")
        title.setObjectName("title_label")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #3498db;")
        layout.addWidget(title)

        # Log Table (compact for small screen)
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(6)
        self.log_table.setHorizontalHeaderLabels([
            "Time", "Alt (°)", "Az (°)", "Target", "Action", "Details"
        ])
        # Optimize table for small screen
        self.log_table.setStyleSheet("""
            QTableWidget { font-size: 11px; }
            QHeaderView::section { 
                font-size: 10px; 
                padding: 2px; 
                background-color: #3498db; 
                color: black;
            }
        """)
        # Resize columns to fit 800px width
        header = self.log_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Time
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Alt
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Az
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Target
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Action
        header.setSectionResizeMode(5, QHeaderView.Stretch)           # Details (fill remaining)
        
        # Limit table height for 480px window
        self.log_table.setMaximumHeight(280)
        layout.addWidget(self.log_table)

        # Control Buttons (smaller for 800×480)
        btn_layout = QHBoxLayout()
        self.clear_btn = QPushButton("Clear Logs")
        self.export_btn = QPushButton("Export Logs")
        # Match motor widget button styling
        btn_style = """
            QPushButton { 
                background-color: #3498db; 
                color: white; 
                border: none; 
                border-radius: 4px; 
                padding: 6px 8px; 
                font-size: 12px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """
        self.clear_btn.setStyleSheet(btn_style)
        self.export_btn.setStyleSheet(btn_style)

        self.clear_btn.clicked.connect(self.clear_logs)
        self.export_btn.clicked.connect(self.export_logs)

        btn_layout.addWidget(self.clear_btn)
        btn_layout.addWidget(self.export_btn)
        layout.addLayout(btn_layout)

        # Status Frame (compact)
        status_frame = QFrame()
        status_frame.setStyleSheet("background-color: #f8f9fa; border-radius: 4px; padding: 8px;")
        status_layout = QVBoxLayout(status_frame)
        self.log_count_label = QLabel("Total Logs: 0")
        self.log_count_label.setStyleSheet("font-size: 11px; color: #666;")
        status_layout.addWidget(self.log_count_label)
        layout.addWidget(status_frame)

    def add_log_entry(self, log_data):
        # Add new log to table (insert at top for readability)
        row = 0
        self.log_table.insertRow(row)
        for col, data in enumerate(log_data):
            # Format numeric values for compact display
            if col in [1,2] and data is not None:
                item = QTableWidgetItem(f"{data:.1f}")
            else:
                item = QTableWidgetItem(str(data) if data else "-")
            item.setTextAlignment(Qt.AlignCenter)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Read-only
            self.log_table.setItem(row, col, item)
        
        # Update log count
        self.log_count_label.setText(f"Total Logs: {self.log_table.rowCount()}")

    def clear_logs(self):
        confirm = QMessageBox.question(
            self, "Clear Logs", "Are you sure you want to clear all logs?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.log_table.setRowCount(0)
            # Clear database
            try:
                self.db_thread.db_cursor.execute("DELETE FROM telescope_logs")
                self.db_thread.db_conn.commit()
                self.log_count_label.setText("Total Logs: 0")
            except Exception as e:
                self.show_error(f"Clear Error: {str(e)}")

    def export_logs(self):
        try:
            import csv
            filename = f"telescope_logs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                # Write header
                writer.writerow(["Time", "Alt (°)", "Az (°)", "Target", "Action", "Details"])
                # Write rows
                for row in range(self.log_table.rowCount()):
                    row_data = []
                    for col in range(self.log_table.columnCount()):
                        item = self.log_table.item(row, col)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)
            QMessageBox.information(self, "Export Success", f"Logs exported to {filename}")
        except Exception as e:
            self.show_error(f"Export Error: {str(e)}")

    def show_error(self, error_msg):
        QMessageBox.critical(self, "Database Error", error_msg)

    def closeEvent(self, event):
        self.db_thread.stop()
        event.accept()

# Fix missing datetime import (critical for logs)
import datetime