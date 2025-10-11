import os
import threading
import time

import cv2
from cv2_enumerate_cameras import enumerate_cameras
from dotenv import load_dotenv
from loguru import logger

from EnvActuator import ActuatorManager
from MotorContol.motor_control import MotorControl
from agent.PlantRecognition import PlantRecognitionAgent
from agent.PlantRequirements import PlantRequirementsAgent
from app import run_flask_server, state as flask_state, serial_output_callback
from common import GlobalState
from common import scheduler
from sensors.packed_sensor_input import get_packed_sensor_input
from yolo import detect_plants, get_model


def main():
    # Start Flask server in background thread
    flask_thread = threading.Thread(target=run_flask_server, daemon=True)
    flask_thread.start()
    logger.info("Flask server started on http://0.0.0.0:5000")

    task = scheduler.every(10).minutes.do(job)

    try:
        while True:
            if flask_state['job_control'].get('run_now'):
                flask_state['job_control']['run_now'] = False
                job()
            scheduler.run_pending()
            # Update sensor data
            temp, humidity, soil_humidity = get_packed_sensor_input()
            flask_state['sensor_data'] = {
                'temperature': temp,
                'humidity': humidity,
                'soil_humidity': soil_humidity
            }
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        GlobalState().is_shutting_down = True
        cam.release()


def job():
    from app import socketio
    flask_state['job_status'] = 'running'
    socketio.emit('job_status', {'status': 'running'})
    logger.info("Starting job")
    step_x, step_y = 3, 1.5
    best_frame = None
    best_cluster = None
    best_motor_pos = None
    best_score = float('-inf')

    x_positions = [i * step_x for i in range(int(9.5 / step_x) + 1)]
    y_positions = [j * step_y for j in range(int(9.0 / step_y) + 1)]

    motor.goto(0, 0, 0)
    motor.set_servo_angles(servo_1=0,servo_2=90,servo_3=0)
    time.sleep(5)

    for i, x in enumerate(x_positions):
        if flask_state['job_control']['should_stop']:
            logger.info("Job stopped by user")
            flask_state['job_status'] = 'stopped'
            socketio.emit('job_status', {'status': 'stopped'})
            return
        y_range = reversed(y_positions) if i % 2 else y_positions
        for y in y_range:
            if flask_state['job_control']['should_stop']:
                logger.info("Job stopped by user")
                flask_state['job_status'] = 'stopped'
                socketio.emit('job_status', {'status': 'stopped'})
                return
            motor.move_to(x, y, 0)
            time.sleep(1)

            logger.debug(f"Moved to ({x}, {y})")

            if not cam.isOpened():
                raise IOError("Cannot open webcam")
            ret, frame = cam.read()

            if not ret:
                logger.warning(f"Failed to capture at ({x}, {y})")
                continue

            model = get_model()
            results = model(frame)
            annotated_frame = results[0].plot()

            clusters = detect_plants(frame)

            # Draw clusters on annotated frame
            if clusters:
                colors = [(0, 0, 255), (0, 255, 0), (255, 0, 0), (255, 255, 0), (255, 0, 255), (0, 255, 255)]
                for i, cluster in enumerate(clusters):
                    if len(cluster) > 1:
                        color = colors[i % len(colors)]
                        x1 = min([box[0] for box in cluster])
                        y1 = min([box[1] for box in cluster])
                        x2 = max([box[2] for box in cluster])
                        y2 = max([box[3] for box in cluster])
                        cv2.rectangle(annotated_frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 4)
                        cv2.putText(annotated_frame, f"Cluster {i} ({len(cluster)})", (int(x1), int(y1) - 15),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                frame_h, frame_w = frame.shape[:2]
                center_x, center_y = frame_w / 2, frame_h / 2

                for cluster in clusters:
                    x1 = min([box[0] for box in cluster])
                    y1 = min([box[1] for box in cluster])
                    x2 = max([box[2] for box in cluster])
                    y2 = max([box[3] for box in cluster])
                    cluster_center_x = (x1 + x2) / 2
                    cluster_center_y = (y1 + y2) / 2
                    distance = ((cluster_center_x - center_x) ** 2 + (cluster_center_y - center_y) ** 2) ** 0.5
                    normalized_distance = distance / max(frame_w, frame_h)

                    score = len(cluster) * (1 - normalized_distance)
                    logger.debug(f"Position ({x}, {y}): cluster size={len(cluster)}, distance={normalized_distance:.2f}, score={score:.2f}")

                    if score > best_score:
                        best_score = score
                        best_frame = frame
                        best_cluster = cluster
                        best_cluster_pixel = (cluster_center_x, cluster_center_y)
                        best_motor_pos = (x, y)

            flask_state['yolo_frame'] = annotated_frame

    if best_frame is not None:
        frame_h, frame_w = best_frame.shape[:2]
        center_x, center_y = frame_w / 2, frame_h / 2

        camera_fov_x = 1.04 * 2  # Camera FOV: center to edge = 1.04, full width = 2.08
        camera_fov_y = 1.49 * 2  # Camera FOV: center to edge = 1.49, full height = 2.98
        offset_x = (best_cluster_pixel[0] - center_x) / frame_w * camera_fov_x
        offset_y = (best_cluster_pixel[1] - center_y) / frame_h * camera_fov_y
        motor_x = max(0, min(9.5, best_motor_pos[0] + offset_x))
        motor_y = max(0, min(9.0, best_motor_pos[1] + offset_y))

        logger.debug(f"Frame size: {frame_w}x{frame_h}")
        logger.debug(f"Best cluster pixel: {best_cluster_pixel}, frame center: ({center_x}, {center_y})")
        logger.debug(f"Best motor pos: {best_motor_pos}, offset: ({offset_x:.2f}, {offset_y:.2f})")
        logger.debug(f"Motor moving to ({motor_x:.2f}, {motor_y:.2f})")
        motor.goto(motor_x, motor_y, 0)
        time.sleep(0.9)

        logger.info(
            f"Closest cluster to center at pixel ({best_cluster_pixel[0]:.0f}, {best_cluster_pixel[1]:.0f}) -> motor ({motor_x:.2f}, {motor_y:.2f})")

        ret, frame = cam.read()

        if not ret:
            logger.warning(f"Failed to capture at ({x}, {y})")
            return

        model = get_model()
        results = model(frame)
        annotated_frame = results[0].plot()

        clusters = detect_plants(frame)

        # Recalculate cluster center from current view and adjust motor position
        if clusters:
            frame_h, frame_w = frame.shape[:2]
            center_x, center_y = frame_w / 2, frame_h / 2

            # Find largest cluster (likely the same plant)
            largest_cluster = max(clusters, key=len)
            x1 = min([box[0] for box in largest_cluster])
            y1 = min([box[1] for box in largest_cluster])
            x2 = max([box[2] for box in largest_cluster])
            y2 = max([box[3] for box in largest_cluster])
            cluster_center_x = (x1 + x2) / 2
            cluster_center_y = (y1 + y2) / 2

            offset_x = (cluster_center_x - center_x) / frame_w * camera_fov_x
            offset_y = (cluster_center_y - center_y) / frame_h * camera_fov_y

            if abs(offset_x) > 0.1 or abs(offset_y) > 0.1:
                motor_x = max(0, min(9.5, motor_x + offset_x))
                motor_y = max(0, min(9.0, motor_y + offset_y))
                logger.debug(f"Adjusting to center cluster: moving to ({motor_x:.2f}, {motor_y:.2f})")
                motor.goto(motor_x, motor_y, 0)
                time.sleep(0.9)

                ret, frame = cam.read()
                if ret:
                    results = model(frame)
                    annotated_frame = results[0].plot()
                    clusters = detect_plants(frame)

        if clusters:
            colors = [(0, 0, 255), (0, 255, 0), (255, 0, 0), (255, 255, 0), (255, 0, 255), (0, 255, 255)]
            for i, cluster in enumerate(clusters):
                if len(cluster) > 1:
                    color = colors[i % len(colors)]
                    x1 = min([box[0] for box in cluster])
                    y1 = min([box[1] for box in cluster])
                    x2 = max([box[2] for box in cluster])
                    y2 = max([box[3] for box in cluster])
                    cv2.rectangle(annotated_frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 4)
                    cv2.putText(annotated_frame, f"Cluster {i} ({len(cluster)})", (int(x1), int(y1) - 15),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        flask_state['yolo_frame'] = annotated_frame

        ret, frame = cam.read()
        plant = recognition_agent.regocnize_plant(frame)
        logger.info(f"Plant: {plant.plant_name}, {plant.growth_stage}")

        requirements = requirements_agent.get_requirements(plant.plant_name, plant.growth_stage)
        logger.info(f"Requirements: {requirements}")

        try:
            manager.update(requirements)


            flask_state['target_env'] = {
                'watering_frequency': requirements.watering_frequency,
                'watering_amount': requirements.watering_amount,
                'sunlight': requirements.sunlight,
                'temperature': requirements.temperature,
                'fertilization_frequency': requirements.fertilization_frequency,
                'fertilization_amount': requirements.fertilization_amount,
                'wind': requirements.wind
            }
        except ValueError as e:
            logger.error(f"Failed to update actuator settings due to invalid requirements: {e}")

    flask_state['job_status'] = 'stopped'
    socketio.emit('job_status', {'status': 'stopped'})
    logger.info("Job completed")


if __name__ == "__main__":
    load_dotenv()
    cam_index = -1
    for cam in enumerate_cameras():
        if cam.name == "MF500 camera":
            cam_index = cam.index
            break

    if cam_index == -1:
        for camera_info in enumerate_cameras():
            logger.info(f"Camera index: {camera_info.index}  Name: {camera_info.name}")
        cam_index = int(input("Please enter the camera index to use and press Enter: "))

    cam = cv2.VideoCapture(cam_index)

    recognition_agent = PlantRecognitionAgent(api_key=os.getenv("OPENAI_API_KEY"),
                                              base_url=os.getenv("OPENAI_API_BASE"))
    requirements_agent = PlantRequirementsAgent(api_key=os.getenv("OPENAI_API_KEY"),
                                                base_url=os.getenv("OPENAI_API_BASE"),
                                                firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY"))

    manager = ActuatorManager()
    motor = MotorControl(servo_1_offset=15, servo_2_offset=25, serial_callback=serial_output_callback)

    # Share camera and motor with Flask
    flask_state['camera'] = cam
    flask_state['motor'] = motor

    main()
