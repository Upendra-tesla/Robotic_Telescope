#!/bin/bash

# Robotic Telescope Control System - Complete Installation
# Optimized for Raspberry Pi 4/5 with responsive GUI

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_section() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "Please run as root: sudo $0"
    exit 1
fi

print_section "ROBOTIC TELESCOPE CONTROL SYSTEM INSTALLATION"
print_status "Starting installation on $(lsb_release -ds)"

# Update system
print_section "1. SYSTEM UPDATE"
apt-get update
apt-get upgrade -y
print_status "System updated"

# Install system dependencies
print_section "2. INSTALLING SYSTEM DEPENDENCIES"
apt-get install -y \
    python3-pip \
    python3-dev \
    python3-venv \
    git \
    cmake \
    build-essential \
    libopenblas-dev \
    libatlas-base-dev \
    libhdf5-dev \
    libhdf5-serial-dev \
    libqtgui4 \
    libqt4-test \
    python3-pyqt5 \
    libqt5gui5 \
    libqt5widgets5 \
    libqt5core5a \
    i2c-tools \
    python3-smbus \
    pigpio \
    python3-pigpio \
    v4l-utils \
    fswebcam \
    ffmpeg \
    libjpeg-dev \
    libtiff5-dev \
    libpng-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libgtk-3-dev \
    libcanberra-gtk3-module \
    python3-matplotlib \
    python3-pandas \
    python3-requests \
    python3-numpy \
    python3-astropy \
    python3-psutil

print_status "System dependencies installed"

# Enable hardware interfaces
print_section "3. ENABLING HARDWARE INTERFACES"
raspi-config nonint do_i2c 0
raspi-config nonint do_spi 0
raspi-config nonint do_camera 0
print_status "I2C, SPI, and Camera enabled"

# Enable pigpio daemon
systemctl enable pigpiod
systemctl start pigpiod
print_status "pigpio daemon enabled"

# Create project directory
print_section "4. SETTING UP PROJECT"
PROJECT_DIR="/opt/robotic_telescope"
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# Create directory structure
mkdir -p logs recordings snapshots camera_data exports modules

# Copy all Python files
print_status "Copying Python files..."
# Note: You need to copy your actual Python files here
# For now, create placeholder structure

# Create __init__.py
cat > __init__.py << 'EOF'
# This file will be replaced with the actual __init__.py
print("Please copy the actual __init__.py file here")
EOF

# Create requirements.txt
cat > requirements.txt << 'EOF'
PyQt5==5.15.9
gpiozero==1.6.2
RPi.GPIO==0.7.1
pigpio==1.78
smbus2==0.4.3
opencv-python-headless==4.8.1.78
numpy==1.24.3
Pillow==10.0.0
astropy==5.3.2
pandas==2.1.3
matplotlib==3.8.0
requests==2.31.0
loguru==0.7.2
psutil==5.9.6
EOF

# Create settings.json
cat > settings.json << 'EOF'
{
  "gpio": {
    "altitude_up": 17,
    "altitude_down": 18,
    "azimuth_left": 22,
    "azimuth_right": 23,
    "pwm_frequency": 100,
    "enable_physical_pins": true,
    "available_pins": [
      {"gpio": 2, "physical": 3},
      {"gpio": 3, "physical": 5},
      {"gpio": 4, "physical": 7},
      {"gpio": 17, "physical": 11},
      {"gpio": 27, "physical": 13},
      {"gpio": 22, "physical": 15},
      {"gpio": 10, "physical": 19},
      {"gpio": 9, "physical": 21},
      {"gpio": 11, "physical": 23},
      {"gpio": 0, "physical": 27},
      {"gpio": 5, "physical": 29},
      {"gpio": 6, "physical": 31},
      {"gpio": 13, "physical": 33},
      {"gpio": 19, "physical": 35},
      {"gpio": 26, "physical": 37},
      {"gpio": 14, "physical": 8},
      {"gpio": 15, "physical": 10},
      {"gpio": 18, "physical": 12},
      {"gpio": 23, "physical": 16},
      {"gpio": 24, "physical": 18},
      {"gpio": 25, "physical": 22},
      {"gpio": 8, "physical": 24},
      {"gpio": 7, "physical": 26},
      {"gpio": 1, "physical": 28},
      {"gpio": 12, "physical": 32},
      {"gpio": 16, "physical": 36},
      {"gpio": 20, "physical": 38},
      {"gpio": 21, "physical": 40}
    ]
  },
  "camera": {
    "default_camera": 0,
    "resolutions": ["640x480", "800x600", "1280x720", "1920x1080"],
    "default_resolution": "640x480",
    "video_duration": 10,
    "fps": 30
  },
  "location": {
    "latitude": 40.7128,
    "longitude": -74.006,
    "timezone": "America/New_York",
    "altitude": 0
  },
  "ai": {
    "mode": "local",
    "deepseek_api_key": "",
    "ollama_model": "deepseek-r1:1.5b",
    "enable_auto_analysis": false
  },
  "telescope": {
    "altitude_min": 0,
    "altitude_max": 90,
    "azimuth_min": 0,
    "azimuth_max": 360,
    "motor_speed": 5,
    "auto_calibrate": true
  },
  "database": {
    "log_limit": 1000,
    "export_path": "./logs",
    "auto_save": true,
    "save_interval": 60
  },
  "ui": {
    "theme": "dark",
    "font_size": 12,
    "responsive_layout": true,
    "tab_order": ["control", "sensors", "camera", "sun", "moon", "database", "ai"]
  }
}
EOF

# Create virtual environment
print_status "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install Python dependencies
print_section "5. INSTALLING PYTHON DEPENDENCIES"
pip install -r requirements.txt
print_status "Python dependencies installed"

# Create run.py
cat > run.py << 'EOF'
#!/usr/bin/env python3
"""
Robotic Telescope Control System - Main Launcher
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from main import main as run_app
    run_app()
except Exception as e:
    print(f"Failed to start application: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

chmod +x run.py

# Create main.py placeholder
cat > main.py << 'EOF'
#!/usr/bin/env python3
"""
Main application file - Please copy the actual main.py here
"""

print("Please copy the actual main.py file here")
print("Then run: ./run.py")
EOF

print_status "Project structure created"

# Create startup scripts
print_section "6. CREATING STARTUP SCRIPTS"

# Desktop shortcut
if [ -d "/home/pi/Desktop" ]; then
    cat > /home/pi/Desktop/Telescope.desktop << 'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Robotic Telescope Control
Comment=Control system for robotic telescope
Exec=/opt/robotic_telescope/run.py
Icon=/usr/share/icons/HighContrast/256x256/devices/camera.png
Terminal=false
Categories=Utility;Science;Astronomy;
EOF
    chmod +x /home/pi/Desktop/Telescope.desktop
    chown pi:pi /home/pi/Desktop/Telescope.desktop
    print_status "Desktop shortcut created"
fi

# Systemd service
cat > /etc/systemd/system/telescope.service << 'EOF'
[Unit]
Description=Robotic Telescope Control System
After=network.target pigpiod.service
Wants=network.target pigpiod.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/robotic_telescope
Environment=DISPLAY=:0
Environment=PYTHONPATH=/opt/robotic_telescope
ExecStart=/opt/robotic_telescope/run.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable telescope.service
print_status "Systemd service created"

# Test hardware
print_section "7. TESTING HARDWARE"

# Test I2C
if i2cdetect -y 1 | grep -q "UU"; then
    print_status "I2C devices detected"
else
    print_warning "No I2C devices detected (LSM303DLH may not be connected)"
fi

# Test camera
if v4l2-ctl --list-devices | grep -q "video"; then
    print_status "Camera detected"
else
    print_warning "No camera detected")
fi

# Test Python environment
if python3 -c "import PyQt5, gpiozero, cv2, numpy, astropy; print('Python imports successful')" > /dev/null 2>&1; then
    print_status "Python environment verified"
else
    print_error "Python environment has issues"
fi

print_section "INSTALLATION COMPLETE"
echo -e "${GREEN}✓ Installation completed successfully!${NC}"
echo ""
echo "NEXT STEPS:"
echo "1. Copy your Python module files to:"
echo "   /opt/robotic_telescope/modules/"
echo ""
echo "2. Required module files:"
echo "   - altitude.py"
echo "   - azimuth.py"
echo "   - sensor.py"
echo "   - webcam.py"
echo "   - database.py"
echo "   - sun.py"
echo "   - moon.py"
echo "   - deepseek.py"
echo ""
echo "3. Copy main.py to:"
echo "   /opt/robotic_telescope/main.py"
echo ""
echo "4. Configure settings:"
echo "   - Edit /opt/robotic_telescope/settings.json"
echo "   - Update your latitude/longitude"
echo "   - Configure GPIO pins for your setup"
echo ""
echo "5. Start the application:"
echo "   - Desktop: Double-click 'Telescope' icon"
echo "   - Terminal: cd /opt/robotic_telescope && ./run.py"
echo "   - Service: sudo systemctl start telescope"
echo ""
echo "6. Check logs:"
echo "   - Application: /opt/robotic_telescope/logs/application.log"
echo "   - System: journalctl -u telescope.service"
echo ""
echo "SUPPORT:"
echo "• Ensure all hardware is connected properly"
echo "• Check GPIO pin connections match settings.json"
echo "• Verify camera is properly connected"
echo "• Check I2C connection for LSM303DLH sensor"