import time
from loguru import logger
from Yolo import get_model


def experiment_1(cam, motor, flask_state, socketio):
    """
    Experiment 1 is the spray test
    :return:
    """

    flask_state['job_status'] = 'running'
    socketio.emit('job_status', {'status': 'running'})
    logger.info("Starting job")

    motor.ser.write("0,2,0".encode())

    step_x, step_y = 3, 1.5

    x_positions = [i * step_x for i in range(int(9.5 / step_x) + 1)]
    y_positions = [j * step_y for j in range(int(9.0 / step_y) + 1)]

    motor.goto(0, 0, 0)
    motor.set_servo_angles(servo_1=0, servo_2=90, servo_3=0)
    time.sleep(3)

    leaves = []

    for i, x in enumerate(x_positions): # zig-zag pattern
        if flask_state['job_control']['should_stop']:
            logger.info("Job stopped by user")
            flask_state['job_status'] = 'stopped'
            socketio.emit('job_status', {'status': 'stopped'})
            return
        y_range = reversed(y_positions) if i % 2 else y_positions
        time.sleep(1)

        flag = False

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

            flask_state['yolo_frame'] = annotated_frame

            if plant_boxes:
                leaves.extend(plant_boxes)
                flag = True
                break

        if flag:
            break

    logger.debug(f"Detected leaves: {leaves}")

    if not leaves:
        logger.warning("No leaves detected")
        flask_state['job_status'] = 'stopped'
        socketio.emit('job_status', {'status': 'stopped'})
        return

    for _ in range(5):
        if not cam.isOpened():
            raise IOError("Cannot open webcam")
        ret, frame = cam.read()

        if not ret:
            logger.warning(f"Failed to capture at ({x}, {y})")
            continue

        model = get_model()
        results = model(frame)
        annotated_frame = results[0].plot()
        flask_state['yolo_frame'] = annotated_frame

        # Filter out fruits (assuming class 1 is fruit, class 0 is plant)
        if len(results[0].boxes) > 0:
            plant_boxes = []
            for box in results[0].boxes:
                if int(box.cls[0]) == 0:  # Only keep plants (class 0)
                    plant_boxes.append(box.xyxy[0].tolist())
        else:
            plant_boxes = []

        if not plant_boxes:
            break

        x1, y1, x2, y2 = plant_boxes[0]

        # Calculate top center of leaf in pixels
        leaf_top_x = (x1 + x2) / 2
        leaf_top_y = y1  # Top of the bounding box

        # Convert pixel to motor coordinates
        frame_h, frame_w = frame.shape[:2]
        center_x, center_y = frame_w / 2, frame_h / 2

        # Check if leaf is centered
        pixel_distance = ((leaf_top_x - center_x) ** 2 + (leaf_top_y - center_y) ** 2) ** 0.5
        logger.debug(f"Distance from center: {pixel_distance:.2f} pixels, leaf top at ({leaf_top_x:.2f}, {leaf_top_y:.2f})")
        if pixel_distance < 20:
            logger.info("Leaf centered")
            break

        camera_fov_x = 3.45 * 2
        camera_fov_y = 1.68 * 2
        offset_x = (leaf_top_x - center_x) / frame_w * camera_fov_x
        offset_y = (leaf_top_y - center_y) / frame_h * camera_fov_y

        current_motor_x, current_motor_y = motor.get_position()[:2]
        motor_x = max(0, min(9.5, current_motor_x + offset_y))
        motor_y = max(0, min(9.0, current_motor_y + offset_x))

        logger.info(f"Moving to top of leaf at motor ({motor_x:.2f}, {motor_y:.2f})")
        motor.goto(motor_x, motor_y, 0)
        time.sleep(2.5)

    logger.debug(motor.get_position())

    to_spray_x_offset = 1.15
    to_spray_y_offset = -1.69

    current_motor_x, current_motor_y = motor.get_position()[:2]
    motor_x = max(0, min(9.5, current_motor_x + to_spray_x_offset))
    motor_y = max(0, min(9.0, current_motor_y + to_spray_y_offset))
    motor.goto(motor_x, motor_y, 0)
    logger.debug(motor.get_position())
    time.sleep(5)

    motor.ser.write("0,2,100")
    time.sleep(3)
    motor.ser.write("0,2,0")

    time.sleep(10)
    motor.goto(0,0,0)

