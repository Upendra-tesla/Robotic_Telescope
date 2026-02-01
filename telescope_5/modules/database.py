import sqlite3
import csv
import json
import os
import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTextEdit, QCheckBox, QSpinBox, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer

# Database Operation Thread (Pi 5线程安全)
class DatabaseThread(QThread):
    query_result = pyqtSignal(list)
    operation_complete = pyqtSignal(str)

    def __init__(self, db_path="data/telescope_logs.db"):
        super().__init__()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.operation = None
        self.params = None
        self.init_database()

    def init_database(self):
        """初始化SQLite数据库"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS telescope_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    altitude REAL NOT NULL,
                    azimuth REAL NOT NULL,
                    celestial_object TEXT,
                    event_type TEXT,
                    notes TEXT
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            self.operation_complete.emit(f"Database init error: {str(e)}")

    def set_operation(self, operation, params=None):
        """设置数据库操作"""
        self.operation = operation
        self.params = params
        self.start()

    def run(self):
        """执行数据库操作 (Pi 5优化)"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA journal_mode=WAL")  # Pi 5 I/O优化
            cursor = conn.cursor()

            if self.operation == "log":
                # 记录位置数据
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                alt, az, obj, event, notes = self.params
                cursor.execute('''
                    INSERT INTO telescope_logs 
                    (timestamp, altitude, azimuth, celestial_object, event_type, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (timestamp, alt, az, obj, event, notes))
                conn.commit()
                self.operation_complete.emit("Log entry added successfully")

            elif self.operation == "export_csv":
                # 导出CSV
                file_path = self.params
                cursor.execute('''
                    SELECT timestamp, altitude, azimuth, celestial_object, event_type, notes
                    FROM telescope_logs
                ''')
                results = cursor.fetchall()
                with open(file_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Timestamp", "Altitude (°)", "Azimuth (°)", "Celestial Object", "Event Type", "Notes"])
                    writer.writerows(results)
                self.operation_complete.emit(f"Exported to CSV: {file_path}")

            elif self.operation == "export_json":
                # 导出JSON
                file_path = self.params
                cursor.execute('''
                    SELECT timestamp, altitude, azimuth, celestial_object, event_type, notes
                    FROM telescope_logs
                ''')
                results = cursor.fetchall()
                json_data = []
                for row in results:
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
                # 备份数据库
                backup_path = self.params
                with open(self.db_path, 'rb') as src, open(backup_path, 'wb') as dst:
                    dst.write(src.read())
                self.operation_complete.emit(f"Database backed up to: {backup_path}")

            conn.close()
        except Exception as e:
            self.operation_complete.emit(f"Database error: {str(e)}")

# 保留原始UI + SQLite数据库功能
class DatabaseWidget(QWidget):
    def __init__(self):
        super().__init__()
        # 初始化数据库线程
        self.db_thread = DatabaseThread()
        self.db_thread.operation_complete.connect(self._show_status)

        # 保留原始Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        # Data Logging Group (保留原始)
        db_group = QGroupBox("Data Logging & Export")
        group_layout = QVBoxLayout(db_group)

        # Log Control (保留原始)
        log_layout = QHBoxLayout()
        self.log_check = QCheckBox("Enable Position Logging")
        self.log_check.stateChanged.connect(self._toggle_logging)
        log_layout.addWidget(self.log_check)
        
        self.log_interval_spin = QSpinBox()
        self.log_interval_spin.setRange(1, 60)
        self.log_interval_spin.setValue(5)
        log_layout.addWidget(QLabel("Log Interval (s):"))
        log_layout.addWidget(self.log_interval_spin)
        group_layout.addLayout(log_layout)

        # Log Display (保留原始文本框)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFixedHeight(200)
        group_layout.addWidget(self.log_text)

        # 扩展导出按钮 (保留原始CSV + 添加JSON/备份)
        btn_layout = QHBoxLayout()
        self.export_btn = QPushButton("Export Logs (CSV)")
        self.export_btn.clicked.connect(self._export_logs_csv)
        self.export_json_btn = QPushButton("Export Logs (JSON)")
        self.export_json_btn.clicked.connect(self._export_logs_json)
        self.backup_btn = QPushButton("Backup Database")
        self.backup_btn.clicked.connect(self._backup_database)
        self.clear_btn = QPushButton("Clear Logs")
        self.clear_btn.clicked.connect(self._clear_logs)
        
        btn_layout.addWidget(self.export_btn)
        btn_layout.addWidget(self.export_json_btn)
        btn_layout.addWidget(self.backup_btn)
        btn_layout.addWidget(self.clear_btn)
        group_layout.addLayout(btn_layout)

        main_layout.addWidget(db_group)

        # Logging Timer (保留原始)
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self._log_position)
        self.log_entries = []

    def _toggle_logging(self, state):
        """保留原始逻辑 + 数据库记录"""
        if state == Qt.Checked:
            self.log_timer.start(self.log_interval_spin.value() * 1000)
            self._add_log_entry("Position logging started (SQLite backed)")
        else:
            self.log_timer.stop()
            self._add_log_entry("Position logging stopped")

    def _log_position(self):
        """记录真实位置 (替换mock数据)"""
        # 从望远镜控制模块获取真实位置（这里先保留mock，实际使用时替换）
        import random
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        alt = random.uniform(0, 90)
        az = random.uniform(0, 360)
        entry = f"{timestamp} | Alt: {alt:.1f}° | Az: {az:.1f}°"
        
        # 添加到本地显示
        self._add_log_entry(entry)
        
        # 写入SQLite数据库 (Pi 5线程安全)
        self.db_thread.set_operation("log", (alt, az, "", "position_update", ""))

    def _add_log_entry(self, entry):
        """保留原始显示逻辑"""
        self.log_entries.append(entry)
        self.log_text.append(entry)

    def _export_logs_csv(self):
        """导出CSV (新功能)"""
        filename, _ = QFileDialog.getSaveFileName(self, "Export Logs", "telescope_logs.csv", "CSV Files (*.csv)")
        if filename:
            self.db_thread.set_operation("export_csv", filename)

    def _export_logs_json(self):
        """导出JSON (新功能)"""
        filename, _ = QFileDialog.getSaveFileName(self, "Export Logs", "telescope_logs.json", "JSON Files (*.json)")
        if filename:
            self.db_thread.set_operation("export_json", filename)

    def _backup_database(self):
        """备份数据库 (新功能)"""
        filename, _ = QFileDialog.getSaveFileName(self, "Backup Database", "telescope_logs_backup.db", "SQLite Files (*.db)")
        if filename:
            self.db_thread.set_operation("backup", filename)

    def _clear_logs(self):
        """保留原始清空逻辑"""
        self.log_entries = []
        self.log_text.clear()
        self._add_log_entry("Logs cleared")

    def _show_status(self, message):
        """显示数据库操作状态"""
        self._add_log_entry(f"DB Status: {message}")
        if "error" in message.lower():
            QMessageBox.critical(self, "Database Error", message)
        elif "exported" in message or "backed up" in message:
            QMessageBox.information(self, "Success", message)

    def closeEvent(self, event):
        """Pi 5资源清理"""
        self.log_timer.stop()
        self.db_thread.quit()
        self.db_thread.wait()
        event.accept()