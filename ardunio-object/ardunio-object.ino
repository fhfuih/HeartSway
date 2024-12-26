/* This file only runs on the board where int is 2 bytes, like Uno.
 * https://docs.arduino.cc/language-reference/en/variables/data-types/int/
 */

#include <Arduino.h>
#include <PacketSerial.h>
#include <PulseSensorPlayground.h>
#include <string.h>

#include "pulsesensor.h"

PacketSerial myPacketSerial;

void setup() {
    myPacketSerial.begin(9600);
    myPacketSerial.setPacketHandler(&onPacketReceived);

    // Send a starting timestamp so that raspi can align relative ts with
    // absolute ts Convert `now` (4 bytes) to a byte array
    unsigned long now = millis();
    byte now_bytes[4];
    memcpy(now_bytes, &now, 4);
    myPacketSerial.send(now_bytes, 4);

    // Set up components
    Pulse::setup(A0, LED_BUILTIN, 5, 550);
    Pulse::stop();
}

void loop() {
    unsigned int pulse_ts = 0;
    int bpm = 0, ibi = 0;
    Pulse::loop(pulse_ts, bpm, ibi);

    // Send sensor data to raspi
    if (pulse_ts != 0 || bpm != 0 || ibi != 0) {
        int buffer_length = 1 +  // message type
                            4 +  // pulse_ts
                            2 +  // bpm
                            2;   // ibi
        byte buffer[buffer_length];
        buffer[0] = 2;
        memcpy(buffer + 1, &pulse_ts, 4);
        memcpy(buffer + 5, &bpm, 2);
        memcpy(buffer + 7, &ibi, 2);
        myPacketSerial.send(buffer, buffer_length);
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
                Pulse::stop();
            } else if (buffer[1] == 1) {
                Pulse::resume();
            } else {
                log("?Control" + String(buffer[1]));
            }
            break;
        case 1:
            /* raspi's log. Should not use. Ignore. */
            break;
        case 2:
            /* vibration */
            break;
        case 3:
            /* air pump */
            break;
        default:
            log("?MsgType" + String(buffer[0]));
            break;
    }
}

void log(String msg) {
    auto msg_length = msg.length();
    byte buffer[msg_length + 2];  // 1 byte for the message type, 1 byte for
                                  // the null terminator
    buffer[0] = 1;
    msg.getBytes(buffer + 1, msg_length + 1);
    buffer[msg_length + 1] = '\0';
    myPacketSerial.send(buffer, msg_length + 2);
}
