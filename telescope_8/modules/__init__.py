import json
import os
import sys
from pathlib import Path
from PyQt5.QtGui import QFont

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# --------------------------
# Critical Fix: Ensure SETTINGS is ALWAYS defined (even on error)
# --------------------------
SETTINGS = {}  # Initialize empty first to prevent ImportError

def load_settings():
    """Load settings from JSON file (with full error handling)"""
    settings_path = PROJECT_ROOT / "settings.json"
    
    # Default settings (100% valid Python syntax - no missing commas)
    default_settings = {
        "gpio": {
            "altitude_pins": {"in1": 17, "in2": 27, "ena": 22},
            "azimuth_pins": {"in1": 23, "in2": 24, "ena": 25},
            "sensor_i2c_address": "0x19",
            "pwm_frequency": 1000
        },
        "camera": {
            "default_resolution": "640x480",
            "framerate": 30,
            "recording_format": "mp4",
            "auto_record": False,
            "histogram_enabled": True,
            "default_camera": 0,
            "camera_width": 640,
            "camera_height": 480,
            "video_duration": 300,  # Fix KeyError: video_duration
            "recording_quality": 80,
            "preview_scale": 1.0,
            "flip_horizontal": False,
            "flip_vertical": False
        },
        "telescope": {
            "altitude_min": 0,
            "altitude_max": 90,
            "azimuth_min": 0,
            "azimuth_max": 360,
            "speed_min": 10,
            "speed_max": 100,
            "default_speed": 50
        },
        "ai": {
            "mode": "local",
            "deepseek_api_key": "",
            "ollama_model": "deepseek-r1:1.5b",
            "enable_auto_analysis": False
        },
        "database": {
            "auto_save": True,
            "log_limit": 1000,
            "export_format": "csv",
            "save_interval": 30,  # ADD: Missing key (30 seconds default)
            "db_filename": "telescope_logs.db",  # ADD: Database filename
            "table_name": "telescope_data",  # ADD: Default table name
            "backup_enabled": True,  # ADD: Auto-backup toggle
            "backup_interval": 1440  # ADD: Backup interval (minutes - 24hrs)
        },
        "ui": {
            "responsive_layout": False,
            "fixed_size": "800x480",
            "font_size": 9,
            "theme": "dark",
            "tab_order": ["control", "sensors", "camera", "sun", "moon", "database", "ai"]
        }
    }
    
    try:
        if settings_path.exists():
            with open(settings_path, "r") as f:
                loaded_settings = json.load(f)
            # Merge loaded settings with defaults (fill missing keys)
            for key in default_settings.keys():
                if key not in loaded_settings:
                    loaded_settings[key] = default_settings[key]
                else:
                    # Merge nested keys (e.g., camera/default_camera)
                    for subkey, subval in default_settings[key].items():
                        if subkey not in loaded_settings[key]:
                            loaded_settings[key][subkey] = subval
            return loaded_settings
        else:
            # Create new settings file with defaults
            with open(settings_path, "w") as f:
                json.dump(default_settings, f, indent=2)
            return default_settings
    except Exception as e:
        print(f"CRITICAL ERROR loading settings: {e}")
        print("Falling back to DEFAULT settings")
        return default_settings

# --------------------------
# Initialize SETTINGS (safe - never fails)
# --------------------------
try:
    SETTINGS = load_settings()
except Exception as e:
    print(f"FATAL: Could not load settings - using empty defaults: {e}")
    SETTINGS = {
        "gpio": {"altitude_pins": {"in1":17,"in2":27,"ena":22}, "azimuth_pins":{"in1":23,"in2":24,"ena":25}},
        "camera": {"default_camera":0},
        "telescope": {"speed_min":10,"speed_max":100,"default_speed":50},
        "ui": {"fixed_size":"800x480"}
    }

# --------------------------
# Remaining helper functions (unchanged)
# --------------------------
def cleanup_gpio():
    """Clean up GPIO resources"""
    try:
        from gpiozero import Device
        from gpiozero.pins.mock import MockFactory
        Device.pin_factory = MockFactory()
        print("GPIO cleaned up successfully")
    except ImportError:
        pass
    except Exception as e:
        print(f"Error cleaning up GPIO: {e}")

def get_responsive_stylesheet():
    """Get responsive stylesheet optimized for 800x480 touchscreen"""
    return """
    /* Base Styles */
    QWidget {
        background-color: #2b2b2b;
        color: #ffffff;
        font-size: 9px;
        font-family: Arial;
    }
    
    /* Group Boxes */
    QGroupBox {
        border: 1px solid #444444;
        border-radius: 5px;
        margin-top: 8px;
        padding-top: 5px;
        font-weight: bold;
    }
    
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px 0 5px;
    }
    
    /* Buttons */
    QPushButton {
        background-color: #333333;
        border: 1px solid #555555;
        border-radius: 4px;
        padding: 4px 8px;
        min-height: 25px;
        font-weight: bold;
    }
    
    QPushButton:hover {
        background-color: #444444;
    }
    
    QPushButton:pressed {
        background-color: #00a8ff;
    }
    
    QPushButton:disabled {
        background-color: #2a2a2a;
        color: #888888;
    }
    
    /* Line Edits */
    QLineEdit {
        background-color: #333333;
        border: 1px solid #555555;
        border-radius: 4px;
        padding: 3px;
        min-height: 22px;
    }
    
    /* Combo Boxes */
    QComboBox {
        background-color: #333333;
        border: 1px solid #555555;
        border-radius: 4px;
        padding: 3px;
        min-height: 22px;
    }
    
    QComboBox::drop-down {
        border-left: 1px solid #555555;
        width: 20px;
    }
    
    QComboBox QAbstractItemView {
        background-color: #333333;
        border: 1px solid #555555;
        selection-background-color: #00a8ff;
    }
    
    /* Progress Bars */
    QProgressBar {
        background-color: #333333;
        border: 1px solid #555555;
        border-radius: 4px;
        text-align: center;
        height: 18px;
    }
    
    QProgressBar::chunk {
        background-color: #00a8ff;
        border-radius: 3px;
    }
    
    /* Labels */
    QLabel {
        padding: 2px;
    }
    
    /* Tab Widgets */
    QTabWidget::pane {
        border: 1px solid #444444;
        background-color: #2b2b2b;
    }
    
    QTabBar::tab {
        background-color: #333333;
        color: #cccccc;
        padding: 6px 12px;
        margin-right: 2px;
        min-width: 60px;
        min-height: 20px;
    }
    
    QTabBar::tab:selected {
        background-color: #2b2b2b;
        color: #ffffff;
        border-bottom: 2px solid #00a8ff;
    }
    
    /* Text Edit */
    QTextEdit {
        background-color: #333333;
        border: 1px solid #555555;
        padding: 5px;
        font-size: 8px;
    }
    
    /* Scroll Area */
    QScrollArea {
        border: none;
    }
    
    QScrollBar:vertical {
        background-color: #333333;
        width: 10px;
        border-radius: 5px;
    }
    
    QScrollBar::handle:vertical {
        background-color: #555555;
        border-radius: 5px;
    }
    
    /* Status Bar */
    QStatusBar {
        background-color: #333333;
        border-top: 1px solid #444444;
    }
    
    /* Menu Bar */
    QMenuBar {
        background-color: #333333;
        border-bottom: 1px solid #444444;
    }
    
    QMenuBar::item {
        padding: 4px 8px;
    }
    
    QMenuBar::item:selected {
        background-color: #00a8ff;
    }
    
    QMenu {
        background-color: #333333;
        border: 1px solid #444444;
    }
    
    QMenu::item:selected {
        background-color: #00a8ff;
    }
    
    /* Tool Bar */
    QToolBar {
        background-color: #333333;
        border-bottom: 1px solid #444444;
    }
    """

def get_pin_display_name(pin_number):
    """Get human-readable pin display name"""
    pin_map = {
        2: "GPIO2 (SDA)",
        3: "GPIO3 (SCL)",
        4: "GPIO4",
        5: "GPIO5",
        6: "GPIO6",
        7: "GPIO7 (CE1)",
        8: "GPIO8 (CE0)",
        9: "GPIO9 (MISO)",
        10: "GPIO10 (MOSI)",
        11: "GPIO11 (SCLK)",
        12: "GPIO12",
        13: "GPIO13",
        14: "GPIO14 (TXD)",
        15: "GPIO15 (RXD)",
        16: "GPIO16",
        17: "GPIO17",
        18: "GPIO18 (PWM0)",
        19: "GPIO19 (MISO)",
        20: "GPIO20 (MOSI)",
        21: "GPIO21",
        22: "GPIO22",
        23: "GPIO23",
        24: "GPIO24",
        25: "GPIO25",
        26: "GPIO26",
        27: "GPIO27"
    }
    return pin_map.get(pin_number, f"GPIO{pin_number}")

def save_settings():
    """Save current settings to file"""
    try:
        settings_path = PROJECT_ROOT / "settings.json"
        with open(settings_path, "w") as f:
            json.dump(SETTINGS, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False