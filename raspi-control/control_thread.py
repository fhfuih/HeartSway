import logging
from threading import Thread, Event
import time
from typing import Optional
import weakref

import numpy as np
from cobs import cobs
import serial
from gpiozero import DistanceSensor
from gpiozero.pins.pigpio import PiGPIOFactory
from questdb.ingress import Sender, TimestampNanos

from led_thread import LEDThread
import utils

USE_MOCK_SENSOR = False


class ControlTread(Thread):
    def __init__(
        self,
        serial: serial.Serial,
        qdb_sender: Sender,
        led_thread: LEDThread,
        exit_event: Event,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.serial = serial
        self.qdb_sender = qdb_sender
        self.led_thread = weakref.ref(led_thread)
        self.exit_event = exit_event

        self.__distance_sensor = DistanceSensor(
            echo=utils.DISTANCE_SENSOR_ECHO,
            trigger=utils.DISTANCE_SENSOR_TRIG,
            pin_factory=PiGPIOFactory(),
        )
        self.__last_presence_state = False

        # For test purpose
        self.__mock_presence_timer = time.time()

        # It will automatically get data on init
        self.__sensor_data_controller = utils.SensorDataController()

    def run(self) -> None:
        self.__update_led_data()

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
                    self.__turn_on_arduino()
                else:
                    logging.info("Someone is leaving")
                    self.__turn_off_arduino()
            elif presence_state:
                # If someone continutes to be present,
                # Go check if it's time to send the next batch of data
                self.__send_data_if_needed()

            time.sleep(0.05)

        # Clean up
        self.__turn_off_arduino()
        logging.info("Exiting ControlThread")

    def __send_data_if_needed(self) -> None:
        data_to_send = self.__sensor_data_controller.should_send(now=time.time())

        for field, field_data in data_to_send.items():
            if field_data is None:
                continue

            match field:
                case "ibi":
                    type_byte = b"\x02"
                ## No need to send breaths data to Arduino
                # case "breaths":
                #     type_byte = b"\x03"
                case _:
                    continue

            message = bytearray(type_byte)
            for d in field_data:
                message.extend(d.to_bytes(2, "little", signed=False))

            self.__send_message(message)

    def __turn_on_arduino(self) -> None:
        # Send ON message to Arduino
        self.__send_message(bytes((0, True)))
        self.qdb_sender.row(
            "controls", columns={"on_off": True}, at=TimestampNanos.now()
        )

        # Send data to Arduino
        self.__send_data_if_needed()

    def __update_led_data(self):
        led_thread_ref = self.led_thread()
        if led_thread_ref is not None:
            breath_data = self.__sensor_data_controller.get_session_data("breaths")
            led_thread_ref.show(breath_data)
            logging.info("LEDThread show(data)")

    def __turn_off_arduino(self) -> None:
        # Send OFF message to Arduino
        self.__send_message(bytes((0, False)))
        self.qdb_sender.row(
            "controls", columns={"on_off": False}, at=TimestampNanos.now()
        )

        # Stop the LED
        led_thread_ref = self.led_thread()
        if led_thread_ref is not None:
            led_thread_ref.stop()

        # Prepare next session
        self.__sensor_data_controller.reset_data()
        self.__update_led_data()

    def __send_message(self, message: bytes) -> None:
        data = cobs.encode(message) + b"\x00"
        self.serial.write(data)

    def __get_mock_presence_state(self) -> bool:
        current_time = time.time()
        if current_time - self.__mock_presence_timer > 5:
            self.__mock_presence_timer = current_time
            return not self.__last_presence_state
        return self.__last_presence_state
