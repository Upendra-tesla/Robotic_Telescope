import smbus2
import time

class LSM303DLH:
    """LSM303DLH Accelerometer/Magnetometer Sensor Driver (Pi 5 I2C)"""
    
    # I2C Addresses
    ACCEL_ADDR = 0x18
    MAG_ADDR = 0x1E
    
    # Accelerometer Registers
    ACCEL_CTRL_REG1_A = 0x20
    ACCEL_OUT_X_L_A = 0x28
    ACCEL_OUT_Y_L_A = 0x2A
    ACCEL_OUT_Z_L_A = 0x2C
    
    # Magnetometer Registers
    MAG_CRA_REG_M = 0x00
    MAG_CRB_REG_M = 0x01
    MAG_MR_REG_M = 0x02
    MAG_OUT_X_H_M = 0x03
    MAG_OUT_Y_H_M = 0x05
    MAG_OUT_Z_H_M = 0x07

    def __init__(self, i2c_bus=0, accel_addr=ACCEL_ADDR, mag_addr=MAG_ADDR):
        self.bus = smbus2.SMBus(i2c_bus)
        self.accel_addr = accel_addr
        self.mag_addr = mag_addr
        self.accel_scale = 1.0 / 1000.0  # g per LSB
        self.mag_scale = 1.0  # mG per LSB

    def initialize(self):
        """Initialize accelerometer and magnetometer (Pi 5 optimized)"""
        # Initialize Accelerometer (100Hz, normal power)
        self.bus.write_byte_data(self.accel_addr, self.ACCEL_CTRL_REG1_A, 0x27)
        
        # Initialize Magnetometer (15Hz, normal mode)
        self.bus.write_byte_data(self.mag_addr, self.MAG_CRA_REG_M, 0x10)
        self.bus.write_byte_data(self.mag_addr, self.MAG_CRB_REG_M, 0x20)
        self.bus.write_byte_data(self.mag_addr, self.MAG_MR_REG_M, 0x00)
        
        time.sleep(0.1)  # Sensor startup delay

    def _read_16bit(self, addr, reg):
        """Read 16-bit value from I2C register (little-endian)"""
        low = self.bus.read_byte_data(addr, reg)
        high = self.bus.read_byte_data(addr, reg + 1)
        value = (high << 8) | low
        
        # Convert to signed integer
        if value > 32767:
            value -= 65536
        return value

    def read_accelerometer(self):
        """Read accelerometer data (X/Y/Z in g)"""
        x = self._read_16bit(self.accel_addr, self.ACCEL_OUT_X_L_A) * self.accel_scale
        y = self._read_16bit(self.accel_addr, self.ACCEL_OUT_Y_L_A) * self.accel_scale
        z = self._read_16bit(self.accel_addr, self.ACCEL_OUT_Z_L_A) * self.accel_scale
        return (x, y, z)

    def read_magnetometer(self):
        """Read magnetometer data (X/Y/Z in mG)"""
        x = self._read_16bit(self.mag_addr, self.MAG_OUT_X_H_M - 1) * self.mag_scale
        y = self._read_16bit(self.mag_addr, self.MAG_OUT_Y_H_M - 1) * self.mag_scale
        z = self._read_16bit(self.mag_addr, self.MAG_OUT_Z_H_M - 1) * self.mag_scale
        return (x, y, z)

    def close(self):
        """Close I2C bus (Pi 5 resource cleanup)"""
        self.bus.close()