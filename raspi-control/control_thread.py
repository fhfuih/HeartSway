import logging
from threading import Thread, Event
import time
from typing import Optional

from cobs import cobs
import serial
from gpiozero import DistanceSensor
from gpiozero.pins.pigpio import PiGPIOFactory
from questdb.ingress import Sender, TimestampNanos
import requests


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

        self.__last_presence_state = False
        self.__mock_presence_timer = time.time()

        self.__distance_sensor = DistanceSensor(
            echo=27, trigger=4, pin_factory=PiGPIOFactory()
        )

        self.__sensor_data_to_send: Optional[list] = None
        self.__next_send_data_index: int = 0
        self.__next_send_data_time: float = 0
        self.__last_vibration_message = None

    def run(self) -> None:
        while not self.exit_event.is_set():
            presence_state = self.__distance_sensor.in_range

            if presence_state != self.__last_presence_state:
                # If the presense state changes
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
            elif presence_state and time.time() > (self.__next_send_data_time):
                # If someone continutes to be present, and it is time to send the next batch of data
                # But it is time to send the next batch of data
                self.__send_data()

            time.sleep(0.05)

        # Clean up
        self.__send_on_off(False)
        logging.info("Exiting ControlThread")

    def __send_on_off(self, on_off: bool) -> None:
        # Send the on/off command to the Arduino
        self.__send_message(bytes((0, on_off)))
        self.qdb_sender.row(
            "control", columns={"on_off": on_off}, at=TimestampNanos.now()
        )

    def __send_data(self) -> None:
        # If not yet done, get the data to send
        if self.__sensor_data_to_send is None:
            self.__sensor_data_to_send = self.__get_sensor_data(0)
            self.__next_send_data_index = 0

        # If still no data, do nothing. Retry getting data in 5 seconds
        if self.__sensor_data_to_send is None:
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
        self.__next_send_data_time = time.time() + 0.8 * sum(data_to_send) / 1000

        # Send the data to Arduino. Convert each number in data_to_send to 2-byte integer and concat together
        data = bytearray(b"\x02")
        for d in data_to_send:
            data.extend(d.to_bytes(2, "little", signed=True))
        self.__send_message(data)

    def __send_message(self, message: bytes) -> None:
        data = cobs.encode(message) + b"\x00"
        self.serial.write(data)

    def __get_sensor_data(self, last_person_index: int) -> Optional[list]:
        query = f"""WITH e AS (SELECT *, row_number() OVER (ORDER BY timestamp DESC) FROM control WHERE on_off = false),
s AS (SELECT * FROM control WHERE on_off = true),
r AS (SELECT e.timestamp AS et, s.timestamp AS st, FROM e ASOF JOIN s WHERE e.row_number = {last_person_index + 1})
SELECT ibi FROM sensors JOIN r ON sensor.timestamp >= r.st AND sensor.timestamp <= r.et"""
        resp = requests.get("http://localhost:9000/exec", params={"query": query})
        if not resp.ok:
            logging.error("Error getting sensor data %s", resp.text)
            return None
        resp = resp.json()
        return resp["dataset"]

    def __get_mock_presence_state(self) -> bool:
        current_time = time.time()
        if current_time - self.__mock_presence_timer > 5:
            self.__mock_presence_timer = current_time
            return not self.__last_presence_state
        return self.__last_presence_state
