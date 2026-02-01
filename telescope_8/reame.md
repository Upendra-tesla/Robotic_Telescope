# Robotic Telescope Control System

A complete robotic telescope control system for Raspberry Pi with GUI, sensor integration, camera control, and AI assistance.

## Features

- **Motor Control**: Altitude and azimuth control with PWM motors
- **Sensor Integration**: LSM303DLH compass for orientation
- **Camera System**: Live view, recording, and snapshots
- **Astronomy Tracking**: Sun and moon position calculation and tracking
- **AI Assistant**: DeepSeek integration for astronomical analysis
- **Data Logging**: Comprehensive logging and export capabilities
- **GUI Interface**: PyQt5-based touchscreen interface optimized for Raspberry Pi

## Hardware Requirements

- Raspberry Pi 4/5 (recommended 4GB+ RAM)
- LSM303DLH compass module (I2C)
- 2x DC motors with motor drivers (for altitude and azimuth)
- USB webcam or Raspberry Pi Camera Module
- 5V power supply
- Optional: 7-inch touchscreen display

## Installation

1. **Flash Raspberry Pi OS** (64-bit recommended) to SD card
2. **Enable SSH** and connect to your Pi
3. **Run the installation script**:

```bash
sudo ./install.sh