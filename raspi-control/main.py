import argparse
import logging
import threading
from typing import cast

from serial import Serial
from questdb.ingress import Sender

from control_thread import ControlTread
from led_thread import LEDThread
from receive_message_thread import ReceiveMessageThread
import utils

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

for logger_name in "requests.packages.urllib3", "requests", "urllib3":
    requests_log = logging.getLogger(logger_name)
    requests_log.setLevel(logging.WARNING)
    requests_log.propagate = False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--verbose", "-v", action="count")
    args = parser.parse_args()

    if args.verbose:
        console_handler.setLevel(logging.DEBUG)

    logging.info(
        "Starting Hammock " + "with" if utils.WITH_SENSORS else "without" + "Arduino"
    )

    serial = Serial("/dev/ttyUSB0", 9600)
    qdb_sender = Sender.from_conf("http::addr=127.0.0.1:9000;")
    qdb_sender.establish()

    exit_event = threading.Event()
    threads: list[threading.Thread] = [
        LEDThread(exit_event),
        ReceiveMessageThread(serial, qdb_sender, exit_event),
    ]
    threads.append(
        ControlTread(serial, qdb_sender, cast(LEDThread, threads[0]), exit_event)
    )

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
