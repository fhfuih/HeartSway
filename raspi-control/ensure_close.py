from cobs import cobs
from serial import Serial


if __name__ == "__main__":
    data = cobs.encode(bytes((0, False))) + b"\x00"
    with Serial("/dev/ttyUSB0", 9600) as serial:
        serial.write(data)
