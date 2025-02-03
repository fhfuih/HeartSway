/* This file only runs on the board where int is 2 bytes, like Uno.
 * https://docs.arduino.cc/language-reference/en/variables/data-types/int/
 */

#include <Adafruit_MPR121.h>
#include <Arduino.h>
#include <PacketSerial.h>
#include <PulseSensorPlayground.h>
#include <limits.h>
#include <string.h>

PacketSerial myPacketSerial;

bool inRange = false; // If using distance sensor --- attached to Pi and transmitted to Arduino
bool isTouching = false; // Is using capacitative sensor --- attached to Arduino

// Controlling PulseSensor
PulseSensorPlayground pulseSensor;
const int PULSE_INPUT_PIN = A0;
const int PULSE_BLINK_PIN = 0;
const int PULSE_FADE_PIN = 0;
const int PULSE_THRESHOLD = 550;

// Controlling stretch sensor
const int STRETCH_1 = A1;
const int STRETCH_RESISTOR = 1E4;
int next_read_stretch_time = 0;

// Controlling Vibration
const int VIBRATION_PIN = 3;
const int VIBRATION_BLINK_PIN = LED_BUILTIN;
const int VIBRATION_DURATION = 100;
const int VIBRATION_STRENGTH = 100;
unsigned long nextVibrationEnd = ULONG_MAX;

// Controlling capasitive sensor
// Adafruit_MPR121 cap = Adafruit_MPR121();
// const uint8_t capPin = 0;
// uint16_t lasttouched = 0;
// uint16_t currtouched = 0;
// #ifndef _BV
// #define _BV(bit) (1 << (bit))
// #endif

// Reading IBI data
uint16_t ibi_list[30] = { 0 };
constexpr auto ibi_list_size = sizeof(ibi_list);
constexpr auto ibi_list_len = ibi_list_size / sizeof(ibi_list[0]);
int ibi_list_write_i = 0;
int ibi_list_read_i = 0;
unsigned long ibi_next_read_millis = 0;

void onPacketReceived(const byte* buffer, size_t size);
void sendControl(bool on);
void sendTimestamp(unsigned long now = millis());
void exitSession();
void startSession();
void log(String msg);

void setup() {
    myPacketSerial.begin(9600);
    myPacketSerial.setPacketHandler(&onPacketReceived);

    // Send a starting timestamp so that raspi can align relative ts with
    // absolute ts Convert `now` (4 bytes) to a byte array
    sendTimestamp();

    // Set up capasitive sensor
    // Default (not connected) ADDR is 0x5A, if tied to 3.3V its 0x5B
    // If tied to SDA its 0x5C and if SCL then 0x5D
    // if (!cap.begin(0x5A)) {
    //     log("!MPR121CapSenseNotFound");
    // }

    // Set up pulse sensor
    pulseSensor.analogInput(PULSE_INPUT_PIN);
    pulseSensor.setThreshold(PULSE_THRESHOLD);
    if (PULSE_BLINK_PIN) {
        pulseSensor.blinkOnPulse(PULSE_BLINK_PIN);
    }
    if (PULSE_FADE_PIN) {
        pulseSensor.fadeOnPulse(PULSE_FADE_PIN);
    }
    const bool hasBegun = pulseSensor.begin();
    if (!hasBegun) {
        log("!PulseSensorBeginFailed");
    }

    // Stop all components
    exitSession();

    log(".SetupDone");
}

void loop() {
    auto now = millis();

    // Loop capasitive sensor: if it WAS touched and now ISN'T, alert!
    // currtouched = cap.touched();
    // if ((currtouched & _BV(capPin)) && !(lasttouched & _BV(capPin))) {
    //     sendControl(true);
    //     isTouching = true;
    // }
    // if (!(currtouched & _BV(capPin)) && (lasttouched & _BV(capPin))) {
    //     sendControl(false);
    //     isTouching = false;
    // }
    // lasttouched = currtouched;

    // Loop PulseSensors
    uint16_t bpm = 0;
    uint16_t ibi = 0;
    if (pulseSensor.sawStartOfBeat()) {
        bpm = pulseSensor.getBeatsPerMinute();
        ibi = pulseSensor.getInterBeatIntervalMs();
    }

    // Send sensor data to raspi
    if (bpm != 0 || ibi != 0) {
        int buffer_length = 1 + // message type
            4 + // pulse_ts
            2 + // bpm
            2; // ibi
        byte buffer[buffer_length];
        buffer[0] = 3;
        memcpy(buffer + 1, &now, 4);
        memcpy(buffer + 5, &bpm, 2);
        memcpy(buffer + 7, &ibi, 2);
        myPacketSerial.send(buffer, buffer_length);
    }

    if (inRange) {
        /* Consume incoming data if needed */
        if (now > ibi_next_read_millis) {
            auto ibi = ibi_list[ibi_list_read_i];
            // If ibi is 0, chances are that the entire list is short (<= 10)
            // We go back to the beginning and read again.
            // If the beginning is also 0, it means there is no data.
            // Then we do nothing and the next loop will attempt to read again
            if (ibi != 0) {
                // Regular read
                ibi_next_read_millis = now + ibi; // ibi unit is also ms
                ibi_list_read_i = (ibi_list_read_i + 1) % ibi_list_len;
            } else if (ibi_list_read_i != 0) {
                // ibi data is 0 at non-beginning position
                ibi = ibi_list[0];
                ibi_list_read_i = 1;
                ibi_next_read_millis = now + ibi;
            }

            // If now ibi is still 0, then the list begins with 0
            // Ask next loop to read from start again
            if (ibi == 0) {
                ibi_list_read_i = 0;
                ibi_next_read_millis = now;
            } else {
                /* Consume one IBI value: start vibration now */
                analogWrite(VIBRATION_PIN, VIBRATION_STRENGTH);
                if (VIBRATION_BLINK_PIN) {
                    digitalWrite(VIBRATION_BLINK_PIN, HIGH);
                }
                nextVibrationEnd = now + VIBRATION_DURATION;
                auto logString = "ReadIbi" + String(ibi) + "at" + String(now) + "endAt" + String(nextVibrationEnd);
                log(logString);
            }
        }

        /* Turn off vibration if needed */
        if (now > nextVibrationEnd) {
            log("VibrationOff");
            analogWrite(VIBRATION_PIN, 0);
            if (VIBRATION_BLINK_PIN) {
                digitalWrite(VIBRATION_BLINK_PIN, LOW);
            }
            nextVibrationEnd = ULONG_MAX;
        }

        /* Loop stretch sensor and send to raspi */
        if (now >= next_read_stretch_time) {
            float reading = analogRead(STRETCH_1); // 10-bit, 0~1023 for Uno
            reading = (1023 / reading) - 1; // 0 ~ inf
            reading = STRETCH_RESISTOR / reading; // 0 ~ inf
            next_read_stretch_time += 1000;

            int buffer_length = 1 + 4 + 4;
            byte buffer[buffer_length];
            buffer[0] = 4;
            memcpy(buffer + 1, &now, 4);
            memcpy(buffer + 5, &reading, 4);
            myPacketSerial.send(buffer, buffer_length);
        }
    }

    myPacketSerial.update();
}

void onPacketReceived(const byte* buffer, size_t size) {
    // If empty data, do nothing
    if (size == 0) {
        log("?EmptyMsg");
        return;
    }
    switch (buffer[0]) {
    case 0:
        /* control on/off */
        if (size != 2) {
            log("?MsgSize" + String(size) + "Bwant2B");
        } else if (buffer[1] == 0) {
            inRange = false;
            exitSession();
            ibi_list_read_i = 0;
            ibi_list_write_i = 0;
            memset(ibi_list, 0, ibi_list_size);
            log(".ControlOff");
        } else if (buffer[1] == 1) {
            inRange = true;
            startSession();
            log(".ControlOn");
        } else {
            log("?Control" + String(buffer[1]));
        }
        break;
    case 1:
        /* raspi's log. Should not use. Ignore. */
        break;
    case 2:
        /* IBI */
        {
            if (size < 3) {
                log("?IBIarrSize" + String(size) + "Bwant>=3B");
                break;
            }
            String logString = ".IBIarrLen" + (size - 1) / 2;
            for (int i = 1; i < size; i += 2) {
                uint16_t ibi = buffer[i + 1] << 8 | buffer[i];
                ibi_list[ibi_list_write_i] = ibi;
                ibi_list_write_i = (ibi_list_write_i + 1) % ibi_list_len;
                //                 logString += String(ibi) + ",";
            }
            log(logString);
        }
        break;
    case 3:
        /* inhale-exhale cycle */
        break;
    default:
        log("?MsgType" + String(buffer[0]));
        break;
    }
}

void sendControl(bool on) {
    byte buffer[2] = { 0, on ? 1 : 0 };
    myPacketSerial.send(buffer, 2);
}

void sendTimestamp(unsigned long now = millis()) {
    byte buffer[5];
    buffer[0] = 2;
    memcpy(buffer + 1, &now, 4);
    myPacketSerial.send(buffer, 5);
}

void exitSession() {
    pulseSensor.pause();
    analogWrite(VIBRATION_PIN, 0);
}

void startSession() {
    pulseSensor.resume();
}

void log(String msg) {
    auto msg_length = msg.length();
    byte buffer[msg_length + 2]; // 1 byte for the message type, 1 byte for
                                 // the null terminator
    buffer[0] = 1;
    msg.getBytes(buffer + 1, msg_length + 1);
    buffer[msg_length + 1] = '\0';
    myPacketSerial.send(buffer, msg_length + 2);
}
