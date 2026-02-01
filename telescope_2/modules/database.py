import sqlite3
import csv
import json
import os
import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTableWidget, QTableWidgetItem, QLineEdit,
    QComboBox, QDateEdit, QMessageBox, QFileDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QDate, QTimer
from PyQt5.QtGui import QFont

# Database Operation Thread (thread-safe for Pi 5 - avoids GUI freezing)
class DatabaseThread(QThread):
    query_result = pyqtSignal(list)  # Emits query results (list of rows)
    operation_complete = pyqtSignal(str)  # Emits status message

    def __init__(self, db_path="data/telescope_logs.db"):
        super().__init__()
        # Ensure data directory exists (Pi 5 file system)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.operation = None  # "log", "query", "export", "backup", "restore"
        self.params = None     # Parameters for the operation

    def init_database(self):
        """Initialize SQLite database and create logs table (run once)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # Create logs table with all required fields
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS telescope_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    altitude REAL NOT NULL,
                    azimuth REAL NOT NULL,
                    celestial_object TEXT,
                    event_type TEXT,  -- "position_update", "capture", "slew", "park"
                    notes TEXT
                )
            ''')
            conn.commit()
            conn.close()
            print(f"Database initialized (file: {self.db_path})")
        except Exception as e:
            self.operation_complete.emit(f"Database init error: {str(e)}")

    def set_operation(self, operation, params=None):
        """Set the database operation to execute (thread-safe)"""
        self.operation = operation
        self.params = params
        self.start()

    def run(self):
        """Execute database operations in background (Pi 5 optimized)"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA journal_mode=WAL")  # Optimize for Pi 5's I/O
            cursor = conn.cursor()

            if self.operation == "log":
                # Log telescope data (params: altitude, azimuth, object, event_type, notes)
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                alt, az, obj, event, notes = self.params
                cursor.execute('''
                    INSERT INTO telescope_logs 
                    (timestamp, altitude, azimuth, celestial_object, event_type, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (timestamp, alt, az, obj, event, notes))
                conn.commit()
                self.operation_complete.emit("Log entry added successfully")

            elif self.operation == "query":
                # Query logs (params: start_date, end_date, object, event_type)
                start_date, end_date, obj, event = self.params
                query = '''
                    SELECT timestamp, altitude, azimuth, celestial_object, event_type, notes
                    FROM telescope_logs
                    WHERE timestamp BETWEEN ? AND ?
                '''
                params = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
                
                # Add optional filters
                if obj:
                    query += " AND celestial_object = ?"
                    params.append(obj)
                if event:
                    query += " AND event_type = ?"
                    params.append(event)
                
                cursor.execute(query, params)
                results = cursor.fetchall()
                self.query_result.emit(results)
                self.operation_complete.emit(f"Query returned {len(results)} rows")

            elif self.operation == "export_csv":
                # Export logs to CSV (params: file_path, data)
                file_path, data = self.params
                with open(file_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Timestamp", "Altitude (°)", "Azimuth (°)", "Celestial Object", "Event Type", "Notes"])
                    writer.writerows(data)
                self.operation_complete.emit(f"Exported to CSV: {file_path}")

            elif self.operation == "export_json":
                # Export logs to JSON (params: file_path, data)
                file_path, data = self.params
                json_data = []
                for row in data:
                    json_data.append({
                        "timestamp": row[0],
                        "altitude_deg": row[1],
                        "azimuth_deg": row[2],
                        "celestial_object": row[3],
                        "event_type": row[4],
                        "notes": row[5]
                    })
                with open(file_path, 'w') as f:
                    json.dump(json_data, f, indent=2)
                self.operation_complete.emit(f"Exported to JSON: {file_path}")

            elif self.operation == "backup":
                # Backup database (params: backup_path)
                backup_path = self.params
                with open(self.db_path, 'rb') as src, open(backup_path, 'wb') as dst:
                    dst.write(src.read())
                self.operation_complete.emit(f"Database backed up to: {backup_path}")

            elif self.operation == "restore":
                # Restore database (params: backup_path)
                backup_path = self.params
                if os.path.exists(backup_path):
                    with open(backup_path, 'rb') as src, open(self.db_path, 'wb') as dst:
                        dst.write(src.read())
                    self.operation_complete.emit(f"Database restored from: {backup_path}")
                else:
                    self.operation_complete.emit(f"Backup file not found: {backup_path}")

            conn.close()
        except Exception as e:
            self.operation_complete.emit(f"Database error: {str(e)}")

# Main Database Widget for GUI
class DatabaseWidget(QWidget):  # Critical: Exact class name for main.py import
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self._setup_ui()
        self.setLayout(self.layout)

        # Initialize database thread (Pi 5 optimized)
        self.db_thread = DatabaseThread()
        self.db_thread.init_database()
        self.db_thread.query_result.connect(self._populate_table)
        self.db_thread.operation_complete.connect(self._show_status)

        # Store current query results (for export)
        self.current_results = []

    def _setup_ui(self):
        """Create database UI with query, export, backup features"""
        # Title
        self.layout.addWidget(QLabel("<h2>Telescope Data Logging</h2>"))

        # Query Controls
        query_group = QGroupBox("Filter & Query Logs")
        query_layout = QHBoxLayout()

        # Date range
        query_layout.addWidget(QLabel("Start Date:"))
        self.start_date = QDateEdit(QDate.currentDate())
        self.start_date.setCalendarPopup(True)
        query_layout.addWidget(self.start_date)

        query_layout.addWidget(QLabel("End Date:"))
        self.end_date = QDateEdit(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        query_layout.addWidget(self.end_date)

        # Celestial object filter
        query_layout.addWidget(QLabel("Object:"))
        self.obj_filter = QLineEdit()
        self.obj_filter.setPlaceholderText("e.g., Sun, Moon")
        query_layout.addWidget(self.obj_filter)

        # Event type filter
        query_layout.addWidget(QLabel("Event:"))
        self.event_filter = QComboBox()
        self.event_filter.addItems(["", "position_update", "capture", "slew", "park"])
        query_layout.addWidget(self.event_filter)

        # Query button
        self.query_btn = QPushButton("Run Query")
        self.query_btn.clicked.connect(self._run_query)
        query_layout.addWidget(self.query_btn)

        query_group.setLayout(query_layout)
        self.layout.addWidget(query_group)

        # Results Table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels([
            "Timestamp", "Altitude (°)", "Azimuth (°)", "Celestial Object", "Event Type", "Notes"
        ])
        # Make table touch-friendly (Pi 5 touchscreen)
        self.results_table.horizontalHeader().setMinimumSectionSize(120)
        self.results_table.setFont(QFont("Arial", 10))
        self.layout.addWidget(self.results_table)

        # Action Buttons (Export/Backup/Restore)
        action_layout = QHBoxLayout()

        # Export buttons
        self.export_csv_btn = QPushButton("Export to CSV")
        self.export_csv_btn.clicked.connect(self._export_csv)
        action_layout.addWidget(self.export_csv_btn)

        self.export_json_btn = QPushButton("Export to JSON")
        self.export_json_btn.clicked.connect(self._export_json)
        action_layout.addWidget(self.export_json_btn)

        # Backup/Restore buttons
        self.backup_btn = QPushButton("Backup Database")
        self.backup_btn.clicked.connect(self._backup_database)
        action_layout.addWidget(self.backup_btn)

        self.restore_btn = QPushButton("Restore Database")
        self.restore_btn.clicked.connect(self._restore_database)
        action_layout.addWidget(self.restore_btn)

        self.layout.addLayout(action_layout)

        # Status Label
        self.status_label = QLabel("Status: Ready")
        self.status_label.setStyleSheet("color: #ffffff;")
        self.layout.addWidget(self.status_label)

    def _run_query(self):
        """Trigger database query (thread-safe)"""
        start = self.start_date.date().toString("yyyy-MM-dd")
        end = self.end_date.date().toString("yyyy-MM-dd")
        obj = self.obj_filter.text().strip()
        event = self.event_filter.currentText()
        
        self.db_thread.set_operation("query", (start, end, obj, event))
        self.status_label.setText("Status: Running query...")

    def _populate_table(self, results):
        """Populate table with query results (Pi 5 UI optimized)"""
        self.current_results = results
        self.results_table.setRowCount(0)  # Clear existing rows
        
        for row_idx, row_data in enumerate(results):
            self.results_table.insertRow(row_idx)
            for col_idx, value in enumerate(row_data):
                # Format numbers for readability
                if col_idx in [1, 2]:  # Altitude/Azimuth
                    item = QTableWidgetItem(f"{value:.1f}")
                else:
                    item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignCenter)
                self.results_table.setItem(row_idx, col_idx, item)
        
        self.status_label.setText(f"Status: Query complete ({len(results)} rows)")

    def _export_csv(self):
        """Export current results to CSV (Pi 5 file system compatible)"""
        if not self.current_results:
            QMessageBox.warning(self, "No Data", "Run a query first to get data to export")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV File", 
            f"data/telecope_logs_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
            "CSV Files (*.csv)"
        )
        if file_path:
            self.db_thread.set_operation("export_csv", (file_path, self.current_results))

    def _export_json(self):
        """Export current results to JSON"""
        if not self.current_results:
            QMessageBox.warning(self, "No Data", "Run a query first to get data to export")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save JSON File", 
            f"data/telecope_logs_{datetime.datetime.now().strftime('%Y%m%d')}.json",
            "JSON Files (*.json)"
        )
        if file_path:
            self.db_thread.set_operation("export_json", (file_path, self.current_results))

    def _backup_database(self):
        """Backup the SQLite database file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Backup Database", 
            f"data/telescope_logs_backup_{datetime.datetime.now().strftime('%Y%m%d')}.db",
            "SQLite Files (*.db)"
        )
        if file_path:
            self.db_thread.set_operation("backup", file_path)

    def _restore_database(self):
        """Restore the SQLite database from a backup"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Restore Database", 
            "data/",
            "SQLite Files (*.db)"
        )
        if file_path:
            reply = QMessageBox.question(
                self, "Confirm Restore",
                "Restoring will overwrite current database. Are you sure?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.db_thread.set_operation("restore", file_path)

    def _show_status(self, message):
        """Show database operation status to user"""
        self.status_label.setText(f"Status: {message}")
        # Show popup for critical operations
        if "error" in message.lower():
            QMessageBox.critical(self, "Database Error", message)
        elif "exported" in message or "backed up" in message or "restored" in message:
            QMessageBox.information(self, "Success", message)

    def log_telescope_data(self, alt, az, obj="", event="position_update", notes=""):
        """Public method to log telescope data (called from other modules)"""
        self.db_thread.set_operation("log", (alt, az, obj, event, notes))

    def closeEvent(self, event):
        """Clean up database thread on widget close (Pi 5 resource management)"""
        self.db_thread.quit()
        self.db_thread.wait()
        event.accept()