import os
import time

import cv2
import schedule
from dotenv import load_dotenv
from loguru import logger
from cv2_enumerate_cameras import enumerate_cameras

from agent.PlantRecognition import PlantRecognitionAgent
from agent.PlantRequirements import PlantRequirementsAgent
from EnvActuator import ActuatorManager
from common import GlobalState
from common import scheduler
from MotorContol.motor_control import MotorControl
from yolo import detect_plants

def main():
    task = scheduler.every(10).minutes.do(job)
    task.run()

    try:
        while True:
            scheduler.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        GlobalState().is_shutting_down = True
        cam.release()


def job():
    logger.info("Starting job")
    step_x, step_y = 0.5, 0.5

    for x in [i * step_x for i in range(int(9.5 / step_x) + 1)]:
        for y in [j * step_y for j in range(int(9.0 / step_y) + 1)]:
            motor.move_to(x, y, 0.5)

            if not cam.isOpened():
                raise IOError("Cannot open webcam")
            ret, frame = cam.read()

            if not ret:
                logger.warning(f"Failed to capture at ({x}, {y})")
                continue

            clusters = detect_plants(frame)
            if clusters:
                plant = recognition_agent.regocnize_plant(frame)
                logger.info(f"At ({x}, {y}): {len(clusters)} clusters, {plant.plant_name}, {plant.growth_stage}")

                requirements = requirements_agent.get_requirements(plant.plant_name, plant.growth_stage)
                logger.info(f"Requirements: {requirements}")

                manager.update(requirements)


if __name__ == "__main__":
    load_dotenv()

    for camera_info in enumerate_cameras():
        logger.info(f"Camera index: {camera_info.index}  Name: {camera_info.name}")
    time.sleep(1)  # Give user time to read the camera list
    cam_index = int(input("Please enter the camera index to use and press Enter: "))
    cam = cv2.VideoCapture(cam_index)

    recognition_agent = PlantRecognitionAgent(api_key=os.getenv("OPENAI_API_KEY"),
                                              base_url=os.getenv("OPENAI_API_BASE"))
    requirements_agent = PlantRequirementsAgent(api_key=os.getenv("OPENAI_API_KEY"),
                                                base_url=os.getenv("OPENAI_API_BASE"),
                                                firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY"))

    manager = ActuatorManager()
    motor = MotorControl()

    main()
