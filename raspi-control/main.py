import argparse
import logging
import threading

from serial import Serial

from control_thread import ControlTread
from receive_sensor_thread import ReceiveSensorThread


logger = logging.getLogger("hammock")

logger.propagate = False

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)

file_handler = logging.FileHandler("webrtc.log")
file_handler.setLevel(logging.WARNING)
logger.addHandler(file_handler)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--verbose", "-v", action="count")
    args = parser.parse_args()

    if args.verbose:
        console_handler.setLevel(logging.DEBUG)

    # serial = Serial("/dev/ttyUSB0", 9600)

    threads = [
        ControlTread(),
        # ReceiveSensorThread(serial),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
