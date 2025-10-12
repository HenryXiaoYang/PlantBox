from Common import Singleton, PlantBoxSerial

class MotorControl(metaclass=Singleton):
    def __init__(self, plant_box_serial:PlantBoxSerial, servo_1_offset=0, servo_2_offset=0, servo_3_offset=0):
        self.current_x = 0.0
        self.current_y = 0.0
        self.current_z = 0.0
        self.current_servo_1 = 180
        self.current_servo_2 = 82.5
        self.current_servo_3 = 90
        self.servo_1_offset = servo_1_offset
        self.servo_2_offset = servo_2_offset
        self.servo_3_offset = servo_3_offset
        self.ser = plant_box_serial

    def move_to(self, x: float, y: float, z: float):
        if not (0 <= x <= 9.5):
            raise ValueError("X coordinate out of range (0 to 9.5)")
        elif not (0 <= y <= 9.0):
            raise ValueError("Y coordinate out of range (0 to 9.0)")
        elif not (0 <= z <= 1.5):
            raise ValueError("Z coordinate out of range (0 to 1.5)")


        command = f"{x},{y},{z},{self.current_servo_1},{self.current_servo_2},{self.current_servo_3}\n"
        self.ser.write(command.encode())

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

    def set_servo_angles(self, servo_1: float = -1.0, servo_2: float = -1.0, servo_3: float = -1.0):
        if servo_1 == -1.0:
            servo_1 = self.current_servo_1
        if servo_2 == -1.0:
            servo_2 = self.current_servo_2
        if servo_3 == -1.0:
            servo_3 = self.current_servo_3

        if not (0 <= servo_1 <= 360):
            raise ValueError("Servo 1 angle out of range (0 to 360)")
        elif not (20 <= servo_2 <= 160):
            raise ValueError("Servo 2 angle out of range (20 to 160)")
        elif not (0 <= servo_3 <= 180):
            raise ValueError("Servo 3 angle out of range (0 to 180)")

        s1 = servo_1 + self.servo_1_offset
        s2 = servo_2 + self.servo_2_offset
        s3 = servo_3 + self.servo_3_offset

        if not (0 <= s1 <= 360):
            raise ValueError(f"Servo 1 angle {s1} out of range after offset")
        elif not (20 <= s2 <= 160):
            raise ValueError(f"Servo 2 angle {s2} out of range after offset")
        elif not (0 <= s3 <= 180):
            raise ValueError(f"Servo 3 angle {s3} out of range after offset")

        command = f"{self.current_x},{self.current_y},{self.current_z},{s1},{s2},{s3}\n"
        self.ser.write(command.encode())

        self.current_servo_1 = s1
        self.current_servo_2 = s2
        self.current_servo_3 = s3