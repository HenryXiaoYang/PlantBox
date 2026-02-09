import os
import time

import cv2
from ultralytics import YOLO

import MotorContol
from Agent import PlantRequirements, PlantRecognition
from Common import GlobalState
from EnvActuator import ActuatorManager
from loguru import logger

_tomato_model = None

TOMATO_CLASSES = {
    0: 'b_fully_ripened',
    1: 'b_green',
    2: 'b_half_ripened',
    3: 'l_fully_ripened',
    4: 'l_green',
    5: 'l_half_ripened',
    6: 'leaf',
}

# Indices of tomato classes (exclude leaf)
TOMATO_CLASS_IDS = {i for i, name in TOMATO_CLASSES.items() if name != 'leaf'}


def get_tomato_model():
    global _tomato_model
    if _tomato_model is None:
        model_path = os.path.join(os.path.dirname(__file__), '..', 'Yolo', 'tomato.pt')
        _tomato_model = YOLO(model_path)
    return _tomato_model


def detect_tomato(camera: cv2.VideoCapture):
    ret, frame = camera.read()
    if not ret:
        logger.warning("Failed to read frame from camera")
        return None

    model = get_tomato_model()
    results = model(frame)

    boxes = results[0].boxes
    if boxes is None or len(boxes) == 0:
        return None

    # Check if any detected object is a tomato (not leaf)
    has_tomato = any(int(box.cls[0]) in TOMATO_CLASS_IDS for box in boxes)
    if not has_tomato:
        return None

    annotated_frame = results[0].plot()
    return annotated_frame


def job(camera: cv2.VideoCapture, motor: MotorContol.MotorControl, env_manager: ActuatorManager, flask_state: dict,
        recognition_agent: PlantRecognition.PlantRecognitionAgent,
        requirements_agent: PlantRequirements.PlantRequirementsAgent, socketio):
    motor.goto(0, 0, 0)
    motor.set_servo_angles(servo_1=0, servo_2=25, servo_3=90)
    time.sleep(5)
    env_manager.sunlight_actuator.provide_light(2)

    step_x, step_y = 3, 1.5
    x_positions = [i * step_x for i in range(int(9.5 / step_x) + 1)]
    y_positions = [j * step_y for j in range(int(9.0 / step_y) + 1)]

    # Clear previous YOLO frame and scan data
    flask_state['yolo_frame'] = None

    for i, x in enumerate(x_positions):  # zig-zag pattern
        y_range = reversed(y_positions) if i % 2 else y_positions
        time.sleep(1)

        for y in y_range:
            # Check for stop signal
            if flask_state['job_control']['should_stop']:
                logger.info("Job stopped by user")
                flask_state['job_status'] = 'stopped'
                socketio.emit('job_status', {'status': 'stopped'})
                return

            motor.move_to(x, y, 0)
            time.sleep(1)
            logger.debug(f"Moved to ({x}, {y})")

            annotated_frame = detect_tomato(camera)
            if annotated_frame is not None:
                flask_state['yolo_frame'] = annotated_frame
            else:
                continue






