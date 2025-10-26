import time
from threading import Thread

from loguru import logger
from serial import Serial

from Common import Singleton


class PlantBoxSerial(metaclass=Singleton):
    def __init__(self, port='COM3', baudrate=115200, timeout=1, serial_callback=None):
        self.ser = Serial(port, baudrate, timeout=timeout)
        self.serial_callback = serial_callback
        self.latest_line = None
        Thread(target=self._read_serial, daemon=True).start()

    def _read_serial(self):
        while True:
            if self.ser.in_waiting:
                try:
                    line = self.ser.readline().decode().strip()
                    if line:
                        self.latest_line = line
                        if self.serial_callback:
                            self.serial_callback(line)
                except:
                    pass
            time.sleep(0.1)

    def write(self, data):
        if isinstance(data, str):
            data = data.encode()
        logger.debug(f"Writing to serial: {data}")
        self.ser.write(data)

    def close(self):
        self.ser.close()

    def readline(self):
        return self.latest_line
