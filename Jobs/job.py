import math
import os
import time

import cv2
import numpy as np
from loguru import logger

import MotorContol
from Agent import PlantRequirements, PlantRecognition
from Common import GlobalState
from EnvActuator import ActuatorManager
from Yolo import get_model


def job(camera: cv2.VideoCapture, motor: MotorContol.MotorControl, env_manager: ActuatorManager, flask_state: dict,
        recognition_agent: PlantRecognition.PlantRecognitionAgent,
        requirements_agent: PlantRequirements.PlantRequirementsAgent, socketio):
    plants_cord = GlobalState().scan_data

    env_manager.sunlight_actuator.provide_light(2)

    # Make dir Images/{time}
    now = time.strftime("%Y%m%d-%H%M%S")
    save_dir = f"Images/{now}"
    os.makedirs(save_dir, exist_ok=True)

    plant_images = []
    i = 0
    for plant_x, plant_y in plants_cord:
        motor.goto(plant_x, plant_y, motor.current_z)
        time.sleep(7)
        goto_plant_center(camera, motor, flask_state)
        # take a photo!
        if not camera.isOpened():
            raise IOError("Cannot open webcam")
        ret, frame = camera.read()
        if not ret:
            logger.warning(f"Failed to capture at ({plant_x}, {plant_y})")
            continue
        plant_images.append(frame)

        # save the image in Images/time/plant_i.jpg
        cv2.imwrite(f"{save_dir}/plant_{i}.jpg", frame)
        i += 1

    env_manager.sunlight_actuator.stop_light()

    # Combine the images into one
    if plant_images:
        plant_images = combine_image(plant_images)
        flask_state['yolo_frame'] = plant_images

    result = recognition_agent.regocnize_plant(plant_images)
    logger.info(f"Plant: {result.plant_name}, {result.growth_stage}")
    plant_requirements = requirements_agent.get_requirements(result.plant_name, result.growth_stage, result.details,
                                                             plant_images)
    logger.info(f"Requirements: {plant_requirements}")

    try:
        env_manager.update(plant_requirements)

        flask_state['target_env'] = {
            'watering_frequency': plant_requirements.watering_frequency,
            'watering_amount': plant_requirements.watering_amount,
            'light_duration': plant_requirements.light_duration,
            'temperature': plant_requirements.temperature,
            'fertilization_frequency': plant_requirements.fertilization_frequency,
            'fertilization_amount': plant_requirements.fertilization_amount,
            'wind': plant_requirements.wind
        }
    except ValueError as e:
        logger.error(f"Failed to update actuator settings due to invalid requirements: {e}")

    flask_state['job_status'] = 'stopped'
    socketio.emit('job_status', {'status': 'stopped'})
    logger.info("Job completed")


def goto_plant_center(camera, motor: MotorContol.MotorControl, flask_state):
    step_size = 0.15  # Small incremental movement
    model = get_model()
    for _ in range(20):
        if not camera.isOpened():
            raise IOError("Cannot open webcam")
        ret, frame = camera.read()

        if not ret:
            logger.warning(f"Failed to capture at ({motor.current_x}, {motor.current_y})")
            continue

        results = model(frame)
        annotated_frame = results[0].plot()
        flask_state['yolo_frame'] = annotated_frame

        plant_boxes = [box.xyxy[0].tolist() for box in results[0].boxes if int(box.cls[0]) == 0]
        if not plant_boxes:
            logger.warning("No plant detected")
            continue
        x1, y1, x2, y2 = plant_boxes[0]
        leaf_top_x = (x1 + x2) / 2
        leaf_top_y = (y1 + y2) / 2

        frame_h, frame_w = frame.shape[:2]
        center_x, center_y = frame_w / 2, frame_h / 2

        # Calculate distance for each axis
        distance_x = abs(leaf_top_x - center_x)
        distance_y = abs(leaf_top_y - center_y)

        logger.debug(f"Distance from center: x={distance_x:.2f}, y={distance_y:.2f} pixels")

        if distance_x < 20 and distance_y < 20:
            logger.info("Leaf centered")
            break

        # Move incrementally towards leaf
        current_motor_x, current_motor_y = motor.get_position()[:2]

        motor_x = current_motor_x if distance_y < 10 else current_motor_x + (
            -step_size if leaf_top_y < center_y else step_size)
        motor_y = current_motor_y if distance_x < 10 else current_motor_y + (
            -step_size if leaf_top_x < center_x else step_size)

        motor_x = max(0, min(9.5, motor_x))
        motor_y = max(0, min(9.0, motor_y))

        logger.info(
            f"Leaf at ({leaf_top_x:.0f}, {leaf_top_y:.0f}), center ({center_x:.0f}, {center_y:.0f}), moving to ({motor_x:.2f}, {motor_y:.2f})")
        motor.goto(motor_x, motor_y, 0)
        time.sleep(2)


def combine_image(images):
    n = len(images)
    cols = math.ceil(math.sqrt(n * 4 / 3))
    rows = math.ceil(n / cols)
    h, w = images[0].shape[:2]
    combined = np.zeros((rows * h, cols * w, 3), dtype=np.uint8)
    for idx, img in enumerate(images):
        i, j = divmod(idx, cols)
        combined[i * h:(i + 1) * h, j * w:(j + 1) * w] = img

    return combined
