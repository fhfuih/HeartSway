from typing import Optional
import streamlit as st
import pandas as pd
import time

from utils import SensorDataController

TOTAL: Optional[int] = None


def load_data():
    global TOTAL
    if TOTAL is None:
        TOTAL = SensorDataController.get_total_session_count()
    ibi_series = SensorDataController.get_sensor_database_column()
    return ibi_series


st.title("Hammock Control")

data = load_data()

df = pd.DataFrame({"first column": [1, 2, 3, 4], "second column": [10, 20, 30, 40]})

option = st.selectbox("Which number do you like best?", df["first column"])

"You selected: ", option

"Starting a long computation..."

# Add a placeholder
latest_iteration = st.empty()
bar = st.progress(0)

for i in range(100):
    # Update the progress bar with each iteration.
    latest_iteration.text(f"Iteration {i + 1}")
    bar.progress(i + 1)
    time.sleep(0.1)

"...and now we're done!"
