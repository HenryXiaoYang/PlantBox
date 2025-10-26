import time
import cv2
import numpy as np
from loguru import logger
from Yolo import detect_plants, get_model
from Common import GlobalState
from Common.dbscan import cluster_boxes_dbscan
from Common.cluster_merge import merge_clusters_across_positions


def job(cam, motor, flask_state, socketio, recognition_agent, requirements_agent, manager):
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
    motor.set_servo_angles(servo_1=0, servo_2=90, servo_3=0)
    time.sleep(5)

    # Clear previous YOLO frame and scan data
    flask_state['yolo_frame'] = None
    GlobalState().scan_data = []

    for i, x in enumerate(x_positions): # zig-zag pattern
        if flask_state['job_control']['should_stop']:
            logger.info("Job stopped by user")
            flask_state['job_status'] = 'stopped'
            socketio.emit('job_status', {'status': 'stopped'})
            return
        y_range = reversed(y_positions) if i % 2 else y_positions
        time.sleep(0.5)
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

            # Filter out fruits (assuming class 1 is fruit, class 0 is plant)
            if len(results[0].boxes) > 0:
                plant_boxes = []
                for box in results[0].boxes:
                    if int(box.cls[0]) == 0:  # Only keep plants (class 0)
                        plant_boxes.append(box.xyxy[0].tolist())
            else:
                plant_boxes = []

            clusters = cluster_boxes_dbscan(plant_boxes, eps=2000, min_samples=3) if plant_boxes else []

            # Save scan data
            for cluster in clusters:
                GlobalState().scan_data.append({
                    'motor_position': (x, y),
                    'cluster': cluster.tolist() if hasattr(cluster, 'tolist') else list(cluster),
                    'detections': results[0].boxes.data.tolist() if len(results[0].boxes) > 0 else []
                })

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
                    logger.debug(
                        f"Position ({x}, {y}): cluster size={len(cluster)}, distance={normalized_distance:.2f}, score={score:.2f}")

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
        time.sleep(5)

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

        # Merge clusters across all positions and visualize
        merged_clusters = merge_clusters_across_positions(GlobalState().scan_data, eps=1.5, min_samples=1)

        # Filter out small clusters (1-2 detections)
        filtered_clusters = []
        for merged_group in merged_clusters:
            total_detections = sum(len(cluster_data['cluster']) for cluster_data in merged_group)
            if total_detections > 2:
                filtered_clusters.append(merged_group)
        merged_clusters = filtered_clusters

        # Create visualization canvas
        scale = 60
        camera_fov_x = 1.7 * 2
        camera_fov_y = 1.49 * 2
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

        flask_state['yolo_frame'] = canvas

        plant = recognition_agent.regocnize_plant(frame)
        logger.info(f"Plant: {plant.plant_name}, {plant.growth_stage}")

        requirements = requirements_agent.get_requirements(plant.plant_name, plant.growth_stage)
        logger.info(f"Requirements: {requirements}")

        try:
            manager.update(requirements)

            flask_state['target_env'] = {
                'watering_frequency': requirements.watering_frequency,
                'watering_amount': requirements.watering_amount,
                'light_duration': requirements.light_duration,
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

