#ifndef PULSESENSOR_H
#define PULSESENSOR_H

namespace Pulse {
void setup(int PULSE_INPUT, int PULSE_BLINK, int PULSE_FADE, int THRESHOLD);
void loop(unsigned int& ts, int& bpm, int& ibi);
void stop();
void resume();
}  // namespace Pulse

#endif