import threading
import datetime
import time
from loguru import logger
from Common import GlobalState


class WateringActuator:
    def __init__(self):
        self.watering_frequency = 0.0 # 1 time per x day
        self.watering_amount = 0.0 # ml each time

        # I do not want to block main thread
        self.managing_thread = threading.Thread(target=self.managing_loop, daemon=True)
        self.managing_thread.start()
        logger.info("Watering managing actuator initialized.")

    def update_watering(self, frequency: float, amount: float):
        """Update watering frequency and amount."""
        if frequency < 0:
            raise ValueError("Watering frequency cannot be negative.")
        if amount < 0:
            raise ValueError("Watering amount cannot be negative.")
        self.watering_frequency = frequency
        self.watering_amount = amount
        logger.info(f"Updated watering frequency to {frequency} days and amount to {amount} ml.")

    def managing_loop(self):
        """Continuously manage watering based on the set frequency. Will water at noon"""
        last_watering_date = None
        while not GlobalState().is_shutting_down:
            now = datetime.datetime.now()
            if (last_watering_date is None or (now.date() - last_watering_date).days >= self.watering_frequency) and now.time().hour == 12:
                self.provide_water()
                last_watering_date = now.date()
            time.sleep(60)
        logger.info("Watering managing loop exited.")

    def provide_water(self):
        logger.info(f"Providing {self.watering_amount}ml of water...")
        pass
