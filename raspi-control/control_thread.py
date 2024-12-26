import logging
from threading import Thread, Event
import time

from cobs import cobs
import serial
from gpiozero import DistanceSensor
from gpiozero.pins.pigpio import PiGPIOFactory


class ControlTread(Thread):
    def __init__(
        self, serial: serial.Serial, exit_event: Event, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)

        self.serial = serial
        self.exit_event = exit_event

        self.__last_presence_state = False
        self.__mock_presence_timer = time.time()

        self.__distance_sensor = DistanceSensor(
            echo=27, trigger=4, pin_factory=PiGPIOFactory()
        )

        self.__last_vibration_message = None

    def run(self) -> None:
        while not self.exit_event.is_set():
            presence_state = self.__distance_sensor.in_range

            if presence_state != self.__last_presence_state:
                self.__last_presence_state = presence_state
                if presence_state:
                    logging.info("Someone is present")

                    # Turn on the sensors on Arduino
                    self.__send_on_off(True)

                    # Forge the data for Arduino feedback
                    pass
                else:
                    logging.info("Someone is leaving")

                    # Turn off the sensors on Arduino
                    self.__send_on_off(False)

            time.sleep(0.05)

        # Clean up
        self.__send_on_off(False)
        logging.info("Exiting ControlThread")

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
