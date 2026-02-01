import smbus2
import time

class LSM303DLH:
    """LSM303DLH Driver (Pi 5 I2C) - With Retries & Error Handling"""
    
    # I2C Addresses (update if i2cdetect shows different values)
    ACCEL_ADDR = 0x18
    MAG_ADDR = 0x1E
    
    # Registers
    ACCEL_CTRL_REG1_A = 0x20
    ACCEL_OUT_X_L_A = 0x28
    ACCEL_OUT_Y_L_A = 0x2A
    ACCEL_OUT_Z_L_A = 0x2C
    MAG_CRA_REG_M = 0x00
    MAG_CRB_REG_M = 0x01
    MAG_MR_REG_M = 0x02
    MAG_OUT_X_H_M = 0x03
    MAG_OUT_Y_H_M = 0x05
    MAG_OUT_Z_H_M = 0x07

    def __init__(self, i2c_bus=0, accel_addr=0x18, mag_addr=0x1E):  # i2c_bus=0 (not 1)
        # ✅ Fixed Indentation: All lines below are indented with 4 spaces
        self.mag_x_offset = 0
        self.mag_y_offset = 0
        self.mag_z_offset = 0
        self.bus = smbus2.SMBus(i2c_bus)  # Uses Bus 0 by default
        self.accel_addr = accel_addr
        self.mag_addr = mag_addr
        self.accel_scale = 1.0 / 1000.0
        self.mag_scale = 0.1
        self.initialized = False  # Track sensor state

    def initialize(self):
        """Initialize sensor with retries (fixes intermittent I2C errors)"""
        retries = 5  # Retry 5 times before failing
        delay = 0.2  # 200ms delay between retries
        
        while retries > 0 and not self.initialized:
            try:
                # Initialize Accelerometer (100Hz, enable all axes)
                self.bus.write_byte_data(self.accel_addr, self.ACCEL_CTRL_REG1_A, 0x27)
                
                # Initialize Magnetometer (15Hz, continuous mode)
                self.bus.write_byte_data(self.mag_addr, self.MAG_CRA_REG_M, 0x10)
                self.bus.write_byte_data(self.mag_addr, self.MAG_CRB_REG_M, 0x20)
                self.bus.write_byte_data(self.mag_addr, self.MAG_MR_REG_M, 0x00)
                
                time.sleep(0.1)  # Sensor startup delay
                self.initialized = True
                print("✅ Sensor initialized successfully")
                return
                
            except OSError as e:
                retries -= 1
                print(f"⚠️ I2C Initialization Retry {5 - retries}/5: {e}")
                time.sleep(delay)
        
        # If all retries fail
        raise RuntimeError(
            "❌ Failed to initialize LSM303DLH\n"
            "Check: \n1. Wiring (3.3V, SDA/SCL)\n2. I2C addresses (i2cdetect -y 0)\n3. I2C permissions"
        )

    def _read_16bit(self, addr, reg):
        """Read 16-bit value with error handling"""
        try:
            if addr == self.accel_addr:
                # Accelerometer: LOW byte first
                low = self.bus.read_byte_data(addr, reg)
                high = self.bus.read_byte_data(addr, reg + 1)
                value = (high << 8) | low
            else:
                # Magnetometer: HIGH byte first
                high = self.bus.read_byte_data(addr, reg)
                low = self.bus.read_byte_data(addr, reg + 1)
                value = (high << 8) | low

            # Convert to signed integer
            if value > 32767:
                value -= 65536
            return value
        except OSError as e:
            print(f"⚠️ I2C Read Error: {e}")
            return 0  # Fallback to 0 instead of crashing

    def read_accelerometer(self):
        if not self.initialized:
            return (0.0, 0.0, 0.0)
        x = self._read_16bit(self.accel_addr, self.ACCEL_OUT_X_L_A) * self.accel_scale
        y = self._read_16bit(self.accel_addr, self.ACCEL_OUT_Y_L_A) * self.accel_scale
        z = self._read_16bit(self.accel_addr, self.ACCEL_OUT_Z_L_A) * self.accel_scale
        return (x, y, z)

    def read_magnetometer(self):
        if not self.initialized:
            return (0.0, 0.0, 0.0)
        x = self._read_16bit(self.mag_addr, self.MAG_OUT_X_H_M) * self.mag_scale
        y = self._read_16bit(self.mag_addr, self.MAG_OUT_Y_H_M) * self.mag_scale
        z = self._read_16bit(self.mag_addr, self.MAG_OUT_Z_H_M) * self.mag_scale
        return (x, y, z)

    def read_magnetometer_calibrated(self):
        x, y, z = self.read_magnetometer()
        x_cal = x - self.mag_x_offset
        y_cal = y - self.mag_y_offset
        z_cal = z - self.mag_z_offset
        return (x_cal, y_cal, z_cal)

    def close(self):
        """Safe I2C bus closure"""
        try:
            self.bus.close()
            print("✅ I2C bus closed safely")
        except:
            pass  # Ignore errors during closure