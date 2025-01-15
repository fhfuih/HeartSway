import logging
from threading import Thread, Event
import time
from typing import Optional

import numpy as np
from cobs import cobs
import serial
from gpiozero import DistanceSensor
from gpiozero.pins.pigpio import PiGPIOFactory
from questdb.ingress import Sender, TimestampNanos

import utils

USE_MOCK_SENSOR = False


class ControlTread(Thread):
    def __init__(
        self,
        serial: serial.Serial,
        qdb_sender: Sender,
        exit_event: Event,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.serial = serial
        self.qdb_sender = qdb_sender
        self.exit_event = exit_event

        self.__distance_sensor = DistanceSensor(
            echo=27, trigger=4, pin_factory=PiGPIOFactory()
        )
        self.__last_presence_state = False

        # For test purpose
        self.__mock_presence_timer = time.time()

        self.__sensor_data_controller = utils.SensorDataController()

    def run(self) -> None:
        while not self.exit_event.is_set():
            presence_state = (
                self.__get_mock_presence_state()
                if USE_MOCK_SENSOR
                else self.__distance_sensor.in_range
            )

            if presence_state != self.__last_presence_state:
                # If the presense state changes
                self.__last_presence_state = presence_state
                if presence_state:
                    logging.info("Someone is present")

                    # Turn on the sensors on Arduino
                    self.__send_on()

                    # Forge the data for Arduino feedback
                    self.__send_data()
                    pass
                else:
                    logging.info("Someone is leaving")

                    # Turn off the sensors on Arduino
                    self.__send_off()
                    self.__prepare_next_session()
            elif presence_state:
                # If someone continutes to be present,
                # Go check if it's time to send the next batch of data
                self.__send_data()

            time.sleep(0.05)

        # Clean up
        self.__send_off()
        logging.info("Exiting ControlThread")

    def __prepare_next_session(self) -> None:
        self.__sensor_data_controller.reset_data()

    def __send_data(self) -> None:
        data_to_send = self.__sensor_data_controller.should_send(now=time.time())

        for field, data in data_to_send.items():
            if not data:
                continue

            match field:
                case "ibi":
                    type_byte = b"\x02"
                case "breaths":
                    type_byte = b"\x03"
                case _:
                    continue

            data = bytearray(type_byte)
            for d in data:
                data.extend(d.to_bytes(2, "little", signed=False))

            self.__send_message(data)

    def __send_on(self) -> None:
        self.__send_message(bytes((0, True)))
        self.qdb_sender.row(
            "controls", columns={"on_off": True}, at=TimestampNanos.now()
        )

    def __send_off(self) -> None:
        self.__send_message(bytes((0, False)))
        self.qdb_sender.row(
            "controls", columns={"on_off": False}, at=TimestampNanos.now()
        )

    def __send_message(self, message: bytes) -> None:
        data = cobs.encode(message) + b"\x00"
        self.serial.write(data)

    def __get_mock_presence_state(self) -> bool:
        current_time = time.time()
        if current_time - self.__mock_presence_timer > 5:
            self.__mock_presence_timer = current_time
            return not self.__last_presence_state
        return self.__last_presence_state
