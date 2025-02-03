import time
import pandas as pd
import numpy as np
import psycopg
from questdb.ingress import Sender


con = psycopg.connect(
    "dbname='qdb' user='admin' host='tsrb' port='8812' password='quest'"
)

df = pd.read_sql("SELECT timestamp, on_off FROM controls", con)
df["prev"] = df["on_off"].shift(1)
df["prev_ts"] = df["timestamp"].shift(1)
df["next"] = df["on_off"].shift(-1)
df["next_ts"] = df["timestamp"].shift(-1)

print(df)
# print(df["timestamp"].dtype)

start_with_next_start = df[(df["on_off"] == True) & (df["next"] == True)]
ends_to_insert = pd.DataFrame(
    {
        "timestamp": start_with_next_start["next_ts"] - pd.offsets.Micro(1),
        "on_off": False,
    }
)

end_with_prev_end = df[(df["on_off"] == False) & (df["prev"] == False)]
starts_to_insert = pd.DataFrame(
    {"timestamp": end_with_prev_end["prev_ts"] + pd.offsets.Micro(1), "on_off": True}
)

print("Ends to insert")
print(ends_to_insert)
print("Starts to insert")
print(starts_to_insert)

insert = pd.concat([ends_to_insert, starts_to_insert]).sort_values(
    "timestamp", ignore_index=True
)
print("Insert")
print(insert)

confirm = input(
    f"Among {len(df)} rows, detected {len(ends_to_insert)} missing ends and {len(starts_to_insert)} missing starts. Proceed? [y/N] "
)
if confirm.lower() != "y":
    print("Aborting")
    exit()

with Sender.from_conf("http::addr=tsrb:9000;") as qdb_sender:
    qdb_sender.dataframe(insert, table_name="controls", at="timestamp")

time.sleep(1)

df = pd.read_sql("SELECT timestamp, on_off FROM controls", con)
df["prev"] = df["on_off"].shift(1)
df["prev_ts"] = df["timestamp"].shift(1)
df["next"] = df["on_off"].shift(-1)
df["next_ts"] = df["timestamp"].shift(-1)
start_with_next_start = df[(df["on_off"] == True) & (df["next"] == True)]
end_with_prev_end = df[(df["on_off"] == False) & (df["prev"] == False)]
if len(start_with_next_start) > 0:
    print("Still missing ends")
    print(start_with_next_start)
if len(end_with_prev_end) > 0:
    print("Still missing starts")
    print(end_with_prev_end)
