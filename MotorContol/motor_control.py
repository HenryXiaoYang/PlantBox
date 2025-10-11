import serial
import time

class MotorControl:
    def __init__(self, port='COM3', baudrate=115200):
        self.current_x = 0.0
        self.current_y = 0.0
        self.current_z = 0.0
        self.current_servo_1 = 180
        self.current_servo_2 = 82.5
        self.current_servo_3 = 90
        self.ser = serial.Serial(port, baudrate, timeout=1)
        time.sleep(2)

    def move_to(self, x: float, y: float, z: float):
        if not (0 <= x <= 9.5):
            raise ValueError("X coordinate out of range (0 to 9.5)")
        elif not (0 <= y <= 9.0):
            raise ValueError("Y coordinate out of range (0 to 9.0)")
        elif not (0 <= z <= 1.5):
            raise ValueError("Z coordinate out of range (0 to 1.5)")

        command = f"{x},{y},{z},{self.current_servo_1},{self.current_servo_2},{self.current_servo_3}\n"
        self.ser.write(command.encode())
        time.sleep(5)

        self.current_x = x
        self.current_y = y
        self.current_z = z

    def goto(self, x: float, y: float, z: float):
        """Alias for move_to."""
        self.move_to(x, y, z)

    # Relative movement
    def move_by(self, dx: float, dy: float, dz: float):
        """Move the motor by the specified (dx, dy, dz) offsets."""
        if not (-9.5 <= self.current_x + dx <= 9.5):
            raise ValueError("Resulting X coordinate out of range (0 to 9.5)")
        elif not (-9.0 <= self.current_y + dy <= 9.0):
            raise ValueError("Resulting Y coordinate out of range (0 to 9.0)")
        elif not (-1.5 <= self.current_z + dz <= 1.5):
            raise ValueError("Resulting Z coordinate out of range (0 to 1.5)")
        new_x = self.current_x + dx
        new_y = self.current_y + dy
        new_z = self.current_z + dz
        self.move_to(new_x, new_y, new_z)