import threading
import datetime
import time
from loguru import logger
from Common import GlobalState


class SunlightActuator:
    def __init__(self):
        self.sunlight_duration = 0.0

        # Start and end time for each day's sunlight provision
        self.start_time = datetime.time(12, 0, 0)
        self.end_time = datetime.time(12, 0, 0)

        # The sunlight is on or off?
        self.is_sunlight_on = False

        # I do not want to block main thread
        self.managing_thread = threading.Thread(target=self.managing_loop, daemon=True)
        self.managing_thread.start()
        logger.info("Sunlight managing actuator initialized.")

    def update_sunlight(self, duration: float):
        """Update sunlight duration in hours."""
        if duration < 0:
            raise ValueError("Sunlight duration cannot be negative.")
        self.sunlight_duration = duration

        noon = datetime.time(12, 0, 0)
        half_duration = datetime.timedelta(hours=duration / 2)
        self.start_time = (datetime.datetime.combine(datetime.date.today(), noon) - half_duration).time()
        self.end_time = (datetime.datetime.combine(datetime.date.today(), noon) + half_duration).time()

    def managing_loop(self):
        """Continuously manage sunlight based on the set duration."""
        while not GlobalState().is_shutting_down:
            if self.sunlight_duration > 0:
                now = datetime.datetime.now().time()
                if self.start_time <= now <= self.end_time and not self.is_sunlight_on:
                    self.provide_sunlight()
                else:
                    self.stop_sunlight()
            time.sleep(60)
        logger.info("Sunlight managing loop exited.")

    def provide_sunlight(self):
        self.is_sunlight_on = True
        logger.info("Providing sunlight...")
        pass

    def stop_sunlight(self):
        self.is_sunlight_on = False
        logger.info("Stopping sunlight...")
        pass