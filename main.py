import os
import re
import threading
import time
import cv2
import numpy as np
from cv2_enumerate_cameras import enumerate_cameras
from dotenv import load_dotenv
from loguru import logger
import Common
from Agent.PlantRecognition import PlantRecognitionAgent
from Agent.PlantRequirements import PlantRequirementsAgent
from Common import GlobalState, PlantBoxSerial
from Common import scheduler
from EnvActuator import ActuatorManager
from MotorContol.motor_control import MotorControl
from Sensors.packed_sensor_input import get_packed_sensor_input
from Yolo import detect_plants, get_model
from Common.dbscan import cluster_boxes_dbscan
from app import run_flask_server, state as flask_state, serial_output_callback
from app import socketio
from Common.cluster_merge import merge_clusters_across_positions
from Jobs import experiment_1, experiment_2, init_plant_scan, init_plant_scan, job

def main():
    # Start Flask server in background thread
    flask_thread = threading.Thread(target=run_flask_server, daemon=True)
    flask_thread.start()
    logger.info("Flask server started on http://0.0.0.0:5000")

    init_plant_scan(cam, motor, flask_state, socketio, recognition_agent, requirements_agent, manager)

    task = scheduler.every(6).hours.do(lambda: job(cam, motor, manager, flask_state,recognition_agent, requirements_agent, socketio))
    try:
        while True:
            if flask_state['job_control'].get('run_now'):
                flask_state['job_control']['run_now'] = False
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

if __name__ == "__main__":
    load_dotenv()

    ser = Common.PlantBoxSerial(port='COM8', baudrate=115200, serial_callback=serial_output_callback)

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
                                                base_url=os.getenv("OPENAI_API_BASE"))

    manager = ActuatorManager()

    motor = MotorControl(ser, 10, 25, 0)

    # Share camera and motor with Flask
    flask_state['camera'] = cam
    flask_state['motor'] = motor

    main()
