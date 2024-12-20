from threading import Thread
import time


class ControlTread(Thread):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.__last_presence_state = False
        self.__mock_presence_timer = time.time()

        self.__last_vibration_message = None

    def run(self) -> None:
        while True:
            # Task 1: Read presence state
            current_presence_state = self.__get_mock_presence_state()
            if current_presence_state != self.__last_presence_state:
                self.__last_presence_state = current_presence_state
                print(f"Presence state changed to {current_presence_state}")

            time.sleep(0.05)

    def __get_mock_presence_state(self) -> bool:
        current_time = time.time()
        if current_time - self.__mock_presence_timer > 5:
            self.__mock_presence_timer = current_time
            return not self.__last_presence_state
        return self.__last_presence_state
