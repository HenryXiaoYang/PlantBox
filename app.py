from flask import Flask, Response, jsonify, request
from flask_socketio import SocketIO
from flask_cors import CORS
import cv2
import threading
import time

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Shared state
state = {
    'camera': None,
    'motor': None,
    'yolo_frame': None,
    'sensor_data': {'temperature': 0, 'humidity': 0, 'soil_humidity': 0},
    'target_env': {},
    'serial_buffer': [],
    'job_status': 'stopped',
    'job_control': {'should_stop': False, 'run_now': False}
}

def generate_camera_stream():
    """Generate MJPEG stream from camera."""
    while True:
        if state['camera'] and state['camera'].isOpened():
            ret, frame = state['camera'].read()
            if ret:
                _, buffer = cv2.imencode('.jpg', frame)
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        time.sleep(0.033)

def generate_yolo_stream():
    """Generate MJPEG stream from YOLO output."""
    while True:
        if state['yolo_frame'] is not None:
            _, buffer = cv2.imencode('.jpg', state['yolo_frame'])
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        time.sleep(0.033)

@app.route('/api/camera/stream')
def camera_stream():
    return Response(generate_camera_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/yolo/stream')
def yolo_stream():
    return Response(generate_yolo_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/status')
def status():
    motor_data = {}
    if state['motor']:
        motor_data = {
            'x': state['motor'].current_x,
            'y': state['motor'].current_y,
            'z': state['motor'].current_z,
            'servo_1': state['motor'].current_servo_1,
            'servo_2': state['motor'].current_servo_2,
            'servo_3': state['motor'].current_servo_3
        }

    return jsonify({
        'motor': motor_data,
        'sensors': state['sensor_data'],
        'target_env': state['target_env'],
        'job_status': state['job_status']
    })

@app.route('/api/job/start', methods=['POST'])
def start_job():
    if state['job_status'] == 'running':
        return jsonify({'success': False, 'error': 'Job already running'})
    state['job_control']['should_stop'] = False
    state['job_control']['run_now'] = True
    return jsonify({'success': True})

@app.route('/api/job/stop', methods=['POST'])
def stop_job():
    state['job_control']['should_stop'] = True
    return jsonify({'success': True})

@app.route('/api/motor/command', methods=['POST'])
def motor_command():
    if not state['motor']:
        return jsonify({'success': False, 'error': 'Motor not initialized'})

    data = request.json
    try:
        command = f"{data['x']},{data['y']},{data['z']},{data['servo_1']},{data['servo_2']},{data['servo_3']}\n"
        state['motor'].ser.write(command.encode())
        state['motor'].current_x = data['x']
        state['motor'].current_y = data['y']
        state['motor'].current_z = data['z']
        state['motor'].current_servo_1 = data['servo_1']
        state['motor'].current_servo_2 = data['servo_2']
        state['motor'].current_servo_3 = data['servo_3']
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/serial/command', methods=['POST'])
def serial_command():
    if not state['motor']:
        return jsonify({'success': False, 'error': 'Motor not initialized'})

    data = request.json
    try:
        state['motor'].ser.write((data['command'] + '\n').encode())
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def serial_output_callback(line):
    """Callback for serial output from motor controller."""
    socketio.emit('serial_output', {'line': line})

def emit_status_updates():
    """Background thread to emit status updates via WebSocket."""
    while True:
        motor_data = {}
        if state['motor']:
            motor_data = {
                'x': state['motor'].current_x,
                'y': state['motor'].current_y,
                'z': state['motor'].current_z,
                'servo_1': state['motor'].current_servo_1,
                'servo_2': state['motor'].current_servo_2,
                'servo_3': state['motor'].current_servo_3
            }

        socketio.emit('status_update', {
            'motor': motor_data,
            'sensors': state['sensor_data'],
            'target_env': state['target_env']
        })
        time.sleep(1)

def run_flask_server():
    """Run Flask server in a separate thread."""
    threading.Thread(target=emit_status_updates, daemon=True).start()
    socketio.run(app, allow_unsafe_werkzeug=True, host='0.0.0.0', port=5000, debug=False, use_reloader=False)
