import logging
import traceback
from threading import Thread
import time
from typing import Optional, cast

import serial
from questdb.ingress import Sender, TimestampNanos

logger = logging.getLogger("hammock")


class ReceiveSensorThread(Thread):
    def __init__(self, serial: serial.Serial, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.serial = serial
        self.arduino_start_ns: Optional[int] = None

    def run(self) -> None:
        self.sender = Sender.from_conf("http::addr=127.0.0.1:9000;")
        while True:
            if self.serial.in_waiting:
                data = self.serial.readline().decode("utf-8").strip().split(",")
                self.__on_message(data)

            time.sleep(0.05)

    def __on_message(self, data: list[str]) -> None:
        if len(data) == 1:
            # A millis() call from Ardunio at start
            now = time.time_ns()
            millis = int(data[0])
            self.arduino_start_ns = now - millis * 1_000_000
            return

        # A normal sensor data call
        millis, bpm, ibi = [int(x) if x else None for x in data]
        data_ns = self.__get_arduino_timestamp(millis)
        logger.debug(f"Received message@{data_ns}: BPM={bpm}, IBI={ibi}")
        self.sender.row("sensors", columns={"bpm": bpm, "ibi": ibi}, at=data_ns)

    def __get_arduino_timestamp(self, millis: Optional[int]) -> TimestampNanos:
        if self.arduino_start_ns is None or millis is None:
            return TimestampNanos.now()
        return TimestampNanos(self.arduino_start_ns + millis * 1_000_000)
