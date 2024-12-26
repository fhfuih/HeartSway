import argparse
import logging
import threading

from serial import Serial
from questdb.ingress import Sender

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
    qdb_sender = Sender.from_conf("http::addr=127.0.0.1:9000;")
    qdb_sender.establish()

    exit_event = threading.Event()
    threads: list[threading.Thread] = [
        ControlTread(serial, exit_event),
        ReceiveMessageThread(serial, qdb_sender, exit_event),
    ]
    for t in threads:
        t.start()
    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt. Exiting...")
        exit_event.set()
        for t in threads:
            t.join()
        qdb_sender.close(flush=True)
        logging.info("QuestDB sender closed")
        serial.flush()
        serial.close()
        logging.info("Serial closed")
