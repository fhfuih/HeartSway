Communication protocol
======

All int in little endian

Raspi to Ardunio:
* 1B: type
* type 0: control (e.g., from distance sensor)
    * 1B: on (1) or off (0)
* type 1: log
    * all the rest in UTF-8 string
* type 2: IBI
    * 2B*5 unsigned int: ibi (normally 500~1100) in ms
    * typically 10 numbers/20B in total, but expect exceptions
* type 3: inhale-exhale cycle
    * 2B*5: the next 5 inhale-exhale cycle
    * in the order of in, out, in, out... normally 3000~6000 ms
    * typically 10 numbers/20B in total, but expect exceptions

Ardunio to Raspi:
* 1B: type
* type 0: control (e.g., from capacitive sensor)
    * 1B: on (1) or off (0)
* type 1: log
    * all the rest in UTF-8 string
* type 2: time
    * 4B unsigned int: the result of a millis() near Arduino's start.
* type 3: pulse sensor data
    * 4B unsigned long: millis()
    * 2B unsigned int: bpm (normally 60~100)
    * 2B unsigned int: ibi (normally 500~1100) in ms
* type 4: stretch sensor data
    * 4B unsigned long: millis()
    * 4B float: stretchable cord resistence
