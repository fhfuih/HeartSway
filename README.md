Communication protocol
======

All int in little endian

Raspi to Ardunio:
* 1B: type
* (type 0: control)
    * 1B: on (1) or off (0)
* (type 1: log)
    * all the rest in UTF-8 string
* (type 2: vibration)
    * 10B: the next 10 IBI
* (type 3: air pump)
    * 10B: the next 5 inhale-exhale cycle

Ardunio to Raspi:
* 1B: type
* type 0: reserved
* type 1: log
    * all the rest in UTF-8 string
* type 2: time
    * 4B unsigned int: the result of a millis() near Arduino's start.
* type 3: sensor data
    * 4B unsigned long: millis()
    * 2B int: bpm (normally 60~100)
    * 2B int: ibi (normally 500~1100)
