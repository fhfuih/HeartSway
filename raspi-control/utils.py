import time
from typing import NamedTuple, Union
import logging
from typing import Optional
import numpy as np
import numpy.typing as npt
import requests
from scipy.signal import find_peaks, medfilt

SERIAL_PORT = "/dev/ttyUSB0"


Array = Union[list, npt.NDArray]


class DataPaginator:
    def __init__(self, data: Array, page_size=10) -> None:
        self._data = data
        self.__len = len(data)
        self.__page_size = page_size
        self.__next_idx = 0
        self.__next_time = 0  # in seconds
        self.will_paginate = self.__len > self.__page_size
        self.dont_send_more = False

    def get_next_page(self, now: Optional[float] = None):
        if not self.will_paginate:
            paginaged_data = self._data
            self.__next_idx = 0
            self.dont_send_more = True
        else:
            from_i = self.__next_idx
            to_i = from_i + self.__page_size
            paginaged_data = self._data[from_i:to_i]
            self.__next_idx = 0 if to_i >= self.__len else to_i

        # set the next send time as 80% of the current data page
        # cuz we want to prepare some time ahead
        data_duration_ms = np.sum(paginaged_data)
        now = now or time.time()
        self.__next_time = now + data_duration_ms / 1000 * 0.8

        return paginaged_data

    def should_send(self, now: Optional[float] = None) -> bool:
        if self.dont_send_more:
            return False
        return (now or time.time()) >= self.__next_time


class SensorDataController:
    def __init__(self) -> None:
        self.reset_data()

    def should_send(self, now: Optional[float] = None) -> dict[str, Optional[Array]]:
        data_to_send: dict[str, Optional[Array]] = {}
        for field, paginator in self.data_paginators.items():
            data_to_send[field] = (
                paginator.get_next_page(now) if paginator.should_send(now) else None
            )
        return data_to_send

    def get_session_data(self, field: str) -> Array:
        return self.data_paginators[field]._data

    def reset_data(self) -> None:
        session_data = self.get_sensor_data()
        self.data_paginators = {
            field: DataPaginator(data, page_size=10)
            for field, data in session_data.items()
        }

    @staticmethod
    def find_breaths(ibi: npt.ArrayLike) -> npt.NDArray:
        smoothed = medfilt(ibi, kernel_size=3)

        # From my own experience, the peaks seem flatter than the troughs
        # Thus, there is a width limit for the peaks but not for the troughs
        # Thus, the trough list may be longer than the peak list
        peaks_idx, _ = find_peaks(smoothed, width=2)
        troughs_idx, _ = find_peaks(-smoothed)

        # If #peaks >= 2, #troughs inside the peaks always >= 1, and there may be extra troughs outside
        if len(peaks_idx) < 2:
            return np.array(())

        # We eventually get the list of [p, t, ..., p]
        if troughs_idx[0] < peaks_idx[0]:
            troughs_idx = troughs_idx[1:]
        if troughs_idx[-1] > peaks_idx[-1]:
            troughs_idx = troughs_idx[:-1]

        # We want to manually ensure that there is only one trough between two peaks
        # And simply average the trough indices if there are many
        # Anyway, we can determine the number of in/exhales first — by the number of peaks
        breaths = np.zeros((len(peaks_idx) - 1) * 2)
        for i, (p1, p2) in enumerate(zip(peaks_idx[:-1], peaks_idx[1:])):
            t = troughs_idx[np.logical_and(troughs_idx > p1, troughs_idx < p2)]
            if t.shape != ():
                t = np.mean(t, dtype=int)
            # The first half is the inhale (ibi going down)
            # Inhale time = sum of ibi from the first peak to the trough
            breaths[i * 2] = np.sum(ibi[p1:t])  # type: ignore
            breaths[i * 2 + 1] = np.sum(ibi[t:p2])  # type: ignore

        return breaths

    @staticmethod
    def get_total_session_count() -> Optional[int]:
        query = "SELECT COUNT(*) from controls where on_off=false"
        resp = requests.get("http://localhost:9000/exec", params={"query": query})
        if not resp.ok:
            logging.error("Error getting total session count %s", resp.text)
            return None
        resp = resp.json()
        return resp["dataset"][0][0]

    @staticmethod
    def get_sensor_data(max_try=50, start_try_idx=0) -> dict[str, Array]:
        # Search the past `max_try` sessions to find a preferrable IBI series
        candidate_ibi = []
        candidate_breaths = []
        for last_person_index in range(start_try_idx, start_try_idx + max_try):
            this_bpm = SensorDataController.get_sensor_database_column(
                last_person_index, database="sensors", column="bpm"
            )

            if this_bpm is None:
                this_ibi = []
            else:
                this_ibi = np.array(this_bpm)
                this_ibi = 60_000 * 2 / this_ibi
                this_ibi = this_ibi.astype(int).tolist()

            if len(this_ibi) == 0:
                # No data found, try next session
                logging.debug("Data #%d has empty ibi", last_person_index)
                continue
            elif len(this_ibi) < 10:
                # Not preferrable but save it as a candidate if is the longest & long enough to calculate breaths
                if len(this_ibi) > len(candidate_ibi):
                    this_breaths = SensorDataController.find_breaths(this_ibi)
                    if len(this_breaths) > 0:
                        candidate_breaths = this_breaths
                        candidate_ibi = this_ibi
                    logging.debug(
                        "Data #%d has %d ibi and %d breath",
                        last_person_index,
                        len(this_ibi),
                        len(this_breaths),
                    )
            else:
                # Long enough, use it as long as the breaths can be calculated
                candidate_ibi = this_ibi
                candidate_breaths = SensorDataController.find_breaths(this_ibi)
                logging.debug(
                    "Data #%d has %d ibi and %d breath",
                    last_person_index,
                    len(candidate_ibi),
                    len(candidate_breaths),
                )
                if len(candidate_breaths) > 0:
                    break

        if len(candidate_breaths) == 0:
            logging.warning("No preferrable data within the last %d sessions", max_try)
        else:
            logging.debug("Choose #%d session's data", last_person_index)
            logging.debug("IBI: %s", candidate_ibi)
            logging.debug("Breath: %s", candidate_breaths)

        return {
            "ibi": candidate_ibi,
            "breaths": candidate_breaths,
        }

    @staticmethod
    def get_sensor_database_column(
        idx, database="sensors", column="ibi"
    ) -> Optional[Array]:
        query = f"""WITH e AS (SELECT *, row_number() OVER (ORDER BY timestamp DESC) FROM controls WHERE on_off = false),
s AS (SELECT * FROM controls WHERE on_off = true),
r AS (SELECT e.timestamp AS et, s.timestamp AS st, FROM e ASOF JOIN s WHERE e.row_number = {idx + 1})
SELECT {column} FROM {database} ss JOIN r ON ss.timestamp >= r.st AND ss.timestamp <= r.et"""
        resp = requests.get("http://localhost:9000/exec", params={"query": query})

        if not resp.ok:
            logging.error("Error getting sensor data %s", resp.text)
            return None

        resp = resp.json()
        series = [x for x2d in resp["dataset"] for x in x2d]

        return series


def easeInOutQuad(x):
    return 2 * x * x if x < 0.5 else 1 - np.pow(-2 * x + 2, 2) / 2


def easeInOutSine(x):
    return -(np.cos(np.pi * x) - 1) / 2
