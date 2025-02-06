import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
import numpy.typing as npt
import pandas as pd
import requests
import ruptures as rpt
from scipy.signal import find_peaks, medfilt

SERIAL_PORT = "/dev/ttyUSB0"

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


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
                this_ibi = 60_000 / this_ibi
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
            return {
                "ibi": [],
                "breaths": [],
                "stretch": [],
            }

        stretch = SensorDataController.get_sensor_database_column(
            last_person_index, database="stretch", column="primary"
        )
        if stretch is None:
            stretch = []

        logging.info("Choose #%d session's data", last_person_index)
        logging.debug("IBI length: %d", len(candidate_ibi))
        logging.debug("Breath length: %d", len(candidate_breaths))
        logging.debug("Stretch length: %d", len(stretch))

        result = {
            "ibi": candidate_ibi,
            "breaths": candidate_breaths,
            "stretch": stretch,
        }

        SensorDataController.save_data_to_plot(result)

        return result

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

    @staticmethod
    def save_data_to_plot(data: dict[str, Array]) -> None:
        dt = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        if "ibi" in data:
            fig, ax = plt.subplots()
            plt.plot(data["ibi"])
            file = LOG_DIR / f"ibi-{dt}.jpg"
            fig.savefig(file)
            logging.info(f"Saved IBI plot to {file}")
        if "stretch" in data:
            d = pd.Series(data["stretch"])
            window_size = 100
            rolling_mean = d.rolling(window=window_size, center=True).mean()
            rolling_std = d.rolling(window=window_size, center=True).std()
            threshold = 3
            is_outlier = (d > rolling_mean + threshold * rolling_std) | (
                d < rolling_mean - threshold * rolling_std
            )
            d[is_outlier] = rolling_mean[is_outlier]
            algo = rpt.Pelt(model="rbf").fit(d.values)
            change_points = algo.predict(pen=10)

            fig, ax = plt.subplots()
            ax.xaxis.set_major_formatter(
                lambda sec, x: time.strftime("%M:%S", time.gmtime(sec))
            )
            ax.xaxis.set_minor_formatter(
                lambda sec, x: time.strftime("%M", time.gmtime(sec))
                if sec % 60 == 0
                else ""
            )
            ax.xaxis.set_minor_locator(matplotlib.ticker.MultipleLocator(30))
            ax.xaxis.set_major_locator(matplotlib.ticker.FixedLocator(change_points))
            ax.tick_params(which="minor", axis="x", labelsize=7, pad=-8)
            ax.grid(which="minor", axis="x")
            for cp in change_points:
                plt.axvline(cp, color="red", linestyle="--")
            ax.plot(data["stretch"])
            ax.set_xticks(change_points)
            fig.tight_layout()
            file = LOG_DIR / f"stretch-{dt}.jpg"
            fig.savefig(file)
            logging.info(f"Saved stretch plot to {file}")


def easeInOutQuad(x):
    return 2 * x * x if x < 0.5 else 1 - np.pow(-2 * x + 2, 2) / 2


def easeInOutSine(x):
    return -(np.cos(np.pi * x) - 1) / 2
