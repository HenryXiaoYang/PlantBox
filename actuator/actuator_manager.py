from agent.PlantRequirements import PlantRequirementsResult
from common import singleton

from .watering import WateringActuator
from .sunlight import SunlightActuator
from .temperature import TemperatureActuator
from .fertilization import FertilizationActuator
from .wind import WindActuator

@singleton
class ActuatorManager:
    def __init__(self):
        self.requirements = PlantRequirementsResult

        self.water_actuator = WateringActuator()
        self.sunlight_actuator = SunlightActuator()
        self.temperature_actuator = TemperatureActuator()
        self.fertilization_actuator = FertilizationActuator()
        self.wind_actuator = WindActuator()

    def update(self, requirements: PlantRequirementsResult):
        self.requirements = requirements
        self.water_actuator.update_watering(requirements.watering_frequency, requirements.watering_amount)
        self.sunlight_actuator.update_sunlight(requirements.sunlight)
        self.temperature_actuator.update_temperature(requirements.temperature)
        self.fertilization_actuator.update_fertilization(requirements.fertilization_frequency, requirements.fertilization_amount)
        self.wind_actuator.update_wind(requirements.wind)
