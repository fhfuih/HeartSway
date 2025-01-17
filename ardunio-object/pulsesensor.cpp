#include <PulseSensorPlayground.h>

#include "pulsesensor.h"

namespace Pulse {
PulseSensorPlayground pulseSensor;

bool hasBegun = false;
unsigned long hardwareTimerNextOutput = 0;

void setup(int PULSE_INPUT, int PULSE_BLINK, int PULSE_FADE, int THRESHOLD) {
    pulseSensor.analogInput(PULSE_INPUT);
    pulseSensor.setThreshold(THRESHOLD);

    if (PULSE_BLINK) {
        pulseSensor.blinkOnPulse(PULSE_BLINK);
    }
    if (PULSE_FADE) {
        pulseSensor.fadeOnPulse(PULSE_FADE);
    }

    // Now that everything is ready, start reading the PulseSensor signal.
    hasBegun = pulseSensor.begin();
    // if (!pulseSensor.begin()) {
    //     /*
    //        PulseSensor initialization failed,
    //        likely because our particular Arduino platform interrupts
    //        aren't supported yet.

    //        If your Sketch hangs here, try PulseSensor_BPM_Alternative.ino,
    //        which doesn't use interrupts.
    //     */
    //     for (;;) {
    //         // Flash the led to show things didn't work.
    //         digitalWrite(PULSE_BLINK, LOW);
    //         delay(50);
    //         Serial.println('!');
    //         digitalWrite(PULSE_BLINK, HIGH);
    //         delay(50);
    //     }
    // }
}

/// @brief Non-blocking function to read the PulseSensor data.
/// @return A tuple containing the BPM, IBI, and amplitude of the pulse. All of
/// them are 0 if data is not available.
void loop(unsigned int& ts, int& bpm, int& ibi) {
    if (!hasBegun || pulseSensor.isPaused()) {
        ts = 0;
        bpm = 0;
        ibi = 0;
        return;
    }

    // /*
    //   See if a sample is ready from the PulseSensor.

    //   If USE_HARDWARE_TIMER is true, the PulseSensor Playground
    //   will automatically read and process samples from
    //   the PulseSensor.

    //   If USE_HARDWARE_TIMER is false, the call to sawNewSample()
    //   will check to see how much time has passed, then read
    //   and process a sample (analog voltage) from the PulseSensor.
    //   Call this function often to maintain 500Hz sample rate,
    //   that is every 2 milliseconds. Best not to have any delay()
    //   functions in the loop when using a software timer.

    //   Check the compatibility of your hardware at this link
    //   <url>
    //   and delete the unused code portions in your saved copy, if you like.
    // */
    // if (pulseSensor.UsingHardwareTimer) {
    //     /*
    //        Write the latest sample to Serial every 20 millis.
    //        We don't output every sample, because our baud rate
    //        won't support that much I/O.
    //        None-blocking version of
    //         // delay(20);
    //         // pulseSensor.outputSample();
    //     */
    //     const unsigned long currentTime = millis();
    //     if ((long)(hardwareTimerNextOutput - currentTime) > 0L) {
    //         // not time yet.
    //         return {0, 0, 0};
    //     } else {
    //         // time to output
    //         hardwareTimerNextOutput = currentTime + 20;
    //         pulseSensor.outputSample();
    //     }
    // } else {
    //     /*
    //         When using a software timer, we have to check to see if it is
    //         time to acquire another sample. A call to sawNewSample will do
    //         that.
    //     */
    //     if (pulseSensor.sawNewSample()) {
    //         /*
    //             Every so often, send the latest Sample.
    //             We don't print every sample, because our baud rate
    //             won't support that much I/O.
    //         */
    //         if (--pulseSensor.samplesUntilReport == (byte)0) {
    //             pulseSensor.samplesUntilReport = SAMPLES_PER_SERIAL_SAMPLE;
    //             pulseSensor.outputSample();
    //         }
    //     }
    // }
    /*
       If a beat has happened since we last checked,
       write the per-beat information to Serial.
     */
    if (pulseSensor.sawStartOfBeat()) {
        ts = millis();
        bpm = pulseSensor.getBeatsPerMinute();
        ibi = pulseSensor.getInterBeatIntervalMs();
    }
}
void stop() {
    pulseSensor.pause();
}
void resume() {
    pulseSensor.resume();
}
}  // namespace Pulse