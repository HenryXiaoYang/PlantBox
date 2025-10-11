# def job():
#     from app import socketio
#     flask_state['job_status'] = 'running'
#     socketio.emit('job_status', {'status': 'running'})
#     logger.info("Starting jaob")
#     step_x, step_y = 3, 1.5
#     best_frame = None
#     best_cluster = None
#     best_motor_pos = None
#
#     x_positions = [i * step_x for i in range(int(9.5 / step_x) + 1)]
#     y_positions = [j * step_y for j in range(int(9.0 / step_y) + 1)]
#
#     motor.goto(0, 0, 0)
#     motor.set_servo_angles(servo_1=180,servo_2=90,servo_3=0)
#     time.sleep(5)
#
#     for i, x in enumerate(x_positions):
#         if flask_state['job_control']['should_stop']:
#             logger.info("Job stopped by user")
#             flask_state['job_status'] = 'stopped'
#             socketio.emit('job_status', {'status': 'stopped'})
#             return
#         y_range = reversed(y_positions) if i % 2 else y_positions
#         for y in y_range:
#             if flask_state['job_control']['should_stop']:
#                 logger.info("Job stopped by user")
#                 flask_state['job_status'] = 'stopped'
#                 socketio.emit('job_status', {'status': 'stopped'})
#                 return
#             motor.move_to(x, y, 0)
#             time.sleep(1)
#
#             logger.debug(f"Moved to ({x}, {y})")
#
#             if not cam.isOpened():
#                 raise IOError("Cannot open webcam")
#             ret, frame = cam.read()
#
#             if not ret:
#                 logger.warning(f"Failed to capture at ({x}, {y})")
#                 continue
#
#             model = get_model()
#             results = model(frame)
#             annotated_frame = results[0].plot()
#
#             clusters = detect_plants(frame)
#
#             # Draw clusters on annotated frame
#             if clusters:
#                 colors = [(0, 0, 255), (0, 255, 0), (255, 0, 0), (255, 255, 0), (255, 0, 255), (0, 255, 255)]
#                 for i, cluster in enumerate(clusters):
#                     if len(cluster) > 1:
#                         color = colors[i % len(colors)]
#                         x1 = min([box[0] for box in cluster])
#                         y1 = min([box[1] for box in cluster])
#                         x2 = max([box[2] for box in cluster])
#                         y2 = max([box[3] for box in cluster])
#                         cv2.rectangle(annotated_frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 4)
#                         cv2.putText(annotated_frame, f"Cluster {i} ({len(cluster)})", (int(x1), int(y1) - 15),
#                                     cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
#
#                 frame_h, frame_w = frame.shape[:2]
#                 center_x, center_y = frame_w / 2, frame_h / 2
#                 best_score = float('-inf')
#
#                 for cluster in clusters:
#                     x1 = min([box[0] for box in cluster])
#                     y1 = min([box[1] for box in cluster])
#                     x2 = max([box[2] for box in cluster])
#                     y2 = max([box[3] for box in cluster])
#                     cluster_center_x = (x1 + x2) / 2
#                     cluster_center_y = (y1 + y2) / 2
#                     distance = ((cluster_center_x - center_x) ** 2 + (cluster_center_y - center_y) ** 2) ** 0.5
#
#                     score = len(cluster) - (distance / max(frame_w, frame_h))
#
#                     if score > best_score:
#                         best_score = score
#                         best_frame = frame
#                         best_cluster = cluster
#                         best_motor_pos = (x, y)
#
#             flask_state['yolo_frame'] = annotated_frame
#
#     if best_frame is not None:
#         x1 = min([box[0] for box in best_cluster])
#         y1 = min([box[1] for box in best_cluster])
#         x2 = max([box[2] for box in best_cluster])
#         y2 = max([box[3] for box in best_cluster])
#         pixel_x = (x1 + x2) / 2
#         pixel_y = (y1 + y2) / 2
#
#         frame_h, frame_w = best_frame.shape[:2]
#         offset_x = (pixel_x - frame_w / 2) / frame_w * 9.5
#         offset_y = (pixel_y - frame_h / 2) / frame_h * 9.0
#         motor_x = best_motor_pos[0] + offset_x
#         motor_y = best_motor_pos[1] + offset_y
#
#         motor.goto(motor_x, motor_y, 0)
#         time.sleep(0.9)
#
#         logger.info(
#             f"Closest cluster to center at pixel ({pixel_x:.0f}, {pixel_y:.0f}) -> motor ({motor_x:.2f}, {motor_y:.2f})")
#
#         ret, frame = cam.read()
#
#         if not ret:
#             logger.warning(f"Failed to capture at ({x}, {y})")
#             return
#
#         model = get_model()
#         results = model(frame)
#         annotated_frame = results[0].plot()
#
#         clusters = detect_plants(frame)
#
#         if clusters:
#             colors = [(0, 0, 255), (0, 255, 0), (255, 0, 0), (255, 255, 0), (255, 0, 255), (0, 255, 255)]
#             for i, cluster in enumerate(clusters):
#                 if len(cluster) > 1:
#                     color = colors[i % len(colors)]
#                     x1 = min([box[0] for box in cluster])
#                     y1 = min([box[1] for box in cluster])
#                     x2 = max([box[2] for box in cluster])
#                     y2 = max([box[3] for box in cluster])
#                     cv2.rectangle(annotated_frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 4)
#                     cv2.putText(annotated_frame, f"Cluster {i} ({len(cluster)})", (int(x1), int(y1) - 15),
#                                 cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
#         flask_state['yolo_frame'] = annotated_frame
#
#         plant = recognition_agent.regocnize_plant(frame)
#         logger.info(f"Plant: {plant.plant_name}, {plant.growth_stage}")
#
#         requirements = requirements_agent.get_requirements(plant.plant_name, plant.growth_stage)
#         logger.info(f"Requirements: {requirements}")
#
#         try:
#             manager.update(requirements)
#
#
#             flask_state['target_env'] = {
#                 'watering_frequency': requirements.watering_frequency,
#                 'watering_amount': requirements.watering_amount,
#                 'sunlight': requirements.sunlight,
#                 'temperature': requirements.temperature,
#                 'fertilization_frequency': requirements.fertilization_frequency,
#                 'fertilization_amount': requirements.fertilization_amount,
#                 'wind': requirements.wind
#             }
#         except ValueError as e:
#             logger.error(f"Failed to update actuator settings due to invalid requirements: {e}")
#
#     flask_state['job_status'] = 'stopped'
#     socketio.emit('job_status', {'status': 'stopped'})
#     logger.info("Job completed")