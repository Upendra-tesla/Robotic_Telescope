#!/usr/bin/env python3
"""
Robotic Telescope Control System - Main Launcher
OPTIMIZED FOR RASPBERRY PI 5 (800x480 Touchscreen)
NO PIGPIO DEPENDENCY (Pi 5 Compatible)
"""

import sys
import os
import logging
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Create required directories (ensure write permissions)
required_dirs = ["logs", "recordings", "snapshots", "camera_data", "exports"]
for directory in required_dirs:
    dir_path = PROJECT_ROOT / directory
    dir_path.mkdir(exist_ok=True)
    # Set permissions for Raspberry Pi
    os.chmod(dir_path, 0o755)

# Setup detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(PROJECT_ROOT / 'logs' / 'application.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def check_dependencies():
    """Check for REQUIRED dependencies (no pigpio)"""
    dependencies = [
        ("PyQt5", "PyQt5"),
        ("gpiozero", "gpiozero"),
        ("opencv-python", "cv2"),
        ("numpy", "numpy"),
        ("astropy", "astropy"),
        ("pandas", "pandas"),
        ("requests", "requests"),
        ("matplotlib", "matplotlib"),
        ("smbus2", "smbus2")
    ]
    
    missing = []
    optional_missing = []
    
    for pip_name, import_name in dependencies:
        try:
            __import__(import_name)
            logger.info(f"✓ {pip_name} installed")
        except ImportError:
            if pip_name in ["smbus2"]:
                optional_missing.append(pip_name)
                logger.warning(f"⚠ {pip_name} missing (optional for sensor support)")
            else:
                missing.append(pip_name)
                logger.error(f"✗ {pip_name} missing (required)")
    
    # Pigpio is OPTIONAL (skip check for Pi 5)
    logger.info("⚠ Pigpio skipped (incompatible with Raspberry Pi 5)")
    
    return missing, optional_missing

def check_raspberry_pi():
    """Check if running on Raspberry Pi (Pi 5 compatible)"""
    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read()
            if 'Raspberry Pi' in cpuinfo:
                logger.info("✓ Running on Raspberry Pi (Pi 5 detected)")
                # NO PIGPIO ENV VARS (breaks Pi 5)
                return True
    except Exception as e:
        logger.warning(f"⚠ Could not detect Raspberry Pi: {e}")
    
    logger.warning("⚠ Running on non-Raspberry Pi hardware - GPIO features disabled")
    return False

def main():
    """Main launch sequence (Pi 5 compatible)"""
    logger.info("=" * 60)
    logger.info("ROBOTIC TELESCOPE CONTROL SYSTEM - PI 5 EDITION")
    logger.info("=" * 60)
    
    # Step 1: Check dependencies
    missing_required, missing_optional = check_dependencies()
    if missing_required:
        logger.error(f"\nMissing required dependencies: {', '.join(missing_required)}")
        logger.error("Install with: pip3 install " + " ".join(missing_required))
        response = input("\nContinue anyway? (y/N): ").strip().lower()
        if response != 'y':
            sys.exit(1)
    
    # Step 2: Check hardware (no pigpio)
    is_pi = check_raspberry_pi()
    
    # Step 3: Check settings file
    settings_file = PROJECT_ROOT / "settings.json"
    if not settings_file.exists():
        logger.warning("⚠ settings.json not found - creating default configuration")
        from modules import load_settings
        load_settings()
        logger.info("✓ Created default settings file")
    
    # Step 4: Launch application (SAFE IMPORT)
    try:
        logger.info("\nLoading main application (800x480 mode)...")
        
        # Safe import of main app
        import main as main_module
        
        logger.info("=" * 60)
        logger.info("APPLICATION STARTING - PI 5 COMPATIBLE MODE")
        logger.info("=" * 60)
        
        # Run the main application
        main_module.main()
        
    except KeyboardInterrupt:
        logger.info("\nApplication stopped by user")
    except Exception as e:
        logger.error(f"Failed to start application: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()