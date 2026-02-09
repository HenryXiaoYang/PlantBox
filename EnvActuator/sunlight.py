import threading
import datetime
import time
from loguru import logger
from Common import GlobalState, PlantBoxSerial


class LightActuator:
    def __init__(self):
        self.serial = PlantBoxSerial()
        self.light_type = 0 # 0: off, 1: ultraviolet, 2: normal
        self.light_duration = 0.0

        # Start and end time for each day's light_duration provision
        self.start_time = datetime.time(12, 0, 0)
        self.end_time = datetime.time(12, 0, 0)

        # The light_duration is on or off?
        self.is_light_on = False

        # I do not want to block main thread
        self.managing_thread = threading.Thread(target=self.managing_loop, daemon=True)
        self.managing_thread.start()
        logger.info("Sunlight managing actuator initialized.")

    def update_light(self, light_type: int, duration: float):
        """Update light_duration duration in hours."""
        if duration < 0:
            raise ValueError("Sunlight duration cannot be negative.")
        self.light_type = light_type
        self.light_duration = duration

        noon = datetime.time(12, 0, 0)
        half_duration = datetime.timedelta(hours=duration / 2)
        self.start_time = (datetime.datetime.combine(datetime.date.today(), noon) - half_duration).time()
        self.end_time = (datetime.datetime.combine(datetime.date.today(), noon) + half_duration).time()
        logger.info(f"Updated light: type={light_type}, duration={duration} hours, start_time={self.start_time}, end_time={self.end_time}")

    def managing_loop(self):
        """Continuously manage light_duration based on the set duration."""
        while not GlobalState().is_shutting_down:
            if self.light_duration > 0:
                now = datetime.datetime.now().time()
                if self.start_time <= now <= self.end_time:
                    self.provide_light(self.light_type)
                else:
                    self.stop_light()
            time.sleep(60)
        logger.info("Sunlight managing loop exited.")

    def provide_light(self, light_type: int):
        self.is_light_on = True
        logger.info("Providing light_duration...")
        with GlobalState().serial_command_lock:
            para1 = GlobalState().serial_command[0]
            para2 = light_type
            para3 = GlobalState().serial_command[2]
            GlobalState().serial_command = (para1, para2, para3)
            command = f"{para1},{para2},{para3}"
            self.serial.write(command.encode())
            time.sleep(1)

    def stop_light(self):
        self.is_light_on = False
        logger.info("Stopping light_duration...")
        with GlobalState().serial_command_lock:
            para1 = GlobalState().serial_command[0]
            para2 = 0
            para3 = GlobalState().serial_command[2]
            GlobalState().serial_command = (para1, para2, para3)
            command = f"{para1},{para2},{para3}"
            self.serial.write(command.encode())
            time.sleep(1)