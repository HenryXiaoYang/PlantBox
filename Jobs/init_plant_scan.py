import math
import time

import cv2
import flask_socketio
import numpy as np
from loguru import logger

import MotorContol
from Agent import PlantRecognition, PlantRequirements
from Common import GlobalState
from Common.cluster_merge import merge_clusters_across_positions
from EnvActuator import ActuatorManager
from Yolo import get_model



def init_plant_scan(cam: cv2.VideoCapture, motor: MotorContol.MotorControl, flask_state: dict, socketio: flask_socketio.SocketIO,
                    recognition_agent: PlantRecognition.PlantRecognitionAgent,
                    requirements_agent: PlantRequirements.PlantRequirementsAgent, manager: ActuatorManager):
    flask_state['job_status'] = 'running'
    socketio.emit('job_status', {'status': 'running'})
    logger.info("Starting job")

    step_x, step_y = 3, 1.5
    x_positions = [i * step_x for i in range(int(9.5 / step_x) + 1)]
    y_positions = [j * step_y for j in range(int(9.0 / step_y) + 1)]

    motor.goto(0, 0, 0)
    motor.set_servo_angles(servo_1=0, servo_2=90, servo_3=0)
    time.sleep(5)

    # Clear previous YOLO frame and scan data
    flask_state['yolo_frame'] = None
    GlobalState().scan_data = []
    manager.sunlight_actuator.provide_light(2)
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

            annotated_frame = detect_and_save_plant(cam, x, y)
            if annotated_frame is not None:
                flask_state['yolo_frame'] = annotated_frame
            else:
                continue

    merged_clusters_group = merge_clusters_across_positions(GlobalState().scan_data, eps=2, min_samples=1,
                                                            camera_fov_x=3, camera_fov_y=2)
    flask_state['yolo_frame'] = visualize_cluster_group(merged_clusters_group, 3, 2)
    time.sleep(5)

    plants = get_cluster_group_centers(merged_clusters_group)
    GlobalState().scan_data = plants

    # cg short for clusters group
    plant_images = []
    for cg_x, cg_y in plants:
        motor.goto(cg_x, cg_y, motor.current_z)
        time.sleep(7)
        goto_plant_center(cam, motor, flask_state)
        # take a photo!
        if not cam.isOpened():
            raise IOError("Cannot open webcam")
        ret, frame = cam.read()
        if not ret:
            logger.warning(f"Failed to capture at ({cg_x}, {cg_y})")
            continue
        plant_images.append(frame)
    manager.sunlight_actuator.stop_light()

    # Combine the images into one
    if plant_images:
        plant_images = combine_image(plant_images)
        flask_state['yolo_frame'] = plant_images

    result = recognition_agent.regocnize_plant(plant_images)
    logger.info(f"Plant: {result.plant_name}, {result.growth_stage}")
    plant_requirements = requirements_agent.get_requirements(result.plant_name, result.growth_stage, result.details, plant_images)
    logger.info(f"Requirements: {plant_requirements}")

    try:
        manager.update(plant_requirements)

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
    logger.info("Init plant scan completed")


def detect_and_save_plant(camera, x, y):
    if not camera.isOpened():
        raise IOError("Cannot open webcam")
    ret, frame = camera.read()

    if not ret:
        logger.warning(f"Failed to capture at ({x}, {y})")
        return None

    model = get_model()
    results = model(frame)
    annotated_frame = results[0].plot()

    plant_boxes = [box.xyxy[0].tolist() for box in results[0].boxes if int(box.cls[0]) == 0]

    for box in plant_boxes:
        GlobalState().scan_data.append({
            'motor_position': (x, y),
            'bbox': box,
            'detections': results[0].boxes.data.tolist()
        })

    return annotated_frame


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


def get_cluster_group_centers(merged_clusters):
    """Get the middle motor position of each cluster group"""
    centers = []
    for group in merged_clusters:
        motor_positions = [cluster_data['motor_position'] for cluster_data in group]
        avg_x = sum(pos[0] for pos in motor_positions) / len(motor_positions)
        avg_y = sum(pos[1] for pos in motor_positions) / len(motor_positions)
        centers.append((avg_x, avg_y))
    return centers


def visualize_cluster_group(merged_clusters, camera_fov_x: float = 1.7, camera_fov_y: float = 1.7):
    # Create visualization canvas
    scale = 60
    camera_fov_x = camera_fov_x * 2
    camera_fov_y = camera_fov_y * 2
    canvas_w = int((9.5 + camera_fov_x) * scale)
    canvas_h = int((9.0 + camera_fov_y) * scale)
    canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)

    frame_w, frame_h = 640, 480
    center_x, center_y = frame_w / 2, frame_h / 2

    # Draw edges (white)
    edge_x1 = int((0 + camera_fov_x / 2) * scale)
    edge_y1 = int((0 + camera_fov_y / 2) * scale)
    edge_x2 = int((9.5 + camera_fov_x / 2) * scale)
    edge_y2 = int((9.0 + camera_fov_y / 2) * scale)
    cv2.rectangle(canvas, (edge_x1, edge_y1), (edge_x2, edge_y2), (255, 255, 255), 2)

    # Draw all detections first (gray)
    for scan in GlobalState().scan_data:
        motor_y, motor_x = scan['motor_position']
        if 'detections' in scan:
            for det in scan['detections']:
                x1, y1, x2, y2 = det[0], det[1], det[2], det[3]

                pixel_offset_x1 = x1 - center_x
                pixel_offset_y1 = y1 - center_y
                pixel_offset_x2 = x2 - center_x
                pixel_offset_y2 = y2 - center_y

                motor_offset_x1 = (pixel_offset_x1 / frame_w) * camera_fov_x
                motor_offset_y1 = (pixel_offset_y1 / frame_h) * camera_fov_y
                motor_offset_x2 = (pixel_offset_x2 / frame_w) * camera_fov_x
                motor_offset_y2 = (pixel_offset_y2 / frame_h) * camera_fov_y

                world_x1 = motor_x + motor_offset_x1
                world_y1 = 9.0 - (motor_y + motor_offset_y1)
                world_x2 = motor_x + motor_offset_x2
                world_y2 = 9.0 - (motor_y + motor_offset_y2)

                canvas_x1 = int((world_x1 + camera_fov_x / 2) * scale)
                canvas_y1 = int((world_y1 + camera_fov_y / 2) * scale)
                canvas_x2 = int((world_x2 + camera_fov_x / 2) * scale)
                canvas_y2 = int((world_y2 + camera_fov_y / 2) * scale)

                cv2.rectangle(canvas, (canvas_x1, canvas_y1), (canvas_x2, canvas_y2), (128, 128, 128), 1)

    for i, merged_group in enumerate(merged_clusters):
        # Draw individual clusters in world coordinates
        for cluster_data in merged_group:
            motor_y, motor_x = cluster_data['motor_position']
            x1, y1, x2, y2 = cluster_data['bbox']

            pixel_offset_x1 = x1 - center_x
            pixel_offset_y1 = y1 - center_y
            pixel_offset_x2 = x2 - center_x
            pixel_offset_y2 = y2 - center_y

            motor_offset_x1 = (pixel_offset_x1 / frame_w) * camera_fov_x
            motor_offset_y1 = (pixel_offset_y1 / frame_h) * camera_fov_y
            motor_offset_x2 = (pixel_offset_x2 / frame_w) * camera_fov_x
            motor_offset_y2 = (pixel_offset_y2 / frame_h) * camera_fov_y

            world_x1 = motor_x + motor_offset_x1
            world_y1 = 9.0 - (motor_y + motor_offset_y1)
            world_x2 = motor_x + motor_offset_x2
            world_y2 = 9.0 - (motor_y + motor_offset_y2)

            canvas_x1 = int((world_x1 + camera_fov_x / 2) * scale)
            canvas_y1 = int((world_y1 + camera_fov_y / 2) * scale)
            canvas_x2 = int((world_x2 + camera_fov_x / 2) * scale)
            canvas_y2 = int((world_y2 + camera_fov_y / 2) * scale)

            cv2.rectangle(canvas, (canvas_x1, canvas_y1), (canvas_x2, canvas_y2), (0, 0, 255), 2)

        # Draw merged bounding box
        all_world_coords = []
        for cluster_data in merged_group:
            motor_y, motor_x = cluster_data['motor_position']
            x1, y1, x2, y2 = cluster_data['bbox']

            pixel_offset_x1 = x1 - center_x
            pixel_offset_y1 = y1 - center_y
            pixel_offset_x2 = x2 - center_x
            pixel_offset_y2 = y2 - center_y

            motor_offset_x1 = (pixel_offset_x1 / frame_w) * camera_fov_x
            motor_offset_y1 = (pixel_offset_y1 / frame_h) * camera_fov_y
            motor_offset_x2 = (pixel_offset_x2 / frame_w) * camera_fov_x
            motor_offset_y2 = (pixel_offset_y2 / frame_h) * camera_fov_y

            all_world_coords.extend([
                (motor_x + motor_offset_x1, 9.0 - (motor_y + motor_offset_y1)),
                (motor_x + motor_offset_x2, 9.0 - (motor_y + motor_offset_y2))
            ])

        merged_x1 = int((min([c[0] for c in all_world_coords]) + camera_fov_x / 2) * scale)
        merged_y1 = int((min([c[1] for c in all_world_coords]) + camera_fov_y / 2) * scale)
        merged_x2 = int((max([c[0] for c in all_world_coords]) + camera_fov_x / 2) * scale)
        merged_y2 = int((max([c[1] for c in all_world_coords]) + camera_fov_y / 2) * scale)

        cv2.rectangle(canvas, (merged_x1, merged_y1), (merged_x2, merged_y2), (0, 255, 0), 4)
        cv2.putText(canvas, f"Merged {i} ({len(merged_group)})", (merged_x1, merged_y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    return canvas


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
