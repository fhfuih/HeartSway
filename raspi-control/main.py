import argparse
import logging
import threading

from serial import Serial

from control_thread import ControlTread
from receive_message_thread import ReceiveMessageThread

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

file_handler = logging.FileHandler("hammock.log")
file_handler.setLevel(logging.WARNING)

logging.basicConfig(
    handlers=[
        console_handler,
        file_handler,
    ],
    level=logging.DEBUG,
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--verbose", "-v", action="count")
    args = parser.parse_args()

    if args.verbose:
        console_handler.setLevel(logging.DEBUG)

    serial = Serial("/dev/ttyUSB0", 9600)

    threads = [
        ControlTread(serial),
        ReceiveMessageThread(serial),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
