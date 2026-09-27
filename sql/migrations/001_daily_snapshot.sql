CREATE TABLE IF NOT EXISTS daily_snapshot (
  snapshot_id TEXT PRIMARY KEY,
  as_of TIMESTAMP NOT NULL,
  model_version TEXT NOT NULL,
  snapshot_hash TEXT NOT NULL UNIQUE,
  stress_level TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  markdown TEXT NOT NULL,
  generated_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_daily_snapshot_as_of
ON daily_snapshot(as_of, model_version);
