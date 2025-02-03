from abc import ABC, abstractmethod
import time

from gpiozero import DistanceSensor
from gpiozero.pins.pigpio import PiGPIOFactory

DISTANCE_SENSOR_ECHO = 17
DISTANCE_SENSOR_TRIG = 4


class BaseControlProvider(ABC):
    @abstractmethod
    def get_presence_state(self) -> bool:
        pass


class DistanceSensorControlProvider(BaseControlProvider):
    def __init__(self):
        super().__init__()
        self.__distance_sensor = DistanceSensor(
            echo=DISTANCE_SENSOR_ECHO,
            trigger=DISTANCE_SENSOR_TRIG,
            pin_factory=PiGPIOFactory(),
        )

    def get_presence_state(self):
        return self.__distance_sensor.in_range


class MockControlProvider(BaseControlProvider):
    def __init__(self):
        super().__init__()
        self.__mock_presence_timer = time.time()
        self.__last_presence_state = False

    def get_presence_state(self):
        current_time = time.time()
        if current_time - self.__mock_presence_timer > 5:
            self.__mock_presence_timer = current_time
            self.__last_presence_state = not self.__last_presence_state
        return self.__last_presence_state


class AlwaysOnControlProvider(BaseControlProvider):
    def get_presence_state(self):
        return True
