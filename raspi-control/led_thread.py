import logging
import time
from threading import Event, Thread

import board
import neopixel
import utils

PIXEL_PIN = board.D18
NUM_PIXELS = 60
ORDER = neopixel.GRB
LED_REFRESH_RATE = 0.01


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
            PIXEL_PIN,  # type: ignore
            NUM_PIXELS,
            brightness=0,
            auto_write=True,
            pixel_order=ORDER,
        )
        pixels.fill((100, 100, 100))
        logging.debug("Setting up LEDThread")

        # Loop
        while not self.exit_event.is_set():
            if self._data is not None and len(self._data) > 0:
                item = self._data[self._data_index]
                is_reversed = self._data_index % 2 == 1
                anim_progress = self._item_progress / item
                if is_reversed:
                    anim_progress = 1 - anim_progress
                anim_value = utils.easeInOutQuad(anim_progress)

                self._item_progress += LED_REFRESH_RATE * 1000
                if self._item_progress > item:
                    self._item_progress = 0
                    self._data_index += 1
                    if self._data_index >= len(self._data):
                        self._data_index = 0
                        self._item_progress = 0

                pixels.brightness = anim_value * 0.8

            time.sleep(LED_REFRESH_RATE)

        # Clean up: turn off LED
        pixels.deinit()
        logging.info("Exiting LEDThread")
