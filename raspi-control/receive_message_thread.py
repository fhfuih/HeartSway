import logging
import traceback
from threading import Thread, Event
import time
from typing import Optional
import struct

import serial
from cobs import cobs
from questdb.ingress import Sender, TimestampNanos

import utils

USE_ARDUINO_TIMESTAMP = False


class ReceiveMessageThread(Thread):
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
        self.serial_buffer = bytearray()

        self.arduino_start_ns: Optional[int] = None

    def run(self) -> None:
        while not self.exit_event.is_set():
            # Read all available bytes
            while self.serial.in_waiting:
                byte = self.serial.read()
                if byte == b"\x00":
                    if self.serial_buffer:
                        try:
                            data = cobs.decode(self.serial_buffer)
                            if len(data) > 0:
                                self.__on_message(data)
                        except cobs.DecodeError as e:
                            logging.error(f"Error decoding message: {e}")
                            logging.error(traceback.format_exc())
                        except Exception as e:
                            logging.error(f"Error processing message: {e}")
                            logging.error(traceback.format_exc())
                    self.serial_buffer.clear()
                else:
                    self.serial_buffer.extend(byte)

            time.sleep(0.05)

        # Clean up
        logging.info("Exiting ReceiveMessageThread")

    def __on_message(self, data: bytes) -> None:
        msg_type = data[0]
        msg_content = data[1:]
        match msg_type:
            case 2:  # A millis() call from Ardunio at start
                now = time.time_ns()
                if (millis_len := len(msg_content)) != 4:
                    logging.warning(
                        f"Invalid millis() call from Arduino. Expected 4B but got {millis_len}B"
                    )
                millis = int.from_bytes(msg_content[:4], "little", signed=False)
                self.arduino_start_ns = now - millis * 1_000_000
                logging.info(
                    f"Received Arduino millis {millis} at {now}. Set Arduino start time to {time.ctime(self.arduino_start_ns // 1e9)}"
                )
            case 1:  # Arduino logs something
                msg = msg_content.decode("utf-8", errors="replace")
                match msg[0]:
                    case ".":
                        level = logging.INFO
                    case "?":
                        level = logging.WARNING
                    case "!":
                        level = logging.ERROR
                    case _:
                        level = logging.DEBUG
                logging.log(level, f"Arduino: {msg}")
            case 3:  # A normal pulse sensor data call
                millis = int.from_bytes(msg_content[:4], "little", signed=False)
                bpm = int.from_bytes(msg_content[4:6], "little", signed=False)
                ibi = int.from_bytes(msg_content[6:8], "little", signed=False)
                data_ns = self.__get_arduino_timestamp(millis)
                logging.debug(f"Received HR@{data_ns}: BPM={bpm}, IBI={ibi}")
                self.qdb_sender.row(
                    "sensors", columns={"bpm": bpm, "ibi": ibi}, at=data_ns
                )
            case 4:  # A stretch sensor data call
                millis = int.from_bytes(msg_content[:4], "little", signed=False)
                data_ns = self.__get_arduino_timestamp(millis)
                stretch = struct.unpack("f", msg_content[4:8])
                logging.debug(f"Received stretch@{data_ns}: {stretch}")
                self.qdb_sender.row("stretch", columns={"primary": stretch}, at=data_ns)

    def __get_arduino_timestamp(self, millis: Optional[int]) -> TimestampNanos:
        if not USE_ARDUINO_TIMESTAMP or self.arduino_start_ns is None or millis is None:
            return TimestampNanos.now()
        return TimestampNanos(self.arduino_start_ns + millis * 1_000_000)
