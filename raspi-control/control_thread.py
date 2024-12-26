import logging
from threading import Thread
import time

from cobs import cobs
import serial
from gpiozero import DistanceSensor
from gpiozero.pins.pigpio import PiGPIOFactory


class ControlTread(Thread):
    def __init__(self, serial: serial.Serial, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.serial = serial

        self.__last_presence_state = False
        self.__mock_presence_timer = time.time()

        self.__distance_sensor = DistanceSensor(
            echo=27, trigger=4, pin_factory=PiGPIOFactory()
        )

        self.__last_vibration_message = None

    def run(self) -> None:
        while True:
            # Wait until someone is present
            self.__distance_sensor.wait_for_in_range()  # type: ignore
            logging.info("Someone is present")

            # Turn on the sensors on Arduino
            self.__send_on_off(True)

            # Forge the data for Arduino feedback
            pass

            # Wait until someone is not present
            self.__distance_sensor.wait_for_out_of_range()  # type: ignore
            logging.info("Someone is leaving")

            # Turn off the sensors on Arduino
            self.__send_on_off(False)

    def __send_on_off(self, on_off: bool) -> None:
        # Send the on/off command to the Arduino
        self.__send_message(bytes((0, on_off)))

    def __send_message(self, message: bytes) -> None:
        data = cobs.encode(message) + b"\x00"
        self.serial.write(data)

    def __get_mock_presence_state(self) -> bool:
        current_time = time.time()
        if current_time - self.__mock_presence_timer > 5:
            self.__mock_presence_timer = current_time
            return not self.__last_presence_state
        return self.__last_presence_state
