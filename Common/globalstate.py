from .singleton import Singleton
from threading import Lock

class GlobalState(metaclass=Singleton):
    def __init__(self):
        self.is_shutting_down = False
        self.serial_command_lock = Lock()
        self.serial_command = (0,0,0)
        self.scan_data = []
