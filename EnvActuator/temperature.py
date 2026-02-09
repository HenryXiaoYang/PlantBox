import threading
import time
from loguru import logger
from Common import GlobalState
import Sensors


class TemperatureActuator:
    def __init__(self):
        self.target_temperature = 0.0 # in celsius
        self._difference_threshold = 2.0 # in celsius

        # is the heater on or off?
        self.is_heater_on = False

        # I do not want to block main thread
        self.managing_thread = threading.Thread(target=self.managing_loop, daemon=True)
        self.managing_thread.start()
        logger.info("Temperature managing actuator initialized.")

    def update_temperature(self, temperature: float):
        """Update desired temperature in celsius."""
        self.target_temperature = temperature
        logger.info(f"Updated desired temperature to {temperature}°C.")

    def managing_loop(self):
        """Continuously manage temperature based on the set temperature."""
        while not GlobalState().is_shutting_down:
            if self.target_temperature > 0:
                current_temp = Sensors.get_sensor_temperature()
                if current_temp < self.target_temperature - self._difference_threshold and not self.is_heater_on:
                    self.provide_heat()
                elif current_temp > self.target_temperature + self._difference_threshold and self.is_heater_on:
                    self.stop_heat()
            time.sleep(30)
        logger.info("Temperature managing loop exited.")

    def provide_heat(self):
        self.is_heater_on = True
        logger.info(f"Providing heat to reach {self.target_temperature}°C...")
        pass

    def stop_heat(self):
        self.is_heater_on = False
        logger.info("Stopping heat...")
        pass
