from .singleton import singleton

@singleton
class GlobalState:
    def __init__(self):
        self.is_shutting_down = False