create table sensors_clean as (
  WITH
  e AS (SELECT *, row_number() OVER (ORDER BY timestamp DESC) FROM controls WHERE on_off = false),
  s AS (SELECT * FROM controls WHERE on_off = true),
  r AS (SELECT s.timestamp AS st, e.timestamp AS et, e.row_number, FROM e LT JOIN s ORDER BY et)
  SELECT sensors.*, r.row_number from sensors LEFT JOIN r ON sensors.timestamp > r.st AND sensors.timestamp < r.et
  WHERE row_number IS NOT NULL
)