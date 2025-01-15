import logging
from threading import Event, Thread
import time
import board
import neopixel

import utils

PIXEL_PIN = board.D18
NUM_PIXELS = 60
ORDER = neopixel.GRB


class LEDThread(Thread):
    def __init__(
        self,
        exit_event: Event,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.exit_event = exit_event
        self._data = None
        self._data_index = 0
        self._item_progress = 0

    def show(self, data):
        """Assume data is a list of integers describing the in/out/in/out breathing pattern in ms"""
        self._data = data
        self._data_index = 0
        self._item_progress = 0

        # Ensure that the data length is even (in, out, in, out)
        if len(self._data) % 2 != 0:
            self._data.append(data[-1])

    def stop(self):
        self._data = None
        self._data_index = 0
        self._item_progress = 0

    def run(self) -> None:
        # Set up
        pixels = neopixel.NeoPixel(
            PIXEL_PIN, NUM_PIXELS, brightness=0.2, auto_write=False, pixel_order=ORDER
        )
        pixels.fill((255, 239, 196))  # light yellow
        pixels.brightness = 0

        # Loop
        while not self.exit_event.is_set():
            if self._data:
                item = self._data[self._data_index]
                is_reversed = self._data_index % 2 == 1
                anim_progress = self._item_progress / item
                if is_reversed:
                    anim_progress = 1 - anim_progress
                anim_value = utils.easeInOutQuad(anim_progress)

                # Assume 1ms per loop/progress.
                # If changing the progress step, please adjust the sleep time accordingly.
                self._item_progress += 1
                if self._item_progress > item:
                    self._item_progress = 0
                    self._data_index += 1
                    if self._data_index >= len(self._data):
                        self._data_index = 0
                        self._item_progress = 0

                pixels.brightness = anim_value * 0.8
                pixels.show()

            time.sleep(0.001)

        # Clean up: turn off LED
        pixels.deinit()
        logging.info("Exiting LEDThread")
