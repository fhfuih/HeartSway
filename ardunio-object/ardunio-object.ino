/* This file only runs on the board where int is 2 bytes, like Uno.
 * https://docs.arduino.cc/language-reference/en/variables/data-types/int/
 */

#include <Arduino.h>
#include <PacketSerial.h>
#include <PulseSensorPlayground.h>
#include <string.h>

#include "pulsesensor.h"

PacketSerial myPacketSerial;

uint16_t ibi_list[30] = {0};
int ibi_list_write_i = 0;
int ibi_list_read_i = 0;
unsigned long ibi_next_read_millis = 0;

void setup() {
    myPacketSerial.begin(9600);
    myPacketSerial.setPacketHandler(&onPacketReceived);

    // Send a starting timestamp so that raspi can align relative ts with
    // absolute ts Convert `now` (4 bytes) to a byte array
    sendTimestamp();

    // Set up components
    Pulse::setup(A0, LED_BUILTIN, 5, 550);
    Pulse::stop();
}

void loop() {
    // Read sensor data
    unsigned int pulse_ts = 0;
    int bpm_i = 0, ibi_i = 0;
    Pulse::loop(pulse_ts, bpm_i, ibi_i);
    uint16_t bpm = bpm_i;
    uint16_t ibi = ibi_i;

    // Send sensor data to raspi
    if (pulse_ts != 0 || bpm != 0 || ibi != 0) {
        int buffer_length = 1 +  // message type
                            4 +  // pulse_ts
                            2 +  // bpm
                            2;   // ibi
        byte buffer[buffer_length];
        buffer[0] = 3;
        memcpy(buffer + 1, &pulse_ts, 4);
        memcpy(buffer + 5, &bpm, 2);
        memcpy(buffer + 7, &ibi, 2);
        myPacketSerial.send(buffer, buffer_length);
    }

    // Consume incoming data if needed
    auto now = millis();
    // Initially, ibi_next_read_millis is 0, so will read immediately
    if (now > ibi_next_read_millis) {
        auto ibi = ibi_list[ibi_list_read_i];
        // If ibi is 0, it is time to read but there is no data
        // Do nothing and the next loop will attempt to read again
        if (ibi != 0) {
            ibi_next_read_millis = now + ibi;  // ibi unit is also ms
            ibi_list_read_i = (ibi_list_read_i + 1) % sizeof(ibi_list);
            log("ReadIbi" + String(ibi) + "at" + String(now));
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
                Pulse::stop();
                log("Control off");
            } else if (buffer[1] == 1) {
                Pulse::resume();
                log("Control on");
            } else {
                log("?Control" + String(buffer[1]));
            }
            break;
        case 1:
            /* raspi's log. Should not use. Ignore. */
            break;
        case 2:
            /* IBI */
            if (size < 3) {
                log("?IBIarrSize" + String(size) + "Bwant>=3B");
                break;
            }
            String logString = "IBIarr:";
            for (int i = 1; i < size; i += 2) {
                uint16_t ibi = buffer[i] << 8 | buffer[i + 1];
                ibi_list[ibi_list_write_i] = ibi;
                ibi_list_write_i = (ibi_list_write_i + 1) % sizeof(ibi_list);
                logString += String(ibi) + ",";
            }
            log(logString);
            break;
        case 3:
            /* inhale-exhale cycle */
            break;
        default:
            log("?MsgType" + String(buffer[0]));
            break;
    }
}

void sendTimestamp() {
    unsigned long now = millis();
    byte now_bytes[5];
    now_bytes[0] = 2;
    memcpy(now_bytes + 1, &now, 4);
    myPacketSerial.send(now_bytes, 5);
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
