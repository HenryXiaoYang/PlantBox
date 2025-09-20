import threading
import datetime
import time
from loguru import logger
from common import GlobalState


class FertilizationActuator:
    def __init__(self):
        self.fertilization_frequency = 0.0 # in days, 0 means no fertilization needed
        self.fertilization_amount = 0.0 # in ml each time

        # I do not want to block main thread
        self.managing_thread = threading.Thread(target=self.managing_loop, daemon=True)
        self.managing_thread.start()
        logger.info("Fertilization managing actuator initialized.")

    def update_fertilization(self, frequency: float, amount: float):
        """Update sunlight duration in hours."""
        self.fertilization_frequency = frequency
        self.fertilization_amount = amount
        logger.info(f"Fertilization updated: frequency={frequency} days, amount={amount} ml")


    def managing_loop(self):
        """A loop to manage the fertilization based on the frequency. Provide fertilization at noon."""
        last_fertilization_time = None
        while not GlobalState().is_shutting_down:
            if self.fertilization_frequency > 0:
                now = datetime.datetime.now()
                if now.hour == 12 and (last_fertilization_time is None or (now - last_fertilization_time).days >= self.fertilization_frequency):
                    self.provide_fertilization(self.fertilization_amount)
                    last_fertilization_time = now
            time.sleep(60)
        logger.info("Fertilization managing loop exited.")

    def provide_fertilization(self, amount: float):
        """Providing fertilization."""
        logger.info(f"Provided {amount} ml of fertilizer.")
        pass