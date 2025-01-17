#include <Arduino.h>

#include "vibration.h"

namespace Vibration {

const int VIBRATION_DURATION = 2000;

int PIN = 0;
int BLINK = 0;
bool isOn = false;
unsigned long nextVibrationEnd = 0;

void setup(int PIN, int BLINK) {
    Vibration::PIN = PIN;
    Vibration::BLINK = BLINK;
//    pinMode(PIN, OUTPUT);
}

void loop(const unsigned long now) {
    if (!isOn)
        return;

    if (now >= nextVibrationEnd) {
        analogWrite(PIN, 0);
        if (BLINK) {
            digitalWrite(BLINK, LOW);
        }
    }
}

void setVibration(unsigned long now) {
    analogWrite(PIN, 200);
    if (BLINK) {
        digitalWrite(BLINK, HIGH);
    }
    nextVibrationEnd = now + VIBRATION_DURATION;
}

void stop() {
    isOn = false;
    analogWrite(PIN, 0);
}

void resume() {
    isOn = true;
}
}  // namespace Vibration
