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
import requests

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

        self.__reset_states()

    def run(self) -> None:
        self.__prepare_next_session()

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
                    pass
                else:
                    logging.info("Someone is leaving")

                    # Turn off the sensors on Arduino
                    self.__send_off()
                    self.__prepare_next_session()
            elif presence_state and time.time() > (self.__next_send_data_time):
                # If someone continutes to be present, and it is time to send the next batch of data
                # But it is time to send the next batch of data
                self.__send_data()

            time.sleep(0.05)

        # Clean up
        self.__send_off()
        logging.info("Exiting ControlThread")

    def __reset_states(self) -> None:
        self.__sensor_data_to_send: Optional[list] = None
        self.__next_send_data_index: int = 0
        self.__next_send_data_time: float = 0
        self.__last_vibration_message = None

    def __prepare_next_session(self) -> None:
        self.__sensor_data_to_send = self.__get_last_session_data()
        self.__next_send_data_index: int = 0
        self.__next_send_data_time: float = 0
        logging.debug("Session data to serve is %s", self.__sensor_data_to_send)

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

    def __get_last_session_data(self) -> Optional[list]:
        session_index = 0
        session_data = None
        total_session_count = self.__get_total_session_count() or 1
        logging.info("Total session count is %s", total_session_count)

        while session_index < total_session_count:
            session_data = self.__get_sensor_data(session_index)
            if session_data is None or len(session_data) == 0:
                # Errorneous data None or empty data
                logging.debug("No data for session %s", session_index)
                session_index += 1
            else:
                # Reaching good data. Stop searching
                break

        if session_data is None or len(session_data) == 0:
            return None
        return session_data

    def __send_data(self) -> None:
        # Data should have been prepared already. But if no, retry preparing data
        if self.__sensor_data_to_send is None:
            self.__prepare_next_session()

        # If still no data, do nothing. Retry getting data in 5 seconds
        if self.__sensor_data_to_send is None:
            logging.warning("No data to send. Retry sending data in 5 seconds.")
            self.__next_send_data_time = time.time() + 5
            return

        paginate = 10
        total_data_len = len(self.__sensor_data_to_send)

        if total_data_len < 10:
            # If data length is less than 10, double it and send all
            data_to_send = self.__sensor_data_to_send + self.__sensor_data_to_send
            self.__next_send_data_index = 0
        else:
            # Otherwise, paginate the data in 10 points each.
            from_i = self.__next_send_data_index
            to_i = from_i + paginate
            data_to_send = self.__sensor_data_to_send[from_i:to_i]
            self.__next_send_data_index = 0 if to_i == total_data_len else to_i

            # If less than 10 left, rotate back to the first data
            if (so_far_data_len := len(data_to_send)) < paginate:
                data_to_send.extend(
                    self.__sensor_data_to_send[: paginate - so_far_data_len]
                )
                self.__next_send_data_index = paginate - so_far_data_len

        # Schedule the next time to send data: 80% of all IBI (millisecond) to send summed
        logging.debug("Data to send is %s", data_to_send)
        self.__next_send_data_time = time.time() + 0.8 * sum(data_to_send) / 1000

        # Send the data to Arduino. Convert each number in data_to_send to 2-byte integer and concat together
        data = bytearray(b"\x02")
        for d in data_to_send:
            data.extend(d.to_bytes(2, "little", signed=False))
        self.__send_message(data)

    def __send_message(self, message: bytes) -> None:
        data = cobs.encode(message) + b"\x00"
        self.serial.write(data)

    def __get_sensor_data(self, last_person_index: int) -> Optional[list]:
        query = f"""WITH e AS (SELECT *, row_number() OVER (ORDER BY timestamp DESC) FROM controls WHERE on_off = false),
s AS (SELECT * FROM controls WHERE on_off = true),
r AS (SELECT e.timestamp AS et, s.timestamp AS st, FROM e ASOF JOIN s WHERE e.row_number = {last_person_index + 1})
SELECT ibi FROM sensors ss JOIN r ON ss.timestamp >= r.st AND ss.timestamp <= r.et"""
        resp = requests.get("http://localhost:9000/exec", params={"query": query})
        if not resp.ok:
            logging.error("Error getting sensor data %s", resp.text)
            return None
        resp = resp.json()
        return [x for x2d in resp["dataset"] for x in x2d]  # flatten

    def __get_total_session_count(self) -> Optional[int]:
        query = "SELECT COUNT(*) from controls where on_off=false"
        resp = requests.get("http://localhost:9000/exec", params={"query": query})
        if not resp.ok:
            logging.error("Error getting total session count %s", resp.text)
            return None
        resp = resp.json()
        return resp["dataset"][0][0]

    def __get_mock_presence_state(self) -> bool:
        current_time = time.time()
        if current_time - self.__mock_presence_timer > 5:
            self.__mock_presence_timer = current_time
            return not self.__last_presence_state
        return self.__last_presence_state
