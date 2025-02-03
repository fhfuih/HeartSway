WITH
e AS (SELECT *, row_number() OVER (ORDER BY timestamp DESC) FROM controls WHERE on_off = false),
s AS (SELECT * FROM controls WHERE on_off = true),
r AS (SELECT s.timestamp AS st, e.timestamp AS et, e.row_number, FROM e LT JOIN s ORDER BY et)
SELECT r.st, r.et, COUNT(*)
  FROM sensors LEFT JOIN r ON sensors.timestamp > r.st AND sensors.timestamp < r.et
  GROUP BY r.st, r.et
  ORDER BY r.et