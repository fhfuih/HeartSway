import time
from typing import Optional

import pandas as pd
import streamlit as st
from utils import SensorDataController

TOTAL: Optional[int] = None


def load_total():
    global TOTAL
    TOTAL = SensorDataController.get_total_session_count()


def load_data(idx):
    global TOTAL
    if TOTAL is None:
        TOTAL = SensorDataController.get_total_session_count()
    ibi_series = SensorDataController.get_sensor_database_column(
        idx, database="sensors", column="ibi"
    )
    return ibi_series


if "total" not in st.session_state:
    st.session_state["total"] = load_total()
TOTAL = st.session_state.total

if "session_idx" not in st.session_state:
    st.session_state["session_idx"] = 0
current_session_select = st.session_state.session_idx

st.title("Hammock Control")

data = load_data(current_session_select)
st.line_chart(data)

"Total sessions", TOTAL

current_session_select = st.number_input(
    "select a session", min_value=0, max_value=TOTAL, value=current_session_select
)
st.session_state.session_idx = current_session_select
"Current session", current_session_select

# df = pd.DataFrame({"first column": [1, 2, 3, 4], "second column": [10, 20, 30, 40]})
#
# option = st.selectbox("Which number do you like best?", df["first column"])
#
# "You selected: ", option
#
# "Starting a long computation..."
#
# # Add a placeholder
# latest_iteration = st.empty()
# bar = st.progress(0)
#
# for i in range(100):
#     # Update the progress bar with each iteration.
#     latest_iteration.text(f"Iteration {i + 1}")
#     bar.progress(i + 1)
#     time.sleep(0.1)
#
# "...and now we're done!"
