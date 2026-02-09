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
        return None, []

    model = get_tomato_model()
    results = model(frame)

    boxes = results[0].boxes
    if boxes is None or len(boxes) == 0:
        return None, []

    # Check if any detected object is a tomato (not leaf)
    tomato_boxes = []
    for box in boxes:
        cls_id = int(box.cls[0])
        if cls_id not in TOMATO_CLASS_IDS:
            continue
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        conf = float(box.conf[0])
        tomato_boxes.append({
            'cx': cx, 'cy': cy,
            'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
            'cls': cls_id, 'conf': conf,
        })

    if not tomato_boxes:
        return None, []

    annotated_frame = results[0].plot()
    return annotated_frame, tomato_boxes


def select_closest_to_top_left(tomato_boxes):
    """Select the tomato whose bounding box center is closest to the top-left corner (0,0)."""
    return min(tomato_boxes, key=lambda t: t['cx'] ** 2 + t['cy'] ** 2)


def goto_tomato_center(camera: cv2.VideoCapture, motor: MotorContol.MotorControl, flask_state: dict):
    """Move the motor so the closest tomato is centered in the camera frame.

    Follows the same pixel-to-motor-axis mapping as goto_plant_center in job.py:
    pixel_y -> motor_x, pixel_x -> motor_y.
    """
    max_step = 0.5
    min_step = 0.08
    model = get_tomato_model()

    for iteration in range(20):
        if not camera.isOpened():
            raise IOError("Cannot open webcam")
        ret, frame = camera.read()
        if not ret:
            logger.warning(f"Failed to capture at ({motor.current_x}, {motor.current_y})")
            continue

        results = model(frame)
        annotated_frame = results[0].plot()
        flask_state['yolo_frame'] = annotated_frame

        # Collect tomato boxes from detection
        tomato_boxes = []
        if results[0].boxes is not None:
            for box in results[0].boxes:
                cls_id = int(box.cls[0])
                if cls_id not in TOMATO_CLASS_IDS:
                    continue
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                tomato_boxes.append({
                    'cx': (x1 + x2) / 2,
                    'cy': (y1 + y2) / 2,
                })

        if not tomato_boxes:
            logger.warning("No tomato detected during centering")
            continue

        frame_h, frame_w = frame.shape[:2]
        center_x, center_y = frame_w / 2, frame_h / 2

        # Pick the tomato closest to frame center for tracking
        target = min(tomato_boxes, key=lambda t: (t['cx'] - center_x) ** 2 + (t['cy'] - center_y) ** 2)
        tomato_px, tomato_py = target['cx'], target['cy']

        distance_x = abs(tomato_px - center_x)
        distance_y = abs(tomato_py - center_y)
        logger.debug(f"Tomato centering iter {iteration}: distance from center x={distance_x:.2f}, y={distance_y:.2f} px")

        if distance_x < 20 and distance_y < 20:
            logger.info("Tomato centered")
            return True

        current_motor_x, current_motor_y = motor.get_position()[:2]

        # Adaptive step: large when far, small when close
        max_dist = max(center_x, center_y)
        total_dist = (distance_x ** 2 + distance_y ** 2) ** 0.5
        step_size = min_step + (max_step - min_step) * min(total_dist / max_dist, 1.0)

        # pixel_y -> motor_x, pixel_x -> motor_y  (flipped signs to move TOWARD tomato)
        motor_x = current_motor_x if distance_y < 10 else current_motor_x + (
            step_size if tomato_py < center_y else -step_size)
        motor_y = current_motor_y if distance_x < 10 else current_motor_y + (
            step_size if tomato_px < center_x else -step_size)

        motor_x = max(0, min(9.5, motor_x))
        motor_y = max(0, min(9.0, motor_y))

        logger.info(
            f"Tomato at ({tomato_px:.0f}, {tomato_py:.0f}), center ({center_x:.0f}, {center_y:.0f}), "
            f"step={step_size:.2f}, moving to ({motor_x:.2f}, {motor_y:.2f})")
        motor.goto(motor_x, motor_y, 0)
        time.sleep(2)

    logger.warning("Failed to center tomato after 20 iterations")
    return False


def pick_tomato(motor: MotorContol.MotorControl):
    """Execute the physical pick-and-place sequence."""
    cur_x, cur_y = motor.get_position()[:2]

    motor.open_claw()
    time.sleep(1)

    motor.goto(cur_x, cur_y, 1.5)
    time.sleep(3)

    motor.close_claw()
    time.sleep(1)

    motor.goto(cur_x, cur_y, 0)
    time.sleep(2)

    motor.goto(0, 0, 0)
    time.sleep(3)

    motor.open_claw()
    time.sleep(1)

    logger.info("Pick-and-place sequence completed")


def pick(camera: cv2.VideoCapture, motor: MotorContol.MotorControl, env_manager: ActuatorManager, flask_state: dict,
        recognition_agent: PlantRecognition.PlantRecognitionAgent,
        requirements_agent: PlantRequirements.PlantRequirementsAgent, socketio):
    motor.goto(0, 0, 0)
    motor.set_servo_angles(servo_1=0, servo_2=90, servo_3=0)
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
                env_manager.sunlight_actuator.stop_light()
                flask_state['job_status'] = 'stopped'
                socketio.emit('job_status', {'status': 'stopped'})
                return

            motor.move_to(x, y, 0)
            time.sleep(1)
            logger.debug(f"Moved to ({x}, {y})")

            annotated_frame, tomato_boxes = detect_tomato(camera)
            if annotated_frame is not None:
                flask_state['yolo_frame'] = annotated_frame
            else:
                continue

            if not tomato_boxes:
                continue

            # Select the tomato closest to top-left corner
            target = select_closest_to_top_left(tomato_boxes)
            logger.info(
                f"Selected tomato: class={TOMATO_CLASSES.get(target['cls'], 'unknown')}, "
                f"conf={target['conf']:.2f}, center=({target['cx']:.0f}, {target['cy']:.0f})")

            # Center the camera on the tomato
            if not goto_tomato_center(camera, motor, flask_state):
                logger.warning("Failed to center on tomato, continuing scan")
                continue

            # Execute pick-and-place
            pick_tomato(motor)

            # Done – picked one tomato, finish the job
            env_manager.sunlight_actuator.stop_light()
            flask_state['job_status'] = 'stopped'
            socketio.emit('job_status', {'status': 'stopped'})
            logger.info("Pick job completed – tomato picked")
            return

    # Scan finished without finding / picking any tomato
    env_manager.sunlight_actuator.stop_light()
    flask_state['job_status'] = 'stopped'
    socketio.emit('job_status', {'status': 'stopped'})
    logger.info("Pick job completed – no tomato found")
