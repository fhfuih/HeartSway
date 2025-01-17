#include <Arduino.h>

#include "vibration.h"

namespace Vibration {

const int VIBRATION_DURATION = 100;

int PIN = 0;
int BLINK = 0;
bool isOn = false;
unsigned long nextVibrationStart = 0;
unsigned long nextVibrationEnd = 0;

void setup(int PIN, int BLINK) {
    Vibration::PIN = PIN;
    Vibration::BLINK = BLINK;
    pinMode(PIN, OUTPUT);
}

void loop(const unsigned long currentTime) {
    if (!isOn)
        return;

    if (currentTime >= nextVibrationEnd) {
        isOn = false;
        analogWrite(PIN, 0);
        if (BLINK) {
            digitalWrite(BLINK, LOW);
        }
    } else if (currentTime >= nextVibrationStart) {
        analogWrite(PIN, 255);
        if (BLINK) {
            digitalWrite(BLINK, HIGH);
        }
    }
}

void setVibration(unsigned long nextStart) {
    nextVibrationStart = nextStart;
    nextVibrationEnd = nextStart + VIBRATION_DURATION;
}

void stop() {
    isOn = false;
    analogWrite(PIN, 0);
}

void resume() {
    isOn = true;
}
}  // namespace Vibration