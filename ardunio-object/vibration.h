#ifndef VIBRATION_H
#define VIBRATION_H

namespace Vibration {
void setup(int PIN, int BLINK);
void loop(const unsigned long currentTime);
void stop();
void resume();
void setVibration(unsigned long nextStart);
}  // namespace Vibration

#endif