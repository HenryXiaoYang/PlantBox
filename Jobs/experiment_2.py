import re
import time
from loguru import logger
from Yolo import get_model


def experiment_2(cam, motor, flask_state, socketio):
    flask_state['job_status'] = 'running'
    socketio.emit('job_status', {'status': 'running'})
    logger.info("Starting job")

    motor.ser.write("0,2,0".encode())

    step_x, step_y = 3, 1

    x_positions = [i * step_x for i in range(int(9.5 / step_x) + 1)]
    y_positions = [j * step_y for j in range(int(9.0 / step_y) + 1)]

    motor.goto(0, 0, 0)
    motor.set_servo_angles(servo_1=0, servo_2=90, servo_3=0)
    time.sleep(3)

    leaves = []

    for i, x in enumerate(x_positions):  # zig-zag pattern
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

    step_size = 0.15  # Small incremental movement
    model = get_model()
    for _ in range(20):
        if not cam.isOpened():
            raise IOError("Cannot open webcam")
        ret, frame = cam.read()

        if not ret:
            logger.warning(f"Failed to capture at ({x}, {y})")
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

        motor_x = current_motor_x if distance_y < 10 else current_motor_x + (-step_size if leaf_top_y < center_y else step_size)
        motor_y = current_motor_y if distance_x < 10 else current_motor_y + (-step_size if leaf_top_x < center_x else step_size)

        motor_x = max(0, min(9.5, motor_x))
        motor_y = max(0, min(9.0, motor_y))

        logger.info(f"Leaf at ({leaf_top_x:.0f}, {leaf_top_y:.0f}), center ({center_x:.0f}, {center_y:.0f}), moving to ({motor_x:.2f}, {motor_y:.2f})")
        motor.goto(motor_x, motor_y, 0)
        time.sleep(2)

    logger.debug(motor.get_position())

    motor.goto(motor.current_x, motor.current_y, 1.5)
    time.sleep(4)

    count = 0
    humidity = []
    while count < 10:
        response = motor.ser.readline().strip()
        if response.startswith("婀垮害鍊?"):
            try:
                hum_value = re.search(r'\d+\.?\d*', response).group()
                humidity.append(hum_value)
                count += 1
                logger.debug(f"Humidity reading {count}: {hum_value}%")
                time.sleep(2)
            except ValueError:
                logger.warning(f"Invalid humidity value received: {response}")

    humidity.sort()
    humidity = humidity[1:-1]  # Remove highest and lowest
    average_humidity = sum(map(float, humidity)) / len(humidity)
    logger.info(f"Average humidity: {average_humidity:.2f}%")

    motor.goto(motor.current_x, motor.current_y, 0)
    time.sleep(2.5)


