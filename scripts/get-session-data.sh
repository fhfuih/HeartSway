#!/usr/bin/env bash

sid=$1
rownum=`expr ${sid} + 1`

echo "Session index $1, row_numer $rownum"

curl -G --data-urlencode "query=WITH e AS (SELECT *, row_number() OVER (ORDER BY timestamp DESC) FROM controls WHERE on_off = false), s AS (SELECT * FROM controls WHERE on_off = true), r AS (SELECT e.timestamp AS et, s.timestamp AS st, FROM e ASOF JOIN s WHERE e.row_number = ${rownum}) SELECT sensors.* FROM sensors JOIN r ON sensors.timestamp >= r.st AND sensors.timestamp <= r.et;" http://localhost:9000/exec

echo ""
