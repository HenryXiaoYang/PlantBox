import threading
import time
from loguru import logger
from common import GlobalState


class WindActuator:
    def __init__(self):
        self.target_wind = 0.0 # in percentage

        self.current_wind = 0.0 # in percentage

        # I do not want to block main thread
        self.managing_thread = threading.Thread(target=self.managing_loop, daemon=True)
        self.managing_thread.start()
        logger.info("Wind managing actuator initialized.")

    def update_wind(self, wind: float):
        """Update desired wind in percentage"""
        self.target_wind = wind
        logger.info(f"Updated desired wind to {wind}%.")
        self.change_wind(wind)

    def managing_loop(self):
        """Continuously manage temperature based on the set temperature."""
        while not GlobalState().is_shutting_down:
            if self.target_wind != self.current_wind:
                self.change_wind(self.target_wind)
            time.sleep(60)
        logger.info("Wind managing loop exited.")

    def change_wind(self, wind: float):
        self.current_wind = wind
        logger.info(f"Changing wind to {wind}%...")
        pass