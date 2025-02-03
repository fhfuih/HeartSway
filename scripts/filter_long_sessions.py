import time
import pandas as pd
import numpy as np
import psycopg
from questdb.ingress import Sender


con = psycopg.connect(
    "dbname='qdb' user='admin' host='tsrb' port='8812' password='quest'"
)

df = pd.read_sql("SELECT timestamp, on_off FROM controls", con)
df["next"] = df["on_off"].shift(-1)
df["next_ts"] = df["timestamp"].shift(-1)
df = df[(df["on_off"] == True) & (df["next"] == False)]

df["count"] = 0

for i in df.index:
    from_ts = df.at[i, "timestamp"]
    to_ts = df.at[i, "next_ts"]
    sql = f"SELECT COUNT(*) FROM sensors WHERE timestamp > '{from_ts}' AND timestamp < '{to_ts}'"
    count = pd.read_sql(sql, con).iloc[0]["count"]
    df.at[i, "count"] = count

df = df[df["count"] > 50]
print(df)

new_control = pd.concat(
    [
        pd.DataFrame({"timestamp": df["timestamp"], "on_off": True}),
        pd.DataFrame({"timestamp": df["next_ts"], "on_off": False}),
    ]
).sort_values("timestamp", ignore_index=True)

with Sender.from_conf("http::addr=tsrb:9000;") as qdb_sender:
    qdb_sender.dataframe(new_control, table_name="new_controls", at="timestamp")
